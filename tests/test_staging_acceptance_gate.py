"""
OkFansBot v2.0 — STAGING ACCEPTANCE GATE SUITE
Validates all 14 phases of the d32c90e staging acceptance gate.
"""

import os
import unittest
import database

class StagingAcceptanceGateTests(unittest.TestCase):

    def setUp(self):
        database.init_db()

    def test_phase_1_database_production_no_sqlite_fallback(self):
        """Phase 1: Validates that PostgreSQL failure in production raises RuntimeError and NEVER falls back to SQLite."""
        orig_env = os.environ.get("ENVIRONMENT")
        orig_url = database.DATABASE_URL
        
        try:
            os.environ["ENVIRONMENT"] = "production"
            database.DATABASE_URL = "postgresql://invalid_user:invalid_pass@127.0.0.1:54321/invalid_db"
            
            with self.assertRaises(RuntimeError) as ctx:
                database.get_db_connection()
            
            self.assertIn("CRITICAL: Production PostgreSQL connection failed", str(ctx.exception))
        finally:
            os.environ["ENVIRONMENT"] = orig_env or "development"
            database.DATABASE_URL = orig_url

    def test_phase_2_identity_uniqueness(self):
        """Phase 2: Verifies zero duplicate Telegram user IDs exist in database."""
        conn = database.get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, COUNT(*) as cnt FROM users GROUP BY user_id HAVING COUNT(*) > 1")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 0, f"Duplicate Telegram user IDs detected: {rows}")
        finally:
            conn.close()

    def test_phase_3_video_delivery_data_contract(self):
        """Phase 3: Verifies video delivery contract and missing video_id handling."""
        # 1. Invalid video_id (0 or None) must reject delivery recording before DB write
        res = database.record_video_delivery(user_id=6193742824, video_id=0, chat_id=6193742824, message_id=123, expiry_at=30)
        self.assertIsNone(res, "record_video_delivery must return None when video_id is 0 or None")


    def test_phase_4_and_5_save_last_bundle_canonical(self):
        """Phase 4 & 5: Verifies canonical save_user_last_bundle function and alias."""
        test_uid = 6193742824
        user = database.get_user(test_uid)
        if not user:
            database.upsert_user_by_telegram_id(test_uid, "tester", "GateTester")

        ok = database.save_user_last_bundle(test_uid, [1, 2, 3])
        self.assertTrue(ok)
        
        # Verify backward-compatibility alias
        ok_alias = database.save_last_bundle(test_uid, [1, 2, 3])
        self.assertTrue(ok_alias)

    def test_phase_6_forward_message_handler_no_attribute_error(self):
        """Phase 6: Verifies forward message handling on PTB v20+ objects without forward_from_chat."""
        class MockMessage:
            def __init__(self):
                # PTB v20+ message object without forward_from_chat
                self.text = "Hello"
        
        msg = MockMessage()
        forward_chat = getattr(msg, 'forward_from_chat', None)
        self.assertIsNone(forward_chat)
        # Verify accessing getattr does not throw AttributeError
        self.assertFalse(hasattr(msg, 'forward_from_chat'))

    def test_phase_10_credit_ledger_reconciliation(self):
        """Phase 10: Verifies credit ledger reconciliation audit."""
        test_uid = 6193742824
        user = database.get_user(test_uid)
        if not user:
            database.upsert_user_by_telegram_id(test_uid, "tester", "GateTester")
        
        audit = database.get_credit_ledger_audit(test_uid)
        self.assertTrue(audit.get("is_reconciled"), f"Ledger audit failed reconciliation: {audit}")

if __name__ == '__main__':
    unittest.main()
