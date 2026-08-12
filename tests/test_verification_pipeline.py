"""
Automated Test Suite for OkFansBot v2.0
Validates Verification Service State Machine, Live Overrides, Bypass Prevention,
Session Management, Single Identity Upsert, and Credit Idempotency.
"""
import unittest
import asyncio
import os
import random
import database
from services.verification import VerificationService, TelegramStatus, ApplicationResult

class TestVerificationPipeline(unittest.TestCase):
    def setUp(self):
        database.init_db()

    def test_single_identity_upsert(self):
        """Phase 4 & 51: Single Identity Mapping - Username change must NOT duplicate user."""
        test_tg_id = random.randint(100000000, 999999999)
        user1, is_new1 = database.upsert_user_by_telegram_id(test_tg_id, username="old_username", first_name="John")
        self.assertEqual(user1["user_id"], test_tg_id)
        self.assertTrue(is_new1)

        user2, is_new2 = database.upsert_user_by_telegram_id(test_tg_id, username="new_username", first_name="John Updated")
        self.assertEqual(user2["user_id"], test_tg_id)
        self.assertFalse(is_new2)
        self.assertEqual(user2["username"], "new_username")

    def test_session_lifecycle(self):
        """Phase 11 & 35: Secure Session Creation, Retrieval, and Revocation."""
        test_user_id = random.randint(100000000, 999999999)
        database.upsert_user_by_telegram_id(test_user_id, "session_tester", "Session Tester")

        session = database.create_user_session(test_user_id, auth_method="MINI_APP")
        self.assertIsNotNone(session["session_token"])

        user = database.get_user_by_session(session["session_token"])
        self.assertIsNotNone(user)
        self.assertEqual(user["user_id"], test_user_id)

        revoked = database.revoke_user_session(session["session_token"])
        self.assertTrue(revoked)

        user_after = database.get_user_by_session(session["session_token"])
        self.assertIsNone(user_after)

    def test_credit_deduction_idempotency(self):
        """Phase 20: Credit deduction must be atomic and fail if balance is insufficient."""
        test_user_id = random.randint(100000000, 999999999)
        database.upsert_user_by_telegram_id(test_user_id, "credit_tester", "Tester")
        database.add_credits(test_user_id, 2, "test_deposit")

        success1 = database.deduct_credits(test_user_id, 1, "test_spend_1")
        self.assertTrue(success1)

        success2 = database.deduct_credits(test_user_id, 1, "test_spend_2")
        self.assertTrue(success2)

        success3 = database.deduct_credits(test_user_id, 1, "test_spend_3")
        self.assertFalse(success3)

    def test_verification_policy_pending_request(self):
        """Phase 6 & 7: REQUEST_PENDING satisfies application policy (PASS)."""
        test_user_id = random.randint(100000000, 999999999)
        database.upsert_user_by_telegram_id(test_user_id, "pending_tester", "Tester")
        
        link = f"https://t.me/+testlink_{random.randint(100, 999)}"
        database.save_required_channel(None, "TEST_LABEL", "Test Channel", link, "starter", "join_request", 1, 1)
        channels = database.get_required_channels()
        test_ch = channels[0]

        database.record_join_event(test_user_id, test_ch["id"], "requested")

        res = asyncio.run(VerificationService.check_user_community(test_user_id, test_ch))
        self.assertEqual(res["telegram_status"], TelegramStatus.REQUEST_PENDING)
        self.assertEqual(res["application_result"], ApplicationResult.PASS)

    def test_verification_bypass_prevention_left_user(self):
        """Phase 5: User joined previously, but left. Live status LEFT must evaluate to FAIL."""
        test_user_id = random.randint(100000000, 999999999)
        database.upsert_user_by_telegram_id(test_user_id, "left_tester", "Tester")
        
        link = f"https://t.me/+testlink_{random.randint(10000, 99999)}"
        database.save_required_channel(None, "TEST_LEFT_LABEL", "Test Channel Left", link, "starter", "direct_join", 1, 1)
        channels = database.get_required_channels()
        test_ch = [c for c in channels if c["invite_link"] == link][0]

        database.record_join_event(test_user_id, test_ch["id"], "joined")
        database.mark_join_left(test_user_id, test_ch["id"])

        res = asyncio.run(VerificationService.check_user_community(test_user_id, test_ch))
        self.assertEqual(res["application_result"], ApplicationResult.FAIL)

if __name__ == "__main__":
    unittest.main()
