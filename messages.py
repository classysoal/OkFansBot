"""
Text Formatters & UI Message Templates for OkFansBot v2.0
"""

def build_progress_bar(current: int, total: int, length: int = 5) -> str:
    if total <= 0:
        return "⬡" * length
    percentage = min(1.0, max(0.0, current / total))
    filled_length = int(round(length * percentage))
    bar = "⬢" * filled_length + "⬡" * (length - filled_length)
    return bar

import random
import database

def get_random_media_url() -> str:
    # Random message ID from channel -1002482913486 (range 155 - 250)
    msg_id = random.randint(155, 250)
    return f"https://t.me/c/2482913486/{msg_id}"

def attach_media_banner(text: str, media_url: str = None) -> str:
    if not media_url or not media_url.strip() or media_url == "random":
        media_url = get_random_media_url()
    url = media_url.strip()
    return f'<a href="{url}">&#8203;</a>{text}'

def get_welcome_dashboard_text(user: dict, total_channels: int, referral_count: int = 0, media_url: str = None) -> str:
    username_display = f"@{user['username']}" if user['username'] else user['first_name']
    is_completed = bool(user.get("starter_completed", 0))
    state = user.get("verification_state", "UNVERIFIED")
    vip_info = database.get_user_vip_tier_info(user["user_id"])
    
    if is_completed or state == "VERIFIED":
        status_line = "🟢 <b>VIP Status: Active & Verified</b>"
    else:
        status_line = "🔴 <b>VIP Status: Verification Pending</b>"
        
    welcome_text = (
        f"✨ <b>Welcome to OkFansBot, {username_display}!</b> ✨\n\n"
        f"{status_line}\n"
        f"• Active Rank: <b>{vip_info['title']}</b>\n"
        f"• Reward Bundle: <b>{vip_info['bundle_size']} Videos / redemption</b>\n\n"
        f"• Available Credits: <b>{user['credits']} 🪙</b>\n"
        f"• Successful Invites: <b>{referral_count} 👥</b>\n\n"
    )
    
    if is_completed:
        welcome_text += f"<blockquote>🎉 Your VIP access is active! Tap <b>Get Video</b> below to claim your {vip_info['bundle_size']}-video reward bundle ({vip_info['credit_cost']} credit).</blockquote>"
    else:
        welcome_text += "<blockquote>🔒 To unlock exclusive VIP video rewards, tap <b>Start Verification</b> below to complete quick tasks.</blockquote>"
        
    return attach_media_banner(welcome_text, media_url)

def get_step1_join_text(required_channels: list, media_url: str = None) -> str:
    text = (
        "🔒 <b>VIP Verification Quest</b>\n"
        "<blockquote>Join all required partner channels below to complete your verification and claim your reward credits:</blockquote>\n\n"
    )
    for idx, ch in enumerate(required_channels, 1):
        text += f"<b>{idx}. {ch['title']}</b>\n"
    
    text += "\n<blockquote>💡 <i>Note: For request-to-join links, simply tap 'Request to Join' and then click Verify.</i></blockquote>"
    return attach_media_banner(text, media_url)

def get_verification_summary_text(results: list, passed_count: int, required_count: int, still_missing: list, media_url: str = None) -> str:
    if passed_count == required_count:
        res_text = (
            "🎉 <b>VIP Verification Complete!</b>\n\n"
            f"<blockquote>✅ All required channels have been verified! Your starter reward credits have been credited. Tap <b>Get Video</b> to claim your 5-video bundle!</blockquote>"
        )
        return attach_media_banner(res_text, media_url)
    
    summary = "📊 <b>Verification Status:</b>\n\n"
    for item in results:
        icon = "✅" if item["passed"] else "❌"
        summary += f"• {item['label']}: {icon}\n"
        
    summary += (
        "\n<blockquote>⚠️ You still need to join the missing channels above before verification can succeed.</blockquote>"
    )
    return attach_media_banner(summary, media_url)

def get_profile_text(user: dict, ref_count: int, total_channels: int, media_url: str = None) -> str:
    username_display = f"@{user['username']}" if user['username'] else user['first_name']
    state = user.get("verification_state", "UNVERIFIED")
    ref_code = user.get("ref_code") or "Default"
    
    profile_text = (
        f"👤 <b>User VIP Dashboard</b>\n\n"
        f"• Name: <b>{user['first_name']}</b>\n"
        f"• Username: <b>{username_display}</b>\n"
        f"• Account Status: <b>{state}</b>\n"
        f"• Unique Referral Code: <code>{ref_code}</code>\n\n"
        f"• Credits Balance: <b>{user['credits']} 🪙</b>\n"
        f"• Verified Referrals: <b>{ref_count} 👥</b>"
    )
    return attach_media_banner(profile_text, media_url)

def get_vip_tiers_text(user_id: int, media_url: str = None) -> str:
    vip_info = database.get_user_vip_tier_info(user_id)
    text = (
        f"🏆 <b>VIP Progression & Level Tiers</b>\n\n"
        f"<blockquote>Current Rank: <b>{vip_info['title']}</b>\n"
        f"Reward Yield: <b>{vip_info['bundle_size']} Videos per 1 Credit</b></blockquote>\n\n"
        f"<b>Unlocked VIP Level Tiers:</b>\n"
        f"🌟 <b>Level 1: Novice VIP</b> (5 Videos per 1 Credit)\n"
        f"🔥 <b>Level 2: Silver VIP</b> (7 Videos per 1 Credit • Unlock: 1 Invite)\n"
        f"👑 <b>Level 3: Gold VIP</b> (10 Videos per 1 Credit • Unlock: 4 Invites)\n"
        f"💎 <b>Level 4: Diamond VIP</b> (15 Ultra Videos per 1 Credit • Unlock: 7 Invites)\n\n"
        f"💡 <i>{vip_info['next_requirement']}</i>"
    )
    return attach_media_banner(text, media_url)

def get_rules_text(media_url: str = None) -> str:
    rules_text = (
        "📜 <b>OkFansBot Rules & Content Policy</b>\n\n"
        "<blockquote>"
        "1. <b>Channel Verification</b>: Must join required channels to redeem videos.\n"
        "2. <b>Reward Bundles</b>: 1 Credit = 5 Exclusive Media Items.\n"
        "3. <b>Content Expiry</b>: Rewards auto-delete to prevent copyright flags.\n"
        "4. <b>Referral Rewards</b>: Earn 3 credits for every verified friend invited.\n"
        "5. <b>Fair Use Policy</b>: Circumvention or referral abuse will trigger an instant ban."
        "</blockquote>"
    )
    return attach_media_banner(rules_text, media_url)

def get_admin_dashboard_text(sys_stats: dict, detailed_cat: dict, media_url: str = None) -> str:
    v_str = ", ".join([f"Vault {v}: {cnt}" for v, cnt in detailed_cat.get("vaults", {}).items()]) or "No videos"
    admin_text = (
        "⚙️ <b>OkFansBot Master Admin Panel</b>\n\n"
        "<blockquote>"
        f"• Total Users: <b>{sys_stats.get('total_users', 0)}</b>\n"
        f"• Total Credits Issued: <b>{sys_stats.get('total_credits', 0)} 🪙</b>\n"
        f"• Catalog Total Videos: <b>{detailed_cat.get('total', 0)}</b>\n"
        f"• Vault Breakdown: <i>{v_str}</i>\n"
        "</blockquote>\n"
        "<i>Select an administrative action from the control menu below:</i>"
    )
    return attach_media_banner(admin_text, media_url)
