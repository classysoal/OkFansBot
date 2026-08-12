# 🏛️ OkFansBot v2.0 Production Architecture & Security Documentation

## 1. System Topology

OkFansBot v2.0 is an authoritative, asynchronous Python system operating two concurrent subsystems:

```text
                                 TG_BOT_TOKEN
                                      │
       ┌──────────────────────────────┴──────────────────────────────┐
       ▼                                                             ▼
Telegram Bot Application                                FastAPI Authoritative REST API
(python-telegram-bot v20.x)                             (api.py + uvicorn on port 8080)
  ├── Polling Updates                                      ├── GET / (Health Check)
  ├── ChatJoinRequestHandler                               ├── POST /api/auth/miniapp
  ├── ReplyKeyboard Navigation                             ├── GET /auth/telegram/callback (OIDC)
  └── DM Video Uploads                                     ├── GET /api/dashboard
       │                                                   ├── POST /api/rewards/redeem
       │                                                   └── POST /api/verification/check
       └──────────────────────────────┬──────────────────────────────┘
                                      │
                                      ▼
                          Database Layer (database.py)
                          Primary: Cloud Supabase PostgreSQL
                          Fallback: Local SQLite (okfans_bot.db)
```

---

## 2. Authentication & Identity Pipeline

### Single Identity Mapping (`telegram_user_id`)
- `telegram_user_id` is the primary external key and maps 1-to-1 with internal user account (`user_id`).
- Username changes or logins from multiple devices/browsers map back to the same internal user without account duplication.

### Dual Entry Points
1. **Telegram Mini App (`/api/auth/miniapp`)**:
   - Validates `Telegram.WebApp.initData` using `HMAC_SHA256(bot_token, "WebAppData")` and 24-hour timestamp freshness.
   - Generates a 7-day UUID4 session token returned in `{ "session_token": "..." }`.
2. **Telegram OIDC / Login Widget (`/auth/telegram/callback`)**:
   - Validates query signature parameters using `TELEGRAM_LOGIN_CLIENT_SECRET`.
   - `TELEGRAM_LOGIN_CLIENT_SECRET` is kept strictly on backend environment variables.

---

## 3. Verification Engine State Machine

The verification engine ([`services/verification.py`](file:///c:/Python314/TG/services/verification.py)) enforces a strict state machine:

### States:
- **`MEMBER`**: Active member, owner, or administrator ➔ **`PASS`**
- **`REQUEST_PENDING`**: Active pending join request ➔ **`PASS`** (accepted by policy)
- **`NOT_JOINED`**: Not a member ➔ **`FAIL`**
- **`LEFT`**: User joined previously but left ➔ **`FAIL`**
- **`BANNED`**: User is banned or kicked ➔ **`FAIL`**
- **`CHECK_ERROR`**: Transient Telegram API timeout ➔ **`ERROR`**

### Live Verification Rules:
- Live Telegram API `getChatMember` checks **ALWAYS override database history**.
- Verification checks are strictly **READ-ONLY** (`READ ➔ EVALUATE ➔ RECORD`). Pressing "Check Verification" never approves or modifies Telegram join requests.
