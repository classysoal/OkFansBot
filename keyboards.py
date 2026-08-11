"""
Inline Keyboard Markup Generator for OkFansBot v2.0
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def get_main_reply_keyboard(is_owner: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🎁 Get Video"), KeyboardButton("🏆 VIP Tiers")],
        [KeyboardButton("🎁 Daily Bonus"), KeyboardButton("🤝 Invite Friends")],
        [KeyboardButton("👤 My Profile"), KeyboardButton("📜 Rules & Info")]
    ]
    if is_owner:
        keyboard.append([KeyboardButton("🛠️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def get_unverified_home_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🚀 Start Verification", callback_data="btn_start_verification")],
        [InlineKeyboardButton("🏆 VIP Tiers", callback_data="btn_vip_tiers"), InlineKeyboardButton("🎁 Daily Bonus", callback_data="btn_daily_bonus")],
        [InlineKeyboardButton("👤 Profile", callback_data="btn_profile"), InlineKeyboardButton("🤝 Invite Friend", callback_data="btn_invite")],
        [InlineKeyboardButton("📜 Rules", callback_data="btn_rules")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_verified_home_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🎁 Get Video", callback_data="btn_get_video")],
        [InlineKeyboardButton("🏆 VIP Tiers", callback_data="btn_vip_tiers"), InlineKeyboardButton("🎁 Daily Bonus", callback_data="btn_daily_bonus")],
        [InlineKeyboardButton("👤 Profile", callback_data="btn_profile"), InlineKeyboardButton("🤝 Invite Friend", callback_data="btn_invite")],
        [InlineKeyboardButton("📜 Rules", callback_data="btn_rules")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_home_keyboard(is_starter_completed: bool = False) -> InlineKeyboardMarkup:
    if is_starter_completed:
        return get_verified_home_keyboard()
    return get_unverified_home_keyboard()

def get_step1_join_keyboard(required_channels: list) -> InlineKeyboardMarkup:
    keyboard = []
    for ch in required_channels:
        keyboard.append([InlineKeyboardButton(f"🔗 Join {ch['label']}", url=ch["invite_link"])])
    keyboard.append([InlineKeyboardButton("✅ Verify", callback_data="btn_verify")])
    keyboard.append([InlineKeyboardButton("👤 Profile", callback_data="btn_profile"), InlineKeyboardButton("🏠 Home", callback_data="btn_home")])
    return InlineKeyboardMarkup(keyboard)

def get_verification_failed_keyboard(missing_channels: list) -> InlineKeyboardMarkup:
    keyboard = []
    for ch in missing_channels:
        keyboard.append([InlineKeyboardButton(f"🔗 Join {ch['label']}", url=ch["invite_link"])])
    keyboard.append([InlineKeyboardButton("🔄 Re-Verify Joins", callback_data="btn_verify")])
    keyboard.append([InlineKeyboardButton("🏠 Back to Home", callback_data="btn_home")])
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Home", callback_data="btn_home")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📢 Mass Broadcast", callback_data="btn_admin_broadcast"), InlineKeyboardButton("🎬 Video Catalog", callback_data="btn_admin_catalog")],
        [InlineKeyboardButton("👥 User Manager", callback_data="btn_admin_users"), InlineKeyboardButton("📢 Channels Manager", callback_data="btn_admin_channels")],
        [InlineKeyboardButton("🩺 Diagnostics & Health", callback_data="btn_admin_diagnostics"), InlineKeyboardButton("📊 Detailed Stats", callback_data="btn_admin_stats")],
        [InlineKeyboardButton("🔙 Exit Admin Panel", callback_data="btn_home")]
    ]
    return InlineKeyboardMarkup(keyboard)
