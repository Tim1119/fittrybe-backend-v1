# Fit Trybe Backend — CLAUDE.md

## Project Overview
Fit Trybe is a B2B SaaS fitness platform. This is the Django +
DRF backend. Flutter mobile app consumes this API.

## Stack
- Python 3.12, Django 5.2, Django REST Framework
- PostgreSQL (primary DB), Redis (cache + Celery broker)
- Celery + Celery Beat (async tasks)
- Django Channels (WebSockets for chat)
- JWT auth via djangorestframework-simplejwt
- django-axes (account lockout)
- django-ratelimit (rate limiting)
- zxcvbn (password strength)
- Mailgun via django-anymail (emails)
- drf-spectacular (OpenAPI/Swagger)
- docker-compose for local Postgres + Redis

## Running the Project
1. docker-compose up -d db redis
2. source venv/bin/activate
3. python manage.py migrate
4. python manage.py runserver
Or just: make docker-up && make run

## App Structure
apps/
  core/          - Shared: APIResponse, exceptions, pagination, middleware
  accounts/      - Auth: User model, JWT, email verification, permissions
  profiles/      - Trainer and Gym profiles
  clients/       - Client membership management
  chat/          - Community chatroom + DMs (Django Channels)
  marketplace/   - Product listings and enquiries
  badges/        - Badge assignment and recognition
  subscriptions/ - Platform billing (Paystack + Stripe)
  trackers/      - Exercise and nutrition trackers (client add-on)
  analytics/     - Stats and reporting
  notifications/ - Push notifications (FCM)

## Coding Conventions
- Always write FAILING TESTS first, then implement (TDD)
- Never write code without a corresponding test
- Use APIResponse for ALL responses — never return raw Response()
- Use ErrorCode constants for all error codes
- Use StandardPagination for all list endpoints
- Feature-first app structure — keep related code together
- Always run: make lint before committing

## Swagger / OpenAPI Rules
Every view MUST have @extend_schema with ALL of the following before committing.
No view is complete without Swagger documentation.
- summary: short one-line description of what the endpoint does
- description: fuller explanation including edge cases, rate limits, side effects
- request: the serializer or inline_serializer for POST/PUT/PATCH request bodies
- responses: dict of every status code the endpoint can return with OpenApiResponse descriptions
- tags: logical grouping (Authentication, Subscriptions, Profiles, etc.)
- auth=[]: on every public endpoint (removes the lock icon in Swagger UI)

## API Response Format
Every endpoint returns:
{
  "status": "success" | "error",
  "message": "Human readable string",
  "data": {} | [] | null,
  "errors": {},        (only on error)
  "code": "ERROR_CODE", (only on error)
  "meta": {
    "timestamp": "ISO8601",
    "version": "v1",
    "pagination": {}   (only on paginated responses)
  }
}

## Commit Convention
Single line only. Format: type(scope): description
Types: feat, fix, docs, test, refactor, chore
Examples:
  feat(accounts): add email verification
  fix(profiles): handle missing avatar
  test(chat): add chatroom member tests
Max 72 characters. No body. No bullet points.

## TDD Rules
1. Write test first — it must FAIL
2. Write minimum code to make it pass
3. Refactor
4. Coverage must stay above 80%
5. Run: make test before every commit

## User Roles
- trainer: individual fitness instructor (Basic plan)
- gym: gym admin (Pro plan, up to 3 logins)
- client: free user added by trainer/gym

## Key Models (Phase 1)
- User (apps.accounts) — AUTH_USER_MODEL
- Subscription (apps.subscriptions) — platform billing
- TrainerProfile / GymProfile (apps.profiles)
- ClientMembership (apps.clients)

## Environment Variables
Copy .env.example to .env and fill in values.
Never commit .env — it is gitignored.
Required: SECRET_KEY, DB_*, REDIS_URL, MAILGUN_*, FRONTEND_URL
