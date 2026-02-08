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
