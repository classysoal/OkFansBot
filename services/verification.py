"""
Verification Engine, State Machine, and Audit Logging for OkFansBot v2.0
"""
import logging
import database

logger = logging.getLogger(__name__)

class StateMachine:
    NEW = "NEW"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    VERIFIED = "VERIFIED"
    REWARD_ELIGIBLE = "REWARD_ELIGIBLE"
    BANNED = "BANNED"

class ChannelVerifier:
    @staticmethod
    async def verify_channel(user_id: int, channel: dict, bot) -> dict:
        db_id = channel["id"]
        cid = channel["channel_id"]
        label = channel["label"]
        v_method = channel.get("verification_method", "direct_join")
        
        is_passed = False
        reason = "Not joined"
        
        # 1. Check DB join events first
        evt = database.get_join_event(user_id, db_id)
        if evt and (evt.get("verified") == 1 or evt.get("status") in ["requested", "joined", "approved"]):
            is_passed = True
            reason = f"Join event verified ({evt.get('status', 'requested')})"

        # 2. If channel_id is known, check via Telegram API
        if cid:
            try:
                member = await bot.get_chat_member(chat_id=cid, user_id=user_id)
                if member.status in ["creator", "administrator", "member", "restricted"]:
                    if not evt or evt.get("status") != "joined":
                        database.record_join_event(user_id, db_id, "joined")
                    is_passed = True
                    reason = f"Verified via Telegram API (status: {member.status})"
                elif member.status in ["left", "kicked"]:
                    if evt and evt.get("status") in ["requested", "approved"]:
                        is_passed = True
                        reason = "Pending join request verified in queue"
                    else:
                        is_passed = False
                        reason = f"User left or kicked (status: {member.status})"
                        if evt and evt.get("verified") == 1:
                            database.mark_join_left(user_id, db_id)
            except Exception as e:
                logger.debug(f"API membership check failed for user {user_id} in channel {cid}: {e}")
                if evt and (evt.get("verified") == 1 or evt.get("status") in ["requested", "joined"]):
                    is_passed = True
                    reason = "Verified via database join record fallback"
        else:
            if not is_passed:
                if v_method == "request_join" or (evt and evt.get("status") == "requested"):
                    is_passed = True
                    reason = "Request-to-join channel verified"
                else:
                    logger.warning(f"Required channel '{label}' (DB ID: {db_id}) has no resolved channel_id.")

        # 3. Record verification in DB if passed
        if is_passed:
            database.verify_join(user_id, db_id)
            
        return {
            "db_id": db_id,
            "label": label,
            "passed": is_passed,
            "reason": reason
        }

class AuditLogger:
    @staticmethod
    def log_result(user_id: int, channel_db_id: int, result: str, reason: str = None):
        try:
            database.log_verification_attempt(user_id, channel_db_id, result, reason)
        except Exception as e:
            logger.error(f"Failed to log verification audit for user {user_id}: {e}")

class VerificationManager:
    @staticmethod
    async def process_verification(user_id: int, active_channels: list, bot) -> tuple[list, int, int, list]:
        """
        Runs independent channel verifications for all required channels.
        Returns:
          - results: list of dicts with {"db_id", "label", "passed", "reason"}
          - passed_count: number of channels passed
          - required_count: total channels required
          - still_missing: list of channel dicts that failed
        """
        user = database.get_user(user_id)
        claimed_count = database.get_user_claimed_videos_count(user_id)
        batch_size = 5  # default 5 per batch
        total_channels = len(active_channels)
        required_count = min(total_channels, (claimed_count + 1) * batch_size) if not user.get("starter_completed", 0) else total_channels
        
        required_channels = active_channels[:required_count]
        
        results = []
        still_missing = []
        passed_count = 0
        
        for ch in required_channels:
            res = await ChannelVerifier.verify_channel(user_id, ch, bot)
            results.append(res)
            AuditLogger.log_result(user_id, ch["id"], "PASS" if res["passed"] else "FAIL", res["reason"])
            
            if res["passed"]:
                passed_count += 1
            else:
                still_missing.append(ch)
                
        # Update State Machine
        if passed_count == len(required_channels):
            database.mark_starter_completed(user_id)
            database.update_verification_state(user_id, StateMachine.VERIFIED)
        elif passed_count > 0:
            database.update_verification_state(user_id, StateMachine.PARTIALLY_VERIFIED)
        else:
            database.update_verification_state(user_id, StateMachine.PENDING_VERIFICATION)
            
        return results, passed_count, len(required_channels), still_missing
