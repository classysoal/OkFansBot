"""
Reward Distribution and Ledger Service for OkFansBot v2.0
"""
import logging
import database

logger = logging.getLogger(__name__)

class RewardCalculator:
    STARTER_BONUS_CREDITS = 1
    REFERRAL_CREDITS = 3

class RewardManager:
    @staticmethod
    def grant_starter_reward(user_id: int) -> bool:
        """
        Grants the 1-time starter bonus credit if not already granted.
        """
        conn = database.get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM credit_ledger WHERE user_id = %s AND reason = 'starter_bonus'", (user_id,))
            row = cursor.fetchone()
            if row and row["count"] > 0:
                return False  # Already granted
                
            database.add_credits(user_id, RewardCalculator.STARTER_BONUS_CREDITS, "starter_bonus")
            logger.info(f"Granted starter bonus credit to user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error checking/granting starter reward for {user_id}: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def process_referral_reward(referred_user_id: int) -> tuple[int, int]:
        """
        Grants referral credits to the inviter if the invitee is eligible.
        Returns: (inviter_id, inviter_new_credits)
        """
        return database.add_referral_credits_if_eligible(
            referred_user_id=referred_user_id,
            referral_credits=RewardCalculator.REFERRAL_CREDITS
        )
