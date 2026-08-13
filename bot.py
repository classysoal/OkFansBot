import os
import json
import logging
import asyncio
import random
from datetime import datetime, timedelta, timezone

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
try:
    import dotenv
except ImportError:
    dotenv = None
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    ChatJoinRequestHandler,
    filters
)

import database
import messages
from keyboards import (
    get_home_keyboard,
    get_step1_join_keyboard,
    get_verification_failed_keyboard,
    get_back_keyboard,
    get_admin_keyboard
)

from services.verification import VerificationManager, StateMachine
from services.video_catalog import VideoCatalog
from services.rewards import RewardManager
from services.referrals import ReferralManager
from services.diagnostics import StartupValidator, DiagnosticsManager, HealthMonitor

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load env variables and config.json
if dotenv:
    dotenv.load_dotenv()
BOT_TOKEN = os.getenv("TG_BOT_TOKEN")

CONFIG_PATH = "config.json"
def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

config = load_config()
OWNER_ID = config.get("owner_id", 6193742824)
DATABASE_CHANNEL_ID = config.get("database_channel_id", -1003950233105)
UPDATES_SUPERGROUP_ID = config.get("updates_supergroup_id", -1002376104010)
WELCOME_VIDEO_CHANNEL = config.get("welcome_video_channel", "@PIROsx07")

# Global In-Memory Tracking
USER_VERIFY_COOLDOWN = {}
ADMIN_STATES = {}

def is_maintenance() -> bool:
    return load_config().get("maintenance_mode", False)

def sync_channels_to_db():
    required_list = config.get("required_channels", [])
    for ch in required_list:
        database.save_required_channel(
            channel_id=ch.get("channel_id"),
            label=ch.get("label", "Channel"),
            title=ch.get("title", "Required Channel"),
            invite_link=ch.get("invite_link"),
            channel_type=ch.get("channel_type", "starter"),
            verification_method=ch.get("verification_method", "direct_join"),
            is_active=ch.get("is_active", 1),
            priority=ch.get("priority", 0)
        )
    logger.info("Synced channels from config.json to database.")

async def safe_delete_message(bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.debug(f"Could not delete message {message_id} in {chat_id}: {e}")

async def check_user_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    db_user = database.get_user(user.id)
    if db_user and db_user.get("is_banned") == 1:
        if update.callback_query:
            await update.callback_query.answer("❌ You are banned from using this bot.", show_alert=True)
        elif update.message:
            await update.message.reply_text("❌ You are banned from using this bot.")
        return False
    if is_maintenance() and user.id != OWNER_ID:
        if update.callback_query:
            await update.callback_query.answer("Maintenance in progress. Please check back later.", show_alert=True)
        elif update.message:
            await update.message.reply_html("<b>OkFansBot is under maintenance.</b>\nPlease check back later.")
        return False
    return True

# --- COMMAND HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_access(update, context):
        return
        
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    referred_by = None
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        referred_by = ReferralManager.resolve_referrer_id(arg)
                
    user, is_new = database.register_user(
        user_id=user_id,
        username=username,
        first_name=first_name,
        referred_by=referred_by
    )
    if not user:
        await update.effective_chat.send_message("An error occurred starting the bot. Please try again.")
        return
    
    if is_new and referred_by:
        ReferralManager.register_referral(user_id, referred_by)
        
    active_channels = database.get_required_channels()
    total_channels = len(active_channels)
    ref_count = ReferralManager.get_verified_referrals_count(user_id)
    
    welcome_text = messages.get_welcome_dashboard_text(user, total_channels, ref_count)
    if is_new and referred_by and referred_by != user_id:
        referrer = database.get_user(referred_by)
        referrer_name = referrer['first_name'] if referrer else f"User {referred_by}"
        welcome_text = f"👋 <i>You were referred by {referrer_name}!</i>\n\n" + welcome_text

    is_completed = bool(user.get("starter_completed", 0))
    home_kb = get_home_keyboard(is_completed)

    # Pick intro video randomly between range 155 and 250
    video_ids = config.get("welcome_video_message_ids", [155, 250])
    if isinstance(video_ids, list) and len(video_ids) == 2 and isinstance(video_ids[0], int) and isinstance(video_ids[1], int) and video_ids[0] < video_ids[1]:
        chosen_id = random.randint(video_ids[0], video_ids[1])
    elif isinstance(video_ids, list) and len(video_ids) > 0:
        chosen_id = random.choice(video_ids)
    else:
        chosen_id = random.randint(155, 250)
        
    sent_msg = None
    try:
        sent_msg = await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=WELCOME_VIDEO_CHANNEL,
            message_id=chosen_id,
            caption=welcome_text,
            parse_mode="HTML",
            reply_markup=home_kb
        )
    except Exception as e:
        logger.warning(f"Could not copy welcome video {chosen_id} from {WELCOME_VIDEO_CHANNEL}: {e}. Falling back to text.")
        sent_msg = await update.effective_chat.send_message(
            welcome_text,
            reply_markup=home_kb,
            parse_mode="HTML"
        )
    
    if sent_msg:
        database.update_last_menu_message(user_id, sent_msg.message_id)

    # v2.0: Bot is the communication/entry layer.
    # The Mini App (via home_kb inline buttons and reply keyboard) is the primary interface.
    # The reply keyboard below gives quick persistent access to the app.
    try:
        nav_text = (
            "📱 <b>Your VIP Dashboard is ready.</b>\n\n"
            "Tap <b>🚀 Open VIP App</b> below to launch your full dashboard — "
            "view credits, complete quests, invite friends, and redeem rewards."
        )
        if not is_completed:
            nav_text += "\n\n⚡ <i>New member? Open the App and complete your VIP Verification Quest first!</i>"
        await context.bot.send_message(
            chat_id=user_id,
            text=nav_text,
            parse_mode="HTML",
            reply_markup=get_main_reply_keyboard(is_owner=(user_id == OWNER_ID))
        )
    except Exception:
        pass


    asyncio.create_task(delete_after_delay(context.bot, update.effective_chat.id, update.effective_message.message_id, delay=10))

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(HealthMonitor.get_health_report())

def get_attached_media_url() -> str:
    return config.get("attached_media_url", "random")

async def admin_set_media_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        await update.effective_chat.send_message(
            f"ℹ️ Current Attached Media URL: <code>{get_attached_media_url() or 'None'}</code>\n\nUsage: <code>/setmedia [https://t.me/c/.../msg_id]</code>",
            parse_mode="HTML"
        )
        return
    url = context.args[0]
    config["attached_media_url"] = url
    save_config(config)
    await update.effective_chat.send_message(f"✅ Attached media banner updated to:\n<code>{url}</code>", parse_mode="HTML")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return
        
    await update.message.reply_html(
        "🛠️ <b>Admin Control Panel</b>\nChoose an administrative action below:",
        reply_markup=get_admin_keyboard()
    )

# --- CALLBACK QUERY HANDLERS ---

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not await check_user_access(update, context):
        return
        
    user_id = update.effective_user.id
    data = query.data
    
    user = database.get_user(user_id)
    if not user:
        return
        
    active_channels = database.get_required_channels()
    total_channels = len(active_channels)
    
    if data.startswith("link_"):
        parts = data.split("_")
        db_id = int(parts[1])
        channel_id = int(parts[2])
        if user_id != OWNER_ID:
            return
            
        conn = database.get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE required_channels SET channel_id = %s WHERE id = %s", (channel_id, db_id))
            await query.edit_message_text(
                f"✅ <b>Successfully linked required channel (DB ID: {db_id}) to Resolved Channel ID <code>{channel_id}</code>!</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error linking channel: {e}")
            await query.answer("Error linking channel.", show_alert=True)
        finally:
            conn.close()
        return

    elif data == "btn_admin_cancel":
        if user_id == OWNER_ID:
            await query.delete_message()
        return

    elif data == "btn_admin_stop_sync":
        if user_id == OWNER_ID:
            VideoCatalog.stop_sync()
            await query.answer("🛑 Stop signal sent. Channel sync is halting...", show_alert=True)
            try:
                await query.edit_message_text("🛑 <b>Sync Cancelled by Admin.</b>", parse_mode="HTML")
            except Exception:
                pass
        return
        
    elif data == "btn_home":
        ref_count = ReferralManager.get_verified_referrals_count(user_id)
        is_completed = bool(user.get("starter_completed", 0))
        media_url = get_attached_media_url()
        welcome_txt = messages.get_welcome_dashboard_text(user, total_channels, ref_count, media_url=media_url)
        home_kb = get_home_keyboard(is_completed)
        try:
            await query.edit_message_text(
                welcome_txt,
                reply_markup=home_kb,
                parse_mode="HTML"
            )
        except Exception:
            sent_msg = await context.bot.send_message(
                chat_id=user_id,
                text=welcome_txt,
                reply_markup=home_kb,
                parse_mode="HTML"
            )
            database.update_last_menu_message(user_id, sent_msg.message_id)

    elif data == "btn_start_verification":
        # Step 1 — Join Screen
        batch_size = config.get("channels_per_verification_batch", 5)
        required_list = active_channels[:batch_size]
        step1_text = messages.get_step1_join_text(required_list)
        step1_kb = get_step1_join_keyboard(required_list)
        try:
            await query.edit_message_text(
                step1_text,
                reply_markup=step1_kb,
                parse_mode="HTML"
            )
        except Exception:
            await safe_delete_message(context.bot, user_id, query.message.message_id)
            sent_msg = await context.bot.send_message(
                chat_id=user_id,
                text=step1_text,
                reply_markup=step1_kb,
                parse_mode="HTML"
            )
            database.update_last_menu_message(user_id, sent_msg.message_id)

    elif data == "btn_verify":
        now = get_utc_now()
        last_click = USER_VERIFY_COOLDOWN.get(user_id)
        if last_click and (now - last_click).total_seconds() < 5:
            await query.answer("⚠️ Please wait 5 seconds before clicking verify again.", show_alert=True)
            return
        USER_VERIFY_COOLDOWN[user_id] = now
        
        # Step 2 & 3 — Verification Engine & Results Aggregator
        results, passed_count, required_count, still_missing = await VerificationManager.process_verification(
            user_id=user_id,
            active_channels=active_channels,
            bot=context.bot
        )
        
        user = database.get_user(user_id)
        if passed_count == required_count:
            # Step 4 — Rewards & Credit Processing
            did_grant = RewardManager.grant_starter_reward(user_id)
            inviter_id, inviter_credits = RewardManager.process_referral_reward(user_id)
            
            if inviter_id:
                try:
                    ref_code = ReferralManager.get_or_create_user_ref_code(user_id)
                    reward_amount = ReferralManager.calculate_referral_reward_amount(user_id)
                    if reward_amount > 3:
                        extra = reward_amount - 3
                        database.add_credits(inviter_id, extra, "referral_boost")
                        inviter_user = database.get_user(inviter_id)
                        inviter_credits = inviter_user["credits"] if inviter_user else inviter_credits + extra
                        
                    boost_tag = "⚡ (24h Flash Power-Hour Bonus!)" if reward_amount == 5 else ""
                    await context.bot.send_message(
                        chat_id=inviter_id,
                        text=(
                            f"🎉 <b>New Referral Verified!</b> {boost_tag}\n\n"
                            f"<blockquote>User <b>{user['first_name']}</b> completed channel verification using code <code>{ref_code}</code>!</blockquote>\n"
                            f"🎁 You earned <b>+{reward_amount} Credits 🪙</b>! Total balance: <b>{inviter_credits} 🪙</b>"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Could not notify inviter {inviter_id}: {e}")
                    
            user = database.get_user(user_id)
            summary_text = messages.get_verification_summary_text(results, passed_count, required_count, [])
            try:
                await query.edit_message_text(
                    summary_text,
                    reply_markup=get_verified_home_keyboard(),
                    parse_mode="HTML"
                )
            except Exception:
                await safe_delete_message(context.bot, user_id, query.message.message_id)
                sent_msg = await context.bot.send_message(
                    chat_id=user_id,
                    text=summary_text,
                    reply_markup=get_verified_home_keyboard(),
                    parse_mode="HTML"
                )
                database.update_last_menu_message(user_id, sent_msg.message_id)
        else:
            summary_text = messages.get_verification_summary_text(results, passed_count, required_count, still_missing)
            failed_kb = get_verification_failed_keyboard(still_missing)
            try:
                await query.edit_message_text(
                    summary_text,
                    reply_markup=failed_kb,
                    parse_mode="HTML"
                )
            except Exception:
                await safe_delete_message(context.bot, user_id, query.message.message_id)
                sent_msg = await context.bot.send_message(
                    chat_id=user_id,
                    text=summary_text,
                    reply_markup=failed_kb,
                    parse_mode="HTML"
                )
                database.update_last_menu_message(user_id, sent_msg.message_id)

    elif data == "btn_profile":
        ref_count = ReferralManager.get_verified_referrals_count(user_id)
        profile_text = messages.get_profile_text(user, ref_count, total_channels)
        try:
            await query.edit_message_text(profile_text, reply_markup=get_back_keyboard(), parse_mode="HTML")
        except Exception:
            await safe_delete_message(context.bot, user_id, query.message.message_id)
            sent_msg = await context.bot.send_message(chat_id=user_id, text=profile_text, reply_markup=get_back_keyboard(), parse_mode="HTML")
            database.update_last_menu_message(user_id, sent_msg.message_id)

    elif data == "btn_rules":
        rules_text = messages.get_rules_text()
        try:
            await query.edit_message_text(rules_text, reply_markup=get_back_keyboard(), parse_mode="HTML")
        except Exception:
            await safe_delete_message(context.bot, user_id, query.message.message_id)
            sent_msg = await context.bot.send_message(chat_id=user_id, text=rules_text, reply_markup=get_back_keyboard(), parse_mode="HTML")
            database.update_last_menu_message(user_id, sent_msg.message_id)

    elif data == "btn_daily_bonus":
        res = database.claim_daily_checkin(user_id)
        if res and res.get("success"):
            msg = f"🎉 Daily VIP Bonus Claimed!\n\n• Received: +1 Credit 🪙\n• Daily Streak: {res['streak']} days 🔥\n• New Balance: {res['credits']} 🪙"
            await query.answer(msg, show_alert=True)
            ref_count = ReferralManager.get_verified_referrals_count(user_id)
            is_completed = bool(user.get("starter_completed", 0))
            media_url = get_attached_media_url()
            try:
                await query.edit_message_text(
                    messages.get_welcome_dashboard_text(user, total_channels, ref_count, media_url=media_url),
                    reply_markup=get_home_keyboard(is_completed),
                    parse_mode="HTML"
                )
            except Exception:
                pass
        elif res and res.get("reason") == "cooldown":
            await query.answer(f"⏳ Daily bonus already claimed! Next bonus available in {res.get('hours_left', 1)} hours.", show_alert=True)
        else:
            await query.answer("❌ Could not claim daily bonus. Please try again later.", show_alert=True)
        return

    elif data == "btn_invite":
        bot_username = (await context.bot.get_me()).username
        ref_code = ReferralManager.get_or_create_user_ref_code(user_id)
        ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
        ref_count = ReferralManager.get_verified_referrals_count(user_id)
        invite_text = (
            f"⚡ <b>24-Hour Flash Invite Power-Hour!</b>\n\n"
            f"<blockquote>🔥 <b>Earn 5 Credits per invite</b> when your friends join & verify within 24h! (Standard: 3 Credits)</blockquote>\n\n"
            f"Share your unique referral link:\n"
            f"<code>{ref_link}</code>\n\n"
            f"• Your Code: <code>{ref_code}</code>\n"
            f"• Total Verified Invites: <b>{ref_count}</b>"
        )
        share_url = f"https://t.me/share/url?url={ref_link}&text=" + "Join%20OkFansBot%20for%20exclusive%20video%20rewards!"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share Referral Link", url=share_url)],
            [InlineKeyboardButton("🔙 Back to Home", callback_data="btn_home")]
        ])
        try:
            await query.edit_message_text(invite_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await safe_delete_message(context.bot, user_id, query.message.message_id)
            sent_msg = await context.bot.send_message(chat_id=user_id, text=invite_text, reply_markup=kb, parse_mode="HTML")
            database.update_last_menu_message(user_id, sent_msg.message_id)

    elif data == "btn_vip_tiers":
        vip_text = messages.get_vip_tiers_text(user_id, media_url=get_attached_media_url())
        try:
            await query.edit_message_text(vip_text, reply_markup=get_back_keyboard(), parse_mode="HTML")
        except Exception:
            await safe_delete_message(context.bot, user_id, query.message.message_id)
            sent_msg = await context.bot.send_message(chat_id=user_id, text=vip_text, reply_markup=get_back_keyboard(), parse_mode="HTML")
            database.update_last_menu_message(user_id, sent_msg.message_id)

    elif data == "btn_get_video":
        # Step 5 — Reward Redemption
        if not user.get("starter_completed", 0):
            await query.answer("⚠️ You must complete channel verification first!", show_alert=True)
            batch_size = config.get("channels_per_verification_batch", 5)
            required_list = active_channels[:batch_size]
            await query.edit_message_text(
                messages.get_step1_join_text(required_list),
                reply_markup=get_step1_join_keyboard(required_list),
                parse_mode="HTML"
            )
            return

        vip_info = database.get_user_vip_tier_info(user_id)
        required_cost = vip_info["credit_cost"]
        bundle_size = vip_info["bundle_size"]

        if user["credits"] < required_cost:
            insufficient_text = (
                f"❌ <b>Insufficient Credits!</b>\n\n"
                f"Your active rank (<b>{vip_info['title']}</b>) requires <b>{required_cost} Credit(s)</b> to redeem your <b>{bundle_size}-video bundle</b>.\n\n"
                f"• Your Balance: <b>{user['credits']} 🪙</b>\n\n"
                f"💡 <i>Invite friends using your referral link to earn credits instantly!</i>"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🤝 Invite Friend", callback_data="btn_invite")],
                [InlineKeyboardButton("🔙 Back to Home", callback_data="btn_home")]
            ])
            try:
                await query.edit_message_text(insufficient_text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await safe_delete_message(context.bot, user_id, query.message.message_id)
                sent_msg = await context.bot.send_message(chat_id=user_id, text=insufficient_text, reply_markup=kb, parse_mode="HTML")
                database.update_last_menu_message(user_id, sent_msg.message_id)
            return

        deducted = database.deduct_credits(user_id, required_cost, "video_spend")
        if not deducted:
            await query.answer("Error deducting credits.", show_alert=True)
            return

        expiry_delay = int(config.get("video_deletion_delay_seconds", 1800))
        del_minutes = max(1, expiry_delay // 60)
        
        vault_mapping = ["A", "B", "C", "D", "E"]
        user_vault_ptr = user.get("vault_pointer") or 0

        unlocked_limit = config.get("unlocked_video_limit", 50)
        items_delivered = 0
        delivered_videos = []
        for item_idx in range(bundle_size):
            active_vault = vault_mapping[(user_vault_ptr + item_idx) % len(vault_mapping)]
            video = VideoCatalog.get_next_video(user_id, active_vault, max_limit=unlocked_limit)
            if not video:
                video = VideoCatalog.get_next_video(user_id, "B", max_limit=unlocked_limit)
            if not video:
                break
                
            delivered_videos.append(video)
            caption_text = (
                f"🎁 <b>{vip_info['badge']} VIP Reward Item ({item_idx + 1}/{bundle_size})</b>\n\n"
                f"{video['caption'] or ''}\n\n"
                f"⏱️ <i>This item will automatically delete in {del_minutes} minutes to prevent copyright flags. Save it now!</i>"
            )
            try:
                sent_video = await context.bot.send_video(
                    chat_id=user_id,
                    video=video["file_id"],
                    caption=caption_text,
                    parse_mode="HTML",
                    protect_content=True,
                    has_spoiler=True
                )
                expiry_time = get_utc_now() + timedelta(seconds=expiry_delay)
                delivery_id = VideoCatalog.mark_delivered(
                    user_id=user_id,
                    video_id=video["video_id"],
                    chat_id=user_id,
                    message_id=sent_video.message_id,
                    expiry_at=expiry_time
                )
                if delivery_id:
                    schedule_auto_deletion(context.application, user_id, sent_video.message_id, delivery_id, expiry_time)
                    items_delivered += 1
            except Exception as e:
                logger.error(f"Error sending item {item_idx+1} to user {user_id}: {e}")

        database.increment_vault_pointer(user_id)
        if items_delivered > 0:
            database.save_user_last_bundle(user_id, [v["video_id"] for v in delivered_videos])
            resend_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Resend Last Bundle (3/3 Resends Left)", callback_data="btn_resend_bundle")],
                [InlineKeyboardButton("🏠 Back to Home", callback_data="btn_home")]
            ])
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ <b>Bundle Delivered!</b> Received <b>{items_delivered} video(s)</b>.\n\n💡 <i>Missed saving a video? Tap <b>Resend Last Bundle</b> below (up to 3 free resends!).</i>",
                parse_mode="HTML",
                reply_markup=resend_kb
            )
        else:
            database.add_credits(user_id, required_cost, "admin_adjust")
            await query.answer("😔 No videos available right now. Your credit has been refunded.", show_alert=True)

    elif data == "btn_resend_bundle":
        bundle_info = database.get_user_last_bundle(user_id)
        if not bundle_info or not bundle_info.get("videos"):
            await query.answer("⚠️ No previous bundle found to resend.", show_alert=True)
            return
            
        resends_used = bundle_info["resends_used"]
        if resends_used >= 3:
            await query.answer("⚠️ Maximum 3 free resends reached for this bundle! Earn a new credit to claim your next bundle.", show_alert=True)
            return
            
        database.increment_user_bundle_resend(user_id)
        new_resends_used = resends_used + 1
        resends_left = 3 - new_resends_used
        
        await query.answer(f"🔄 Resending your bundle! ({resends_left} resend(s) remaining)", show_alert=True)
        
        expiry_delay = int(config.get("video_deletion_delay_seconds", 1800))
        del_minutes = max(1, expiry_delay // 60)
        vip_info = database.get_user_vip_tier_info(user_id)
        
        video_ids = bundle_info["videos"]
        for idx, vid_id in enumerate(video_ids, 1):
            conn = database.get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM videos WHERE video_id = %s", (vid_id,))
                row = cursor.fetchone()
                video = dict(row) if row else None
            finally:
                conn.close()
                
            if not video:
                continue
                
            caption_text = (
                f"🔄 <b>{vip_info['badge']} Resent Reward Item ({idx}/{len(video_ids)})</b> [Resend #{new_resends_used}/3]\n\n"
                f"{video['caption'] or ''}\n\n"
                f"⏱️ <i>This item will automatically delete in {del_minutes} minutes to prevent copyright flags. Save it now!</i>"
            )
            try:
                sent_video = await context.bot.send_video(
                    chat_id=user_id,
                    video=video["file_id"],
                    caption=caption_text,
                    parse_mode="HTML",
                    protect_content=True,
                    has_spoiler=True
                )
                expiry_time = get_utc_now() + timedelta(seconds=expiry_delay)
                delivery_id = VideoCatalog.mark_delivered(user_id, video["video_id"], user_id, sent_video.message_id, expiry_time)
                schedule_auto_deletion(context.application, user_id, sent_video.message_id, delivery_id, expiry_time)
            except Exception as e:
                logger.error(f"Error resending video to user {user_id}: {e}")
                
        resend_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔄 Resend Last Bundle ({resends_left}/3 Left)", callback_data="btn_resend_bundle")],
            [InlineKeyboardButton("🏠 Back to Home", callback_data="btn_home")]
        ])
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🔄 <b>Bundle Resent!</b> (Resend #{new_resends_used}/3 • {resends_left} remaining).",
            parse_mode="HTML",
            reply_markup=resend_kb
        )

    elif data == "btn_admin_diagnostics":
        if user_id == OWNER_ID:
            report = DiagnosticsManager.get_diagnostics_report()
            await query.edit_message_text(report, reply_markup=get_admin_keyboard(), parse_mode="HTML")

    elif data == "btn_admin_stats":
        if user_id == OWNER_ID:
            stats = database.get_system_stats()
            detailed_cat = database.get_detailed_catalog_stats()
            text = messages.get_admin_dashboard_text(stats, detailed_cat)
            await query.edit_message_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")

    elif data == "btn_admin_broadcast":
        if user_id == OWNER_ID:
            ADMIN_STATES[OWNER_ID] = {"state": "BROADCASTING"}
            await query.edit_message_text(
                "📢 <b>Mass Broadcast Mode Activated</b>\n\n"
                "Send any message (Text, Image, Video, or Formatted HTML) to this chat right now to broadcast it to all registered bot users.\n\n"
                "<i>Type /cancel to exit broadcast mode.</i>",
                reply_markup=get_admin_keyboard(),
                parse_mode="HTML"
            )

    elif data == "btn_admin_catalog":
        if user_id == OWNER_ID:
            detailed_cat = database.get_detailed_catalog_stats()
            v_str = "\n".join([f"• Vault {v}: <b>{cnt} videos</b>" for v, cnt in detailed_cat.get("vaults", {}).items()]) or "• No videos stored"
            text = (
                "🎬 <b>Video Catalog Management</b>\n\n"
                f"Total Active Catalog Videos: <b>{detailed_cat.get('total', 0)}</b>\n\n"
                f"<b>Vault Breakdown:</b>\n{v_str}\n\n"
                "<b>Admin Commands:</b>\n"
                "• <code>/syncvideos [start] [end] [vault] [channel_id]</code>\n"
                "• <code>/listvideos</code>\n"
                "• <code>/delvideo [video_id]</code>\n"
                "• <i>Forward videos directly to DM to catalog them instantly!</i>"
            )
            await query.edit_message_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")

    elif data == "btn_admin_users":
        if user_id == OWNER_ID:
            stats = database.get_system_stats()
            text = (
                "👥 <b>User Manager Dashboard</b>\n\n"
                f"• Total Registered Users: <b>{stats.get('total_users', 0)}</b>\n"
                f"• Total Credits Balance: <b>{stats.get('total_credits', 0)} 🪙</b>\n\n"
                "<b>User Admin Commands:</b>\n"
                "• <code>/addcredits [user_id] [amount]</code>\n"
                "• <code>/banuser [user_id]</code>\n"
                "• <code>/unbanuser [user_id]</code>"
            )
            await query.edit_message_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")

    elif data == "btn_admin_channels":
        if user_id == OWNER_ID:
            channels = database.get_required_channels(only_active=False)
            ch_list = ""
            for idx, ch in enumerate(channels, 1):
                status = "✅" if ch["channel_id"] else "❓ Unlinked"
                ch_list += f"{idx}. <b>{ch['title']}</b> ({status})\n   ID: <code>{ch['channel_id'] or 'None'}</code>\n"
            text = f"📢 <b>Required Channels Manager</b> ({len(channels)} total)\n\n{ch_list}\n<i>Use /channels to refresh or link channel IDs.</i>"
            await query.edit_message_text(text[:4000], reply_markup=get_admin_keyboard(), parse_mode="HTML")

    elif data == "btn_admin_broadcast":
        if user_id == OWNER_ID:
            await query.edit_message_text(
                "Broadcast mode is not enabled in this build.",
                reply_markup=get_admin_keyboard()
            )

async def delete_after_delay(bot, chat_id: int, message_id: int, delay: int = 3):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.debug(f"Could not auto-delete message {message_id}: {e}")

# --- INCOMING MESSAGE HANDLER ---

async def handle_incoming_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update or not update.effective_user:
        return
    user_id = update.effective_user.id
    
    if user_id == OWNER_ID and update.effective_message and update.effective_message.video:
        video = update.effective_message.video
        state = ADMIN_STATES.get(user_id, {})
        caption = state.get("caption") or update.effective_message.caption or ""
        if not caption.strip():
            vid_num = random.randint(100, 9999)
            caption = f"Exclusive VIP Content #{vid_num}"
            
        vault = state.get("vault", "B")
        added = database.add_video(video.file_id, caption, vault)
        
        # Auto-delete forwarded/uploaded video message from owner DM after 3 seconds
        asyncio.create_task(delete_after_delay(context.bot, update.effective_chat.id, update.effective_message.message_id, delay=3))
        
        if added:
            cat_stats = database.get_detailed_catalog_stats()
            total_vids = cat_stats.get("total", 0)
            confirm_msg = await update.effective_message.reply_html(
                f"✅ <b>Video Uploaded in Vault {vault}!</b>\n\n• Video Number: <b>#{total_vids}</b>\n• Caption: <i>{caption}</i>\n• File ID: <code>{video.file_id[:20]}...</code>"
            )
            # Auto-delete bot confirmation message after 5 seconds
            asyncio.create_task(delete_after_delay(context.bot, update.effective_chat.id, confirm_msg.message_id, delay=5))
        else:
            dup_msg = await update.effective_message.reply_html(
                "ℹ️ <b>Video Ignored</b>: This video is already cataloged in your database (Duplicate file_id detected)."
            )
            asyncio.create_task(delete_after_delay(context.bot, update.effective_chat.id, dup_msg.message_id, delay=5))
        return

    if user_id == OWNER_ID and user_id in ADMIN_STATES:
        state = ADMIN_STATES[user_id]
        if state.get("state") == "BROADCASTING":
            del ADMIN_STATES[user_id]
            user_ids = database.get_all_user_ids()
            status_msg = await update.effective_message.reply_html(f"⏳ <b>Starting Mass Broadcast...</b>\nTargeting <b>{len(user_ids)}</b> registered users.")
            
            success_count = 0
            fail_count = 0
            
            for uid in user_ids:
                try:
                    await context.bot.copy_message(
                        chat_id=uid,
                        from_chat_id=update.effective_chat.id,
                        message_id=update.effective_message.message_id
                    )
                    success_count += 1
                except Exception:
                    fail_count += 1
                await asyncio.sleep(0.05)
                
            await status_msg.edit_text(
                f"✅ <b>Broadcast Completed!</b>\n\n"
                f"• Delivered successfully: <b>{success_count}</b>\n"
                f"• Failed / Blocked users: <b>{fail_count}</b>",
                parse_mode="HTML"
            )
            return
        state = ADMIN_STATES[user_id]
        if state.get("state") == "UPLOADING_VIDEO":
            await update.effective_message.reply_text("Upload mode is active. Send a Telegram video, or use /cancel.")
            return
    
    # Forwarded channel resolver for owner
    if user_id == OWNER_ID and update.message and update.message.forward_from_chat:
        forward_chat = update.message.forward_from_chat
        if forward_chat.type == "channel":
            channel_id = forward_chat.id
            channel_title = forward_chat.title
            
            active_channels = database.get_required_channels(only_active=False)
            matched = None
            
            def normalize(s):
                return "".join(c for c in s if c.isalnum()).lower() if s else ""
                
            norm_title = normalize(channel_title)
            for ch in active_channels:
                if normalize(ch["title"]) == norm_title or normalize(ch["label"]) == norm_title:
                    matched = ch
                    break
                    
            if matched:
                db_id = matched["id"]
                conn = database.get_db_connection()
                try:
                    with conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE required_channels SET channel_id = %s WHERE id = %s", (channel_id, db_id))
                    await update.message.reply_html(
                        f"✅ <b>Successfully linked!</b>\n\n• Channel: <b>{channel_title}</b>\n• Linked to: <b>{matched['label']}</b>\n• Resolved ID: <code>{channel_id}</code>"
                    )
                except Exception as e:
                    logger.error(f"Error updating channel ID: {e}")
                    await update.message.reply_text("Error updating database.")
                finally:
                    conn.close()
            else:
                unlinked = [ch for ch in active_channels if ch["channel_id"] is None]
                if unlinked:
                    keyboard = [[InlineKeyboardButton(ch["label"], callback_data=f"link_{ch['id']}_{channel_id}")] for ch in unlinked]
                    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="btn_admin_cancel")])
                    await update.message.reply_html(
                        f"ℹ️ <b>Forwarded Channel detected:</b>\n• Title: <b>{channel_title}</b>\n• ID: <code>{channel_id}</code>\n\nSelect required channel to link:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await update.message.reply_html(f"ℹ️ Channel: <b>{channel_title}</b> (ID: <code>{channel_id}</code>). All channels already resolved.")
            return

    if not await check_user_access(update, context):
        return

    # Handle Bottom ReplyKeyboard Text Buttons
    if update.message and update.message.text:
        txt = update.message.text.strip()
        user = database.get_user(user_id)
        active_channels = database.get_required_channels()
        total_channels = len(active_channels)

        if txt == "🎁 Get Video":
            class DummyQuery:
                def __init__(self, msg, uid):
                    self.message = msg
                    self.from_user = update.effective_user
                async def answer(self, text, show_alert=False):
                    await update.message.reply_text(text)
                async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
                    await update.message.reply_html(text, reply_markup=reply_markup)

            query = DummyQuery(update.message, user_id)
            # Call btn_get_video handler logic
            if not user.get("starter_completed", 0):
                batch_size = config.get("channels_per_verification_batch", 5)
                required_list = active_channels[:batch_size]
                await update.message.reply_html(
                    messages.get_step1_join_text(required_list, media_url=get_attached_media_url()),
                    reply_markup=get_step1_join_keyboard(required_list)
                )
                return

            vip_info = database.get_user_vip_tier_info(user_id)
            required_cost = vip_info["credit_cost"]
            bundle_size = vip_info["bundle_size"]

            if user["credits"] < required_cost:
                insufficient_text = (
                    f"❌ <b>Insufficient Credits!</b>\n\n"
                    f"Your active rank (<b>{vip_info['title']}</b>) requires <b>{required_cost} Credit(s)</b> to redeem your <b>{bundle_size}-video bundle</b>.\n\n"
                    f"• Your Balance: <b>{user['credits']} 🪙</b>\n\n"
                    f"💡 <i>Invite friends using your referral link to earn credits instantly!</i>"
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🤝 Invite Friend", callback_data="btn_invite")],
                    [InlineKeyboardButton("🔙 Back to Home", callback_data="btn_home")]
                ])
                await update.message.reply_html(insufficient_text, reply_markup=kb)
                return

            deducted = database.deduct_credits(user_id, required_cost, "video_spend")
            if not deducted:
                await update.message.reply_text("Error deducting credits.")
                return

            expiry_delay = int(config.get("video_deletion_delay_seconds", 1800))
            del_minutes = max(1, expiry_delay // 60)
            vault_mapping = ["A", "B", "C", "D", "E"]
            user_vault_ptr = user.get("vault_pointer") or 0
            unlocked_limit = config.get("unlocked_video_limit", 50)
            items_delivered = 0
            delivered_videos = []

            for item_idx in range(bundle_size):
                active_vault = vault_mapping[(user_vault_ptr + item_idx) % len(vault_mapping)]
                video = VideoCatalog.get_next_video(user_id, active_vault, max_limit=unlocked_limit)
                if not video:
                    video = VideoCatalog.get_next_video(user_id, "B", max_limit=unlocked_limit)
                if not video:
                    break

                delivered_videos.append(video)
                caption_text = (
                    f"🎁 <b>{vip_info['badge']} VIP Reward Item ({item_idx + 1}/{bundle_size})</b>\n\n"
                    f"{video['caption'] or ''}\n\n"
                    f"⏱️ <i>This item will automatically delete in {del_minutes} minutes to prevent copyright flags. Save it now!</i>"
                )
                try:
                    sent_video = await context.bot.send_video(
                        chat_id=user_id,
                        video=video["file_id"],
                        caption=caption_text,
                        parse_mode="HTML",
                        protect_content=True,
                        has_spoiler=True
                    )
                    expiry_time = get_utc_now() + timedelta(seconds=expiry_delay)
                    delivery_id = VideoCatalog.mark_delivered(user_id, video["video_id"], user_id, sent_video.message_id, expiry_time)
                    if delivery_id:
                        schedule_auto_deletion(context.application, user_id, sent_video.message_id, delivery_id, expiry_time)
                        items_delivered += 1
                except Exception as e:
                    logger.error(f"Error sending item {item_idx+1}: {e}")

            database.increment_vault_pointer(user_id)
            if items_delivered > 0:
                database.save_user_last_bundle(user_id, [v["video_id"] for v in delivered_videos])
                resend_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Resend Last Bundle (3/3 Resends Left)", callback_data="btn_resend_bundle")],
                    [InlineKeyboardButton("🏠 Back to Home", callback_data="btn_home")]
                ])
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ <b>Bundle Delivered!</b> Received <b>{items_delivered} video(s)</b>.\n\n💡 <i>Missed saving a video? Tap <b>Resend Last Bundle</b> below (up to 3 free resends!).</i>",
                    parse_mode="HTML",
                    reply_markup=resend_kb
                )
            else:
                database.add_credits(user_id, required_cost, "admin_adjust")
                await update.message.reply_text("😔 No videos available right now. Your credit has been refunded.")
            return

        elif txt == "🏆 VIP Tiers":
            await update.message.reply_html(
                messages.get_vip_tiers_text(user_id, media_url=get_attached_media_url()),
                reply_markup=get_back_keyboard()
            )
            return

        elif txt == "🎁 Daily Bonus":
            res = database.claim_daily_checkin(user_id)
            if res["success"]:
                msg = f"🎉 <b>Daily VIP Bonus Claimed!</b>\n\n• Received: <b>+1 Credit 🪙</b>\n• Daily Streak: <b>{res['streak']} days 🔥</b>\n• New Balance: <b>{res['credits']} 🪙</b>"
                await update.message.reply_html(msg)
            elif res.get("reason") == "cooldown":
                await update.message.reply_html(f"⏳ <b>Daily bonus already claimed today!</b> Next bonus available in <b>{res.get('hours_left', 1)} hours</b>.")
            else:
                await update.message.reply_text("❌ Could not claim daily bonus. Please try again later.")
            return

        elif txt == "🤝 Invite Friends":
            bot_username = (await context.bot.get_me()).username
            ref_code = ReferralManager.get_or_create_user_ref_code(user_id)
            ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
            ref_count = ReferralManager.get_verified_referrals_count(user_id)
            invite_text = (
                f"⚡ <b>24-Hour Flash Invite Power-Hour!</b>\n\n"
                f"<blockquote>🔥 <b>Earn 5 Credits per invite</b> when your friends join & verify within 24h! (Standard: 3 Credits)</blockquote>\n\n"
                f"Share your unique referral link:\n"
                f"<code>{ref_link}</code>\n\n"
                f"• Your Code: <code>{ref_code}</code>\n"
                f"• Total Verified Invites: <b>{ref_count}</b>"
            )
            share_url = f"https://t.me/share/url?url={ref_link}&text=" + "Join%20OkFansBot%20for%20exclusive%20video%20rewards!"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Share Referral Link", url=share_url)],
                [InlineKeyboardButton("🔙 Back to Home", callback_data="btn_home")]
            ])
            await update.message.reply_html(invite_text, reply_markup=kb)
            return

        elif txt == "👤 My Profile":
            ref_count = ReferralManager.get_verified_referrals_count(user_id)
            await update.message.reply_html(
                messages.get_profile_text(user, ref_count, total_channels, media_url=get_attached_media_url()),
                reply_markup=get_back_keyboard()
            )
            return

        elif txt == "📜 Rules & Info":
            await update.message.reply_html(
                messages.get_rules_text(media_url=get_attached_media_url()),
                reply_markup=get_back_keyboard()
            )
            return

        elif txt == "🛠️ Admin Panel" and user_id == OWNER_ID:
            stats = database.get_system_stats()
            detailed_cat = database.get_detailed_catalog_stats()
            admin_text = messages.get_admin_dashboard_text(stats, detailed_cat, media_url=get_attached_media_url())
            await update.message.reply_html(admin_text, reply_markup=get_admin_keyboard())
            return

    asyncio.create_task(delete_after_delay(context.bot, update.effective_chat.id, update.effective_message.message_id, delay=10))

# --- CHAT JOIN REQUEST LISTENER ---

async def handle_chat_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    if not request:
        return

    user_id = request.from_user.id
    channel_id = request.chat.id
    invite_link_obj = request.invite_link
    if not invite_link_obj:
        logger.info("Join request for channel %s had no invite link; cannot map it.", channel_id)
        return

    db_id = database.resolve_channel_id_by_invite(invite_link_obj.invite_link, channel_id)
    if db_id:
        database.record_join_event(user_id, db_id, "requested")
        logger.info("Recorded join request for user %s in channel DB ID %s", user_id, db_id)

# --- ADMIN COMMAND HANDLERS ---

async def delete_incoming_cmd(update: Update):
    if update.effective_message and update.effective_chat:
        asyncio.create_task(delete_after_delay(update.get_bot(), update.effective_chat.id, update.effective_message.message_id, delay=10))

async def admin_add_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return

    args = context.args
    if not args or args[0].upper() not in ["A", "B", "C", "D", "E"]:
        await update.effective_chat.send_message("Usage: /addvideo [vault: A/B/C/D/E] [optional_caption]")
        return

    vault = args[0].upper()
    ADMIN_STATES[OWNER_ID] = {
        "state": "UPLOADING_VIDEO",
        "vault": vault,
        "caption": " ".join(args[1:]) if len(args) > 1 else None
    }
    await update.effective_chat.send_message(
        f"Upload mode activated for Vault {vault}. Send videos here, then use /cancel when finished."
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return

    ADMIN_STATES.pop(OWNER_ID, None)
    await update.effective_chat.send_message("Admin upload state cleared.")

def resolve_target_user_from_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message and update.effective_message.reply_to_message and update.effective_message.reply_to_message.from_user:
        target_uid = update.effective_message.reply_to_message.from_user.id
        user = database.get_user(target_uid)
        if user:
            return user
            
    if context.args and len(context.args) > 0:
        arg = context.args[0].strip()
        if arg.isdigit():
            return database.get_user(int(arg))
        else:
            return database.get_user_by_username(arg)
            
    return None

async def admin_give_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return

    target_user = resolve_target_user_from_update(update, context)
    if not target_user:
        await update.effective_chat.send_message(
            "⚠️ <b>User Not Found</b>\n\nUsage:\n• <code>/givecredits [user_id or @username] [amount]</code>\n• Or reply to a user message: <code>/givecredits [amount]</code>",
            parse_mode="HTML"
        )
        return

    amount_arg = None
    if update.effective_message and update.effective_message.reply_to_message and context.args:
        amount_arg = context.args[0]
    elif len(context.args) >= 2:
        amount_arg = context.args[1]

    try:
        amount = int(amount_arg)
    except (TypeError, ValueError):
        await update.effective_chat.send_message("⚠️ Amount must be an integer number.")
        return

    target_uid = target_user["user_id"]
    if database.add_credits(target_uid, amount, "admin_adjust"):
        database.log_admin_action(OWNER_ID, "give_credits", f"Credits: {amount} to user {target_uid}")
        new_user = database.get_user(target_uid)
        await update.effective_chat.send_message(
            f"✅ <b>Credits Updated!</b>\n\n• User: <b>{target_user['first_name']}</b> (ID: <code>{target_uid}</code>)\n• Amount: <b>+{amount} 🪙</b>\n• New Balance: <b>{new_user['credits']} 🪙</b>",
            parse_mode="HTML"
        )
        try:
            await context.bot.send_message(
                chat_id=target_uid,
                text=f"🎉 <b>Credit Reward Added!</b>\n\nAdmin has added <b>+{amount} Credits 🪙</b> to your account!\n• Your Total Balance: <b>{new_user['credits']} 🪙</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        await update.effective_chat.send_message("❌ Failed to adjust credits in database.")

async def admin_ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return

    target_user = resolve_target_user_from_update(update, context)
    if not target_user:
        await update.effective_chat.send_message("⚠️ User not found. Usage: <code>/ban [user_id or @username]</code>", parse_mode="HTML")
        return

    target_uid = target_user["user_id"]
    if database.set_ban_status(target_uid, 1):
        database.log_admin_action(OWNER_ID, "ban_user", f"Banned user {target_uid}")
        await update.effective_chat.send_message(f"🚫 <b>User Banned!</b>\nUser <b>{target_user['first_name']}</b> (ID: <code>{target_uid}</code>) is now blocked.", parse_mode="HTML")
    else:
        await update.effective_chat.send_message("❌ Failed to ban user.")

async def admin_unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return

    target_user = resolve_target_user_from_update(update, context)
    if not target_user:
        await update.effective_chat.send_message("⚠️ User not found. Usage: <code>/unban [user_id or @username]</code>", parse_mode="HTML")
        return

    target_uid = target_user["user_id"]
    if database.set_ban_status(target_uid, 0):
        database.log_admin_action(OWNER_ID, "unban_user", f"Unbanned user {target_uid}")
        await update.effective_chat.send_message(f"✅ <b>User Unbanned!</b>\nUser <b>{target_user['first_name']}</b> (ID: <code>{target_uid}</code>) access restored.", parse_mode="HTML")
    else:
        await update.effective_chat.send_message("❌ Failed to unban user.")

async def admin_toggle_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return

    latest_config = load_config()
    latest_config["maintenance_mode"] = not latest_config.get("maintenance_mode", False)
    save_config(latest_config)
    config["maintenance_mode"] = latest_config["maintenance_mode"]
    database.log_admin_action(OWNER_ID, "toggle_maintenance", f"Set to {latest_config['maintenance_mode']}")
    state = "enabled" if latest_config["maintenance_mode"] else "disabled"
    await update.effective_chat.send_message(f"Maintenance mode {state}.")

async def admin_del_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        await update.effective_chat.send_message("Usage: /delvideo [video_id]")
        return
    try:
        video_id = int(context.args[0])
    except ValueError:
        await update.effective_chat.send_message("Invalid video ID. Must be integer.")
        return
    
    if database.delete_video(video_id):
        database.log_admin_action(OWNER_ID, "delete_video", f"Deleted video ID {video_id}")
        await update.effective_chat.send_message(f"✅ Video ID {video_id} has been deleted from catalog.")
    else:
        await update.effective_chat.send_message("❌ Failed to delete video or video not found.")

async def admin_list_videos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return
    
    page = 1
    if context.args:
        try:
            page = int(context.args[0])
        except ValueError:
            pass
            
    limit = 20
    offset = (page - 1) * limit
    videos = database.list_videos_paginated(offset, limit)
    
    if not videos:
        await update.effective_chat.send_message("No videos found on this page.")
        return
        
    text = f"📹 <b>Catalog Videos (Page {page})</b>\n\n"
    for v in videos:
        cap = (v["caption"][:30] + "...") if v["caption"] and len(v["caption"]) > 30 else (v["caption"] or "No caption")
        text += f"• <b>ID: {v['video_id']}</b> | Vault: <b>{v['vault']}</b> | {cap}\n"
        
    text += f"\nUse <code>/listvideos {page+1}</code> for next page."
    await update.effective_chat.send_message(text, parse_mode="HTML")

async def admin_sync_videos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return
        
    if len(context.args) < 2:
        await update.effective_chat.send_message(
            "Usage: /syncvideos [start_id] [end_id] [vault: A/B/C/D/E] [optional_source_channel_id]"
        )
        return
        
    try:
        start_id = int(context.args[0])
        end_id = int(context.args[1])
    except ValueError:
        await update.effective_chat.send_message("Start ID and End ID must be integers.")
        return
        
    vault = "B"
    if len(context.args) > 2:
        v_arg = context.args[2].upper()
        if v_arg in ["A", "B", "C", "D", "E"]:
            vault = v_arg
            
    source_channel = DATABASE_CHANNEL_ID
    if len(context.args) > 3:
        try:
            raw_cid = context.args[3]
            if not raw_cid.startswith("-100") and raw_cid.lstrip("-").isdigit():
                raw_cid = f"-100{raw_cid.lstrip('-')}"
            source_channel = int(raw_cid)
        except ValueError:
            pass
            
    stop_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop Sync", callback_data="btn_admin_stop_sync")]])
    await update.effective_chat.send_message(
        f"⏳ Starting background sync for message range {start_id} to {end_id} (Vault {vault}) from channel <code>{source_channel}</code>...",
        reply_markup=stop_kb,
        parse_mode="HTML"
    )
    
    imported = await VideoCatalog.sync_database_channel(
        bot=context.bot,
        channel_id=source_channel,
        start_id=start_id,
        end_id=end_id,
        vault=vault,
        target_chat_id=OWNER_ID,
        copy_to_channel_id=DATABASE_CHANNEL_ID
    )
    
    database.log_admin_action(OWNER_ID, "sync_videos", f"Synced range {start_id}-{end_id} from {source_channel} to Vault {vault}")
    await update.effective_chat.send_message(
        f"✅ <b>Sync Completed!</b>\n\n• Messages scanned: {end_id - start_id + 1}\n• Source Channel: <code>{source_channel}</code>\n• Database Channel: <code>{DATABASE_CHANNEL_ID}</code>\n• New videos added: <b>{imported}</b>",
        parse_mode="HTML"
    )

async def admin_dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return
    stats = database.get_system_stats()
    detailed_cat = database.get_detailed_catalog_stats()
    text = messages.get_admin_dashboard_text(stats, detailed_cat)
    await update.effective_chat.send_message(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")

async def admin_unlock_content_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return
    current_limit = config.get("unlocked_video_limit", 50)
    if not context.args:
        await update.effective_chat.send_message(
            f"ℹ️ Current Unlocked Video Pool: <b>{current_limit} videos</b>\n\nUsage:\n• <code>/unlockcontent +50</code> (Unlock next 50 videos)\n• <code>/unlockcontent 100</code> (Set pool to 100 videos)",
            parse_mode="HTML"
        )
        return
    arg = context.args[0].strip()
    try:
        if arg.startswith("+"):
            new_limit = current_limit + int(arg.lstrip("+"))
        else:
            new_limit = int(arg)
    except ValueError:
        await update.effective_chat.send_message("⚠️ Limit must be a number or +amount (e.g. +50).")
        return

    config["unlocked_video_limit"] = new_limit
    save_config(config)
    
    await update.effective_chat.send_message(
        f"✅ <b>Content Tier Unlocked!</b>\nNew active catalog limit: <b>{new_limit} videos</b>.\n\n⏳ Broadcasting teaser announcement to all users...",
        parse_mode="HTML"
    )
    
    user_ids = database.get_all_user_ids()
    dropped_count = max(50, new_limit - current_limit)
    broadcast_text = (
        "🔥 <b>WEEKLY CONTENT DROP IS LIVE!</b>\n\n"
        f"<blockquote>🎬 <b>{dropped_count} New Exclusive VIP Videos</b> have just been unlocked in the Vault! (Total Active Pool: <b>{new_limit} Videos</b>)</blockquote>\n\n"
        "🪙 Tap <b>Get Video</b> or invite friends with your referral link to earn credits and claim the new content now!"
    )
    
    success = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=messages.attach_media_banner(broadcast_text), parse_mode="HTML")
            success += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
        
    await update.effective_chat.send_message(f"📢 <b>Announcement Broadcast Complete!</b> Delivered to {success}/{len(user_ids)} users.", parse_mode="HTML")

async def admin_channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return
        
    active_channels = database.get_required_channels(only_active=False)
    text = "📢 <b>Required Channels & Linking Status</b>\n\n"
    for i, ch in enumerate(active_channels, 1):
        status = f"<code>{ch['channel_id']}</code>" if ch['channel_id'] else "❌ Unresolved (Forward message to resolve)"
        text += f"{i}. <b>{ch['label']}</b>\n• Type: <code>{ch['channel_type']}</code>\n• ID: {status}\n• Link: {ch['invite_link']}\n\n"
        
    await update.effective_chat.send_message(text, parse_mode="HTML")

# --- AUTO DELETION SCHEDULER ---

async def delete_video_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id = job_data["user_id"]
    message_id = job_data["message_id"]
    delivery_id = job_data["delivery_id"]
    
    try:
        await context.bot.delete_message(chat_id=user_id, message_id=message_id)
        logger.info(f"Auto-deleted video message {message_id} for user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to auto-delete video message {message_id} for user {user_id}: {e}")
        
    VideoCatalog.mark_expired(delivery_id)

def schedule_auto_deletion(application, user_id: int, message_id: int, delivery_id: int, expiry_at: datetime):
    delay = (expiry_at - get_utc_now()).total_seconds()
    if delay < 0:
        delay = 0
    application.job_queue.run_once(
        delete_video_job,
        when=delay,
        data={
            "user_id": user_id,
            "message_id": message_id,
            "delivery_id": delivery_id
        },
        name=f"delete_video_{delivery_id}"
    )

async def recover_deletion_jobs(application):
    logger.info("Recovering pending video deletion jobs...")
    pending = database.get_pending_deletions()
    now = get_utc_now()
    recovered = 0
    for deliv in pending:
        try:
            exp = deliv["expiry_at"]
            if isinstance(exp, str):
                exp_dt = datetime.fromisoformat(exp)
            else:
                exp_dt = exp
            if exp_dt.tzinfo is not None:
                exp_dt = exp_dt.replace(tzinfo=None)
            
            if exp_dt <= now:
                try:
                    await application.bot.delete_message(chat_id=deliv["user_id"], message_id=deliv["message_id"])
                except Exception as e:
                    logger.debug(f"Failed deleting expired video message {deliv['message_id']} for user {deliv['user_id']}: {e}")
                VideoCatalog.mark_expired(deliv["delivery_id"])
            else:
                schedule_auto_deletion(application, deliv["user_id"], deliv["message_id"], deliv["delivery_id"], exp_dt)
            recovered += 1
        except Exception as e:
            logger.error(f"Error recovering deletion job for delivery {deliv.get('delivery_id')}: {e}")
    logger.info(f"Recovered {recovered} pending video deletion jobs.")

# --- APPLICATION STARTUP ---

async def on_startup(application: Application):
    database.init_db()
    sync_channels_to_db()
    StartupValidator.validate_preflight(config, BOT_TOKEN, OWNER_ID)
    await recover_deletion_jobs(application)

def run_fastapi_server():
    import uvicorn
    from api import app
    port = int(os.getenv("PORT", 8080))
    try:
        logger.info(f"Starting FastAPI Authoritative REST API server on port {port}...")
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
    except Exception as e:
        logger.warning(f"Failed to start FastAPI server: {e}")

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception handling Telegram update:", exc_info=context.error)

async def admin_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    if update.effective_user.id != OWNER_ID:
        return
    ADMIN_STATES[OWNER_ID] = {"state": "BROADCASTING"}
    await update.effective_chat.send_message(
        "📢 <b>Mass Broadcast Mode Activated</b>\n\n"
        "Send any message (Text, Image, Video, or Formatted HTML) to this chat right now to broadcast it to all registered bot users.\n\n"
        "<i>Type /cancel to exit broadcast mode.</i>",
        parse_mode="HTML"
    )

def main():
    if not BOT_TOKEN or "YOUR_TELEGRAM_BOT_TOKEN" in BOT_TOKEN:
        raise RuntimeError("TG_BOT_TOKEN is missing or unconfigured in environment.")
    
    # 2. Launch FastAPI REST API server thread for Web & Mini App Deployments
    import threading
    t = threading.Thread(target=run_fastapi_server, daemon=True)
    t.start()

    # 3. Build Telegram Application
    application = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    # 4. Register Handlers
    application.add_error_handler(global_error_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("broadcast", admin_broadcast_command))
    application.add_handler(CommandHandler("addvideo", admin_add_video_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("givecredits", admin_give_credits_command))
    application.add_handler(CommandHandler("ban", admin_ban_command))
    application.add_handler(CommandHandler("unban", admin_unban_command))
    application.add_handler(CommandHandler("maintenance", admin_toggle_maintenance))
    application.add_handler(CommandHandler("delvideo", admin_del_video_command))
    application.add_handler(CommandHandler("listvideos", admin_list_videos_command))
    application.add_handler(CommandHandler("syncvideos", admin_sync_videos_command))
    application.add_handler(CommandHandler("channels", admin_channels_command))
    application.add_handler(CommandHandler("setmedia", admin_set_media_command))
    application.add_handler(CommandHandler("unlockcontent", admin_unlock_content_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(ChatJoinRequestHandler(handle_chat_join_request))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_incoming_messages))

    # 5. Start Polling
    logger.info("Starting OkFansBot v2.0 polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
