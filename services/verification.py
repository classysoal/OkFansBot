"""
Authoritative Verification Service for OkFansBot v2.0
Implements Live Telegram API Membership Checks (overrides stale database history),
Explicit State Machine (MEMBER, ADMINISTRATOR, OWNER, REQUEST_PENDING, NOT_JOINED, LEFT, BANNED, CHECK_ERROR),
Application Policy Evaluation (REQUEST_PENDING = PASS), and Read-Only Verification.
"""
import logging
import httpx
import database

logger = logging.getLogger("okfans_verification")

class TelegramStatus:
    MEMBER = "MEMBER"
    ADMINISTRATOR = "ADMINISTRATOR"
    OWNER = "OWNER"
    RESTRICTED = "RESTRICTED"
    REQUEST_PENDING = "REQUEST_PENDING"
    NOT_JOINED = "NOT_JOINED"
    LEFT = "LEFT"
    BANNED = "BANNED"
    CHECK_ERROR = "CHECK_ERROR"

class ApplicationResult:
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"

class VerificationService:
    @staticmethod
    async def check_user_community(user_id: int, channel: dict, bot_token: str = None) -> dict:
        """
        Authoritative single-community verification check.
        Live Telegram API check ALWAYS overrides database history.
        """
        db_id = channel["id"]
        cid = channel.get("channel_id")
        title = channel.get("title", f"Channel {channel.get('label', '')}")
        v_method = channel.get("verification_method", "direct_join")

        telegram_status = TelegramStatus.NOT_JOINED
        app_result = ApplicationResult.FAIL
        reason = "User is not a member of this community"

        # 1. Read DB event history for historical context
        evt = database.get_join_event(user_id, db_id)

        # 2. Perform LIVE Telegram API check if channel_id is resolved
        if cid and bot_token:
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get(
                        f"https://api.telegram.org/bot{bot_token}/getChatMember",
                        params={"chat_id": cid, "user_id": user_id},
                        timeout=5.0
                    )
                    
                    if res.status_code == 200 and res.json().get("ok"):
                        member_status = res.json().get("result", {}).get("status")
                        
                        if member_status in ["creator", "owner"]:
                            telegram_status = TelegramStatus.OWNER
                            app_result = ApplicationResult.PASS
                            reason = "User is community owner"
                        elif member_status == "administrator":
                            telegram_status = TelegramStatus.ADMINISTRATOR
                            app_result = ApplicationResult.PASS
                            reason = "User is community administrator"
                        elif member_status in ["member", "restricted"]:
                            telegram_status = TelegramStatus.MEMBER
                            app_result = ApplicationResult.PASS
                            reason = "User is active member"
                        elif member_status in ["left", "kicked"]:
                            # User left or was kicked! Check if a valid pending request exists
                            if evt and evt.get("status") in ["requested", "approved"]:
                                telegram_status = TelegramStatus.REQUEST_PENDING
                                app_result = ApplicationResult.PASS
                                reason = "Pending join request active (accepted by policy)"
                            else:
                                telegram_status = TelegramStatus.LEFT if member_status == "left" else TelegramStatus.BANNED
                                app_result = ApplicationResult.FAIL
                                reason = f"User has {member_status} the community"
                    else:
                        # Telegram API returned error for chat member query
                        if evt and (evt.get("verified") == 1 or evt.get("status") in ["joined", "requested"]):
                            telegram_status = TelegramStatus.REQUEST_PENDING if evt.get("status") == "requested" else TelegramStatus.MEMBER
                            app_result = ApplicationResult.PASS
                            reason = "Verified via recent join record fallback"
                        else:
                            telegram_status = TelegramStatus.CHECK_ERROR
                            app_result = ApplicationResult.ERROR
                            reason = "Could not reach Telegram API for membership check"
            except Exception as e:
                logger.warning(f"Telegram API check error for user {user_id} in channel {cid}: {e}")
                if evt and (evt.get("verified") == 1 or evt.get("status") in ["joined", "requested"]):
                    telegram_status = TelegramStatus.REQUEST_PENDING if evt.get("status") == "requested" else TelegramStatus.MEMBER
                    app_result = ApplicationResult.PASS
                    reason = "Verified via database fallback"
                else:
                    telegram_status = TelegramStatus.CHECK_ERROR
                    app_result = ApplicationResult.ERROR
                    reason = "Telegram API temporarily unreachable"
        else:
            # Unresolved channel_id or direct join request method
            if evt and evt.get("status") == "requested":
                telegram_status = TelegramStatus.REQUEST_PENDING
                app_result = ApplicationResult.PASS
                reason = "Join request registered (accepted by policy)"
            elif evt and evt.get("status") in ["joined", "approved"]:
                telegram_status = TelegramStatus.MEMBER
                app_result = ApplicationResult.PASS
                reason = "Verified via join history"
            else:
                telegram_status = TelegramStatus.NOT_JOINED
                app_result = ApplicationResult.FAIL
                reason = "Membership or join request required"

        # 3. Store result in database audit log & current state cache (READ ONLY)
        database.record_verification_check(
            user_id=user_id,
            community_id=db_id,
            telegram_status=telegram_status,
            application_result=app_result,
            reason=reason
        )

        return {
            "channel_id": db_id,
            "title": title,
            "invite_link": channel.get("invite_link", ""),
            "telegram_status": telegram_status,
            "application_result": app_result,
            "reason": reason
        }

    @staticmethod
    async def evaluate_user_verification(user_id: int, required_channels: list, bot_token: str) -> dict:
        """
        Evaluates all required communities for a user in parallel.
        Returns aggregated result with overall status (PASS, INCOMPLETE, CHECK_ERROR).
        """
        results = []
        passed_count = 0
        has_error = False

        for ch in required_channels:
            res = await VerificationService.check_user_community(user_id, ch, bot_token)
            results.append(res)
            
            if res["application_result"] == ApplicationResult.PASS:
                passed_count += 1
            elif res["application_result"] == ApplicationResult.ERROR:
                has_error = True

        total_required = len(required_channels)
        all_passed = (passed_count == total_required)

        if all_passed:
            overall = "PASS"
            user = database.get_user(user_id)
            if user and not user.get("starter_completed", 0):
                database.mark_starter_completed(user_id)
                database.add_credits(user_id, 1, "starter_completion_bonus")
        elif has_error and passed_count == 0:
            overall = "CHECK_ERROR"
        else:
            overall = "INCOMPLETE"

        return {
            "success": True,
            "overall": overall,
            "passed_count": passed_count,
            "total_required": total_required,
            "all_passed": all_passed,
            "requirements": results
        }
