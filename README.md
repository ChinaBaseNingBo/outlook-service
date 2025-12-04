# 📫 Outlook Webhook Service (CBNB-AI)

A containerized webhook system for receiving and processing Outlook (Microsoft Graph) message notifications.  
The backend is written in **Python**, running behind **nginx** with HTTPS support and deployable via **Docker Compose** on AWS EC2.

This service automatically generates callback URLs, registers subscriptions, and exposes a public HTTPS endpoint for Microsoft to deliver webhook events.

---

## 🚀 Features

| Functionality |
|---|
| 1. Microsoft Graph webhook subscription 
| 2. `/notifications` inbound webhook endpoint|
| 3. Env-based callback URL generation (`PUBLIC_BASE_URL`)|
| 4. Dockerized backend & reverse proxy|
| 5. HTTPS support (self-signed or real certificate)|
| 6. `.env` secured (not committed to GitHub)|

---

## 🏗 Project Structure

```
outlook-service/
│── src/
│   ├── app.py          # Main service entry
│   ├── auth.py
│   ├── outlook_api.py
│   ├── mongo_service.py
│   └── service.py
│
│── nginx/
│   ├── nginx.conf      
│── certs/
│
│── Dockerfile
│── docker-compose.yml
│── .env      
└── README.md          
```

---

📌 `.env` is not committed — credentials remain private locally and on EC2 only.

---

## 🐳 Local Development with Docker

```bash
docker compose up --build
```

Visit:

```
https://localhost/notifications   # self-signed ok with -k
```

---

## 🌍 Deployment on AWS EC2

```bash
git clone https://github.com/ChinaBaseNingBo/outlook-service.git
cd outlook-service
vim .env   # <-- insert real values
```

Start:

```bash
docker compose up -d --build
```

Your webhook receiving URL becomes:

```
https://cbnb-ai.otono.cn/notifications
```

Use this in your Microsoft Graph subscription payload.

---

## 🔒 SSL / HTTPS Setup

Place certificates under:

```
certs/ssl.crt
certs/ssl.key
```
---
