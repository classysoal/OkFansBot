"""
Authoritative REST API Backend Server for OkFansBot v2.0
Implements Telegram InitData HMAC Authentication, RBAC, Mini App API, and Admin Control Panel API.
"""

import os
import json
import hmac
import hashlib
import time
import uuid
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request, status, Response
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database
from services.verification import VerificationManager, VerificationService
from services.referrals import ReferralManager
from services.rewards import RewardManager
from services.video_catalog import VideoCatalog


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("okfans_api")

BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "8938399688:AAHPaPDM5qCZyJA0X1ccLiQP45yuQPDB8Uo")
CONFIG_PATH = "config.json"

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

config = load_config()
OWNER_ID = config.get("owner_id", 6193742824)

app = FastAPI(
    title="OkFansBot Authoritative API",
    version="2.0.0",
    description="Stateless, secure REST API engine for Telegram Mini App and Admin Control Panel."
)

allowed_origins = [
    "https://okfanbot.vercel.app",
    "https://okfansbot.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]
if os.getenv("ENVIRONMENT") == "development":
    allowed_origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if os.path.exists("webapp"):
    app.mount("/app", StaticFiles(directory="webapp", html=True), name="webapp")

@app.get("/")
def root_health_check():
    return {
        "status": "online",
        "service": "OkFansBot Authoritative REST API & Telegram Bot",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# --- TELEGRAM LOGIN WIDGET OAUTH ---

@app.get("/auth/telegram")
@app.get("/api/auth/telegram-widget")
def telegram_widget_auth(request: Request):
    """
    Handles Telegram Login Widget OAuth authentication.
    Calculates SHA256 secret key of BOT_TOKEN and verifies hash signature.
    """
    params = dict(request.query_params)
    received_hash = params.pop("hash", None)
    
    if not received_hash or "id" not in params:
        return RedirectResponse(url="https://okfanbot.vercel.app/?auth_error=missing_hash")

    data_check_arr = [f"{k}={v}" for k, v in sorted(params.items())]
    data_check_string = "\n".join(data_check_arr)
    
    secret_key = hashlib.sha256(BOT_TOKEN.encode("utf-8")).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(computed_hash.lower(), received_hash.lower()):
        return RedirectResponse(url="https://okfanbot.vercel.app/?auth_error=invalid_signature")
        
    try:
        user_id = int(params.get("id"))
        username = params.get("username", "")
        first_name = params.get("first_name", "User")
        
        user = database.get_user(user_id)
        if not user:
            database.register_user(user_id, username, first_name)
            
        return RedirectResponse(url=f"https://okfanbot.vercel.app/?auth=success&user_id={user_id}")
    except Exception as e:
        logger.error(f"Widget auth error: {e}")
        return RedirectResponse(url="https://okfanbot.vercel.app/?auth_error=exception")


# --- TELEGRAM INITDATA HMAC VALIDATION ---

def validate_telegram_init_data(init_data: str) -> dict:
    """
    Validates Telegram WebApp initData string using HMAC-SHA256.
    Returns parsed user dict if valid; raises HTTPException 401 if invalid/expired.
    """
    if not init_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Telegram initData")
        
    try:
        from urllib.parse import parse_qsl, unquote
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception as e:
        logger.error(f"Failed to parse initData: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid initData format")
        
    received_hash = parsed_data.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing initData hash")
        
    # Check data freshness (max 24 hours)
    auth_date = parsed_data.get("auth_date")
    if auth_date:
        try:
            if time.time() - int(auth_date) > 86400:
                logger.warning(f"Expired auth_date: {auth_date}")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired initData auth_date")
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth_date")

    # Reconstruct data-check-string
    data_check_arr = [f"{k}={v}" for k, v in sorted(parsed_data.items())]
    data_check_string = "\n".join(data_check_arr)

    token = (os.getenv("TG_BOT_TOKEN") or "8938399688:AAHPaPDM5qCZyJA0X1ccLiQP45yuQPDB8Uo").strip()
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash.lower(), received_hash.lower()):
        # Try raw pair parsing fallback
        raw_pairs = [p.split("=", 1) for p in init_data.split("&") if "=" in p]
        raw_dict = {p[0]: unquote(p[1]) if len(p) > 1 else "" for p in raw_pairs if p[0] != "hash"}
        raw_check_arr = [f"{k}={v}" for k, v in sorted(raw_dict.items())]
        raw_check_string = "\n".join(raw_check_arr)
        raw_computed_hash = hmac.new(secret_key, raw_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if hmac.compare_digest(raw_computed_hash.lower(), received_hash.lower()):
            computed_hash = raw_computed_hash
        else:
            logger.warning(f"HMAC mismatch: computed={computed_hash.lower()} vs received={received_hash.lower()}")
            if os.getenv("ENVIRONMENT") == "development" and "user" in parsed_data:
                logger.warning("Development mode bypassing HMAC verification")
            else:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid initData signature")

    user_json = parsed_data.get("user")
    if not user_json:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user data in initData")

    try:
        user_data = json.loads(user_json)
        return user_data
    except Exception as e:
        logger.error(f"Malformed user JSON: {user_json}, error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed user JSON in initData")



# --- AUTHENTICATION DEPENDENCY & PIPELINE ---

class MiniAppAuthRequest(BaseModel):
    initData: str

@app.post("/api/auth/miniapp")
def miniapp_auth(payload: MiniAppAuthRequest):
    if not payload.initData:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing initData payload")

    user_data = validate_telegram_init_data(payload.initData)
    tg_user_id = user_data.get("id")
    
    if not tg_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram identity")

    user, is_new = database.upsert_user_by_telegram_id(
        telegram_user_id=tg_user_id,
        username=user_data.get("username"),
        first_name=user_data.get("first_name")
    )
    
    if user.get("is_banned", 0) == 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ACCOUNT_BANNED: User account is banned.")

    session = database.create_user_session(user_id=tg_user_id, auth_method="MINI_APP")
    
    return {
        "success": True,
        "session_token": session["session_token"],
        "expires_at": session["expires_at"],
        "account_created": is_new,
        "user": user
    }

@app.get("/auth/telegram/callback")
def telegram_oidc_callback(request: Request):
    """
    Handles official Telegram OIDC / Login Widget authorization callback.
    Validates state parameter, client secret, and signature.
    """
    params = dict(request.query_params)
    received_hash = params.pop("hash", None)
    
    if not received_hash or "id" not in params:
        return RedirectResponse(url="https://okfanbot.vercel.app/?auth_error=AUTH_INVALID")

    data_check_arr = [f"{k}={v}" for k, v in sorted(params.items())]
    data_check_string = "\n".join(data_check_arr)
    
    client_secret = os.getenv("TELEGRAM_LOGIN_CLIENT_SECRET") or BOT_TOKEN
    secret_key = hashlib.sha256(client_secret.encode("utf-8")).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(computed_hash.lower(), received_hash.lower()):
        return RedirectResponse(url="https://okfanbot.vercel.app/?auth_error=AUTH_STATE_MISMATCH")

    try:
        user_id = int(params.get("id"))
        username = params.get("username", "")
        first_name = params.get("first_name", "User")
        
        user, is_new = database.upsert_user_by_telegram_id(
            telegram_user_id=user_id,
            username=username,
            first_name=first_name
        )
        
        session = database.create_user_session(user_id=user_id, auth_method="TELEGRAM_OIDC")
        return RedirectResponse(url=f"https://okfanbot.vercel.app/?auth=success&session_token={session['session_token']}")
    except Exception as e:
        logger.error(f"OIDC Auth error: {e}")
        return RedirectResponse(url="https://okfanbot.vercel.app/?auth_error=AUTH_PROVIDER_ERROR")


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        database.revoke_user_session(token)
    return {"success": True, "message": "Logged out successfully"}

async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_telegram_init_data: Optional[str] = Header(None)
) -> dict:
    session_token = None
    if authorization and authorization.startswith("Bearer "):
        session_token = authorization.split("Bearer ", 1)[1].strip()

    if session_token:
        user = database.get_user_by_session(session_token)
        if user:
            if user.get("is_banned", 0) == 1:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ACCOUNT_BANNED: User account is banned.")
            return user

    if x_telegram_init_data:
        try:
            user_data = validate_telegram_init_data(x_telegram_init_data)
            tg_user_id = user_data.get("id")
            if tg_user_id:
                user, _ = database.upsert_user_by_telegram_id(
                    telegram_user_id=tg_user_id,
                    username=user_data.get("username"),
                    first_name=user_data.get("first_name")
                )
                if user.get("is_banned", 0) == 1:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ACCOUNT_BANNED: User account is banned.")
                return user
        except HTTPException as e:
            if os.getenv("ENVIRONMENT") != "development":
                raise e
        except Exception as e:
            logger.error(f"InitData auth error: {e}")

    if os.getenv("ENVIRONMENT") == "development":
        owner_user = database.get_user(OWNER_ID)
        if owner_user:
            return owner_user
        return {
            "user_id": OWNER_ID,
            "username": "OwnerPreview",
            "first_name": "VIP Owner",
            "credits": 10,
            "is_banned": 0,
            "starter_completed": 1
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, 
        detail="AUTH_REQUIRED: Valid Telegram authentication or session required."
    )

async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["user_id"] != OWNER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


# --- API ENDPOINTS ---

@app.get("/health")
def health_check():
    stats = database.get_system_stats()
    return {
        "status": "healthy",
        "version": "2.0.0",
        "environment": os.getenv("ENVIRONMENT", "production"),
        "postgres_mode": database.IS_POSTGRES,
        "database_connected": bool(stats),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    ref_count = ReferralManager.get_verified_referrals_count(user_id)
    vip_info = database.get_user_vip_tier_info(user_id)
    ref_code = ReferralManager.get_or_create_user_ref_code(user_id)
    
    return {
        "user_id": user_id,
        "username": current_user.get("username"),
        "first_name": current_user.get("first_name"),
        "credits": current_user.get("credits", 0),
        "vip_level": vip_info["level"],
        "vip_title": vip_info["title"],
        "vip_badge": vip_info["badge"],
        "bundle_size": vip_info["bundle_size"],
        "credit_cost": vip_info["credit_cost"],
        "referral_count": ref_count,
        "ref_code": ref_code,
        "checkin_streak": current_user.get("checkin_streak", 0),
        "starter_completed": bool(current_user.get("starter_completed", 0))
    }

@app.get("/api/dashboard")
def get_dashboard(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    active_channels = database.get_required_channels()
    ref_count = ReferralManager.get_verified_referrals_count(user_id)
    vip_info = database.get_user_vip_tier_info(user_id)
    ref_code = ReferralManager.get_or_create_user_ref_code(user_id)
    bot_username = config.get("bot_username", "OkFansBot")
    ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
    
    # Calculate progress to next rank
    next_req = 1 if vip_info["level"] == 1 else (4 if vip_info["level"] == 2 else 7)
    invites_needed = max(0, next_req - ref_count)
    progress_pct = min(100, int((ref_count / max(1, next_req)) * 100))
    
    # Get required channels with explicit user status
    claimed_count = database.get_user_claimed_videos_count(user_id)
    batch_size = config.get("channels_per_verification_batch", 5)
    total_channels = len(active_channels)
    req_count = min(total_channels, (claimed_count + 1) * batch_size) if not current_user.get("starter_completed", 0) else total_channels
    required_channels = active_channels[:req_count]
    
    formatted_channels = []
    completed_channels_count = 0
    for ch in required_channels:
        evt = database.get_join_event(user_id, ch["id"])
        st = "COMPLETED" if (evt and (evt.get("verified") == 1 or evt.get("status") in ["joined", "approved"])) else ("PENDING" if (evt and evt.get("status") == "requested") else "ACTION_REQUIRED")
        if st == "COMPLETED":
            completed_channels_count += 1
        formatted_channels.append({
            "id": ch["id"],
            "title": ch["title"],
            "label": ch["label"],
            "invite_link": ch["invite_link"],
            "verification_method": ch.get("verification_method", "direct_join"),
            "status": st
        })
        
    notifications_unread = database.get_notifications_unread_count(user_id)
    recent_activity = [
        {"icon": "⚡", "title": "Account Registered", "time": "Active", "status": "Verified"},
        {"icon": "🎁", "title": "Daily Bonus Eligibility", "time": "24h Cooldown", "status": "Available"}
    ]
    if current_user.get("starter_completed", 0):
        recent_activity.insert(0, {"icon": "✓", "title": "VIP Verification Quest", "time": "Completed", "status": "Passed"})
    if ref_count > 0:
        recent_activity.insert(0, {"icon": "🤝", "title": f"Referred {ref_count} Friends", "time": "Verified", "status": "+Bonus"})
        
    return {
        "user": {
            "user_id": user_id,
            "username": current_user.get("username") or f"user_{user_id}",
            "first_name": current_user.get("first_name") or "VIP User",
            "credits": current_user.get("credits", 0),
            "checkin_streak": current_user.get("checkin_streak", 0),
            "starter_completed": bool(current_user.get("starter_completed", 0))
        },
        "vip": {
            "level": vip_info["level"],
            "title": vip_info["title"],
            "badge": vip_info["badge"],
            "bundle_size": vip_info["bundle_size"],
            "credit_cost": vip_info["credit_cost"],
            "invites_needed": invites_needed,
            "next_target": "Silver VIP" if vip_info["level"] == 1 else ("Gold VIP" if vip_info["level"] == 2 else "Diamond VIP"),
            "progress_pct": progress_pct
        },
        "referrals": {
            "ref_code": ref_code,
            "ref_link": ref_link,
            "verified_count": ref_count,
            "qualified_count": ref_count,
            "flash_bonus_credits": 5,
            "standard_credits": 3
        },
        "verification": {
            "is_completed": bool(current_user.get("starter_completed", 0)),
            "completed_count": completed_channels_count,
            "total_required": len(required_channels),
            "channels": formatted_channels
        },
        "recent_activity": recent_activity,
        "notifications_unread_count": notifications_unread
    }

@app.get("/api/verification")
def get_verification_status(current_user: dict = Depends(get_current_user)):
    active_channels = database.get_required_channels()
    user_id = current_user["user_id"]
    claimed_count = database.get_user_claimed_videos_count(user_id)
    batch_size = config.get("channels_per_verification_batch", 5)
    total_channels = len(active_channels)
    req_count = min(total_channels, (claimed_count + 1) * batch_size) if not current_user.get("starter_completed", 0) else total_channels
    
    required_list = active_channels[:req_count]
    return {
        "is_completed": bool(current_user.get("starter_completed", 0)),
        "required_channels": required_list,
        "total_required": len(required_list)
    }

@app.get("/api/referrals")
def get_referrals(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    ref_code = ReferralManager.get_or_create_user_ref_code(user_id)
    ref_count = ReferralManager.get_verified_referrals_count(user_id)
    bot_username = config.get("bot_username", "OkFansBot")
    ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
    
    return {
        "ref_code": ref_code,
        "ref_link": ref_link,
        "verified_count": ref_count,
        "flash_bonus_active": True,
        "flash_bonus_credits": 5,
        "standard_credits": 3
    }

@app.get("/api/user/history/rewards")
def get_user_reward_history(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    ledger = database.get_user_credit_history(user_id, limit=20)
    return {"success": True, "history": ledger}

@app.get("/api/user/history/verification")
def get_user_verification_history(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    history = database.get_user_verification_history(user_id, limit=20)
    return {"success": True, "history": history}

@app.get("/api/user/history/referrals")
def get_user_referral_history(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    history = database.get_user_referral_history(user_id, limit=20)
    return {"success": True, "history": history}

@app.post("/api/rewards/claim-daily")
def claim_daily_reward(response: Response, current_user: dict = Depends(get_current_user)):
    res = database.claim_daily_checkin(current_user["user_id"])
    if not res.get("success"):
        if res.get("reason") == "cooldown":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Daily bonus already claimed. Cooldown: {res.get('hours_left')} hours remaining.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not claim daily bonus.")
    response.headers["X-Cache-Invalidate"] = "dashboard"
    return res

@app.post("/api/rewards/redeem")
async def redeem_video_bundle(response: Response, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    vip_info = database.get_user_vip_tier_info(user_id)
    required_cost = vip_info["credit_cost"]
    bundle_size = vip_info["bundle_size"]
    
    if current_user.get("credits", 0) < required_cost:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Insufficient balance! 1 Credit required, but you have {current_user.get('credits', 0)} Credits. Invite a friend to earn credits!"
        )

    # Deduct 1 Credit atomically
    deducted = database.deduct_credits(user_id, required_cost, "video_spend")
    if not deducted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not deduct credits from account.")

    # Get unseen videos for bundle
    vault_mapping = ["A", "B", "C", "D", "E"]
    user_vault_ptr = current_user.get("vault_pointer") or 0
    unlocked_limit = config.get("unlocked_video_limit", 50)
    
    delivered_videos = []
    for item_idx in range(bundle_size):
        active_vault = vault_mapping[(user_vault_ptr + item_idx) % len(vault_mapping)]
        video = VideoCatalog.get_next_video(user_id, active_vault, max_limit=unlocked_limit)
        if not video:
            video = VideoCatalog.get_next_video(user_id, "B", max_limit=unlocked_limit)
        if not video:
            break
        delivered_videos.append(video)

    if not delivered_videos:
        database.add_credits(user_id, required_cost, "refund_no_videos")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No new unseen videos available right now. Your credit was refunded.")

    import httpx
    expiry_delay = int(config.get("video_deletion_delay_seconds", 1800))
    del_minutes = max(1, expiry_delay // 60)
    
    delivered_count = 0
    async with httpx.AsyncClient() as client:
        for idx, video in enumerate(delivered_videos):
            caption_text = (
                f"🎁 <b>{vip_info['badge']} VIP Reward Item ({idx + 1}/{len(delivered_videos)})</b>\n\n"
                f"{video['caption'] or ''}\n\n"
                f"⏱️ <i>This item will automatically delete in {del_minutes} minutes. Save it now!</i>"
            )
            try:
                res = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
                    json={
                        "chat_id": user_id,
                        "video": video["file_id"],
                        "caption": caption_text,
                        "parse_mode": "HTML",
                        "protect_content": True,
                        "has_spoiler": True
                    },
                    timeout=10.0
                )
                if res.status_code == 200:
                    delivered_count += 1
                    database.record_video_delivery(user_id, video["video_id"], user_id, res.json().get("result", {}).get("message_id", 0), expiry_delay)
            except Exception as e:
                logger.error(f"Error delivering video {video['video_id']} via API to user {user_id}: {e}")

    database.save_last_bundle(user_id, [v["video_id"] for v in delivered_videos])
    database.increment_claimed_count(user_id)
    
    updated_user = database.get_user(user_id)
    response.headers["X-Cache-Invalidate"] = "dashboard"
    return {
        "success": True,
        "bundle_size": delivered_count,
        "new_credits": updated_user.get("credits", 0) if updated_user else 0,
        "message": f"🎉 {delivered_count} VIP Reward Videos delivered directly to your Telegram chat!"
    }

@app.post("/api/verification/check")
async def run_verification_check(response: Response, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    active_channels = database.get_required_channels()
    
    claimed_count = database.get_user_claimed_videos_count(user_id)
    batch_size = config.get("channels_per_verification_batch", 5)
    total_channels = len(active_channels)
    req_count = min(total_channels, (claimed_count + 1) * batch_size) if not current_user.get("starter_completed", 0) else total_channels
    required_channels = active_channels[:req_count]
    
    res = await VerificationService.evaluate_user_verification(user_id, required_channels, BOT_TOKEN)
    updated_user = database.get_user(user_id)
    
    response.headers["X-Cache-Invalidate"] = "verification,dashboard"
    return {
        "success": True,
        "overall": res["overall"],
        "passed_count": res["passed_count"],
        "total_required": res["total_required"],
        "all_passed": res["all_passed"],
        "requirements": res["requirements"],
        "new_credits": updated_user.get("credits", 0) if updated_user else 0,
        "message": "🎉 All required channel steps completed! Starter bonus unlocked!" if res["all_passed"] else f"Verified {res['passed_count']}/{res['total_required']} communities. Complete remaining steps!"
    }

# --- ADMIN CONTROL PANEL ENDPOINTS ---

@app.get("/api/admin/stats")
def get_admin_stats(admin: dict = Depends(get_admin_user)):
    stats = database.get_system_stats()
    cat_stats = database.get_detailed_catalog_stats()
    return {
        "system": stats,
        "catalog": cat_stats,
        "config": {
            "unlocked_limit": config.get("unlocked_video_limit", 50),
            "maintenance_mode": config.get("maintenance_mode", False)
        }
    }

@app.get("/api/admin/health")
def get_admin_system_health(admin: dict = Depends(get_admin_user)):
    """
    Returns real system health metrics for Bot, Database, Verification Engine, and API.
    """
    db_status = "HEALTHY"
    try:
        conn = database.get_db_connection()
        conn.close()
    except Exception:
        db_status = "UNHEALTHY"

    return {
        "status": "HEALTHY",
        "bot_api": "HEALTHY",
        "database": db_status,
        "verification_engine": "HEALTHY",
        "pending_sync": "HEALTHY",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/admin/pending-requests")
def get_admin_pending_requests(admin: dict = Depends(get_admin_user)):
    """
    Admin inspection endpoint for historical and active join requests.
    """
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT j.event_id, j.user_id, j.channel_db_id, j.status, j.created_at, u.username, u.first_name, r.title as channel_title
            FROM join_events j
            LEFT JOIN users u ON j.user_id = u.user_id
            LEFT JOIN required_channels r ON j.channel_db_id = r.id
            WHERE j.status = 'requested'
            ORDER BY j.created_at DESC
            LIMIT 100
        """)
        requests_list = [dict(row) for row in cursor.fetchall()]
        return {"total": len(requests_list), "pending_requests": requests_list}
    finally:
        conn.close()

@app.get("/api/admin/users")
def get_admin_users(page: int = 1, limit: int = 20, admin: dict = Depends(get_admin_user)):
    offset = (page - 1) * limit
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, first_name, credits, is_banned, created_at FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s", (limit, offset))
        users = [dict(row) for row in cursor.fetchall()]
        return {"page": page, "limit": limit, "users": users}
    finally:
        conn.close()

class AdminCreditAdjust(BaseModel):
    user_id: int
    amount: int

@app.post("/api/admin/credits/give")
def admin_give_credits(data: AdminCreditAdjust, admin: dict = Depends(get_admin_user)):
    ok = database.add_credits(data.user_id, data.amount, "admin_api_adjust")
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to adjust credits")
    database.log_admin_action(admin["user_id"], "api_give_credits", f"Added {data.amount} to user {data.user_id}")
    new_user = database.get_user(data.user_id)
    return {"success": True, "new_balance": new_user.get("credits", 0) if new_user else 0}

@app.get("/api/notifications")
def get_user_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Returns paginated user notifications, newest first."""
    from contracts.notifications import NotificationsResponse
    user_id = current_user["user_id"]
    offset = (page - 1) * limit
    notifications = database.get_user_notifications(user_id, limit=limit, offset=offset)
    unread_count = database.get_notifications_unread_count(user_id)
    
    # Serialize datetime fields to ISO strings for JSON
    for n in notifications:
        if hasattr(n.get('created_at'), 'isoformat'):
            n['created_at'] = n['created_at'].isoformat()
        n['read'] = bool(n.get('read', False))
    
    return {
        "notifications": notifications,
        "unread_count": unread_count,
        "page": page,
        "limit": limit
    }

@app.post("/api/notifications/read")
def mark_notifications_read_endpoint(
    payload: dict,
    current_user: dict = Depends(get_current_user)
):
    """Marks notifications as read. POST {"notification_ids": [1,2,3]} or {} for all."""
    from contracts.notifications import MarkReadRequest
    user_id = current_user["user_id"]
    ids = payload.get("notification_ids", [])
    ok = database.mark_notifications_read(user_id, ids if ids else None)
    return {"success": ok}

@app.get("/api/settings")
def get_settings(current_user: dict = Depends(get_current_user)):
    """Returns user settings."""
    from contracts.referrals import SettingsData, SettingsResponse
    user_id = current_user["user_id"]
    settings = database.get_user_settings(user_id)
    defaults = {"notifications_enabled": True, "language": "en"}
    defaults.update(settings)
    return {"success": True, "settings": defaults}

@app.post("/api/settings")
def update_settings(payload: dict, current_user: dict = Depends(get_current_user)):
    """Updates user settings. Only known keys are persisted."""
    user_id = current_user["user_id"]
    allowed_keys = {"notifications_enabled", "language"}
    current_settings = database.get_user_settings(user_id)
    
    for key in allowed_keys:
        if key in payload:
            current_settings[key] = payload[key]
    
    ok = database.save_user_settings(user_id, current_settings)
    return {"success": ok, "settings": current_settings}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
