# Fit Trybe Backend

Django 5.2 + DRF + PostgreSQL + Redis + Celery + Django Channels

**588 tests · 93.91% coverage**

---

## Table of Contents

- [Requirements](#requirements)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Running the Application](#running-the-application)
- [Seed Test Data](#seed-test-data)
- [API Documentation](#api-documentation)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Key Concepts](#key-concepts)

---

## Requirements

- Python 3.12+
- Docker Desktop (for PostgreSQL + Redis)
- Git

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django 5.2 + Django REST Framework |
| Database | PostgreSQL 16 (via Docker) |
| Cache / Broker | Redis 7 (via Docker) |
| Async Tasks | Celery + Celery Beat |
| Real-time | Django Channels + WebSockets |
| Auth | JWT (SimpleJWT) |
| Payments | Paystack + Stripe |
| Email | Mailtrap (development) |
| API Docs | Swagger / OpenAPI (drf-spectacular) |

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Fit-Trybe/fittrybe-backend-v1.git
cd fittrybe-backend-v1
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
# For local development (includes everything: base + dev tools)
pip install -r requirements/development.txt

# For production (base packages only)
# pip install -r requirements/base.txt
```

> `requirements/development.txt` automatically includes everything in `requirements/base.txt` via `-r base.txt`, so you only need to run one command for local development.

### 4. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in the required values. See the [Environment Variables](#environment-variables) section below for details.

### 5. Start Docker (PostgreSQL + Redis)

Make sure Docker Desktop is running, then:

```bash
docker-compose up -d db redis
```

Verify containers are running:

```bash
docker ps
# Should show: fittrybe_db (postgres:16) and fittrybe_redis (redis:7-alpine)
```

### 6. Run migrations

```bash
python manage.py migrate
```

### 7. Create a superuser (for Django Admin)

```bash
python manage.py createsuperuser
```

### 8. Start the development server

```bash
python manage.py runserver
```

The API is now running at: **http://127.0.0.1:8000**

---

## Environment Variables

Create a `.env` file in the project root. All required variables are listed below.

```env
# Django
DJANGO_SETTINGS_MODULE=fittrybe_backend.settings.development
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (matches Docker Compose defaults)
DB_NAME=fittrybe_db
DB_USER=fittrybe_user
DB_PASSWORD=fittrybe_pass
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# Frontend / Mobile URLs (used in emails and deep links)
FRONTEND_URL=http://localhost:3000
MOBILE_URL=fittrybe://

# Email — Mailtrap (development)
# Sign up free at https://mailtrap.io → Email Testing → SMTP Settings
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=sandbox.smtp.mailtrap.io
EMAIL_HOST_USER=your-mailtrap-username
EMAIL_HOST_PASSWORD=your-mailtrap-password
EMAIL_PORT=2525
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@fittrybe.com

# Paystack (Nigerian payments)
# Get keys from https://dashboard.paystack.com → Settings → API Keys
PAYSTACK_SECRET_KEY=sk_test_your_key_here
PAYSTACK_PUBLIC_KEY=pk_test_your_key_here

# Stripe (international payments)
# Get keys from https://dashboard.stripe.com → Developers → API Keys
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# Deep Links — Mobile App (get these from Godwin / mobile team)
APPLE_TEAM_ID=TEAMID
ANDROID_PACKAGE_NAME=com.fittrybe.app
ANDROID_SHA256_FINGERPRINT=PLACEHOLDER
APP_STORE_URL=#
PLAY_STORE_URL=#
```

### Where to get the values

| Variable | Where to get it |
|----------|----------------|
| `SECRET_KEY` | Generate with: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | Mailtrap → Email Testing → your inbox → SMTP Settings |
| `PAYSTACK_SECRET_KEY` | Paystack Dashboard → Settings → API Keys & Webhooks |
| `STRIPE_SECRET_KEY` | Stripe Dashboard → Developers → API Keys |
| `APPLE_TEAM_ID` | Ask mobile team (Godwin) |
| `ANDROID_SHA256_FINGERPRINT` | Ask mobile team (Godwin) |

> **Note:** For development, Paystack and Stripe keys are optional unless you are testing payments. Email requires Mailtrap — all emails are captured there during development and never sent to real inboxes.

---

## Running the Application

The full application requires 4 processes. Open 4 terminal tabs:

### Terminal 1 — Docker (Database + Redis)

```bash
docker-compose up -d db redis
```

### Terminal 2 — Django Server

```bash
source venv/bin/activate
python manage.py runserver
```

### Terminal 3 — Celery Worker (background tasks)

```bash
source venv/bin/activate
make worker
# or manually:
# celery -A fittrybe_backend worker --loglevel=info
```

### Terminal 4 — Celery Beat (scheduled tasks — optional for dev)

```bash
source venv/bin/activate
make beat
# or manually:
# celery -A fittrybe_backend beat --loglevel=info
```

> **Minimum for development:** Terminal 1 (Docker) + Terminal 2 (Django) is enough to use the API. Celery is only needed for background jobs (payment reminders, subscription checks).

---

## Seed Test Data

Load sample data for development and testing:

```bash
# Seed fresh data
python manage.py seed_test_data

# Wipe existing data and re-seed
python manage.py seed_test_data --clear
```

This creates:

| Role | Count | Details |
|------|-------|---------|
| Gym admins | 2 | FitZone Lagos, Apex Fitness |
| Gym trainers | 4 | 2 per gym |
| Independent trainers | 2 | Published profiles |
| Clients | 24 | Active memberships distributed across trainers/gyms |
| Chatrooms | Auto-created | One per published trainer/gym |

**All passwords:** `Test1234!`

**Sample accounts:**

```
# Gym admin
gym1@fittrybe.com / Test1234!

# Independent trainer
trainer1@fittrybe.com / Test1234!

# Client
client1@fittrybe.com / Test1234!
```

---

## API Documentation

After starting the server, visit:

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8000/api/docs/ | Swagger UI — interactive API explorer |
| http://127.0.0.1:8000/api/redoc/ | ReDoc — clean API reference |
| http://127.0.0.1:8000/api/schema/ | Raw OpenAPI schema (JSON/YAML) |
| http://127.0.0.1:8000/admin/ | Django Admin panel |
| http://127.0.0.1:8000/api/v1/health/ | Health check |

---

## Chat — REST vs WebSocket

The chat feature uses **both** REST and WebSocket. They serve different purposes.

| Protocol | Use for | Speed |
|----------|---------|-------|
| REST (HTTP) | Loading existing data — message history, member list, pinned messages, unread count | Fast — one-time query |
| WebSocket (WSS) | Real-time events — new messages, typing indicators, deletions | Instant — server pushes |

### The flow Flutter/React should follow

```
1. User opens chatroom
   → REST: GET /api/v1/chat/rooms/{id}/messages/   ← load last 50 messages
   → WSS:  connect to ws://localhost:8000/ws/chat/room/{id}/?token=JWT

2. New message arrives
   → WebSocket pushes message.new event automatically
   → NO REST call needed

3. User sends a message
   → WebSocket: send {type: "message.send", content: "..."}
   → Backend saves to DB and broadcasts to all connected members instantly

4. User uploads an image
   → REST: POST /api/v1/chat/rooms/{id}/upload/ ← get back a URL
   → WebSocket: send {type: "message.send", message_type: "image", attachment_url: "..."}

5. User leaves chatroom
   → REST: POST /api/v1/chat/rooms/{id}/read/ ← mark as read
   → WebSocket disconnects automatically
```

### WebSocket Connection URLs

```
# Community chatroom
ws://localhost:8000/ws/chat/room/{chatroom_id}/?token=JWT_ACCESS_TOKEN

# Direct messages
ws://localhost:8000/ws/chat/dm/{other_user_id}/?token=JWT_ACCESS_TOKEN
```

> Use `ws://` locally and `wss://` in production.
> Get the JWT token from `POST /api/v1/auth/login/` → `data.access`

### WebSocket Close Codes

| Code | Meaning |
|------|---------|
| `4001` | No token or invalid token — re-authenticate |
| `4003` | Not a member of this chatroom |

### WebSocket Events You Send

| Event | Payload |
|-------|---------|
| `message.send` | `{message_type, content, attachment_url, reply_to_id, audience, target_user_id}` |
| `message.delete` | `{message_id}` |
| `message.read` | `{}` |
| `typing.start` | `{}` |
| `typing.stop` | `{}` |

### WebSocket Events You Receive

| Event | Meaning |
|-------|---------|
| `message.new` | New message — append to chat |
| `message.deleted` | Message deleted — remove from chat |
| `typing.indicator` | Someone is typing |
| `error` | Something went wrong (check `code` field) |

📖 **Full chat API reference (REST + WebSocket):** https://www.notion.so/330cdf3cc8bc818db3e9e357a96be4b8

---

## Running Tests

```bash
# Run full test suite
venv/bin/pytest --tb=short -q

# Run with coverage report
venv/bin/pytest --cov=apps --cov-report=term-missing

# Run a specific app
venv/bin/pytest apps/chat/ -v

# Run a specific test file
venv/bin/pytest apps/chat/tests/test_chatroom.py -v
```

---

## Project Structure

```
fittrybe-backend/
├── apps/
│   ├── accounts/        # User model, auth, JWT, email verification
│   ├── profiles/        # Trainer/gym/client profiles, wizard, public pages
│   ├── subscriptions/   # Plans, Paystack/Stripe webhooks, billing
│   ├── clients/         # Client membership, invite links, manual add
│   ├── chat/            # Community chatroom, DMs, WebSockets
│   └── core/            # BaseModel, APIResponse, pagination, permissions
├── fittrybe_backend/
│   ├── settings/
│   │   ├── base.py      # Shared settings
│   │   ├── development.py
│   │   └── production.py
│   ├── asgi.py          # WebSocket routing (Django Channels)
│   └── urls.py          # Root URL configuration
├── requirements/
│   ├── base.txt
│   └── development.txt
├── docker-compose.yml
├── Makefile
└── pytest.ini
```

---

## Key Concepts

### User Roles

| Role | Description | Plan |
|------|-------------|------|
| `trainer` | Independent fitness instructor | Basic ₦15,000/mo |
| `gym` | Gym admin account | Pro ₦35,000/mo |
| `client` | Client added by trainer/gym | Free forever |

### Authentication

All protected endpoints require a Bearer token:

```
Authorization: Bearer <access_token>
```

Get tokens from `POST /api/v1/auth/login/`.
Refresh with `POST /api/v1/auth/token/refresh/`.

### Standard API Response Format

Every endpoint returns:

```json
{
  "status": "success | error",
  "message": "Human readable string",
  "data": {},
  "errors": {},
  "code": "ERROR_CODE",
  "meta": {
    "timestamp": "2026-03-27T00:00:00Z",
    "version": "v1",
    "pagination": {}
  }
}
```

### Subscription Gate

Trainers and gyms must have an active subscription to access protected endpoints.

- **Trial**: 14 days free from registration
- **Grace**: 7 days after trial/payment failure
- **Locked**: Payment wall shown

Clients are always free and skip the subscription gate.

### Email in Development

All emails go to **Mailtrap** — they are never sent to real inboxes.

1. Sign up at https://mailtrap.io (free)
2. Go to Email Testing → your inbox
3. Click SMTP Settings → copy credentials to `.env`
4. All emails sent by the app appear in your Mailtrap inbox

---

## Makefile Commands

```bash
make docker-up      # Start PostgreSQL + Redis
make docker-down    # Stop containers
make worker         # Start Celery worker
make beat           # Start Celery Beat scheduler
make test           # Run full test suite
make lint           # Run black + isort + flake8
make migrate        # Run migrations
```

---

## Useful Links

| Resource | URL |
|----------|-----|
| Backend Org Repo | https://github.com/Fit-Trybe/fittrybe-backend-v1 |
| API Docs (local) | http://127.0.0.1:8000/api/docs/ |
| Mailtrap | https://mailtrap.io |
| Paystack Dashboard | https://dashboard.paystack.com |
| Stripe Dashboard | https://dashboard.stripe.com |
| Technical Docs (Notion) | https://www.notion.so/32bcdf3cc8bc8153b05cf7a9c0513b97 |
