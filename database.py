import sqlite3
import os
import logging
from datetime import datetime, timedelta, timezone
try:
    import dotenv
except ImportError:
    dotenv = None

if dotenv:
    dotenv.load_dotenv()

DB_FILE = "okfans_bot.db"

# Detect database configuration
DATABASE_URL = os.getenv("DATABASE_URL").strip() if os.getenv("DATABASE_URL") else None
IS_POSTGRES = bool(DATABASE_URL)

# --- DATABASE WRAPPERS FOR SQLITE COMPATIBILITY ---

class SQLiteCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def __enter__(self):
        self.cursor.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.__exit__(exc_type, exc_val, exc_tb)

    def execute(self, query, params=None):
        # Translate Postgres placeholder '%s' to SQLite placeholder '?'
        query = query.replace("%s", "?")
        if params is not None:
            return self.cursor.execute(query, params)
        return self.cursor.execute(query)

    def executemany(self, query, seq_of_params):
        query = query.replace("%s", "?")
        return self.cursor.executemany(query, seq_of_params)

class SQLiteConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn

    def __getattr__(self, name):
        return getattr(self.conn, name)

    def cursor(self):
        return SQLiteCursorWrapper(self.conn.cursor())

    def __enter__(self):
        self.conn.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.conn.__exit__(exc_type, exc_val, exc_tb)

# --- CONNECTION MANAGEMENT ---

def get_db_connection():
    if DATABASE_URL:
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=10)
            return conn
        except Exception as e:
            logging.warning(f"⚠️ PostgreSQL connection temporary issue: {e}. Using local SQLite fallback for this query.")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return SQLiteConnectionWrapper(conn)

def init_db():
    logging.info(f"Initializing database (Postgres mode: {IS_POSTGRES})...")
    conn = get_db_connection()
    cursor = conn.cursor()

    if IS_POSTGRES:
        # Postgres Schema
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username VARCHAR(255),
            first_name VARCHAR(255),
            referred_by BIGINT REFERENCES users(user_id),
            verified_channels_count INT DEFAULT 0,
            credits INT DEFAULT 0,
            vault_pointer INT DEFAULT 0,
            is_banned INT DEFAULT 0,
            last_menu_message_id BIGINT,
            starter_completed INT DEFAULT 0,
            last_verification TIMESTAMP,
            verification_state VARCHAR(50) DEFAULT 'NEW',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Column migration for existing PostgreSQL users table
        for col_def in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS starter_completed INT DEFAULT 0;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_verification TIMESTAMP;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_state VARCHAR(50) DEFAULT 'NEW';",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS ref_code VARCHAR(100) UNIQUE;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_checkin TIMESTAMP;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS checkin_streak INT DEFAULT 0;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS vip_level INT DEFAULT 1;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_rewards_claimed INT DEFAULT 0;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_bundle_data TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_bundle_resends INT DEFAULT 0;"
        ]:
            try:
                cursor.execute(col_def)
            except Exception:
                pass

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS required_channels (
            id SERIAL PRIMARY KEY,
            channel_id BIGINT UNIQUE,
            label VARCHAR(255) NOT NULL,
            title VARCHAR(255) NOT NULL,
            invite_link VARCHAR(255) UNIQUE NOT NULL,
            channel_type VARCHAR(50) DEFAULT 'starter',
            verification_method VARCHAR(50) DEFAULT 'direct_join',
            is_active INT DEFAULT 1,
            priority INT DEFAULT 0
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_video_history (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            video_id INT NOT NULL REFERENCES videos(video_id),
            delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, video_id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS join_events (
            event_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            channel_db_id INT NOT NULL REFERENCES required_channels(id),
            status VARCHAR(50) DEFAULT 'requested',
            verified INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, channel_db_id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS verification_logs (
            log_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            channel_db_id INT NOT NULL REFERENCES required_channels(id),
            result VARCHAR(50) NOT NULL,
            reason TEXT,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referred_user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
            inviter_user_id BIGINT NOT NULL REFERENCES users(user_id),
            status VARCHAR(50) DEFAULT 'pending',
            credited INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            video_id SERIAL PRIMARY KEY,
            file_id VARCHAR(255) UNIQUE NOT NULL,
            caption TEXT,
            vault VARCHAR(50) DEFAULT 'B',
            idx INT NOT NULL,
            is_active INT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_deliveries (
            delivery_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            video_id INT NOT NULL REFERENCES videos(video_id),
            chat_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expiry_at VARCHAR(100) NOT NULL,
            status VARCHAR(50) DEFAULT 'delivered'
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_ledger (
            ledger_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            amount INT NOT NULL,
            reason VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit_logs (
            log_id SERIAL PRIMARY KEY,
            admin_id BIGINT NOT NULL,
            action VARCHAR(255) NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_events (
            event_id SERIAL PRIMARY KEY,
            event_type VARCHAR(255) NOT NULL,
            user_id BIGINT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id VARCHAR(255) PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            revoked INT DEFAULT 0
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_devices (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            user_agent TEXT,
            platform VARCHAR(100),
            ip_address VARCHAR(100),
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            risk_state VARCHAR(50) DEFAULT 'NORMAL'
        );
        """)
    else:
        # SQLite Schema
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            ref_code TEXT,
            referred_by INTEGER REFERENCES users(user_id),
            verified_channels_count INTEGER DEFAULT 0,
            credits INTEGER DEFAULT 0,
            vault_pointer INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            last_menu_message_id INTEGER,
            starter_completed INTEGER DEFAULT 0,
            last_verification TIMESTAMP,
            verification_state TEXT DEFAULT 'NEW',
            last_checkin TIMESTAMP,
            checkin_streak INTEGER DEFAULT 0,
            vip_level INTEGER DEFAULT 1,
            total_rewards_claimed INTEGER DEFAULT 0,
            last_bundle_data TEXT,
            last_bundle_resends INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        for col_def in [
            "ALTER TABLE users ADD COLUMN starter_completed INTEGER DEFAULT 0;",
            "ALTER TABLE users ADD COLUMN last_verification TIMESTAMP;",
            "ALTER TABLE users ADD COLUMN verification_state TEXT DEFAULT 'NEW';",
            "ALTER TABLE users ADD COLUMN ref_code TEXT;",
            "ALTER TABLE users ADD COLUMN last_checkin TIMESTAMP;",
            "ALTER TABLE users ADD COLUMN checkin_streak INTEGER DEFAULT 0;",
            "ALTER TABLE users ADD COLUMN vip_level INTEGER DEFAULT 1;",
            "ALTER TABLE users ADD COLUMN total_rewards_claimed INTEGER DEFAULT 0;",
            "ALTER TABLE users ADD COLUMN last_bundle_data TEXT;",
            "ALTER TABLE users ADD COLUMN last_bundle_resends INTEGER DEFAULT 0;"
        ]:
            try:
                cursor.execute(col_def)
            except Exception:
                pass

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_video_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            video_id INTEGER NOT NULL REFERENCES videos(video_id),
            delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, video_id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS verification_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            channel_db_id INTEGER NOT NULL REFERENCES required_channels(id),
            result TEXT NOT NULL,
            reason TEXT,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS required_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id BIGINT UNIQUE,
            label TEXT NOT NULL,
            title TEXT NOT NULL,
            invite_link TEXT UNIQUE NOT NULL,
            channel_type TEXT CHECK(channel_type IN ('starter', 'referral', 'bonus', 'hidden', 'inactive')) DEFAULT 'starter',
            verification_method TEXT CHECK(verification_method IN ('join_request', 'direct_join')) DEFAULT 'direct_join',
            is_active INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 0
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS join_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            channel_db_id INTEGER NOT NULL REFERENCES required_channels(id),
            status TEXT CHECK(status IN ('requested', 'joined', 'left')) DEFAULT 'requested',
            verified INTEGER DEFAULT 0 CHECK(verified IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, channel_db_id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referred_user_id INTEGER PRIMARY KEY REFERENCES users(user_id),
            inviter_user_id INTEGER NOT NULL REFERENCES users(user_id),
            status TEXT CHECK(status IN ('pending', 'verified')) DEFAULT 'pending',
            credited INTEGER DEFAULT 0 CHECK(credited IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

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

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_ledger (
            ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            revoked INTEGER DEFAULT 0
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            user_agent TEXT,
            platform TEXT,
            ip_address TEXT,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            risk_state TEXT DEFAULT 'NORMAL'
        );
        """)

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

def register_user(user_id: int, username: str, first_name: str, referred_by: int = None) -> tuple:
    conn = get_db_connection()
    is_new = False
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                is_new = True
                valid_referrer = None
                if referred_by and referred_by != user_id:
                    cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (referred_by,))
                    ref_exists = cursor.fetchone()
                    if ref_exists:
                        valid_referrer = referred_by
                    else:
                        logging.warning(f"Referrer {referred_by} does not exist in DB.")
                
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name, referred_by)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, username, first_name, valid_referrer))
                
                if valid_referrer:
                    cursor.execute("""
                        INSERT INTO referrals (referred_user_id, inviter_user_id, status, credited)
                        VALUES (%s, %s, 'pending', 0)
                        ON CONFLICT (referred_user_id) DO NOTHING
                    """, (user_id, valid_referrer))
                    logging.info(f"Logged pending referral: User {user_id} referred by {valid_referrer}")
            else:
                if user['username'] != username or user['first_name'] != first_name:
                    cursor.execute("UPDATE users SET username = %s, first_name = %s WHERE user_id = %s", (username, first_name, user_id))

            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            return dict(user) if user else None, is_new
    except Exception as e:
        logging.error(f"Error in register_user for {user_id}: {e}")
        return None, False
    finally:
        conn.close()

def get_user(user_id: int) -> dict:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        return dict(user) if user else None
    except Exception as e:
        logging.error(f"Error in get_user {user_id}: {e}")
        return None
    finally:
        conn.close()

def get_user_by_ref_code(ref_code: str) -> dict:
    if not ref_code:
        return None
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE ref_code = %s", (ref_code,))
        user = cursor.fetchone()
        return dict(user) if user else None
    except Exception as e:
        logging.error(f"Error in get_user_by_ref_code {ref_code}: {e}")
        return None
    finally:
        conn.close()

def get_user_by_username(username: str) -> dict:
    if not username:
        return None
    clean_un = username.lstrip("@").strip()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(%s)", (clean_un,))
        user = cursor.fetchone()
        return dict(user) if user else None
    except Exception as e:
        logging.error(f"Error in get_user_by_username {clean_un}: {e}")
        return None
    finally:
        conn.close()

def set_user_ref_code(user_id: int, ref_code: str) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET ref_code = %s WHERE user_id = %s", (ref_code, user_id))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error setting ref_code for user {user_id}: {e}")
        return False
    finally:
        conn.close()

def claim_daily_checkin(user_id: int) -> dict:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT credits, last_checkin, checkin_streak FROM users WHERE user_id = %s", (user_id,))
            user_row = cursor.fetchone()
            if not user_row:
                return {"success": False, "reason": "user_not_found"}
            user = dict(user_row)
                
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            last_dt = user.get("last_checkin")
            if isinstance(last_dt, str):
                try:
                    last_dt = datetime.fromisoformat(last_dt)
                except Exception:
                    last_dt = None
            if last_dt and last_dt.tzinfo is not None:
                last_dt = last_dt.replace(tzinfo=None)
                
            if last_dt:
                diff_sec = (now - last_dt).total_seconds()
                if diff_sec < 86400:
                    hours_remaining = max(1, int((86400 - diff_sec) // 3600))
                    return {"success": False, "reason": "cooldown", "hours_left": hours_remaining}
                    
            new_streak = (user.get("checkin_streak") or 0) + 1
            now_str = now.isoformat()
            
            cursor.execute("""
                UPDATE users 
                SET credits = credits + 1, last_checkin = %s, checkin_streak = %s 
                WHERE user_id = %s
            """, (now_str, new_streak, user_id))
            
            cursor.execute("SELECT credits FROM users WHERE user_id = %s", (user_id,))
            updated_user = cursor.fetchone()
            new_credits = updated_user['credits'] if updated_user else user['credits'] + 1
            return {"success": True, "credits": new_credits, "streak": new_streak}
    except Exception as e:
        logging.error(f"Error in claim_daily_checkin for user {user_id}: {e}")
        return {"success": False, "reason": "error"}
    finally:
        conn.close()

def get_user_vip_tier_info(user_id: int) -> dict:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM referrals WHERE inviter_user_id = %s AND status = 'verified'", (user_id,))
        row = cursor.fetchone()
        ref_count = row['count'] if row else 0
        
        if ref_count >= 7:
            return {
                "level": 4,
                "title": "💎 Diamond VIP Tier",
                "badge": "💎",
                "bundle_size": 15,
                "credit_cost": 1,
                "next_requirement": "🔥 Maximum VIP Rank Achieved!"
            }
        elif ref_count >= 4:
            return {
                "level": 3,
                "title": "👑 Gold VIP Tier",
                "badge": "👑",
                "bundle_size": 10,
                "credit_cost": 1,
                "next_requirement": f"Invite {7 - ref_count} more friend(s) to unlock 💎 Diamond VIP (15 Videos per 1 Credit)!"
            }
        elif ref_count >= 1:
            return {
                "level": 2,
                "title": "🔥 Silver VIP Tier",
                "badge": "🔥",
                "bundle_size": 7,
                "credit_cost": 1,
                "next_requirement": f"Invite {4 - ref_count} more friend(s) to unlock 👑 Gold VIP (10 Videos per 1 Credit)!"
            }
        else:
            return {
                "level": 1,
                "title": "🌟 Novice VIP Tier",
                "badge": "🌟",
                "bundle_size": 5,
                "credit_cost": 1,
                "next_requirement": "Invite 1 friend to unlock 🔥 Silver VIP (7 Videos per 1 Credit)!"
            }
    except Exception as e:
        logging.error(f"Error in get_user_vip_tier_info {user_id}: {e}")
        return {
            "level": 1,
            "title": "🌟 Novice VIP Tier",
            "badge": "🌟",
            "bundle_size": 5,
            "credit_cost": 1,
            "next_requirement": "Invite 1 friend to unlock 🔥 Silver VIP (7 Videos/bundle)!"
        }
    finally:
        conn.close()

import json

def save_user_last_bundle(user_id: int, video_list: list) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            data_str = json.dumps(video_list)
            cursor.execute("""
                UPDATE users 
                SET last_bundle_data = %s, last_bundle_resends = 0, total_rewards_claimed = total_rewards_claimed + 1
                WHERE user_id = %s
            """, (data_str, user_id))
            return True
    except Exception as e:
        logging.error(f"Error saving last bundle for user {user_id}: {e}")
        return False
    finally:
        conn.close()

def get_user_last_bundle(user_id: int) -> dict:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT last_bundle_data, last_bundle_resends FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        if not user or not user.get("last_bundle_data"):
            return None
        videos = json.loads(user["last_bundle_data"])
        return {
            "videos": videos,
            "resends_used": user.get("last_bundle_resends") or 0
        }
    except Exception as e:
        logging.error(f"Error getting last bundle for user {user_id}: {e}")
        return None
    finally:
        conn.close()

def increment_user_bundle_resend(user_id: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET last_bundle_resends = last_bundle_resends + 1 WHERE user_id = %s", (user_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error incrementing bundle resend for user {user_id}: {e}")
        return False
    finally:
        conn.close()

def get_all_user_ids() -> list:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
        rows = cursor.fetchall()
        return [r["user_id"] if isinstance(r, dict) else r[0] for r in rows]
    except Exception as e:
        logging.error(f"Error in get_all_user_ids: {e}")
        return []
    finally:
        conn.close()

def get_detailed_catalog_stats() -> dict:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT vault, COUNT(*) as cnt FROM videos WHERE is_active = 1 GROUP BY vault")
        rows = cursor.fetchall()
        vault_counts = {}
        total = 0
        for r in rows:
            v = r["vault"] if isinstance(r, dict) else r[0]
            c = r["cnt"] if isinstance(r, dict) else r[1]
            vault_counts[v] = c
            total += c
        return {"total": total, "vaults": vault_counts}
    except Exception as e:
        logging.error(f"Error in get_detailed_catalog_stats: {e}")
        return {"total": 0, "vaults": {}}
    finally:
        conn.close()

def set_ban_status(user_id: int, is_banned: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = %s WHERE user_id = %s", (is_banned, user_id))
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
            cursor.execute("UPDATE users SET last_menu_message_id = %s WHERE user_id = %s", (message_id, user_id))
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
        cursor.execute("SELECT last_menu_message_id FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        return row['last_menu_message_id'] if row else None
    except Exception as e:
        logging.error(f"Error in get_last_menu_message for user {user_id}: {e}")
        return None
    finally:
        conn.close()

# --- BALANCE & CREDIT MANAGEMENT ---

def add_credits(user_id: int, amount: int, reason: str) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET credits = credits + %s WHERE user_id = %s", (amount, user_id))
            if cursor.rowcount == 0:
                return False
            cursor.execute("""
                INSERT INTO credit_ledger (user_id, amount, reason)
                VALUES (%s, %s, %s)
            """, (user_id, amount, reason))
            return True
    except Exception as e:
        logging.error(f"Error in add_credits for user {user_id}: {e}")
        return False
    finally:
        conn.close()

def deduct_credits(user_id: int, amount: int, reason: str = "video_spend") -> bool:
    if amount <= 0:
        return False

    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET credits = credits - %s
                WHERE user_id = %s AND credits >= %s
            """, (amount, user_id, amount))
            if cursor.rowcount == 0:
                return False
            cursor.execute("""
                INSERT INTO credit_ledger (user_id, amount, reason)
                VALUES (%s, %s, %s)
            """, (user_id, -amount, reason))
            return True
    except Exception as e:
        logging.error(f"Error in deduct_credits for user {user_id}: {e}")
        return False
    finally:
        conn.close()

def increment_vault_pointer(user_id: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET vault_pointer = vault_pointer + 1 WHERE user_id = %s", (user_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error in increment_vault_pointer for user {user_id}: {e}")
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
                INSERT INTO required_channels (channel_id, label, title, invite_link, channel_type, verification_method, is_active, priority)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (invite_link) DO UPDATE SET
                    channel_id = COALESCE(excluded.channel_id, required_channels.channel_id),
                    label = excluded.label,
                    title = excluded.title,
                    channel_type = excluded.channel_type,
                    verification_method = excluded.verification_method,
                    is_active = excluded.is_active,
                    priority = excluded.priority
            """, (channel_id, label, title, invite_link, channel_type, verification_method, is_active, priority))
            return True
    except Exception as e:
        logging.error(f"Error in save_required_channel: {e}")
        return False
    finally:
        conn.close()

def resolve_channel_id_by_invite(invite_link: str, channel_id: int) -> int:
    """
    Looks up a channel by invite_link.
    If its channel_id is currently NULL or different, updates it to the real channel_id.
    Returns the database primary key `id` of the channel.
    """
    if not invite_link:
        return None
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            clean_link = invite_link.strip()
            
            link_hash = clean_link
            if "+" in clean_link:
                link_hash = clean_link.split("+")[-1]
            elif "joinchat/" in clean_link:
                link_hash = clean_link.split("joinchat/")[-1]

            cursor.execute("SELECT id, channel_id FROM required_channels WHERE invite_link = %s", (clean_link,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("SELECT id, channel_id FROM required_channels WHERE invite_link LIKE %s", (f"%{link_hash}%",))
                row = cursor.fetchone()
                
            if row:
                db_id = row['id']
                existing_cid = row['channel_id']
                if existing_cid is None or existing_cid != channel_id:
                    cursor.execute("UPDATE required_channels SET channel_id = %s WHERE id = %s", (channel_id, db_id))
                    logging.info(f"Dynamically resolved channel ID for {invite_link} to {channel_id}")
                return db_id
            return None
    except Exception as e:
        logging.error(f"Error in resolve_channel_id_by_invite for {invite_link}: {e}")
        return None
    finally:
        conn.close()

def delete_required_channel(channel_id: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM required_channels WHERE channel_id = %s", (channel_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error in delete_required_channel {channel_id}: {e}")
        return False
    finally:
        conn.close()

# --- JOIN EVENTS & VERIFICATION ---

def record_join_event(user_id: int, channel_db_id: int, status: str) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO join_events (user_id, channel_db_id, status, verified)
                VALUES (%s, %s, %s, 0)
                ON CONFLICT(user_id, channel_db_id) DO UPDATE SET
                    status = excluded.status
            """, (user_id, channel_db_id, status))
            return True
    except Exception as e:
        logging.error(f"Error recording join event for user {user_id}, db_id {channel_db_id}: {e}")
        return False
    finally:
        conn.close()

def get_join_event(user_id: int, channel_db_id: int) -> dict:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM join_events WHERE user_id = %s AND channel_db_id = %s", (user_id, channel_db_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logging.error(f"Error fetching join event: {e}")
        return None
    finally:
        conn.close()

def verify_join(user_id: int, channel_db_id: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT verified FROM join_events WHERE user_id = %s AND channel_db_id = %s", (user_id, channel_db_id))
            row = cursor.fetchone()
            if row and row['verified'] == 1:
                return False

            cursor.execute("""
                INSERT INTO join_events (user_id, channel_db_id, status, verified)
                VALUES (%s, %s, 'joined', 1)
                ON CONFLICT(user_id, channel_db_id) DO UPDATE SET
                    status = 'joined',
                    verified = 1
            """, (user_id, channel_db_id))
            
            cursor.execute("UPDATE users SET verified_channels_count = verified_channels_count + 1 WHERE user_id = %s", (user_id,))
            return True
    except Exception as e:
        logging.error(f"Error in verify_join: {e}")
        return False
    finally:
        conn.close()

def record_verification_check(user_id: int, community_id: int, telegram_status: str, application_result: str, reason: str = None) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            if is_postgres_conn(conn):
                cursor.execute("""
                    INSERT INTO verification_logs (user_id, channel_db_id, result, reason)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, community_id, application_result, f"{telegram_status}: {reason or ''}"))
            else:
                cursor.execute("""
                    INSERT INTO verification_logs (user_id, channel_db_id, result, reason)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, community_id, application_result, f"{telegram_status}: {reason or ''}"))
            return True
    except Exception as e:
        logging.error(f"Error recording verification check log: {e}")
        return False
    finally:
        conn.close()

# --- REFERRAL LOGIC ---

def add_referral_credits_if_eligible(referred_user_id: int, referral_credits: int) -> tuple:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT inviter_user_id, status, credited FROM referrals 
                WHERE referred_user_id = %s
            """, (referred_user_id,))
            ref = cursor.fetchone()
            if not ref:
                return None, 0
            
            if ref['status'] == 'verified' or ref['credited'] == 1:
                return None, 0

            inviter_id = ref['inviter_user_id']
            
            cursor.execute("""
                UPDATE referrals 
                SET status = 'verified', credited = 1 
                WHERE referred_user_id = %s
            """, (referred_user_id,))
            
            cursor.execute("UPDATE users SET credits = credits + %s WHERE user_id = %s", (referral_credits, inviter_id))
            
            cursor.execute("""
                INSERT INTO credit_ledger (user_id, amount, reason)
                VALUES (%s, %s, 'referral_bonus')
            """, (inviter_id, referral_credits))

            cursor.execute("SELECT credits FROM users WHERE user_id = %s", (inviter_id,))
            inviter_user = cursor.fetchone()
            new_credits = inviter_user['credits'] if inviter_user else 0
            
            logging.info(f"Referral successfully verified! Credited {referral_credits} to inviter {inviter_id} for user {referred_user_id}")
            return inviter_id, new_credits
    except Exception as e:
        logging.error(f"Error processing referral verification for {referred_user_id}: {e}")
        return None, 0
    finally:
        conn.close()

def get_verified_referrals_count(user_id: int) -> int:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM referrals WHERE inviter_user_id = %s AND status = 'verified'", (user_id,))
        row = cursor.fetchone()
        return row['count'] if row else 0
    except Exception as e:
        logging.error(f"Error in get_verified_referrals_count: {e}")
        return 0
    finally:
        conn.close()

def mark_join_left(user_id: int, channel_db_id: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT verified FROM join_events WHERE user_id = %s AND channel_db_id = %s", (user_id, channel_db_id))
            row = cursor.fetchone()
            if not row or row['verified'] == 0:
                return False

            cursor.execute("""
                UPDATE join_events 
                SET status = 'left', verified = 0
                WHERE user_id = %s AND channel_db_id = %s
            """, (user_id, channel_db_id))
            
            cursor.execute("""
                UPDATE users 
                SET verified_channels_count = CASE WHEN verified_channels_count > 0 THEN verified_channels_count - 1 ELSE 0 END 
                WHERE user_id = %s
            """, (user_id,))
            return True
    except Exception as e:
        logging.error(f"Error in mark_join_left: {e}")
        return False
    finally:
        conn.close()

# --- REWARD VIDEO MANAGEMENT ---

def add_video(file_id: str, caption: str, vault: str) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            # Auto detection of duplicate videos (same file_id)
            cursor.execute("SELECT 1 FROM videos WHERE file_id = %s", (file_id,))
            if cursor.fetchone():
                logging.info(f"Duplicate video file_id detected, skipping: {file_id[:20]}...")
                return False
                
            cursor.execute("SELECT COALESCE(MAX(idx), 0) as max_idx FROM videos WHERE vault = %s", (vault,))
            row = cursor.fetchone()
            max_idx = row['max_idx'] if row else 0
            cursor.execute("""
                INSERT INTO videos (file_id, caption, vault, idx, is_active)
                VALUES (%s, %s, %s, %s, 1)
            """, (file_id, caption, vault, max_idx + 1))
            return True
    except Exception as e:
        logging.error(f"Error adding video {file_id}: {e}")
        return False
    finally:
        conn.close()

def delete_video(video_id: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM videos WHERE video_id = %s", (video_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error deleting video {video_id}: {e}")
        return False
    finally:
        conn.close()

def list_videos_paginated(offset: int, limit: int) -> list:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos ORDER BY video_id DESC LIMIT %s OFFSET %s", (limit, offset))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"Error listing videos paginated: {e}")
        return []
    finally:
        conn.close()


def get_next_reward_video(user_id: int, vault: str, max_limit: int = None) -> dict:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT vault_pointer FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                return None
            pointer = user['vault_pointer']

            cursor.execute("SELECT * FROM videos WHERE vault = %s AND is_active = 1 ORDER BY video_id ASC", (vault,))
            all_videos = [dict(row) for row in cursor.fetchall()]
            if max_limit and isinstance(max_limit, int) and max_limit > 0:
                all_videos = all_videos[:max_limit]

            if not all_videos:
                return None

            cursor.execute("SELECT video_id FROM user_video_history WHERE user_id = %s", (user_id,))
            seen_rows = cursor.fetchall()
            seen_ids = set([r['video_id'] if isinstance(r, dict) else r[0] for r in seen_rows])

            unseen = [v for v in all_videos if v['video_id'] not in seen_ids]
            
            if unseen:
                selected = unseen[0]
            else:
                selected = all_videos[pointer % len(all_videos)]

            if selected:
                try:
                    if is_postgres_conn(conn):
                        cursor.execute("INSERT INTO user_video_history (user_id, video_id) VALUES (%s, %s) ON CONFLICT (user_id, video_id) DO NOTHING", (user_id, selected['video_id']))
                    else:
                        cursor.execute("INSERT OR IGNORE INTO user_video_history (user_id, video_id) VALUES (%s, %s)", (user_id, selected['video_id']))
                except Exception:
                    pass

            return selected
    except Exception as e:
        logging.error(f"Error selecting reward video for user {user_id}: {e}")
        return None
    finally:
        conn.close()

def is_postgres_conn(conn) -> bool:
    return not isinstance(conn, SQLiteConnectionWrapper)

# --- VIDEO DELIVERIES & AUTO-DELETION ---

def record_video_delivery(user_id: int, video_id: int, chat_id: int, message_id: int, expiry_at: datetime) -> int:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            expiry_str = expiry_at.isoformat() if isinstance(expiry_at, datetime) else str(expiry_at)
            
            if is_postgres_conn(conn):
                cursor.execute("""
                    INSERT INTO video_deliveries (user_id, video_id, chat_id, message_id, expiry_at, status)
                    VALUES (%s, %s, %s, %s, %s, 'delivered') RETURNING delivery_id
                """, (user_id, video_id, chat_id, message_id, expiry_str))
                row = cursor.fetchone()
                return row['delivery_id'] if row else None
            else:
                cursor.execute("""
                    INSERT INTO video_deliveries (user_id, video_id, chat_id, message_id, expiry_at, status)
                    VALUES (%s, %s, %s, %s, %s, 'delivered')
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
            cursor.execute("UPDATE video_deliveries SET status = 'deleted' WHERE delivery_id = %s", (delivery_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error marking video as deleted {delivery_id}: {e}")
        return False
    finally:
        conn.close()

def get_user_claimed_videos_count(user_id: int) -> int:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM video_deliveries WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        return row['count'] if row else 0
    except Exception as e:
        logging.error(f"Error in get_user_claimed_videos_count for {user_id}: {e}")
        return 0
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
                VALUES (%s, %s, %s)
            """, (admin_id, action, details))
            return True
    except Exception as e:
        logging.error(f"Error logging admin action: {e}")
        return False
    finally:
        conn.close()

def update_verification_state(user_id: int, state: str) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET verification_state = %s, last_verification = CURRENT_TIMESTAMP 
                WHERE user_id = %s
            """, (state, user_id))
            return True
    except Exception as e:
        logging.error(f"Error in update_verification_state for user {user_id}: {e}")
        return False
    finally:
        conn.close()

def mark_starter_completed(user_id: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET starter_completed = 1, verification_state = 'VERIFIED', last_verification = CURRENT_TIMESTAMP 
                WHERE user_id = %s
            """, (user_id,))
            return True
    except Exception as e:
        logging.error(f"Error in mark_starter_completed for user {user_id}: {e}")
        return False
    finally:
        conn.close()

def log_verification_attempt(user_id: int, channel_db_id: int, result: str, reason: str = None) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO verification_logs (user_id, channel_db_id, result, reason)
                VALUES (%s, %s, %s, %s)
            """, (user_id, channel_db_id, result, reason))
            return True
    except Exception as e:
        logging.error(f"Error in log_verification_attempt for user {user_id}: {e}")
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
                VALUES (%s, %s, %s)
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
        
        cursor.execute("SELECT COUNT(*) as count FROM users")
        row = cursor.fetchone()
        stats["total_users"] = row['count'] if row else 0

        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_banned = 0")
        row = cursor.fetchone()
        stats["active_users"] = row['count'] if row else 0

        cursor.execute("SELECT COUNT(*) as count FROM referrals WHERE status = 'verified'")
        row = cursor.fetchone()
        stats["total_referrals"] = row['count'] if row else 0

        cursor.execute("SELECT COUNT(*) as count FROM video_deliveries")
        row = cursor.fetchone()
        stats["total_redeemed"] = row['count'] if row else 0

        cursor.execute("SELECT COUNT(*) as count FROM video_deliveries WHERE status = 'deleted'")
        row = cursor.fetchone()
        stats["total_deleted"] = row['count'] if row else 0

        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM credit_ledger WHERE amount > 0")
        row = cursor.fetchone()
        stats["total_credits"] = row['total'] if row else 0

        cursor.execute("SELECT vault, COUNT(*) as count FROM videos GROUP BY vault")
        stats["vault_counts"] = {row['vault']: row['count'] for row in cursor.fetchall()}

        return stats
    except Exception as e:
        logging.error(f"Error collecting stats: {e}")
        return {}
    finally:
        conn.close()
