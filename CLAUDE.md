# Outlook Webhook Service

## Overview
Monitors Outlook mailbox via Microsoft Graph webhooks, processes incoming emails by category, and stores data in MongoDB.

## Outlook Accounts
- `chinabaseningbo@outlook.com` — original account (has Bloomberg + Shuchuang folders)
- `chinabaseningbo2@outlook.com` — new account (currently deployed, has 1 folder)
- Credentials stored in Claude memory (not in git)

## Architecture
```
Microsoft Outlook → Graph webhook → nginx (HTTPS:443, Let's Encrypt) → Flask (:8000) → MongoDB
```

## Key Modules (src/)
- `app.py` — Flask entry point, HTTP endpoints, subscription lifecycle daemon thread
- `auth.py` — MSAL device flow auth (personal MS account, scopes: Mail.Read, User.Read)
- `outlook_api.py` — Microsoft Graph API wrapper
- `service.py` — Business logic: route emails by category (Green=Bloomberg, Blue=Shuchuang)
- `mongo_service.py` — MongoDB + GridFS storage with upsert dedup

## Email Processing
- **Green category (Bloomberg)**: extract body → HTML to Markdown → save to `bloomberg` collection
- **Blue category (Shuchuang)**: extract attachments → save to GridFS (`shuchuang_fs`), metadata to `shuchuang`
- Dedup: Bloomberg by email_id, Shuchuang by `email_id:attachment_id`

## Deployment (AWS EC2)
- **Host**: `cbnb_ai` (52.26.11.107, ec2-user, `~/.ssh/cbnb-ai.pem`)
- **Project path**: `/home/ec2-user/outlook-service/`
- **Run**: `docker compose up -d --build`
- **SSL**: Let's Encrypt certs mounted from `/etc/letsencrypt`
- **Containers**: `outlook_app` (Flask), `outlook_nginx` (reverse proxy)

## Environment (.env on server, not in git)
- `OUTLOOK_CLIENT_ID`, `MONGO_URI`, `MONGO_DB_NAME`, `PUBLIC_BASE_URL`
- `MONGO_COLLECTION_BLOOMBERG`, `MONGO_COLLECTION_SHUCHUANG`, `MONGO_COLLECTION_SHUCHUANG_FS`
- Values stored in Claude memory and on server at `/home/ec2-user/outlook-service/.env`

## Known Issues (as of 2026-03-10)
1. ~~**Subscription renewal bug**~~ — Fixed in `fix/subscription-lifecycle` branch (deployed 2026-03-10). Was calling non-existent `renew_subscription()`, now uses `extend_subscription()` and renews all subscriptions.
2. **MSAL token cache not persisted** — `msal_cache.bin` lives inside the container, not mounted as a volume. Container restart = manual re-login via device flow.
3. **MongoDB timeout** — 2026-02-20 had `NetworkTimeout` to 218.0.6.188:13017 (the MongoDB is remote, in China).
4. **Currently using chinabaseningbo2 account** — only 1 folder subscribed (vs original account's 2). May need to confirm with team if this is intended.

## Development
```bash
# Local
docker compose up --build

# Deploy to EC2 (note: server uses docker-compose v1, not "docker compose")
ssh cbnb_ai
cd outlook-service && git pull && docker-compose down && docker-compose up -d --build
# First run requires manual device flow login — watch `docker logs outlook_app`
# Go to https://www.microsoft.com/link and enter the code shown in logs
```
