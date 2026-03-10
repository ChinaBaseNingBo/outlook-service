# Outlook Webhook Service

## Overview
Monitors Outlook mailbox via Microsoft Graph webhooks, processes incoming emails by folder, and stores data in MongoDB.

## Outlook Accounts
- `chinabaseningbo@outlook.com` — original account (has Bloomberg + Shuchuang folders, stopped receiving Bloomberg ~2025-11-07)
- `chinabaseningbo2@outlook.com` — **currently deployed** (Bloomberg 9486+, Shuchuang 1184+, actively receiving)
- Both accounts share password, both require 2FA via James's phone
- Credentials stored in Claude memory (not in git)

## Architecture
```
Microsoft Outlook → Graph webhook → nginx (HTTPS:443, Let's Encrypt) → Flask (:8000) → MongoDB
```

## Key Modules (src/)
- `app.py` — Flask entry point, HTTP endpoints, subscription lifecycle daemon thread
- `auth.py` — MSAL device flow auth (personal MS account, scopes: Mail.Read, User.Read)
- `outlook_api.py` — Microsoft Graph API wrapper, email processing and routing
- `service.py` — Business logic: subscription lifecycle management, notification handling
- `mongo_service.py` — MongoDB + GridFS storage with upsert dedup

## Email Routing
Emails are routed by **parent folder** (primary) with category tag fallback:
- **Bloomberg folder** → extract body (HTML → Markdown) → save to `bloomberg` collection
- **Shuchuang folder** → extract attachments → save to GridFS (`shuchuang_fs`), metadata to `shuchuang`
- Fallback: `Green category` tag → Bloomberg, `Blue category` tag → Shuchuang (for old account compatibility)
- Dedup: Bloomberg by email_id, Shuchuang by `email_id:attachment_id`

## Webhook Subscriptions
- One subscription per target folder (Bloomberg, Shuchuang)
- Max expiration: ~7 days; daemon thread checks every 5 minutes and renews within 60 min of expiry
- chinabaseningbo2 has 2 subscriptions (Bloomberg + Shuchuang folders)

## Deployment (AWS EC2)
- **Host**: `cbnb_ai` (52.26.11.107, ec2-user, `~/.ssh/cbnb-ai.pem`)
- **Project path**: `/home/ec2-user/outlook-service/`
- **Branch**: `fix/subscription-lifecycle` (currently deployed)
- **SSL**: Let's Encrypt certs at `/etc/letsencrypt/live/cbnb-ai.otono.cn/`, copied to `certs/` dir
- **Containers**: `outlook_app` (Flask), `outlook_nginx` (reverse proxy)
- **Token persistence**: `msal_cache.bin` mounted as Docker volume — survives container restarts

## Environment (.env on server, not in git)
- `OUTLOOK_CLIENT_ID`, `MONGO_URI`, `MONGO_DB_NAME`, `PUBLIC_BASE_URL`
- `MONGO_COLLECTION_BLOOMBERG`, `MONGO_COLLECTION_SHUCHUANG`, `MONGO_COLLECTION_SHUCHUANG_FS`
- Values stored in Claude memory and on server at `/home/ec2-user/outlook-service/.env`

## Known Issues (as of 2026-03-10)
1. ~~**Subscription renewal bug**~~ — Fixed. Was calling non-existent `renew_subscription()`, now uses `extend_subscription()`.
2. ~~**MSAL token cache not persisted**~~ — Fixed. `msal_cache.bin` now mounted as Docker volume.
3. ~~**Category-based routing broken on new account**~~ — Fixed. Now routes by parent folder instead of category tags.
4. **MongoDB timeout** — 2026-02-20 had `NetworkTimeout` to remote MongoDB in China. May recur.
5. **SSL cert renewal** — Let's Encrypt certs must be copied to `certs/` dir after renewal. Not automated.

## Development
```bash
# Local
docker compose up --build

# Deploy to EC2 (note: server uses docker-compose v1, not "docker compose")
ssh cbnb_ai
cd outlook-service && git pull && docker-compose down && docker-compose up -d --build
# First run requires manual device flow login — watch `docker logs outlook_app`
# Go to https://www.microsoft.com/link and enter the code shown in logs
# Log in with chinabaseningbo2@outlook.com
```
