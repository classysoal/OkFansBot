# 📘 Complete OkFansBot v2.0 Master Documentation

Welcome to the official, exhaustive master documentation for **OkFansBot v2.0**. This document provides an in-depth breakdown of every feature, command, system scenario, database architecture, and psychological design mechanic built into the bot.

---

## 📑 Table of Contents
1. [System Architecture & Design Philosophy](#1-system-architecture--design-philosophy)
2. [REST API & Telegram Mini App Architecture](#2-rest-api--telegram-mini-app-architecture)
3. [User Features & Access Guide](#3-user-features--access-guide)
4. [VIP Progression & Credit System](#4-vip-progression--credit-system)
5. [Zero-Duplicate & Resend Engine](#5-zero-duplicate--resend-engine)
6. [Owner & Admin Access Guide](#6-owner--admin-access-guide)
7. [Complete Command & API Reference](#7-complete-command--api-reference)
8. [Step-by-Step User & Admin Scenarios](#8-step-by-step-user--admin-scenarios)

---

## 1. System Architecture & Design Philosophy

### 🧠 Decoupled Authoritative Engine
OkFansBot v2.0 separates the frontend presentation layer (Telegram Bot & Mini App) from backend business rules:
- **Authoritative Backend**: Centralized FastAPI REST Server (`api.py`) handles identity authentication, verification rules, credit transactions, and referral processing.
- **Telegram Mini App**: Mobile-first WebApp interface served at `/app` communicating with the backend using HMAC-validated Telegram InitData.
- **Dual-Database Storage**: Primary connection runs on **Cloud Supabase PostgreSQL**. Fallback switches automatically to local **SQLite database (`okfans_bot.db`)**.

---

## 2. REST API & Telegram Mini App Architecture

### 🔒 Security & Authentication
- **InitData HMAC-SHA256 Validation**: Web App requests send `X-Telegram-Init-Data` header. `validate_telegram_init_data` computes HMAC-SHA256 of auth fields using secret key `HMAC(bot_token, "WebAppData")` and checks 24-hour timestamp freshness.
- **Role-Based Access Control (RBAC)**: Admin endpoints verify `get_admin_user` dependency against `OWNER_ID` (`6193742824`).
- **User Sessions & Devices**: `user_sessions` and `user_devices` tables record active devices, IP risk states, and session revocations.

---

## 3. User Features & Access Guide

### 📱 Interface Options
Users navigate using two synchronized UI systems:
1. **Persistent Bottom Telegram ReplyKeyboard** (positioned in the Gboard soft keyboard location):
   ```text
   [ 🎁 Get Video ]   [ 🏆 VIP Tiers ]
   [ 🎁 Daily Bonus ] [ 🤝 Invite Friends ]
   [ 👤 My Profile ]  [ 📜 Rules & Info ]
   ```
2. **Telegram Mini App**: Rich graphical interface accessible via `/app`.

---

## 4. VIP Progression & Credit System

The bot features 4 progressive VIP ranks based on total verified referrals:

| VIP Tier | Title | Required Invites | Credit Cost | Video Bundle Yield |
| :--- | :--- | :---: | :---: | :---: |
| 🌟 Level 1 | **Novice VIP** | 0 Invites | 1 Credit | **5 Videos** / redemption |
| 🔥 Level 2 | **Silver VIP** | 1 Invite | 1 Credit | **7 Videos** / redemption |
| 👑 Level 3 | **Gold VIP** | 4 Invites | 1 Credit | **10 Videos** / redemption |
| 💎 Level 4 | **Diamond VIP** | 7 Invites | 1 Credit | **15 Videos** / redemption |

---

## 5. Zero-Duplicate & Resend Engine

### 🛡️ 100% Zero-Duplicate Guarantee
- Every video delivered to a user is recorded in the `user_video_history` database table.
- Subsequent redemptions query active catalog videos filtering out any video ID present in the user's `user_video_history`.

### 🔄 3-Time Free Bundle Resend Engine
- Inline button `🔄 Resend Last Bundle (3/3 Left)` allows users to re-claim their last delivered bundle up to **3 times max for free**.

---

## 6. Owner & Admin Access Guide

### 📤 Zero-Clutter Owner DM Video Forwarding
- Owner forwards or sends any video directly to the bot in DM.
- Bot automatically captures `file_id` and saves it to Vault B.
- Auto-deletes owner DM video after 3 seconds, and confirmation reply after 5 seconds.

---

## 7. Complete Command & API Reference

### 🌐 REST API Endpoints
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Operational status and database connectivity. |
| `GET` | `/api/me` | Authenticated | Current user profile, VIP level, credits, referral code. |
| `GET` | `/api/dashboard` | Authenticated | User dashboard metrics and streak statistics. |
| `GET` | `/api/verification` | Authenticated | Verification quest status and required channel list. |
| `GET` | `/api/referrals` | Authenticated | Referral link and 24h bonus status. |
| `POST`| `/api/rewards/claim-daily` | Authenticated | Claims +1 Credit daily bonus atomically. |
| `GET` | `/api/admin/stats` | Admin Only | System stats and detailed catalog breakdown. |
| `GET` | `/api/admin/users` | Admin Only | Paginated list of registered users. |
| `POST`| `/api/admin/credits/give` | Admin Only | Adjusts user credit balance with audit log. |

---

*OkFansBot v2.0 Master Documentation — Maintained by Engineering Team.*
