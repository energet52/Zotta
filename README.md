# Zotta — Consumer Lending Platform

Zotta is a full-stack consumer lending management system built for the Caribbean market (Trinidad & Tobago). It covers the entire lending lifecycle — origination, underwriting, disbursement, servicing, collections, and accounting — with AI-powered automation throughout.

## Architecture

```
┌──────────────────┐       ┌───────────────────┐
│  Consumer Portal  │       │  Back-Office Portal│
│  (React/TS)       │       │  (React/TS)        │
└────────┬─────────┘       └────────┬──────────┘
         │                          │
         └──────────┬───────────────┘
                    │
          ┌─────────▼──────────┐
          │   FastAPI Backend   │
          │                    │
          │  Decision Engine   │──────► Credit Bureau (AV Knowles)
          │  Scorecard Engine  │──────► OpenAI GPT-4o (AI services)
          │  Collections AI    │──────► Twilio (WhatsApp)
          │  General Ledger    │
          │  Sector Analysis   │
          │  User Management   │
          └─────────┬──────────┘
                    │
          ┌─────────▼───┐  ┌─────────┐
          │ PostgreSQL   │  │  Redis   │
          │ (50+ tables) │  │ + Celery │
          └─────────────┘  └─────────┘
```

## Module Overview

### 1. Loan Origination & Underwriting

The core lending workflow from application to disbursement.

- **Consumer Portal** — Multi-step loan application with hire-purchase item selection, document upload (ID, proof of income), digital contract signature, and real-time status tracking.
- **Staff-Created Applications** — Back-office users can create applications on behalf of walk-in customers.
- **Application Queue** — Filterable, sortable queue for underwriters with priority indicators.
- **Application Review** — Full application details, applicant profile, documents, references, credit bureau report, AI bank statement analysis, and decision controls (approve / decline / counterpropose).
- **Contract Generation** — Automated hire-purchase agreement generation from DOCX templates with digital signature capture.

### 2. Decision Engine

Two-phase automated decisioning combining credit scoring and configurable business rules.

- **Credit Scoring** — Weighted scorecard model (300–850 range) with risk band mapping.
- **Business Rules** — 21 configurable rules (R01–R21) covering income verification, employment stability, debt-to-income ratio, loan-to-income ratio, age limits, geographic restrictions, employer sector risk, and scorecard score thresholds.
- **Credit Bureau Integration** — Adapter pattern with mock AV Knowles implementation ready for real provider integration.
- **ID Verification** — OCR-powered ID parsing (OpenAI Vision) with mock verification service.
- **Bank Statement Analysis** — AI-powered income and spending pattern analysis from uploaded CSV/PDF bank statements.

### 3. Credit Scoring Module

Full scorecard management with champion-challenger framework and performance monitoring.

- **Scorecard Management** — Create, edit, clone, import (CSV), and retire scorecards. Each scorecard has characteristics, bins (range/category/default), weight multipliers, and base scores.
- **Editable Score Script** — Human-readable Python scoring script auto-generated from the scorecard. Edit the script directly and changes sync back to characteristics & bins (and vice versa).
- **Champion-Challenger Framework** — Run multiple scorecards simultaneously with configurable traffic allocation. Shadow mode for safe testing, challenger mode with real traffic, and one-click promotion to champion.
- **Performance Monitoring** — Gini coefficient, KS statistic, PSI (Population Stability Index), AUC-ROC, score band analysis, vintage analysis, and automated health alerts when metrics degrade.
- **Live Calculation & What-If** — Test scorecard against sample data with step-by-step score trace, or run what-if analysis to simulate the impact of changing applicant data.
- **Batch Scoring** — Upload a CSV of applicants for bulk scoring with summary statistics.
- **Audit Trail** — Every edit (points, weights, cutoffs, script changes, promotions) is logged with timestamps and justifications.

### 4. Scoring & Business Rules

Configurable business rules engine with AI-assisted rule generation.

- **Rules Registry** — 21 built-in rules with enable/disable toggles, configurable thresholds, and severity levels (hard decline, soft decline, refer to manual review).
- **Rule R21: Scorecard Score** — Bridges the scorecard module to the rules engine. Auto-decline below threshold, manual review in the middle band, auto-approve above.
- **AI Rule Generator** — Generate new business rules from natural language descriptions using GPT-4o.
- **Rules Management UI** — Edit thresholds, toggle rules, preview impact — all without code changes.

### 5. Collections Module

AI-first collections management for delinquent loans.

- **Collections Queue** — Prioritized queue of delinquent cases with days-past-due, risk tier, and last contact information. Filterable by status, risk tier, agent assignment, and DPD bands.
- **Case Detail View** — Full case view with AI-generated Next Best Action (NBA), propensity-to-pay scoring, behavioral pattern analysis, and similar borrower outcomes.
- **Promise-to-Pay (PTP)** — Track and manage payment promises with automatic status checking.
- **Settlement Offers** — Auto-calculated settlement amounts with approval workflows.
- **Compliance Engine** — Configurable compliance rules for contact frequency, time-of-day restrictions, and channel permissions per jurisdiction.
- **AI Daily Briefing** — AI-generated daily summary of collections portfolio with key actions and risk highlights.
- **AI Message Drafting** — Generate context-aware collection messages for WhatsApp, email, and SMS.
- **Agent Performance** — Track resolution rates, PTP rates, collection amounts, and SLA compliance per agent.
- **WhatsApp Integration** — Twilio-powered WhatsApp messaging with conversation history and template management.

### 6. Customer 360

Unified customer view aggregating data from all system modules.

- **Overview** — Contact information, employment details, income, and profile completeness.
- **Applications Tab** — All loan applications with status, amounts, and decision history.
- **Loans Tab** — Active and historical loans with payment performance.
- **Collections Tab** — Collection cases, PTP history, and settlement offers.
- **Communications Tab** — All conversations, comments, and WhatsApp messages.
- **Documents Tab** — Uploaded ID documents, proof of income, bank statements.
- **Timeline** — Chronological event timeline across all system interactions.
- **AI Summary & Q&A** — GPT-powered natural language summary and question answering about any customer.

### 7. Hire-Purchase Catalog

Product catalog management for hire-purchase lending.

- **Merchants** — Manage merchant partners with branches and geographic locations.
- **Categories** — Product categories (electronics, furniture, appliances, etc.) assignable per merchant.
- **Credit Products** — Configurable loan products with term ranges, rate ranges, fee structures, and score-based eligibility tiers.
- **Payment Calculator** — Amortization schedules with fee breakdowns for any product/term combination.

### 8. General Ledger

Double-entry accounting system with AI-powered analytics.

- **Chart of Accounts** — Hierarchical account structure (assets, liabilities, equity, revenue, expenses) with sub-accounts.
- **Journal Entries** — Create, approve, post, and reverse journal entries with maker-checker workflow.
- **Automated Mapping** — Templates that automatically generate GL entries from loan events (disbursement, payment, provision, write-off).
- **Financial Statements** — Balance sheet, income statement, and trial balance generation for any date range.
- **Accounting Periods** — Fiscal period management with period-close automation.
- **Anomaly Detection** — AI-powered detection of unusual journal entries and patterns.
- **Natural Language Queries** — Ask questions about GL data in plain English (e.g., "What was total interest income last month?").
- **Forecasting** — AI-powered financial forecasting based on historical GL data.
- **Reconciliation** — Automated reconciliation between sub-ledger and GL balances.

### 9. Sector Analysis & Risk

Portfolio concentration monitoring and sector risk management.

- **Concentration Dashboard** — Visual breakdown of portfolio by industry sector with risk indicators.
- **Sector Detail** — Deep-dive into any sector: exposure, default rates, growth trends, and risk metrics.
- **Sector Policies** — Configurable concentration limits per sector with maker-checker approval workflow.
- **Alert Rules** — Automated alerts when sector concentration exceeds thresholds.
- **Macro Indicators** — Track macroeconomic indicators (GDP, unemployment, inflation) by sector.
- **Stress Testing** — Simulate portfolio impact under adverse economic scenarios.
- **Heatmap** — Visual risk heatmap across all sectors.

### 10. Reporting & Analytics

Comprehensive reporting suite for operational and regulatory needs.

- **Dashboard** — Real-time KPIs: applications, approvals, disbursements, portfolio at risk, collection rates.
- **Standard Reports** — Aged receivables, exposure analysis, interest & fees, loan statements, portfolio summary, loan book, decision audit trail, underwriter performance, collection reports, disbursement reports.
- **CSV Export** — All reports exportable to CSV.
- **Report History** — Stored generated reports for historical reference.

### 11. Error Monitoring

Built-in application error tracking and resolution.

- **Real-Time Dashboard** — Error counts, severity breakdown, top error types, and top failing endpoints.
- **Error Capture** — Middleware automatically logs all 4xx (except 401/403) and 5xx errors with full context: request body, traceback, user info, response time.
- **Resolution Workflow** — Mark errors as resolved/unresolved, add resolution notes, bulk resolve.

### 12. AI-Powered WhatsApp Chatbot

Conversational AI for customer self-service and support.

- **Intent Classification** — Automatic detection of loan inquiry, application status, payment, and support intents.
- **Conversation State Machine** — Guided flows for pre-qualification, application submission, and payment inquiries.
- **Application from Chat** — Start and complete loan applications entirely through WhatsApp.
- **Escalation** — Automatic escalation to human agents for complex cases.
- **Staff Conversations** — Back-office initiated conversations with customers.

### 13. User Management

Enterprise-grade identity, authentication, and access control.

- **User Administration** — Full CRUD for users with status management (active, suspended, locked, deactivated, pending activation). Search, filter, and bulk operations.
- **Role-Based Access Control (RBAC)** — 10 system roles (System Administrator, Senior Underwriter, Junior Underwriter, Loan Officer, Collections Agent, Collections Manager, Credit Risk Manager, Finance Manager, Compliance Officer, Applicant) with 54 granular permissions across 13 modules.
- **Permission Management** — Assign/revoke permissions per role with scope levels (all, own, team). Role hierarchy with parent-child inheritance.
- **Multi-Factor Authentication (MFA)** — TOTP-based MFA via authenticator apps (Google Authenticator, Authy). Setup wizard with QR code provisioning, verification flow, and disable option.
- **Session Management** — JWT-based sessions with unique JTI tracking, device/IP recording, active session listing, and individual/bulk session revocation.
- **Account Security** — Automatic account lockout after 5 failed login attempts (30-minute cooldown), forced password change, login attempt recording with IP and user agent tracking.
- **Maker-Checker Workflow** — Sensitive operations (role changes, user deactivation) can require approval from a second administrator.
- **AI Role Recommendations** — Intelligent role suggestions based on department and job title using keyword matching with OpenAI fallback.
- **AI Admin Queries** — Natural language questions about user data (e.g., "How many active users?", "Users without MFA") with pattern matching and OpenAI fallback.
- **Login Anomaly Detection** — Rule-based heuristics detecting new IP/device, brute force attempts, unusual login times, rapid IP switching, and impossible travel.
- **Audit Logging** — All user management actions (create, update, role assignment, status change, login) logged with actor, timestamp, and change details.

### 14. Consumer Self-Service

Customer-facing portal for loan management.

- **Dashboard** — Application overview with status indicators and quick actions.
- **My Loans** — View active loans, payment schedules, and make online payments.
- **Notifications** — Receive updates on application status, payment reminders, and collection messages.
- **Profile Management** — Update personal and employment information.
- **Chat** — Real-time chat with support agents.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| Frontend | TypeScript, React 19, Vite, Tailwind CSS 4, React Router v6 |
| Database | PostgreSQL 16 (50+ tables, 18 migrations) |
| Cache / Queue | Redis 7, Celery |
| AI | OpenAI GPT-4o-mini (scoring, NLP, analysis, rule generation) |
| Auth | JWT (access + refresh), TOTP MFA (pyotp), bcrypt |
| WhatsApp | Twilio WhatsApp Business API |
| Testing | Pytest (17 test suites), Playwright (352 E2E tests) |
| Infrastructure | Docker Compose, AWS CDK (ECS Fargate, RDS, CloudFront), EC2 |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for frontend development)
- Python 3.12+ (for backend development)

### Run with Docker Compose

```bash
# Clone the repo
git clone https://github.com/energet52/Zotta.git
cd Zotta

# Copy environment config
cp .env.example .env

# Start all services
docker compose up --build

# In another terminal, seed the database
docker compose exec backend python seed.py
```

The application will be available at:
- **Consumer Portal**: http://localhost:5173
- **Back-Office Portal**: http://localhost:5173/backoffice
- **API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs

### Run Without Docker (Development)

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

## Test Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@zotta.tt | Admin123! |
| Senior Underwriter | sarah.uw@zotta.tt | Underwriter1! |
| Junior Underwriter | kevin.uw@zotta.tt | Underwriter1! |
| Applicant | john.doe@email.com | Applicant1! |

## Project Structure

```
Zotta/
├── backend/                    # Python FastAPI backend
│   ├── app/
│   │   ├── api/                # 18 API route modules
│   │   ├── models/             # 27 SQLAlchemy model files (50+ entities)
│   │   ├── services/           # 45 service modules
│   │   │   ├── decision_engine/    # Scoring + rules engine
│   │   │   └── gl/                 # General ledger services
│   │   ├── middleware/         # Error capture + session tracking
│   │   ├── migrations/         # 18 Alembic migrations
│   │   ├── tasks/              # Celery async tasks
│   │   └── templates/          # DOCX contract templates
│   ├── tests/                  # 17 Pytest test suites
│   └── seed.py                 # Test data seeder
├── frontend/                   # React TypeScript frontend
│   └── src/
│       ├── apps/
│       │   ├── consumer/       # 9 consumer portal pages
│       │   └── backoffice/     # 49 back-office pages
│       ├── components/         # 15 shared UI components
│       ├── hooks/              # Custom hooks (usePermission)
│       ├── api/                # API client (endpoints.ts)
│       └── store/              # Zustand state management
├── e2e/                        # Playwright E2E tests (352 tests)
├── infrastructure/             # AWS deployment
│   ├── aws/                    # CDK stack (ECS Fargate, RDS, CloudFront)
│   ├── ec2/                    # Single-server deployment scripts
│   └── scripts/                # Deployment automation
├── docs/                       # Documentation
└── docker-compose.yml          # Local development environment
```

## Deployment

### Option A: EC2 with Docker Compose (~$12-15/month, $0 when stopped)

The simplest and cheapest option. One command creates an EC2 server and runs everything:

```bash
cd infrastructure/ec2
./launch-ec2.sh
```

See [docs/ec2-deployment.md](docs/ec2-deployment.md) for the full guide.

### Option B: Full AWS (ECS Fargate + RDS + CloudFront) (~$70-80/month)

Production-grade with auto-scaling, managed database, and CDN:

```bash
cd infrastructure/scripts
./deploy.sh
```

See [docs/deployment.md](docs/deployment.md) for the full guide.

## Documentation

- [Local Setup](docs/local-setup.md) — Run on your own machine (no AWS needed)
- [EC2 Deployment](docs/ec2-deployment.md) — Deploy to a single AWS server (cheapest)
- [Full AWS Deployment](docs/deployment.md) — Production-grade AWS deployment
- [Architecture](docs/architecture.md) — System design and component details
- [Collections Module](docs/collections-module.md) — Collections module business requirements
- [Customer 360 Requirements](docs/customer-360-business-requirements.md) — Customer 360 specification
- [API Reference](http://localhost:8000/docs) — Auto-generated OpenAPI docs (run backend first)
- [User Guide](docs/user-guide.md) — How to use the consumer and back-office portals

## License

Proprietary — Zotta Financial Services
