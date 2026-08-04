# OkFansBot — Telegram Reward Bot

OkFansBot (`@OkFansBot`) is a local-first, production-ready Telegram bot that gates content behind private channel join requests, manages a sequential video library of rewards, tracks referrals, and handles self-deleting message expiry. All states are stored safely in an SQLite database.

---

## Technical Features

1. **Transactional Database Guarding**: SQLite queries are wrapped in strict transaction blocks (`BEGIN IMMEDIATE TRANSACTION`) to prevent double-claiming or race conditions.
2. **Deterministic Video Distribution**: Utilizes a per-user vault pointer strategy to cycle through videos in vaults sequentially, guaranteeing users do not see duplicates or random overlaps.
3. **Robust Expiry Scheduler**: Video deliveries are logged in SQLite. If the bot is restarted, a recovery function on startup automatically deletes expired messages and reschedules future deletions in the `JobQueue`.
4. **Multi-Verification Gate**: Supports checking both direct membership using `get_chat_member` and request-to-join clicks using a `ChatJoinRequest` update handler.
5. **Traceable Balance Sheets**: Credit balance changes are audited using a credit ledger table for logging and security.

---

## Directory Layout

```
c:\Python314\TG\
├── .env                  # Environment file (TG_BOT_TOKEN)
├── config.json          # Admin configs, channel details, values
├── database.py          # Database models and sqlite3 interface
├── bot.py               # Main bot runtime, job queues, recovery, admin flow
└── requirements.txt     # Python dependency list
```

---

## Installation & Setup

1. **Initialize Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Secrets**:
   Create a file named `.env` in the root folder with your Telegram Bot Token:
   ```env
   TG_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
   ```

3. **Configure Settings**:
   Edit `config.json` to change the owner's Telegram ID (`owner_id`), target required channels, credit values, and video deletion timers:
   ```json
   {
     "owner_id": 6193742824,
     "required_channels": [
       {
         "channel_id": -1003585477205,
         "label": "Required Channel 1",
         "title": "OkFans Required Channel",
         "invite_link": "https://t.me/OkFansRequiredChannel",
         "channel_type": "starter",
         "verification_method": "direct_join",
         "is_active": 1,
         "priority": 1
       }
     ],
     "updates_supergroup_id": -1002376104010,
     "database_channel_id": -1003950233105,
     "welcome_video_channel": "@PIROsx07",
     "credits_per_verified_referral": 3,
     "video_deletion_delay_seconds": 1800,
     "cooldown_between_claims_seconds": 10,
     "max_videos_per_day": 10,
     "maintenance_mode": false
   }
   ```

4. **Initialize Database**:
   Run the database migration schema creation:
   ```bash
   python -c "import database; database.init_db()"
   ```

5. **Start Bot**:
   Run the runtime client:
   ```bash
   python bot.py
   ```

---

## Local Verification Checklist

Use these test scripts to verify the core systems locally:

### 1. User `/start` Flow
- Send `/start` to `@OkFansBot`.
- Verify that a clean welcome screen is sent with status tracking (Joined channels: 0/1) and credits initialized at 0.
- Verify the Profile page loads your Telegram metadata and provides a clean referral link containing your user ID: `https://t.me/OkFansBot?start=ref_<user_id>`.

### 2. Referral Verification
- Send `/start ref_<inviter_id>` from a separate test user account.
- Verify that the welcome message states "You were referred by [Inviter Name]".
- Confirm that the inviter's credit balance **does not** increment yet (no credits are given for phantom referrals).
- Try to verify using the new user's Verify button. Once all channel checks are completed:
  - The referred user gets 1 initial credit.
  - The inviter gets a direct private notification: "Referral Verified! You have received 3 credits!".

### 3. Rate-Limit & Verification Spam Checks
- Click the `✅ Verify` button.
- Click it again immediately. Verify that the bot answers with a notification: "Please wait 10 seconds before clicking verify again".

### 4. Deterministic Vault Rewards
- As the owner, forward 5 mock videos into the bot with `/addvideo B [optional_caption]`.
- As a user with credits, click `🎁 Get Video`.
- Verify the video is received with forwarding/copy protections active.
- Verify that consecutive claims cycle through Vault B's indexes in a strict, predictable order rather than random choice.

### 5. Auto-Deletion Recovery
- Claim a video. Confirm that the SQLite table `video_deliveries` creates a row with `status = 'delivered'` and a deletion time.
- Stop the bot process (kill `bot.py`).
- Wait for the deletion timer to pass (or manually set `expiry_at` in the SQLite file to a past time for testing).
- Start the bot. Confirm that during post-initialization startup, the bot immediately deletes the message from the user's chat and updates `status = 'deleted'`.
