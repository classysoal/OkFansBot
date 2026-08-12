# 🚀 Production Deployment Master Guide — OkFansBot v2.0

As a Lead System Architect, here is the professional, production-grade deployment strategy for your **Telegram Bot + Telegram Mini App + FastAPI Backend**.

---

## 🏛️ Top-Tier Deployment Architecture

```text
┌────────────────────────────────┐        ┌────────────────────────────────┐
│      Frontend Mini App         │        │    Python Bot & REST API       │
│      (HTML / CSS / JS)         │        │    (bot.py & api.py)           │
│  Deployed on: Vercel CDN       │        │  Deployed on: Render / Railway │
└───────────────┬────────────────┘        └───────────────┬────────────────┘
                │                                         │
                │ HTTPS Session / initData API            │ Database Queries
                ▼                                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   Cloud Supabase PostgreSQL Database                     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 PART 1: Deploying Frontend Mini App to Vercel (100% Free)

Telegram Mini Apps **MUST BE SERVED OVER HTTPS**. Vercel provides a free SSL domain automatically (`https://okfansbot.vercel.app`).

### Step-by-Step Vercel Deployment:
1. **Push Code to GitHub**:
   - Push your code to your repository: `https://github.com/classysoal/OkFansBot.git`.
2. **Import into Vercel**:
   - Go to [vercel.com](https://vercel.com) and log in.
   - Click **"Add New" ➔ "Project"** and import `OkFansBot`.
   - Vercel automatically detects `vercel.json` and serves `webapp/`.

---

## ⚙️ PART 2: Deploying Python Bot & REST API to Render (100% Free)

Render runs Python 3.13/3.14 web services with automated GitHub deploys.

### Required Environment Variables on Render:

| Variable Name | Example Value | Description |
| :--- | :--- | :--- |
| `TG_BOT_TOKEN` | `8938399688:AAHPaPDM5qCZy...` | Telegram Bot Token from BotFather |
| `DATABASE_URL` | `postgresql://postgres:...@db...supabase.co:5432/postgres` | Cloud Supabase PostgreSQL Connection String |
| `TELEGRAM_LOGIN_CLIENT_ID` | `8938399688` | Telegram OAuth Client ID |
| `TELEGRAM_LOGIN_CLIENT_SECRET` | `6BSiv8jcdx9EWAY...` | Telegram OAuth Client Secret |
| `ENVIRONMENT` | `production` | Production mode (disables owner preview fallback) |
| `PORT` | `8080` | Server listening port |

---

## 🤖 PART 3: Configuring Telegram Bot & OAuth in BotFather

1. Open Telegram and search for `@BotFather`.
2. Select your bot (`@OkFansBot`).
3. **Configure Mini App URL**:
   - Click **Bot Settings ➔ Menu Button / Main App**.
   - Set WebApp URL to: `https://okfansbot.vercel.app/`
4. **Configure Telegram Login Widget / OIDC Redirect URIs**:
   - Click **Bot Settings ➔ Domain / Login Widget**.
   - Add Allowed Origin: `https://okfansbot.vercel.app/`
   - Add Redirect URI: `https://okfansbot.vercel.app/auth/telegram/callback`

---

## 🧪 PART 4: Verification & Operational Tests

Run automated integration tests:
```bash
python -m unittest tests/test_verification_pipeline.py
```

Verify backend health endpoint:
```bash
curl https://okfansbot-826r.onrender.com/
```

Verify admin observability health:
```bash
curl https://okfansbot-826r.onrender.com/api/admin/health
```
