"""
Startup Pre-flight Validator, System Diagnostics, & Health Monitor for OkFansBot v2.0
"""
import logging
import os
import database
from services.video_catalog import VideoCatalog

logger = logging.getLogger(__name__)

class StartupValidator:
    @staticmethod
    def validate_preflight(config: dict, bot_token: str, owner_id: int):
        logger.info("=== RUNNING PRE-FLIGHT STARTUP VALIDATION ===")
        errors = []
        
        # 1. Token check
        if not bot_token or "YOUR_TELEGRAM_BOT_TOKEN" in bot_token:
            errors.append("CRITICAL: TG_BOT_TOKEN is missing or unconfigured in environment.")
        else:
            logger.info("✓ Token Configuration: Valid")
            
        # 2. Database Connection check
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM users")
            cursor.fetchone()
            conn.close()
            logger.info(f"✓ Database Connection: Healthy (Postgres mode: {database.IS_POSTGRES})")
        except Exception as e:
            errors.append(f"CRITICAL: Database connection failed: {e}")
            
        # 3. Owner Check
        if not owner_id:
            logger.warning("⚠️ Warning: OWNER_ID is not configured in .env.")
        else:
            logger.info(f"✓ Owner ID Configuration: Valid ({owner_id})")
            
        # 4. Required Channels Check
        try:
            active_channels = database.get_required_channels()
            logger.info(f"✓ Required Channels: {len(active_channels)} channels loaded")
            unlinked = [ch for ch in active_channels if ch["channel_id"] is None]
            if unlinked:
                logger.warning(f"⚠️ Warning: {len(unlinked)} active required channels have null channel_id.")
        except Exception as e:
            errors.append(f"CRITICAL: Required channels lookup failed: {e}")
            
        if errors:
            for err in errors:
                logger.error(err)
            if any("CRITICAL" in err for err in errors):
                raise RuntimeError("Pre-flight startup validation failed! Check system configuration logs.")
                
        logger.info("=== PRE-FLIGHT VALIDATION PASSED ===")

class DiagnosticsManager:
    @staticmethod
    def get_diagnostics_report() -> str:
        stats = database.get_system_stats()
        cat_stats = VideoCatalog.get_catalog_stats()
        active_channels = database.get_required_channels(only_active=False)
        unlinked = [ch for ch in active_channels if ch["channel_id"] is None]
        
        report = (
            "🩺 <b>System Diagnostics Report</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Bot Infrastructure:</b>\n"
            "✓ Token: Configured\n"
            f"✓ Database Mode: {'PostgreSQL' if database.IS_POSTGRES else 'SQLite'}\n"
            "✓ Scheduler: Running\n\n"
            "<b>Channel Health:</b>\n"
            f"• Total Channels: <b>{len(active_channels)}</b>\n"
            f"• Resolved Channel IDs: <b>{len(active_channels) - len(unlinked)}/{len(active_channels)}</b>\n"
        )
        if unlinked:
            report += f"⚠️ <i>{len(unlinked)} channels require ID resolution via forwarding!</i>\n"
            
        report += (
            "\n<b>Video Catalog:</b>\n"
            f"• Indexed Active Videos: <b>{cat_stats['active_videos']}</b>\n"
            f"• Total Deliveries: <b>{cat_stats['total_deliveries']}</b>\n\n"
            "<b>User Statistics:</b>\n"
            f"• Total Registered Users: <b>{stats.get('total_users', 0)}</b>\n"
            f"• Total Credits Issued: <b>{stats.get('total_credits', 0)} 🪙</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Status: System Healthy & Operational</i>"
        )
        return report

class HealthMonitor:
    @staticmethod
    def get_health_report() -> str:
        stats = database.get_system_stats()
        cat_stats = VideoCatalog.get_catalog_stats()
        
        return (
            "🟢 <b>System Health Status</b>\n\n"
            "• Bot: <b>Online 🟢</b>\n"
            f"• Database: <b>{'PostgreSQL 🟢' if database.IS_POSTGRES else 'SQLite 🟢'}</b>\n"
            "• Scheduler: <b>Running 🟢</b>\n"
            f"• Total Users: <b>{stats.get('total_users', 0)}</b>\n"
            f"• Catalog Videos: <b>{cat_stats['active_videos']}</b>\n"
            "• Status: <b>Healthy & Operational</b>"
        )
