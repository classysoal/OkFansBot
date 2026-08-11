# 🚀 Production Deployment Master Guide

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
                │ HTTPS initData API Requests             │ Database Queries
                ▼                                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   Cloud Supabase PostgreSQL Database                     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 PART 1: Deploying Frontend Mini App to Vercel (100% Free)

Telegram Mini Apps **MUST BE SERVED OVER HTTPS**. Vercel gives you a free SSL domain automatically (`https://your-app.vercel.app`).

### Step-by-Step Vercel Deployment:
1. **Push Code to GitHub**:
   - Create a repository on GitHub (e.g. `OkFansBot`).
   - Push your code:
     ```bash
     git init
     git add .
     git commit -m "Production ready release"
     git remote add origin https://github.com/YOUR_USERNAME/OkFansBot.git
     git push -u origin main
     ```
2. **Import into Vercel**:
   - Go to [vercel.com](https://vercel.com) and log in.
   - Click **"Add New" ➔ "Project"**.
   - Import your GitHub repository `OkFansBot`.
   - Vercel will automatically detect `vercel.json` and deploy the `webapp/` folder!
3. **Copy your Live Vercel URL**:
   - Your live Mini App will be online at `https://okfansbot.vercel.app`.

---

## ⚙️ PART 2: Deploying Python Bot & REST API to Render / Railway (100% Free)

Python codes (`bot.py` and `api.py`) run continuously in the cloud.

### Step-by-Step Render Deployment:
1. Go to [render.com](https://render.com) and log in.
2. Click **"New" ➔ "Blueprint"**.
3. Connect your GitHub repository `OkFansBot`.
4. Render will read `render.yaml` and create two services automatically:
   - **`okfans-backend-api`** (FastAPI Web Service)
   - **`okfans-telegram-bot`** (Telegram Bot Worker)
5. Set Environment Variables on Render:
   - `TG_BOT_TOKEN` = `8938399688:AAHPaPDM5qCZyJA0X1ccLiQP45yuQPDB8Uo`
   - `DATABASE_URL` = `postgresql://postgres:4xSukoon%40777@db.ztnkwhtmyalklnjikcdk.supabase.co:5432/postgres`

---

## 🤖 PART 3: Linking Mini App to Telegram Bot

Now connect your live Vercel URL (`https://okfansbot.vercel.app`) to your Telegram Bot:

1. Open Telegram and search for `@BotFather`.
2. Send command: `/mybots` ➔ Select `@OkFansBot`.
3. Tap **Bot Settings ➔ Menu Button ➔ Configure Menu Button**.
4. Send your live Vercel URL: `https://okfansbot.vercel.app`.
5. Set Button Title: `🎁 VIP Club`.

Now, whenever users tap the Menu Button or `/start` in Telegram, your live Mini App opens seamlessly inside Telegram!

---

*OkFansBot Master Deployment Guide — Maintained by Engineering Team.*
