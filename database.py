import sqlite3
import os
import logging
from datetime import datetime

DB_FILE = "okfans_bot.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    logging.info("Initializing database...")
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        referred_by INTEGER REFERENCES users(user_id),
        verified_channels_count INTEGER DEFAULT 0,
        credits INTEGER DEFAULT 0,
        vault_pointer INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        last_menu_message_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Required Channels Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS required_channels (
        channel_id INTEGER PRIMARY KEY,
        label TEXT NOT NULL,
        title TEXT NOT NULL,
        invite_link TEXT NOT NULL,
        channel_type TEXT CHECK(channel_type IN ('starter', 'referral', 'bonus', 'hidden', 'inactive')) DEFAULT 'starter',
        verification_method TEXT CHECK(verification_method IN ('join_request', 'direct_join')) DEFAULT 'direct_join',
        is_active INTEGER DEFAULT 1,
        priority INTEGER DEFAULT 0
    );
    """)

    # 3. Join Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS join_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(user_id),
        channel_id INTEGER NOT NULL REFERENCES required_channels(channel_id),
        status TEXT CHECK(status IN ('requested', 'joined', 'left')) DEFAULT 'requested',
        verified INTEGER DEFAULT 0 CHECK(verified IN (0, 1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, channel_id)
    );
    """)

    # 4. Referrals Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referrals (
        referred_user_id INTEGER PRIMARY KEY REFERENCES users(user_id),
        inviter_user_id INTEGER NOT NULL REFERENCES users(user_id),
        status TEXT CHECK(status IN ('pending', 'verified')) DEFAULT 'pending',
        credited INTEGER DEFAULT 0 CHECK(credited IN (0, 1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5. Videos Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        video_id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE NOT NULL,
        caption TEXT,
        vault TEXT CHECK(vault IN ('A', 'B', 'C', 'D', 'E')) DEFAULT 'B',
        idx INTEGER NOT NULL,
        is_active INTEGER DEFAULT 1 CHECK(is_active IN (0, 1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 6. Video Deliveries Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS video_deliveries (
        delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(user_id),
        video_id INTEGER NOT NULL REFERENCES videos(video_id),
        chat_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expiry_at TIMESTAMP NOT NULL,
        status TEXT CHECK(status IN ('delivered', 'deleted')) DEFAULT 'delivered'
    );
    """)

    # 7. Credit Ledger Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS credit_ledger (
        ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(user_id),
        amount INTEGER NOT NULL,
        reason TEXT CHECK(reason IN ('starter_bonus', 'referral_bonus', 'video_spend', 'admin_adjust')) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 8. Admin Audit Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_audit_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 9. Bot Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        user_id INTEGER,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()
    logging.info("Database initialized successfully.")

# --- USER MANAGEMENT ---

def register_user(user_id: int, username: str, first_name: str, referred_by: int = None) -> dict:
    """
    Atomically registers a user if not exists.
    If referred_by is provided, logs a pending referral.
    Returns user info dict and boolean whether user is new.
    """
    conn = get_db_connection()
    is_new = False
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                is_new = True
                # Self-referral protection check
                valid_referrer = None
                if referred_by and referred_by != user_id:
                    # Verify referrer exists
                    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (referred_by,))
                    ref_exists = cursor.fetchone()
                    if ref_exists:
                        valid_referrer = referred_by
                    else:
                        logging.warning(f"Referrer {referred_by} does not exist in DB.")
                
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name, referred_by)
                    VALUES (?, ?, ?, ?)
                """, (user_id, username, first_name, valid_referrer))
                
                if valid_referrer:
                    cursor.execute("""
                        INSERT OR IGNORE INTO referrals (referred_user_id, inviter_user_id, status, credited)
                        VALUES (?, ?, 'pending', 0)
                    """, (user_id, valid_referrer))
                    logging.info(f"Logged pending referral: User {user_id} referred by {valid_referrer}")

            # Re-fetch user details
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            return dict(user), is_new
    except Exception as e:
        logging.error(f"Error in register_user for {user_id}: {e}")
        return None, False
    finally:
        conn.close()

def get_user(user_id: int) -> dict:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        return dict(user) if user else None
    except Exception as e:
        logging.error(f"Error in get_user {user_id}: {e}")
        return None
    finally:
        conn.close()

def set_ban_status(user_id: int, is_banned: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (is_banned, user_id))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error in set_ban_status {user_id}: {e}")
        return False
    finally:
        conn.close()

def update_last_menu_message(user_id: int, message_id: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET last_menu_message_id = ? WHERE user_id = ?", (message_id, user_id))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error in update_last_menu_message for user {user_id}: {e}")
        return False
    finally:
        conn.close()

def get_last_menu_message(user_id: int) -> int:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT last_menu_message_id FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row['last_menu_message_id'] if row else None
    except Exception as e:
        logging.error(f"Error in get_last_menu_message for user {user_id}: {e}")
        return None
    finally:
        conn.close()

# --- BALANCE & CREDIT MANAGEMENT ---

def add_credits(user_id: int, amount: int, reason: str) -> bool:
    """
    Transaction-safe credit addition/deduction with audit ledger entry.
    """
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            # 1. Update credits
            cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
            if cursor.rowcount == 0:
                return False
            # 2. Log to ledger
            cursor.execute("""
                INSERT INTO credit_ledger (user_id, amount, reason)
                VALUES (?, ?, ?)
            """, (user_id, amount, reason))
            return True
    except Exception as e:
        logging.error(f"Error in add_credits for user {user_id}: {e}")
        return False
    finally:
        conn.close()

# --- CHANNEL GATE MANAGEMENT ---

def get_required_channels(only_active=True) -> list:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if only_active:
            cursor.execute("SELECT * FROM required_channels WHERE is_active = 1 ORDER BY priority ASC")
        else:
            cursor.execute("SELECT * FROM required_channels ORDER BY priority ASC")
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"Error in get_required_channels: {e}")
        return []
    finally:
        conn.close()

def save_required_channel(channel_id: int, label: str, title: str, invite_link: str, channel_type: str, verification_method: str, is_active: int = 1, priority: int = 0) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO required_channels (channel_id, label, title, invite_link, channel_type, verification_method, is_active, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (channel_id, label, title, invite_link, channel_type, verification_method, is_active, priority))
            return True
    except Exception as e:
        logging.error(f"Error in save_required_channel {channel_id}: {e}")
        return False
    finally:
        conn.close()

def delete_required_channel(channel_id: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM required_channels WHERE channel_id = ?", (channel_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error in delete_required_channel {channel_id}: {e}")
        return False
    finally:
        conn.close()

# --- JOIN EVENTS & VERIFICATION ---

def record_join_event(user_id: int, channel_id: int, status: str) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO join_events (user_id, channel_id, status, verified)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(user_id, channel_id) DO UPDATE SET
                    status = excluded.status
            """, (user_id, channel_id, status))
            return True
    except Exception as e:
        logging.error(f"Error recording join event for user {user_id}, channel {channel_id}: {e}")
        return False
    finally:
        conn.close()

def get_join_event(user_id: int, channel_id: int) -> dict:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM join_events WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logging.error(f"Error fetching join event: {e}")
        return None
    finally:
        conn.close()

def verify_join(user_id: int, channel_id: int) -> bool:
    """
    Marks a channel join event as verified.
    Returns True if it transitioned from unverified to verified.
    """
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            # Check current verification status
            cursor.execute("SELECT verified FROM join_events WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
            row = cursor.fetchone()
            if row and row['verified'] == 1:
                return False  # Already verified before

            cursor.execute("""
                INSERT INTO join_events (user_id, channel_id, status, verified)
                VALUES (?, ?, 'joined', 1)
                ON CONFLICT(user_id, channel_id) DO UPDATE SET
                    status = 'joined',
                    verified = 1
            """, (user_id, channel_id))
            
            # Increment user's verified channels count
            cursor.execute("UPDATE users SET verified_channels_count = verified_channels_count + 1 WHERE user_id = ?", (user_id,))
            return True
    except Exception as e:
        logging.error(f"Error in verify_join: {e}")
        return False
    finally:
        conn.close()

# --- REFERRAL LOGIC ---

def add_referral_credits_if_eligible(referred_user_id: int, referral_credits: int) -> tuple:
    """
    Validates if referred_user_id has a pending referral.
    If yes, and it gets verified, updates the inviter balance and logs to ledger.
    Returns (inviter_user_id, updated_inviter_credits) if credited, else (None, 0).
    """
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            # 1. Fetch pending referral
            cursor.execute("""
                SELECT inviter_user_id, status, credited FROM referrals 
                WHERE referred_user_id = ?
            """, (referred_user_id,))
            ref = cursor.fetchone()
            if not ref:
                return None, 0
            
            if ref['status'] == 'verified' or ref['credited'] == 1:
                return None, 0 # Already processed

            inviter_id = ref['inviter_user_id']
            
            # 2. Update referral state to verified & credited
            cursor.execute("""
                UPDATE referrals 
                SET status = 'verified', credited = 1 
                WHERE referred_user_id = ?
            """, (referred_user_id,))
            
            # 3. Add credits to the inviter
            cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (referral_credits, inviter_id))
            
            # 4. Insert credit ledger audit entry
            cursor.execute("""
                INSERT INTO credit_ledger (user_id, amount, reason)
                VALUES (?, ?, 'referral_bonus')
            """, (inviter_id, referral_credits))

            # Fetch updated inviter credits
            cursor.execute("SELECT credits FROM users WHERE user_id = ?", (inviter_id,))
            inviter_user = cursor.fetchone()
            new_credits = inviter_user['credits'] if inviter_user else 0
            
            logging.info(f"Referral successfully verified! Credited {referral_credits} to inviter {inviter_id} for user {referred_user_id}")
            return inviter_id, new_credits
    except Exception as e:
        logging.error(f"Error processing referral verification for {referred_user_id}: {e}")
        return None, 0
    finally:
        conn.close()

# --- REWARD VIDEO MANAGEMENT ---

def add_video(file_id: str, caption: str, vault: str) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            # 1. Get max idx for this vault
            cursor.execute("SELECT COALESCE(MAX(idx), 0) as max_idx FROM videos WHERE vault = ?", (vault,))
            row = cursor.fetchone()
            max_idx = row['max_idx']
            # 2. Insert new video
            cursor.execute("""
                INSERT INTO videos (file_id, caption, vault, idx, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (file_id, caption, vault, max_idx + 1))
            return True
    except Exception as e:
        logging.error(f"Error adding video {file_id}: {e}")
        return False
    finally:
        conn.close()

def get_next_reward_video(user_id: int, vault: str) -> dict:
    """
    Implements Vault Pointer deterministic strategy to select a video.
    Retrieves the list of active videos in the vault ordered by idx.
    Chooses the video using: pointer % count.
    Increments user's vault pointer by 1.
    All executed atomically in a transaction.
    """
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            # 1. Fetch user's vault pointer
            cursor.execute("SELECT vault_pointer FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                return None
            pointer = user['vault_pointer']

            # 2. Fetch active videos in the vault
            cursor.execute("""
                SELECT * FROM videos 
                WHERE vault = ? AND is_active = 1 
                ORDER BY idx ASC
            """, (vault,))
            videos = [dict(row) for row in cursor.fetchall()]
            if not videos:
                return None

            # 3. Deterministic selection
            selected_video = videos[pointer % len(videos)]

            # 4. Increment pointer
            cursor.execute("UPDATE users SET vault_pointer = vault_pointer + 1 WHERE user_id = ?", (user_id,))
            
            return selected_video
    except Exception as e:
        logging.error(f"Error selecting reward video for user {user_id}: {e}")
        return None
    finally:
        conn.close()

# --- VIDEO DELIVERIES & AUTO-DELETION ---

def record_video_delivery(user_id: int, video_id: int, chat_id: int, message_id: int, expiry_at: datetime) -> int:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            expiry_str = expiry_at.isoformat()
            cursor.execute("""
                INSERT INTO video_deliveries (user_id, video_id, chat_id, message_id, expiry_at, status)
                VALUES (?, ?, ?, ?, ?, 'delivered')
            """, (user_id, video_id, chat_id, message_id, expiry_str))
            return cursor.lastrowid
    except Exception as e:
        logging.error(f"Error recording video delivery: {e}")
        return None
    finally:
        conn.close()

def get_pending_deletions() -> list:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM video_deliveries WHERE status = 'delivered'")
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"Error fetching pending deletions: {e}")
        return []
    finally:
        conn.close()

def mark_video_deleted(delivery_id: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE video_deliveries SET status = 'deleted' WHERE delivery_id = ?", (delivery_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error marking video as deleted {delivery_id}: {e}")
        return False
    finally:
        conn.close()

# --- LOGGING & AUDIT TRAIL ---

def log_admin_action(admin_id: int, action: str, details: str = None) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO admin_audit_logs (admin_id, action, details)
                VALUES (?, ?, ?)
            """, (admin_id, action, details))
            return True
    except Exception as e:
        logging.error(f"Error logging admin action: {e}")
        return False
    finally:
        conn.close()

def log_bot_event(event_type: str, user_id: int = None, details: str = None) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bot_events (event_type, user_id, details)
                VALUES (?, ?, ?)
            """, (event_type, user_id, details))
            return True
    except Exception as e:
        logging.error(f"Error logging bot event: {e}")
        return False
    finally:
        conn.close()

# --- ANALYTICS / STATS ---

def get_system_stats() -> dict:
    conn = get_db_connection()
    stats = {}
    try:
        cursor = conn.cursor()
        
        # Total Users
        cursor.execute("SELECT COUNT(*) FROM users")
        stats["total_users"] = cursor.fetchone()[0]

        # Active Users (not banned)
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = 0")
        stats["active_users"] = cursor.fetchone()[0]

        # Total Referrals Verified
        cursor.execute("SELECT COUNT(*) FROM referrals WHERE status = 'verified'")
        stats["total_referrals"] = cursor.fetchone()[0]

        # Total Videos Redeemed
        cursor.execute("SELECT COUNT(*) FROM video_deliveries")
        stats["total_redeemed"] = cursor.fetchone()[0]

        # Total Videos Deleted
        cursor.execute("SELECT COUNT(*) FROM video_deliveries WHERE status = 'deleted'")
        stats["total_deleted"] = cursor.fetchone()[0]

        # Total Videos in Vaults
        cursor.execute("SELECT vault, COUNT(*) FROM videos GROUP BY vault")
        stats["vault_counts"] = {row[0]: row[1] for row in cursor.fetchall()}

        return stats
    except Exception as e:
        logging.error(f"Error collecting stats: {e}")
        return {}
    finally:
        conn.close()
