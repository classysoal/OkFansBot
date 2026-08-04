import os
import json
import logging
from datetime import datetime, timedelta
import dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions
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

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load env variables and config.json
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

# Global state dictionary for Admin session states (e.g. uploading videos)
ADMIN_STATES = {} # admin_id: {"state": "UPLOADING_VIDEO", "vault": "A", "caption": "..."}
USER_VERIFY_COOLDOWN = {} # user_id: datetime

# --- SYNC CONFIG CHANNELS TO DATABASE ---
def sync_channels_to_db():
    required_channels = config.get("required_channels", [])
    for ch in required_channels:
        database.save_required_channel(
            channel_id=ch["channel_id"],
            label=ch["label"],
            title=ch["title"],
            invite_link=ch["invite_link"],
            channel_type=ch["channel_type"],
            verification_method=ch["verification_method"],
            is_active=ch.get("is_active", 1),
            priority=ch.get("priority", 0)
        )
    logger.info("Synced channels from config.json to database.")

# --- MIDDLEWARE & SECURITY CHECKS ---

def is_maintenance() -> bool:
    # Refresh config on check to support hot-toggles
    c = load_config()
    return c.get("maintenance_mode", False)

async def safe_delete_message(bot, chat_id: int, message_id: int):
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.debug(f"Failed to delete message {message_id} in chat {chat_id}: {e}")

async def check_user_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if bot is in maintenance or if user is banned.
    Returns True if user is allowed to proceed, False otherwise.
    """
    user_id = update.effective_user.id
    user = database.get_user(user_id)
    
    # 1. Ban check
    if user and user.get("is_banned") == 1:
        msg = "❌ <b>You have been banned from using this bot by the administrator.</b>"
        if update.callback_query:
            await update.callback_query.answer("Banned.", show_alert=True)
        else:
            await update.effective_message.reply_html(msg)
        return False
        
    # 2. Maintenance check (owner bypasses)
    if is_maintenance() and user_id != OWNER_ID:
        msg = "⚠️ <b>OkFansBot is currently undergoing scheduled maintenance.</b>\nPlease check back later!"
        if update.callback_query:
            await update.callback_query.answer("Maintenance in progress...", show_alert=True)
        else:
            await update.effective_message.reply_html(msg)
        return False
        
    return True

# --- EXPIRED MESSAGE CLEANUP / JOBS ---

async def delete_expired_video_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    data = job.data
    message_id = data.get("message_id")
    delivery_id = data.get("delivery_id")
    
    logger.info(f"Triggering auto-deletion job for delivery {delivery_id}, message {message_id} in chat {chat_id}")
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Successfully deleted message {message_id} for delivery {delivery_id}")
    except Exception as e:
        logger.warning(f"Failed to delete message {message_id} in chat {chat_id}: {e}")
    finally:
        database.mark_video_deleted(delivery_id)

async def recover_deletion_jobs(application: Application):
    """
    Scans database for pending video deliveries and schedules them or deletes them immediately if expired.
    """
    logger.info("Scanning for pending auto-deletions to recover...")
    pending = database.get_pending_deletions()
    now = datetime.utcnow()
    
    deleted_count = 0
    rescheduled_count = 0
    
    for delivery in pending:
        delivery_id = delivery["delivery_id"]
        chat_id = delivery["chat_id"]
        message_id = delivery["message_id"]
        expiry_at = datetime.fromisoformat(delivery["expiry_at"])
        
        if expiry_at <= now:
            # Already expired, delete immediately
            try:
                await application.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception as e:
                logger.warning(f"Could not delete expired message {message_id} on recovery: {e}")
            database.mark_video_deleted(delivery_id)
            deleted_count += 1
        else:
            # Schedule future deletion
            delay = (expiry_at - now).total_seconds()
            application.job_queue.run_once(
                delete_expired_video_job,
                when=delay,
                chat_id=chat_id,
                data={"message_id": message_id, "delivery_id": delivery_id}
            )
            rescheduled_count += 1
            
    logger.info(f"Recovery finished. Deleted immediately: {deleted_count}. Rescheduled: {rescheduled_count}.")
    database.log_bot_event(
        "system_restart",
        details=f"Recovered pending deletions. Deleted immediately: {deleted_count}, Rescheduled: {rescheduled_count}"
    )

# --- KEYBOARDS & UI BUILDERS ---

def get_home_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✅ Verify", callback_data="btn_verify")],
        [InlineKeyboardButton("🎁 Get Video", callback_data="btn_get_video")],
        [
            InlineKeyboardButton("👤 Profile", callback_data="btn_profile"),
            InlineKeyboardButton("🤝 Invite Friend", callback_data="btn_invite")
        ],
        [InlineKeyboardButton("📜 Rules", callback_data="btn_rules")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Home", callback_data="btn_home")]])

# --- TEMPLATE TEXT FORMATTERS ---

def get_welcome_text(user: dict, total_channels: int) -> str:
    username_display = f"@{user['username']}" if user['username'] else user['first_name']
    
    # Generate progress indicators
    joined = user['verified_channels_count']
    if joined >= total_channels:
        status_text = "🟢 Verified & Unlocked!"
    else:
        status_text = f"🟡 Joining channels: {joined}/{total_channels} completed"

    return (
        f"<b>Welcome to OkFansBot!</b> 🌟\n\n"
        f"Hello {user['first_name']} ({username_display}). This bot offers exclusive access to premium video vaults.\n\n"
        f"To unlock, verify your membership in our required channels.\n\n"
        f"⚡ <b>Your Status:</b>\n"
        f"• Status: {status_text}\n"
        f"• Available Credits: <b>{user['credits']} 🪙</b>\n"
        f"• Verified Referrals: <b>{user['verified_channels_count']} 👥</b>\n\n"
        f"Use the buttons below to navigate:"
    )

# --- COMMAND HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_access(update, context):
        return

    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    # 1. Attempt to delete incoming user /start message to keep chat clean
    try:
        await update.message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete incoming user message: {e}")

    # 2. Detect referrals: e.g. /start ref_12345
    referred_by = None
    args = context.args
    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0].split("_")[1])
        except ValueError:
            pass

    # Register user in database
    user, is_new = database.register_user(
        user_id=user_id,
        username=username,
        first_name=first_name,
        referred_by=referred_by
    )
    
    if not user:
        await update.effective_chat.send_message("An error occurred starting the bot. Please try again.")
        return

    # 3. Clean up previous menu message if exists
    old_menu_id = database.get_last_menu_message(user_id)
    if old_menu_id:
        await safe_delete_message(context.bot, user_id, old_menu_id)

    # Sync and get channels count
    active_channels = database.get_required_channels()
    total_channels = len(active_channels)

    welcome_text = get_welcome_text(user, total_channels)
    
    # If the user is new and referred by someone, add a special notice
    if is_new and referred_by and referred_by != user_id:
        referrer = database.get_user(referred_by)
        referrer_name = referrer['first_name'] if referrer else f"User {referred_by}"
        welcome_text = f"👋 <i>You were referred by {referrer_name}!</i>\n\n" + welcome_text
        
    sent_msg = await update.effective_chat.send_message(
        welcome_text,
        reply_markup=get_home_keyboard(),
        parse_mode="HTML"
    )
    
    # Save the new menu message ID
    database.update_last_menu_message(user_id, sent_msg.message_id)

# --- CALLBACK QUERY HANDLERS (THE USER UX) ---

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not await check_user_access(update, context):
        return
        
    user_id = update.effective_user.id
    data = query.data
    
    # Load user data
    user = database.get_user(user_id)
    if not user:
        return
        
    active_channels = database.get_required_channels()
    total_channels = len(active_channels)
    
    if data == "btn_home":
        # Return to welcome dashboard
        await query.edit_message_text(
            get_welcome_text(user, total_channels),
            reply_markup=get_home_keyboard(),
            parse_mode="HTML"
        )
        
    elif data == "btn_profile":
        # Profile View
        # Get inviter name
        referred_by_name = "None"
        if user["referred_by"]:
            inviter = database.get_user(user["referred_by"])
            referred_by_name = inviter["first_name"] if inviter else f"ID {user['referred_by']}"
            
        # Count total videos watched
        db_conn = database.get_db_connection()
        cursor = db_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM video_deliveries WHERE user_id = ?", (user_id,))
        videos_watched = cursor.fetchone()[0]
        
        # Count verified referrals
        cursor.execute("SELECT COUNT(*) FROM referrals WHERE inviter_user_id = ? AND status = 'verified'", (user_id,))
        referral_count = cursor.fetchone()[0]
        db_conn.close()
        
        # Map vault index to name
        vaults = ["Vault A (Starter)", "Vault B (Join Rewards)", "Vault C (Referrals)", "Vault D (Premium)", "Vault E (Special)"]
        vault_name = vaults[user["vault_pointer"] % len(vaults)]
        
        profile_text = (
            f"👤 <b>YOUR PROFILE</b>\n"
            f"───────────────────\n"
            f"• <b>Name:</b> {user['first_name']}\n"
            f"• <b>Username:</b> @{user['username'] if user['username'] else 'None'}\n"
            f"• <b>User ID:</b> <code>{user_id}</code>\n"
            f"• <b>Referred By:</b> {referred_by_name}\n"
            f"• <b>Verified Joins:</b> {user['verified_channels_count']}/{total_channels}\n"
            f"• <b>Referrals (Verified):</b> {referral_count}\n"
            f"• <b>Available Credits:</b> {user['credits']} 🪙\n"
            f"• <b>Videos Redeemed:</b> {videos_watched}\n"
            f"• <b>Current Vault Position:</b> {vault_name}\n"
            f"───────────────────\n"
            f"🔗 <b>Your Referral Link:</b>\n"
            f"<code>https://t.me/OkFansBot?start=ref_{user_id}</code>"
        )
        await query.edit_message_text(
            profile_text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
        
    elif data == "btn_invite":
        # Invite Friend View
        invite_text = (
            f"🤝 <b>REFERRAL PROGRAM</b>\n\n"
            f"Invite your friends and earn premium video credits!\n\n"
            f"• For every friend who signs up using your link AND verifies their required channel joins, you will receive <b>{config.get('credits_per_verified_referral', 3)} credits</b>!\n"
            f"• Credits allow you to unlock videos in the premium vaults.\n\n"
            f"🔗 <b>Your Custom Referral Link:</b>\n"
            f"<code>https://t.me/OkFansBot?start=ref_{user_id}</code>\n\n"
            f"<i>Share this link with friends to start earning!</i>"
        )
        await query.edit_message_text(
            invite_text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
        
    elif data == "btn_rules":
        # Rules View
        rules_text = (
            f"📜 <b>RULES & INSTRUCTIONS</b>\n\n"
            f"1. <b>No Fake Channel Farming</b>: You must remain in the required channels to keep your unlocked status. Leaving channels will lock video delivery.\n"
            f"2. <b>Self-Referral Protection</b>: Creating multiple accounts to refer yourself is strictly prohibited. Our anti-abuse engine logs and auto-bans violators.\n"
            f"3. <b>Message Expiration</b>: All reward videos are sent with copy protection and are automatically deleted after 30 minutes. Make sure to watch them promptly!\n"
            f"4. <b>Idempotency</b>: Joins and referrals are counted once. Re-joining a channel or re-inviting the same user does not grant double credits."
        )
        await query.edit_message_text(
            rules_text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
        
    elif data == "btn_verify":
        # Verify Action
        # Rate limit check (Verify Spam Protection)
        now = datetime.utcnow()
        last_click = USER_VERIFY_COOLDOWN.get(user_id)
        if last_click and (now - last_click).total_seconds() < 10:
            await query.answer("⚠️ Please wait 10 seconds before clicking verify again.", show_alert=True)
            return
            
        USER_VERIFY_COOLDOWN[user_id] = now
        
        # Verify joins
        missing = []
        verified_this_session = 0
        
        for ch in active_channels:
            # Perform check
            is_member = False
            # If join_request check DB
            if ch["verification_method"] == "join_request":
                evt = database.get_join_event(user_id, ch["channel_id"])
                if evt and evt["status"] == "requested":
                    is_member = True
            
            # If still not verified, verify via API get_chat_member
            if not is_member:
                try:
                    member = await context.bot.get_chat_member(chat_id=ch["channel_id"], user_id=user_id)
                    if member.status in ["creator", "administrator", "member"]:
                        is_member = True
                        # Update join status in DB as joined
                        database.record_join_event(user_id, ch["channel_id"], "joined")
                except Exception as e:
                    logger.debug(f"API membership check failed for user {user_id} in {ch['channel_id']}: {e}")
                    
            if is_member:
                # Mark as verified in database
                did_verify = database.verify_join(user_id, ch["channel_id"])
                if did_verify:
                    verified_this_session += 1
            else:
                missing.append(ch)

        # Refresh user data
        user = database.get_user(user_id)
        
        if len(missing) == 0:
            # All channels verified!
            # Did they verify new ones this time?
            reward_msg = ""
            if verified_this_session > 0:
                # Milestone check
                # User completed starter gate: grant 1 initial credit
                database.add_credits(user_id, 1, "starter_bonus")
                reward_msg = "\n\n🎉 <b>All channels verified! Initial 1 credit granted.</b>"
                
                # Check if referred by someone and process referral crediting
                inviter_id, inviter_credits = database.add_referral_credits_if_eligible(
                    referred_user_id=user_id,
                    referral_credits=config.get("credits_per_verified_referral", 3)
                )
                if inviter_id:
                    # Notify referrer!
                    try:
                        ref_msg = (
                            f"👥 <b>Referral Verified!</b>\n\n"
                            f"The user you invited ({user['first_name']}) has successfully verified all required channels.\n"
                            f"You have been credited with <b>{config.get('credits_per_verified_referral', 3)} credits</b>!\n"
                            f"Total Credits: <b>{inviter_credits} 🪙</b>"
                        )
                        await context.bot.send_message(
                            chat_id=inviter_id,
                            text=ref_msg,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify inviter {inviter_id}: {e}")

            # Refresh user again for display
            user = database.get_user(user_id)
            await query.edit_message_text(
                f"✅ <b>All required channels verified successfully!</b>{reward_msg}\n\n"
                f"• Available Credits: <b>{user['credits']} 🪙</b>\n"
                f"• Verified Joins: <b>{user['verified_channels_count']}/{total_channels}</b>\n\n"
                f"Tap <b>Get Video</b> to watch your rewards!",
                reply_markup=get_back_keyboard(),
                parse_mode="HTML"
            )
        else:
            # Missing channels, show inline links to join
            kb = []
            for m in missing:
                kb.append([InlineKeyboardButton(f"🔗 Join {m['label']}", url=m["invite_link"])])
            kb.append([InlineKeyboardButton("🔄 Re-Verify Joins", callback_data="btn_verify")])
            kb.append([InlineKeyboardButton("🔙 Back to Home", callback_data="btn_home")])
            
            await query.edit_message_text(
                f"⚠️ <b>Verification Failed!</b>\n\n"
                f"You must join all required channels to verify your access. Please join the channels listed below and click Verify:\n\n"
                f"<i>(Note: For request-to-join links, simply click 'Request to Join' and we will verify the request status)</i>",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="HTML"
            )

    elif data == "btn_get_video":
        # Get Video Action
        # First check verification
        unverified_channels = []
        for ch in active_channels:
            is_member = False
            if ch["verification_method"] == "join_request":
                evt = database.get_join_event(user_id, ch["channel_id"])
                if evt and evt["status"] == "requested":
                    is_member = True
            
            if not is_member:
                try:
                    member = await context.bot.get_chat_member(chat_id=ch["channel_id"], user_id=user_id)
                    if member.status in ["creator", "administrator", "member"]:
                        is_member = True
                except:
                    pass
            if not is_member:
                unverified_channels.append(ch)

        if len(unverified_channels) > 0:
            await query.edit_message_text(
                "❌ <b>Access Denied!</b>\n\n"
                "You must verify your membership in all required channels before requesting reward videos.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Start Verification", callback_data="btn_verify")
                ], [
                    InlineKeyboardButton("🔙 Back to Home", callback_data="btn_home")
                ]]),
                parse_mode="HTML"
            )
            return

        # Check credits
        if user["credits"] < 1:
            await query.edit_message_text(
                "❌ <b>Insufficient Credits!</b>\n\n"
                "You do not have enough credits to redeem a video.\n\n"
                "💡 <i>How to get credits:</i>\n"
                "• Complete your initial channel verification (+1 credit)\n"
                "• Invite friends using your referral link (+3 credits per verified referral)",
                reply_markup=get_back_keyboard(),
                parse_mode="HTML"
            )
            return

        # Cooldown check
        # We can implement cooldown per user to prevent rapid button double-clicks
        # Fetch last delivery
        db_conn = database.get_db_connection()
        cursor = db_conn.cursor()
        cursor.execute("""
            SELECT sent_at FROM video_deliveries 
            WHERE user_id = ? 
            ORDER BY sent_at DESC LIMIT 1
        """, (user_id,))
        last_del = cursor.fetchone()
        db_conn.close()
        
        if last_del:
            sent_time = datetime.fromisoformat(last_del["sent_at"])
            cooldown = config.get("cooldown_between_claims_seconds", 10)
            elapsed = (datetime.utcnow() - sent_time).total_seconds()
            if elapsed < cooldown:
                await query.answer(f"⏳ Cooldown: Please wait {int(cooldown - elapsed)}s before claiming another video.", show_alert=True)
                return

        # Choose vault depending on milestones or just loop
        # The user has Vaults A, B, C, D, E
        # Map pointer to vaults
        vault_mapping = ["A", "B", "C", "D", "E"]
        active_vault = vault_mapping[user["vault_pointer"] % len(vault_mapping)]

        # Try to get next video in that vault
        video = database.get_next_reward_video(user_id, active_vault)
        if not video:
            # Fallback: find any active video in Vault B
            video = database.get_next_reward_video(user_id, "B")
            
        if not video:
            await query.edit_message_text(
                "⚠️ <b>Video Vault Empty!</b>\n\n"
                "There are currently no videos uploaded in the reward library. Please notify the administrator.",
                reply_markup=get_back_keyboard(),
                parse_mode="HTML"
            )
            return

        # Deduct 1 credit from user
        deducted = database.add_credits(user_id, -1, "video_spend")
        if not deducted:
            await query.answer("Transaction failed. Try again.", show_alert=True)
            return

        # Send protected video
        try:
            caption = video["caption"] if video["caption"] else ""
            expiry_delay = config.get("video_deletion_delay_seconds", 1800)
            expiry_time = datetime.utcnow() + timedelta(seconds=expiry_delay)
            
            # Format expiry notice
            expiry_text = f"🔥 <i>This video will auto-delete in {int(expiry_delay/60)} minutes. Forwarding/saving is blocked.</i>"
            full_caption = f"{caption}\n\n{expiry_text}" if caption else expiry_text

            sent_msg = await context.bot.send_video(
                chat_id=user_id,
                video=video["file_id"],
                caption=full_caption,
                parse_mode="HTML",
                protect_content=True
            )
            
            # Record delivery
            delivery_id = database.record_video_delivery(
                user_id=user_id,
                video_id=video["video_id"],
                chat_id=user_id,
                message_id=sent_msg.message_id,
                expiry_at=expiry_time
            )
            
            # Schedule JobQueue auto-deletion
            context.application.job_queue.run_once(
                delete_expired_video_job,
                when=expiry_delay,
                chat_id=user_id,
                data={"message_id": sent_msg.message_id, "delivery_id": delivery_id}
            )

            # Delete the previous menu message now that the video was successfully sent
            await safe_delete_message(context.bot, user_id, query.message.message_id)
            
            # Fetch updated user data (after deduction)
            updated_user = database.get_user(user_id)
            
            # Send new menu message below the video
            new_menu_text = (
                f"🚀 <b>Video Sent! Check it above.</b>\n\n"
                f"{get_welcome_text(updated_user, total_channels)}"
            )
            new_msg = await context.bot.send_message(
                chat_id=user_id,
                text=new_menu_text,
                reply_markup=get_home_keyboard(),
                parse_mode="HTML"
            )
            
            # Save the new menu message ID
            database.update_last_menu_message(user_id, new_msg.message_id)
        except Exception as e:
            logger.error(f"Error sending video {video['video_id']} to user {user_id}: {e}")
            # Refund credit
            database.add_credits(user_id, 1, "admin_adjust")
            await query.edit_message_text(
                "❌ <b>Error Sending Video!</b>\n\n"
                "We encountered a Telegram API error while trying to send the video. Your 1 credit has been refunded.",
                reply_markup=get_back_keyboard(),
                parse_mode="HTML"
            )

# --- CHAT JOIN REQUEST LISTENER ---

async def handle_chat_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggers when a user clicks a request-to-join link in a private channel.
    Allows the bot to log request status to verify gate constraints.
    """
    request = update.chat_join_request
    user_id = request.from_user.id
    channel_id = request.chat.id
    
    logger.info(f"Join request received from user {user_id} for channel {channel_id}")
    
    # Verify if channel is in our configuration gate
    channels = database.get_required_channels(only_active=False)
    target_channel = next((c for c in channels if c["channel_id"] == channel_id), None)
    
    if target_channel:
        # Save join request to database as 'requested' and log as verified request
        database.record_join_event(user_id, channel_id, "requested")
        logger.info(f"Logged pending join request for user {user_id} in required channel {channel_id}")
        
        # Optionally, notify the supergroup or admin
        try:
            log_text = f"🔔 <b>New Join Request:</b>\nUser: <code>{user_id}</code>\nChannel: <code>{channel_id}</code> ({target_channel['label']})"
            await context.bot.send_message(chat_id=UPDATES_SUPERGROUP_ID, text=log_text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Could not send updates notification: {e}")

# --- ADMIN PANEL COMMAND HANDLERS ---

async def delete_incoming_cmd(update: Update):
    try:
        await update.message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete incoming command message: {e}")

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    admin_id = update.effective_user.id
    if admin_id != OWNER_ID:
        # Ignore unauthorized calls
        return
        
    stats = database.get_system_stats()
    
    # Format vault stats list
    vault_stats = ""
    for vault, count in stats.get("vault_counts", {}).items():
        vault_stats += f"• Vault {vault}: <b>{count} videos</b>\n"
        
    stats_text = (
        f"⚙️ <b>OKFANSBOT ADMIN CONSOLE</b>\n"
        f"────────────────────────\n"
        f"• Total Users registered: <b>{stats.get('total_users', 0)}</b>\n"
        f"• Active Users (non-banned): <b>{stats.get('active_users', 0)}</b>\n"
        f"• Verified Referrals: <b>{stats.get('total_referrals', 0)}</b>\n"
        f"• Total Videos Redeemed: <b>{stats.get('total_redeemed', 0)}</b>\n"
        f"• Total Videos Auto-Deleted: <b>{stats.get('total_deleted', 0)}</b>\n"
        f"────────────────────────\n"
        f"📁 <b>Vault Statistics:</b>\n{vault_stats if vault_stats else 'No videos uploaded yet.'}\n"
        f"────────────────────────\n"
        f"ℹ️ <b>Commands:</b>\n"
        f"• <code>/addvideo [vault] [caption]</code> - Bulk upload videos\n"
        f"• <code>/givecredits [user_id] [amt]</code> - Add credits\n"
        f"• <code>/ban [user_id]</code> - Ban user\n"
        f"• <code>/unban [user_id]</code> - Unban user\n"
        f"• <code>/maintenance</code> - Toggle maintenance mode\n"
        f"• <code>/cancel</code> - Exit active admin states"
    )
    
    await update.effective_message.reply_html(stats_text)

async def admin_add_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    admin_id = update.effective_user.id
    if admin_id != OWNER_ID:
        return
        
    args = context.args
    if not args or args[0].upper() not in ["A", "B", "C", "D", "E"]:
        await update.effective_message.reply_text("Usage: /addvideo [vault_name: A/B/C/D/E] [optional_caption]")
        return
        
    vault = args[0].upper()
    caption = " ".join(args[1:]) if len(args) > 1 else None
    
    # Store state
    ADMIN_STATES[admin_id] = {
        "state": "UPLOADING_VIDEO",
        "vault": vault,
        "caption": caption
    }
    
    await update.effective_message.reply_html(
        f"📥 <b>Video Upload Mode Activated!</b>\n\n"
        f"Target Vault: <b>Vault {vault}</b>\n"
        f"Caption Template: <i>{caption if caption else 'None'}</i>\n\n"
        f"Send or Forward any reward videos to this chat. They will be imported automatically.\n"
        f"Type <code>/cancel</code> when done uploading."
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    admin_id = update.effective_user.id
    if admin_id != OWNER_ID:
        return
        
    if admin_id in ADMIN_STATES:
        del ADMIN_STATES[admin_id]
        await update.effective_message.reply_text("❌ Admin active upload state canceled. Exit bulk upload mode.")
    else:
        await update.effective_message.reply_text("No active admin state found.")

async def admin_give_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    admin_id = update.effective_user.id
    if admin_id != OWNER_ID:
        return
        
    args = context.args
    if len(args) < 2:
        await update.effective_message.reply_text("Usage: /givecredits [user_id] [amount]")
        return
        
    try:
        user_id = int(args[0])
        amount = int(args[1])
    except ValueError:
        await update.effective_message.reply_text("Invalid inputs. Ensure user_id and amount are integers.")
        return
        
    user = database.get_user(user_id)
    if not user:
        await update.effective_message.reply_text("User not found in database.")
        return
        
    success = database.add_credits(user_id, amount, "admin_adjust")
    if success:
        database.log_admin_action(admin_id, "give_credits", f"Credits: {amount} to user {user_id}")
        await update.effective_message.reply_html(f"✅ Successfully credited <b>{amount} credits</b> to user <code>{user_id}</code>.")
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🪙 <b>Admin Balance Adjustment:</b>\nYou have received <b>{amount} credits</b>! Total Balance: {user['credits'] + amount} credits."
            )
        except Exception as e:
            logger.warning(f"Could not notify user of admin adjustment: {e}")
    else:
        await update.effective_message.reply_text("Failed to adjust credits.")

async def admin_ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    admin_id = update.effective_user.id
    if admin_id != OWNER_ID:
        return
        
    args = context.args
    if not args:
        await update.effective_message.reply_text("Usage: /ban [user_id]")
        return
        
    try:
        user_id = int(args[0])
    except ValueError:
        await update.effective_message.reply_text("Invalid user ID.")
        return
        
    success = database.set_ban_status(user_id, 1)
    if success:
        database.log_admin_action(admin_id, "ban_user", f"Banned user {user_id}")
        await update.effective_message.reply_text(f"✅ User {user_id} has been banned.")
    else:
        await update.effective_message.reply_text("Failed to ban user or user not found.")

async def admin_unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    admin_id = update.effective_user.id
    if admin_id != OWNER_ID:
        return
        
    args = context.args
    if not args:
        await update.effective_message.reply_text("Usage: /unban [user_id]")
        return
        
    try:
        user_id = int(args[0])
    except ValueError:
        await update.effective_message.reply_text("Invalid user ID.")
        return
        
    success = database.set_ban_status(user_id, 0)
    if success:
        database.log_admin_action(admin_id, "unban_user", f"Unbanned user {user_id}")
        await update.effective_message.reply_text(f"✅ User {user_id} has been unbanned.")
    else:
        await update.effective_message.reply_text("Failed to unban user or user not found.")

async def admin_toggle_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_incoming_cmd(update)
    admin_id = update.effective_user.id
    if admin_id != OWNER_ID:
        return
        
    current = config.get("maintenance_mode", False)
    new_state = not current
    
    config["maintenance_mode"] = new_state
    save_config(config)
    
    database.log_admin_action(admin_id, "toggle_maintenance", f"Set to {new_state}")
    
    state_display = "ENABLED (Users blocked)" if new_state else "DISABLED (Users allowed)"
    await update.effective_message.reply_html(f"🛠️ <b>Maintenance Mode:</b> {state_display}")

# --- TEXT / MEDIA MESSAGE HANDLER (FOR VIDEO UPLOADS) ---

async def handle_incoming_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if admin is in video upload state
    if user_id == OWNER_ID and user_id in ADMIN_STATES:
        state = ADMIN_STATES[user_id]
        if state["state"] == "UPLOADING_VIDEO":
            # Check if message contains video
            if update.effective_message.video:
                video = update.effective_message.video
                file_id = video.file_id
                
                # Check for custom caption or fallback to update caption
                caption = state["caption"]
                if not caption and update.effective_message.caption:
                    caption = update.effective_message.caption
                    
                vault = state["vault"]
                
                # Save to database
                success = database.add_video(file_id, caption, vault)
                if success:
                    await update.effective_message.reply_text(
                        f"✅ Imported Video to Vault {vault} successfully!\nFile ID: {file_id[:20]}..."
                    )
                else:
                    await update.effective_message.reply_text("❌ Video import failed (possibly duplicate file ID).")
            else:
                await update.effective_message.reply_text("⚠️ Upload state is active. Please send a Video or call /cancel to exit.")
            return

    # Normal user chat handling (fall through)
    if not await check_user_access(update, context):
        return
        
    try:
        await update.message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete incoming user message: {e}")

    # Remove old menu and print a fresh new one
    old_menu_id = database.get_last_menu_message(user_id)
    if old_menu_id:
        await safe_delete_message(context.bot, user_id, old_menu_id)

    # Sync and get channels count
    active_channels = database.get_required_channels()
    total_channels = len(active_channels)
    user = database.get_user(user_id)
    if not user:
        return
    
    sent_msg = await update.effective_chat.send_message(
        get_welcome_text(user, total_channels),
        reply_markup=get_home_keyboard(),
        parse_mode="HTML"
    )
    database.update_last_menu_message(user_id, sent_msg.message_id)

# --- STARTUP SYNC & SETUP ---

async def on_startup(application: Application):
    # Initialize DB files
    database.init_db()
    # Sync config channels to database
    sync_channels_to_db()
    # Recover jobs
    await recover_deletion_jobs(application)

# --- MAIN EXECUTION ---

def main():
    if not BOT_TOKEN or "YOUR_TELEGRAM_BOT_TOKEN" in BOT_TOKEN:
        print("CRITICAL ERROR: Telegram Bot Token (TG_BOT_TOKEN) is not configured in .env!")
        return

    # Create Bot Application
    application = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    # Handlers Registration
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(ChatJoinRequestHandler(handle_chat_join_request))
    
    # Admin Command Handlers
    application.add_handler(CommandHandler("admin", admin_panel_command))
    application.add_handler(CommandHandler("addvideo", admin_add_video_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("givecredits", admin_give_credits_command))
    application.add_handler(CommandHandler("ban", admin_ban_command))
    application.add_handler(CommandHandler("unban", admin_unban_command))
    application.add_handler(CommandHandler("maintenance", admin_toggle_maintenance))

    # Fallback Message Handler (Text & Media Messages)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_incoming_messages))

    # Run Application
    print("OkFansBot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
