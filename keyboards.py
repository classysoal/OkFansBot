"""
Inline & Reply Keyboard Markup Generator for OkFansBot v2.0
Mini App-First Architecture
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

WEBAPP_URL = "https://okfanbot.vercel.app"

def get_main_reply_keyboard(is_owner: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🚀 Open VIP App", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton("📢 Notifications"), KeyboardButton("ℹ️ Help & Support")]
    ]
    if is_owner:
        keyboard.append([KeyboardButton("🛠️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def get_home_keyboard(is_starter_completed: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🚀 Launch VIP Mini App", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🏆 VIP Quests", web_app=WebAppInfo(url=f"{WEBAPP_URL}?startapp=verify")),
         InlineKeyboardButton("🎁 Rewards", web_app=WebAppInfo(url=f"{WEBAPP_URL}?startapp=home"))],
        [InlineKeyboardButton("🤝 Invite Friends", web_app=WebAppInfo(url=f"{WEBAPP_URL}?startapp=invite")),
         InlineKeyboardButton("👤 Profile", web_app=WebAppInfo(url=f"{WEBAPP_URL}?startapp=profile"))]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_step1_join_keyboard(required_channels: list) -> InlineKeyboardMarkup:
    keyboard = []
    for ch in required_channels:
        keyboard.append([InlineKeyboardButton(f"🔗 Join {ch['label']}", url=ch["invite_link"])])
    keyboard.append([InlineKeyboardButton("🚀 Verify in VIP App", web_app=WebAppInfo(url=f"{WEBAPP_URL}?startapp=verify"))])
    return InlineKeyboardMarkup(keyboard)

def get_verification_failed_keyboard(missing_channels: list) -> InlineKeyboardMarkup:
    keyboard = []
    for ch in missing_channels:
        keyboard.append([InlineKeyboardButton(f"🔗 Join {ch['label']}", url=ch["invite_link"])])
    keyboard.append([InlineKeyboardButton("🚀 Re-Check in VIP App", web_app=WebAppInfo(url=f"{WEBAPP_URL}?startapp=verify"))])
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🚀 Open VIP App", web_app=WebAppInfo(url=WEBAPP_URL))]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📢 Mass Broadcast", callback_data="btn_admin_broadcast"), InlineKeyboardButton("🎬 Video Catalog", callback_data="btn_admin_catalog")],
        [InlineKeyboardButton("👥 User Manager", callback_data="btn_admin_users"), InlineKeyboardButton("📢 Channels Manager", callback_data="btn_admin_channels")],
        [InlineKeyboardButton("🩺 Diagnostics & Health", callback_data="btn_admin_diagnostics"), InlineKeyboardButton("📊 Detailed Stats", callback_data="btn_admin_stats")],
        [InlineKeyboardButton("🚀 Open Mini App", web_app=WebAppInfo(url=WEBAPP_URL))]
    ]
    return InlineKeyboardMarkup(keyboard)
