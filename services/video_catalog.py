"""
Video Catalog Service for OkFansBot v2.0
"""
import asyncio
import logging
import database

logger = logging.getLogger(__name__)

SYNC_CANCELLED = False

class VideoCatalog:
    @staticmethod
    def stop_sync():
        global SYNC_CANCELLED
        SYNC_CANCELLED = True
        logger.info("Video sync cancellation requested by admin.")
    @staticmethod
    def get_next_video(user_id: int, vault: str = "B", max_limit: int = None) -> dict:
        return database.get_next_reward_video(user_id, vault, max_limit)

    @staticmethod
    def mark_delivered(user_id: int, video_id: int, chat_id: int, message_id: int, expiry_at) -> int:
        return database.record_video_delivery(user_id, video_id, chat_id, message_id, expiry_at)

    @staticmethod
    def mark_expired(delivery_id: int) -> bool:
        return database.mark_video_deleted(delivery_id)

    @staticmethod
    def get_catalog_stats() -> dict:
        conn = database.get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM videos WHERE is_active = 1")
            total_active = cursor.fetchone()["total"]
            
            cursor.execute("SELECT COUNT(*) as delivered FROM video_deliveries")
            total_delivered = cursor.fetchone()["delivered"]
            
            return {
                "active_videos": total_active,
                "total_deliveries": total_delivered
            }
        except Exception as e:
            logger.error(f"Error fetching video catalog stats: {e}")
            return {"active_videos": 0, "total_deliveries": 0}
        finally:
            conn.close()

    @staticmethod
    async def sync_database_channel(bot, channel_id: int, start_id: int, end_id: int, vault: str = "B", target_chat_id: int = None, copy_to_channel_id: int = None) -> int:
        global SYNC_CANCELLED
        SYNC_CANCELLED = False
        
        if not target_chat_id:
            target_chat_id = channel_id
            
        imported_count = 0
        duplicates_count = 0
        logger.info(f"Starting VideoCatalog sync from {channel_id} range {start_id}-{end_id}...")
        
        for msg_id in range(start_id, end_id + 1):
            if SYNC_CANCELLED:
                logger.info(f"Sync stopped at msg_id {msg_id} due to admin cancellation.")
                break
                
            await asyncio.sleep(0.1)  # Yield to event loop to keep bot 100% responsive for all users
            try:
                # Forward to target chat to get the Message object with file_id
                fwd = await bot.forward_message(
                    chat_id=target_chat_id,
                    from_chat_id=channel_id,
                    message_id=msg_id
                )
                
                # Check if it has a video
                if fwd.video:
                    caption = fwd.caption or fwd.video.file_name or ""
                    file_id = fwd.video.file_id
                    
                    # Try to add to DB (will check for duplicate)
                    added = database.add_video(file_id, caption, vault)
                    if added:
                        imported_count += 1
                        logger.info(f"Successfully synced video {msg_id} -> file_id {file_id[:15]}...")
                        
                        # Optionally copy the video to the designated bot database channel
                        if copy_to_channel_id and copy_to_channel_id != channel_id:
                            try:
                                await bot.copy_message(
                                    chat_id=copy_to_channel_id,
                                    from_chat_id=channel_id,
                                    message_id=msg_id
                                )
                            except Exception as ce:
                                logger.debug(f"Could not copy msg {msg_id} to database channel: {ce}")
                    else:
                        duplicates_count += 1
                        
                # Immediately delete the forwarded message from target chat to keep it clean
                try:
                    await bot.delete_message(chat_id=target_chat_id, message_id=fwd.message_id)
                except Exception:
                    pass
                    
            except Exception as e:
                if imported_count == 0 and msg_id <= start_id + 5:
                    logger.warning(f"Failed forwarding msg_id {msg_id} from {channel_id}: {e}")
                else:
                    logger.debug(f"Skipping msg_id {msg_id} due to: {e}")
                continue
                
        logger.info(f"Sync complete. Imported: {imported_count}, Duplicates ignored: {duplicates_count}")
        return imported_count

