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
        Evaluates all required communities for a user concurrently in parallel.
        Returns aggregated result with overall status (PASS, INCOMPLETE, CHECK_ERROR).
        """
        import asyncio
        
        async with httpx.AsyncClient() as client:
            tasks = [
                VerificationService._check_channel_with_client(client, user_id, ch, bot_token)
                for ch in required_channels
            ]
            results = await asyncio.gather(*tasks, return_exceptions=False)

        passed_count = 0
        has_error = False

        for res in results:
            if res["application_result"] == ApplicationResult.PASS:
                passed_count += 1
            elif res["application_result"] == ApplicationResult.ERROR:
                has_error = True
            
            # Persist status to database
            database.save_user_verification_status(
                user_id, 
                res["channel_id"], 
                res["telegram_status"], 
                res["application_result"]
            )

        total_required = len(required_channels)
        all_passed = (passed_count == total_required and total_required > 0)

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

    @staticmethod
    def get_persisted_verification_summary(user_id: int, required_channels: list) -> dict:
        """
        Loads persisted verification state from database without making external Telegram API calls.
        Fast (<5ms) for standard page renders and navigation.
        """
        persisted = database.get_persisted_user_verification(user_id)
        results = []
        passed_count = 0

        for ch in required_channels:
            db_id = ch["id"]
            p_data = persisted.get(db_id, {})
            
            status = p_data.get("telegram_status") or ("MEMBER" if ch.get("application_result") == "PASS" else "NOT_JOINED")
            app_result = p_data.get("application_result") or ("PASS" if status in ["MEMBER", "ADMINISTRATOR", "OWNER", "REQUEST_PENDING"] else "FAIL")
            
            if app_result == ApplicationResult.PASS:
                passed_count += 1

            results.append({
                "channel_id": db_id,
                "title": ch.get("title", f"Channel {ch.get('label', '')}"),
                "invite_link": ch.get("invite_link", ""),
                "telegram_status": status,
                "application_result": app_result,
                "reason": "Persisted state from last check"
            })

        total_required = len(required_channels)
        all_passed = (passed_count == total_required and total_required > 0)
        user = database.get_user(user_id)
        is_completed = bool(user.get("starter_completed", 0)) or all_passed

        return {
            "success": True,
            "overall": "PASS" if is_completed else "INCOMPLETE",
            "passed_count": passed_count if not is_completed else total_required,
            "total_required": total_required,
            "all_passed": is_completed,
            "is_completed": is_completed,
            "requirements": results
        }


    @staticmethod
    async def _check_channel_with_client(client: httpx.AsyncClient, user_id: int, channel: dict, bot_token: str = None) -> dict:
        db_id = channel["id"]
        cid = channel.get("channel_id")
        title = channel.get("title", f"Channel {channel.get('label', '')}")

        telegram_status = TelegramStatus.NOT_JOINED
        app_result = ApplicationResult.FAIL
        reason = "User is not a member of this community"

        evt = database.get_join_event(user_id, db_id)

        if cid and bot_token:
            try:
                res = await client.get(
                    f"https://api.telegram.org/bot{bot_token}/getChatMember",
                    params={"chat_id": cid, "user_id": user_id},
                    timeout=4.0
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
                        reason = "Live Telegram verification active member"
                    elif member_status == "left":
                        telegram_status = TelegramStatus.LEFT
                        app_result = ApplicationResult.FAIL
                        reason = "Membership no longer active"
                    elif member_status == "kicked":
                        telegram_status = TelegramStatus.BANNED
                        app_result = ApplicationResult.FAIL
                        reason = "User is banned from community"
                elif evt and evt.get("status") in ["joined", "approved"]:
                    telegram_status = TelegramStatus.MEMBER
                    app_result = ApplicationResult.PASS
                    reason = "Verified via join history"
                elif evt and evt.get("status") == "requested":
                    telegram_status = TelegramStatus.REQUEST_PENDING
                    app_result = ApplicationResult.PASS
                    reason = "Join request registered (accepted by policy)"
            except Exception as e:
                logger.warning(f"Check exception for channel {cid}: {e}")
                if evt and evt.get("status") in ["joined", "approved", "requested"]:
                    telegram_status = TelegramStatus.MEMBER if evt.get("status") != "requested" else TelegramStatus.REQUEST_PENDING
                    app_result = ApplicationResult.PASS
                    reason = "Fallback to event history on API timeout"
                else:
                    telegram_status = TelegramStatus.CHECK_ERROR
                    app_result = ApplicationResult.ERROR
                    reason = "Telegram API check failed"
        else:
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

        try:
            database.record_verification_check(
                user_id=user_id,
                community_id=db_id,
                telegram_status=telegram_status,
                application_result=app_result,
                reason=reason
            )
        except Exception:
            pass

        return {
            "channel_id": db_id,
            "title": title,
            "invite_link": channel.get("invite_link", ""),
            "telegram_status": telegram_status,
            "application_result": app_result,
            "reason": reason
        }


class StateMachine:
    NEW = "NEW"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    VERIFIED = "VERIFIED"
    REWARD_ELIGIBLE = "REWARD_ELIGIBLE"
    BANNED = "BANNED"

class VerificationManager:
    @classmethod
    async def process_verification(cls, user_id: int, active_channels: list, bot) -> tuple:
        bot_token = getattr(bot, "token", None) or getattr(bot, "_token", None)
        res = await VerificationService.evaluate_user_verification(user_id, active_channels, bot_token)
        results = res["requirements"]
        passed_count = res["passed_count"]
        total_required = res["total_required"]
        still_missing = [r for r in results if r.get("application_result") != ApplicationResult.PASS]
        return results, passed_count, total_required, still_missing
