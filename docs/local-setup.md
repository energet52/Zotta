# Running Zotta on Your Local Machine

This guide walks you through running the complete Zotta application on your own computer. No AWS account needed.

## What You Need Installed

### 1. Docker Desktop (required)

Docker runs the application in isolated containers -- think of it as mini virtual machines that contain everything the app needs.

**Install:**
- Go to https://www.docker.com/products/docker-desktop/
- Download for your operating system (Mac / Windows / Linux)
- Install and open it
- Wait until the Docker icon in your menu bar/system tray shows "Docker Desktop is running"

**Verify it works:** Open Terminal (Mac) or Command Prompt (Windows) and type:
```bash
docker --version
```
You should see something like `Docker version 27.x.x`

### 2. Git (required)

Git downloads the code from GitHub.

**Mac:** It's pre-installed. If not: `xcode-select --install`

**Windows:** Download from https://git-scm.com/download/win

**Verify:** `git --version`

---

## Step-by-Step Setup

### Step 1: Download the code

Open Terminal and run:
```bash
cd ~/Downloads
git clone https://github.com/energet52/Zotta.git
cd Zotta
```

### Step 2: Create your environment file

```bash
cp .env.example .env
```

That's it -- the defaults work for local development. No changes needed.

### Step 3: Start the application

```bash
docker compose up --build
```

**The first time takes 3-5 minutes** because Docker downloads base images (Python, Node.js, PostgreSQL, Redis) and installs dependencies. Subsequent starts take about 15 seconds.

You'll see a lot of log output scrolling by. Wait until you see lines like:
```
backend-1     | INFO:     Uvicorn running on http://0.0.0.0:8000
frontend-1    | VITE v6.x.x  ready in xxx ms
```

### Step 4: Seed the database with test data

Open a **new** Terminal window/tab (keep the first one running) and run:
```bash
cd ~/Downloads/Zotta
docker compose exec backend python seed.py
```

You'll see:
```
Seeding database...
Database seeded successfully!
  - Admin: admin@zotta.tt / Admin123!
  - Senior UW: sarah.uw@zotta.tt / Underwriter1!
  - Applicant: john.doe@email.com / Applicant1!
  ...
```

### Step 5: Open in your browser

| What | URL |
|------|-----|
| **Consumer Portal** (apply for loans) | http://localhost:5173 |
| **API Documentation** (Swagger) | http://localhost:8000/docs |

Both the consumer portal and back-office portal use the same URL. When you log in:
- Applicant accounts go to the **Consumer Portal**
- Staff accounts go to the **Back-Office Portal**

---

## Test Accounts

| Who | Email | Password | What they see |
|-----|-------|----------|---------------|
| Admin | admin@zotta.tt | Admin123! | Back-office dashboard, queue, reports |
| Senior Underwriter | sarah.uw@zotta.tt | Underwriter1! | Back-office with full decision powers |
| Junior Underwriter | kevin.uw@zotta.tt | Underwriter1! | Back-office with limited powers |
| Applicant (John) | john.doe@email.com | Applicant1! | Consumer portal with existing application |
| Applicant (Maria) | maria.garcia@email.com | Applicant1! | Consumer portal with existing application |

---

## Everyday Commands

All commands run from the `Zotta` folder.

### Start the application
```bash
docker compose up
```
Add `-d` to run in the background (no log output):
```bash
docker compose up -d
```

### Stop the application
If running in foreground: press `Ctrl + C`

If running in background:
```bash
docker compose down
```

### View logs (when running in background)
```bash
docker compose logs -f
```
Press `Ctrl + C` to stop viewing (the app keeps running).

### Rebuild after code changes
```bash
docker compose up --build
```

### Reset the database (start fresh)
```bash
docker compose down -v
docker compose up --build
# Then re-seed:
docker compose exec backend python seed.py
```

### Check what's running
```bash
docker compose ps
```

---

## Running Tests

### E2E (Browser) Tests

End-to-end tests use Playwright to automate the browser and verify the hire-purchase flow, admin pages, and login.

**Prerequisites:**
- Application running (`docker compose up`)
- Database seeded (`docker compose exec backend python seed.py`)

**First-time setup:**
```bash
cd Zotta
npm install
npx playwright install chromium
```

**Run all e2e tests:**
```bash
npm run test:e2e
```

**Run with UI (interactive debugging):**
```bash
npm run test:e2e:ui
```

**What the tests cover:**
- **Auth:** Login, register, applicant/admin login redirects
- **Consumer:** Dashboard, hire-purchase flow (steps 1–2), full apply & submit, application status, profile
- **Backoffice:** Dashboard, applications queue, application review, loan book, collections, reports, new application form, products list, product detail, merchants, categories

**Test accounts used:**
- Applicant: `marcus.mohammed0@email.com` / `Applicant1!`
- Admin: `admin@zotta.tt` / `Admin123!`

### Backend Tests

```bash
docker compose exec backend pytest
```

---

## Sharing Remotely with ngrok

ngrok creates a secure public URL that tunnels to your local machine. This lets someone test the full Zotta application from anywhere — they just need the link.

### Prerequisites

- **ngrok installed:** `brew install ngrok` (Mac) or download from https://ngrok.com/download
- **ngrok account:** Sign up at https://ngrok.com and copy your authtoken
- **Authenticate once:**
  ```bash
  ngrok config add-authtoken YOUR_AUTH_TOKEN
  ```
- **Application running** locally (`docker compose up` + seeded)

### How it works

The Vite dev server (port 5173) serves the frontend **and** proxies all `/api` requests to the backend (port 8000). This means you only need **one ngrok tunnel** — on port 5173 — and everything works through a single URL.

```
Remote browser
     │
     └──► https://your-subdomain.ngrok-free.dev
               │
               └──► ngrok tunnel ──► localhost:5173 (Vite)
                                          │
                                    ┌─────┴─────┐
                                    │ Frontend   │  (React pages)
                                    │ /api/*     │──► localhost:8000 (FastAPI)
                                    └────────────┘
```

### Start the tunnel

With a paid plan, use `--url` to claim a stable subdomain on `ngrok.app`:

```bash
ngrok http 5173 --url zotta-demo.ngrok.app
```

ngrok prints the public URL:
```
Forwarding   https://zotta-demo.ngrok.app -> http://localhost:5173
```

Send **https://zotta-demo.ngrok.app** to your tester. They can log in with any of the test accounts listed above.

> **Free plan alternative:** If you don't have a paid plan, run `ngrok http 5173` (without `--url`). You'll get a random `*.ngrok-free.dev` URL that changes on every restart, and visitors will see an ngrok interstitial page.

### Add the ngrok URL to CORS (first time only)

Add the ngrok domain to the `CORS_ORIGINS` line in your `.env` file:

```
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,https://zotta-demo.ngrok.app
```

Then restart the backend:
```bash
docker compose restart backend
```

> **Tip:** With a paid plan the domain is stable, so you only need to do this once. On the free plan the URL changes every restart, so you'd need to update `.env` each time.

### Useful ngrok commands

| Command | What it does |
|---------|-------------|
| `ngrok http 5173 --url zotta-demo.ngrok.app` | Start a tunnel to the full app (paid plan, stable URL) |
| `ngrok http 5173` | Start a tunnel to the full app (free plan, random URL) |
| `ngrok http 8000` | Start a tunnel to the backend API only (for webhooks, Postman) |
| Open http://127.0.0.1:4040 | ngrok inspection dashboard — view all requests in real time |

### Stop the tunnel

Press `Ctrl+C` in the terminal where ngrok is running, or:
```bash
pkill -f ngrok
```

### Twilio webhooks

If you're testing WhatsApp integration, point the Twilio webhook URL to your ngrok backend tunnel:

```
https://zotta-demo.ngrok.app/api/whatsapp/webhook
```

Configure this in the Twilio Console under **Messaging > Settings > WhatsApp sandbox**.

---

## Common Problems

### "Port 5432 already in use"
You have PostgreSQL running locally. Either stop it or change the port in `docker-compose.yml`.

**Mac:** `brew services stop postgresql`

### "Docker Desktop is not running"
Open the Docker Desktop application and wait for it to start.

### "Cannot connect to the Docker daemon"
Same as above -- Docker Desktop needs to be running.

### Frontend shows blank page or errors
Make sure the backend is running. Check with:
```bash
curl http://localhost:8000/api/health
```
Should return: `{"status":"healthy","service":"zotta-api","version":"0.1.0"}`

### "Database seeding failed"
Wait a few more seconds after `docker compose up` for PostgreSQL to be ready, then try the seed command again.

---

## Architecture (What's Running)

When you run `docker compose up`, five containers start:

```
Your Browser
     │
     ├──► localhost:5173  ──► [Frontend Container] React dev server
     │                              │
     └──► localhost:8000  ──► [Backend Container] FastAPI API
                                    │
                          ┌─────────┼─────────┐
                          ▼         ▼         ▼
                    [PostgreSQL] [Redis]  [Celery Worker]
                     port 5432  port 6379  (background tasks)
```

All five containers share a private network. Your browser talks to the frontend (port 5173) and the API (port 8000). The frontend proxies API calls to the backend automatically.
