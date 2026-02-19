# Configuration Reference

All environment variables for the Zotta Lending Platform are managed from **a single file** at the repository root:

```
.env              ← your local config (git-ignored, never committed)
.env.example      ← template with safe defaults (committed)
.env.production   ← production template (git-ignored)
```

The backend reads this file via `backend/app/config.py`, which resolves the root `.env` automatically regardless of working directory. Docker Compose also reads it via `env_file: .env`.

**To change any setting**, edit the root `.env` and restart the affected service.

---

## Quick Start

```bash
cp .env.example .env          # create your local config
# edit .env with your real API keys (Twilio, OpenAI, etc.)
docker compose up --build     # or run backend/frontend directly
```

---

## File Locations

| File | Purpose | Committed to Git? |
|------|---------|-------------------|
| `.env` | Active configuration (your local values) | No |
| `.env.example` | Template with safe defaults for new developers | Yes |
| `.env.production` | Production template with `CHANGE_ME` placeholders | No |
| `backend/app/config.py` | Python `Settings` class — loads `.env`, provides typed access | Yes |
| `docker-compose.yml` | Dev Docker setup — reads `.env`, overrides DB/Redis hosts | Yes |
| `docker-compose.prod.yml` | Prod Docker setup — reads `.env.production` | Yes |
| `playwright.config.ts` | E2E test config — uses `CI` env var and hardcoded base URLs | Yes |
| `frontend/src/api/client.ts` | Frontend API client — reads `VITE_API_URL` at build time | Yes |

---

## All Environment Variables

### General

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `ENVIRONMENT` | `development` | Runtime environment. Controls behaviors like WhatsApp sandbox redirect, Swagger UI visibility, and startup table creation. Values: `development`, `production`. | `.env` |
| `DEBUG` | `true` | Enable debug mode. Set to `false` in production. | `.env` |
| `LOG_LEVEL` | `INFO` | Python logging level. Values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. | `.env` |

### Database (PostgreSQL)

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `POSTGRES_USER` | `zotta` | PostgreSQL username. Used by Docker to create the database user and by Docker Compose to construct connection URLs. | `.env` |
| `POSTGRES_PASSWORD` | `zotta_secret` | PostgreSQL password. **Must be changed in production.** | `.env` |
| `POSTGRES_DB` | `zotta` | PostgreSQL database name. | `.env` |
| `DATABASE_URL` | `postgresql+asyncpg://zotta:zotta_secret@localhost:5432/zotta` | Async database connection string (used by SQLAlchemy async engine). When running in Docker, this is overridden to point to the `db` container. | `.env` for local dev; overridden by `docker-compose.yml` in Docker |
| `DATABASE_URL_SYNC` | `postgresql://zotta:zotta_secret@localhost:5432/zotta` | Synchronous database connection string (used by Alembic migrations, seed scripts, and Celery tasks). Same override behavior as above. | `.env` for local dev; overridden by `docker-compose.yml` in Docker |

> **Note:** When running via Docker Compose, `DATABASE_URL` and `DATABASE_URL_SYNC` are automatically overridden to use the `db` container hostname instead of `localhost`. You only need to set `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` — the URLs are constructed from those.

### Redis

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL for Celery task broker and result backend. Overridden in Docker to use the `redis` container hostname. | `.env` |

### JWT Authentication

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `SECRET_KEY` | `change-me-to-a-random-secret-key-in-production` | Secret key for signing JWT tokens. **Must be changed in production.** Generate with: `openssl rand -hex 32`. | `.env` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | How long an access token (login session) stays valid, in minutes. | `.env` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | How long a refresh token stays valid, in days. Users must re-login after this period. | `.env` |

### CORS

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated list of allowed origins for cross-origin requests. In production, set to your actual domain(s). Example: `https://app.zotta.tt,https://zotta.tt`. | `.env` |

### Credit Bureau Integration

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `CREDIT_BUREAU_PROVIDER` | `mock` | Which credit bureau to use. `mock` returns simulated data. Set to `avknowles` for live AV Knowles integration. | `.env` |
| `AV_KNOWLES_API_URL` | *(empty)* | AV Knowles API base URL. Required only when `CREDIT_BUREAU_PROVIDER=avknowles`. | `.env` |
| `AV_KNOWLES_API_KEY` | *(empty)* | AV Knowles API key. Required only when `CREDIT_BUREAU_PROVIDER=avknowles`. | `.env` |
| `AV_KNOWLES_WEB_URL` | *(empty)* | AV Knowles web portal login URL. Used by the browser-based bureau inquiry. | `.env` |
| `AV_KNOWLES_USERNAME` | *(empty)* | AV Knowles web portal username. Used by the browser-based bureau inquiry. | `.env` |
| `AV_KNOWLES_PASSWORD` | *(empty)* | AV Knowles web portal password. Used by the browser-based bureau inquiry. | `.env` |

### ID Verification

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `ID_VERIFICATION_PROVIDER` | `mock` | ID document verification provider. `mock` simulates verification. Set to the provider name for live integration. | `.env` |

### Twilio (WhatsApp Notifications)

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `TWILIO_ACCOUNT_SID` | *(empty)* | Twilio Account SID (starts with `AC`). Get from [Twilio Console](https://www.twilio.com/console). Required for WhatsApp notifications. | `.env` |
| `TWILIO_AUTH_TOKEN` | *(empty)* | Twilio Auth Token. Get from Twilio Console. | `.env` |
| `TWILIO_WHATSAPP_NUMBER` | `whatsapp:+14155238886` | Twilio WhatsApp sender number. The default is the Twilio sandbox number. In production, use your own Twilio WhatsApp-enabled number with the `whatsapp:` prefix. | `.env` |
| `WHATSAPP_SANDBOX_PHONE` | *(empty)* | Override recipient phone number for non-production environments. When `ENVIRONMENT != production`, **all** WhatsApp messages are redirected to this number instead of the actual customer's phone. This prevents accidentally messaging real customers during development. | `.env` |

> **Important:** In `development` mode, every WhatsApp message goes to `WHATSAPP_SANDBOX_PHONE` regardless of the intended recipient. This is a safety measure. Set this to your personal phone number for testing.

### OpenAI

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key for the Customer Support chatbot and AI-powered summaries (Customer 360 view). If empty, the chatbot falls back to a rule-based response system. | `.env` |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use. `gpt-4o-mini` balances cost and quality. Alternatives: `gpt-4o` (better quality, higher cost), `gpt-3.5-turbo` (cheaper, lower quality). | `.env` |

### File Storage

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `UPLOAD_DIR` | `./uploads` | Directory for uploaded documents (ID photos, bank statements, contracts). Relative to the backend working directory. In Docker, this is mapped to a volume. | `.env` |
| `MAX_UPLOAD_SIZE_MB` | `10` | Maximum file upload size in megabytes. Files larger than this are rejected. | `.env` |

### Lender / Company Info

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `LENDER_NAME` | `Zotta` | Company name displayed in contracts, notifications, and the chatbot persona. | `.env` |
| `LENDER_ADDRESS` | `No. 3 The Summit, St. Andrews Wynd Road, Moka, Maraval, Trinidad and Tobago` | Company address used in generated hire purchase agreement contracts. | `.env` |

### Customer Support Chat Timeouts

These control the automated lifecycle of customer support chat conversations.

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `CONVERSATION_NUDGE_MINUTES` | `5` | Minutes of borrower inactivity before the chatbot sends a nudge message ("Are you still there?"). | `.env` |
| `CONVERSATION_SAVE_SUMMARY_MINUTES` | `30` | Minutes of inactivity before the system saves a conversation summary for backoffice review. | `.env` |
| `CONVERSATION_FOLLOWUP_1_DAYS` | `1` | Days after conversation ends before the first follow-up message is sent. | `.env` |
| `CONVERSATION_FOLLOWUP_2_DAYS` | `3` | Days after conversation ends before the second follow-up message is sent. | `.env` |
| `CONVERSATION_EXPIRE_DAYS` | `7` | Days after last activity before a conversation is marked as expired/closed. | `.env` |

### Frontend

| Variable | Default | Description | Where to change |
|----------|---------|-------------|-----------------|
| `VITE_API_URL` | *(empty)* | Backend API URL for the frontend. When empty, the Vite dev server proxies API calls automatically (recommended for local dev). Set to the full backend URL when running in Docker or production (e.g., `http://localhost:8000`). | `.env` |

> **Note:** `VITE_` prefixed variables are baked into the frontend bundle at **build time** (Vite requirement). Changing this after building requires a rebuild.

---

## Port Mappings

These are configured in `docker-compose.yml` (dev) and `docker-compose.prod.yml` (prod).

| Service | Port | Purpose | Config file |
|---------|------|---------|-------------|
| Frontend (Vite dev server) | `5173` | Consumer portal + Back-office UI | `docker-compose.yml` |
| Backend (FastAPI / Uvicorn) | `8000` | REST API + Swagger docs at `/docs` | `docker-compose.yml` |
| PostgreSQL | `5432` | Database (exposed for local tools like pgAdmin, DBeaver) | `docker-compose.yml` |
| Redis | `6379` | Task queue broker (exposed for debugging with `redis-cli`) | `docker-compose.yml` |
| Nginx (production only) | `80` | Reverse proxy serving frontend + API | `docker-compose.prod.yml` |

To change a port mapping, edit the `ports` section in the relevant `docker-compose*.yml` file. For example, to change the backend port to `9000`:

```yaml
backend:
  ports:
    - "9000:8000"   # host:container
```

---

## E2E Test Configuration

Configured in `playwright.config.ts` at the project root.

| Setting | Value | Description |
|---------|-------|-------------|
| `testDir` | `./e2e` | Directory containing test files |
| `baseURL` | `http://localhost:5173` | Frontend URL used by Playwright tests |
| `timeout` | `30000` (30 seconds) | Max time per test before failure |
| `workers` | `1` | Tests run sequentially (required because they share database state) |
| `retries` | `0` | No automatic retries |
| `browser` | Chromium | Only Chromium is configured |
| `CI` env var | *(not set locally)* | When `CI=true`, `forbidOnly` is enabled (prevents `.only` tests from passing in CI) |

The E2E tests also reference two hardcoded URLs inside `e2e/zotta.spec.ts`:
- `API = http://localhost:8000/api` — backend API base
- `BASE = http://localhost:5173` — frontend base

---

## Docker Volume Mounts

| Mount | Purpose | Config file |
|-------|---------|-------------|
| `pgdata` | Persists PostgreSQL data across container restarts | `docker-compose.yml` |
| `./uploads` → `/app/uploads` | Shared upload directory between host and container | `docker-compose.yml` |
| `./.env` → `/app/.env:ro` | Root `.env` mounted read-only into backend container | `docker-compose.yml` |
| `uploads` (named volume) | Production upload storage | `docker-compose.prod.yml` |

---

## How Variables Flow Through the System

```
.env (root)
 │
 ├─► backend/app/config.py     (pydantic-settings reads .env → settings singleton)
 │       └─► All backend code imports: from app.config import settings
 │
 ├─► docker-compose.yml         (env_file: .env → passed to containers)
 │       ├─► db container        (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)
 │       ├─► backend container   (all vars + overridden DATABASE_URL, REDIS_URL)
 │       ├─► celery container    (same as backend)
 │       └─► frontend container  (VITE_API_URL only)
 │
 └─► .env.production            (same structure, different values for prod)
         └─► docker-compose.prod.yml (env_file: .env.production)
```

---

## Production Checklist

Before deploying to production, ensure these variables are changed from their defaults:

| Variable | Action |
|----------|--------|
| `ENVIRONMENT` | Set to `production` |
| `DEBUG` | Set to `false` |
| `LOG_LEVEL` | Set to `WARNING` or `ERROR` |
| `POSTGRES_PASSWORD` | Set a strong, unique password |
| `SECRET_KEY` | Generate with `openssl rand -hex 32` |
| `CORS_ORIGINS` | Set to your actual domain(s) |
| `DATABASE_URL` / `DATABASE_URL_SYNC` | Update to match new password |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Set real Twilio credentials (or leave empty to disable) |
| `TWILIO_WHATSAPP_NUMBER` | Set to your production WhatsApp number |
| `WHATSAPP_SANDBOX_PHONE` | Leave empty in production (messages go to real customers) |
| `OPENAI_API_KEY` | Set your production API key (or leave empty for fallback bot) |

---

## Adding a New Variable

1. Add the variable to `.env`, `.env.example`, and `.env.production`
2. Add a corresponding field to the `Settings` class in `backend/app/config.py`
3. Access it in code via `from app.config import settings` then `settings.your_variable`
4. If it needs to be available inside Docker containers, it is automatically passed via `env_file: .env`
5. If Docker Compose needs to override it (like DB host), add an `environment:` entry in `docker-compose.yml`


AV Knowles credentials are stored in `.env` (never committed to git):
- `AV_KNOWLES_WEB_URL` — Login page URL
- `AV_KNOWLES_USERNAME` — Web portal username
- `AV_KNOWLES_PASSWORD` — Web portal password