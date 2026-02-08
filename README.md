# Zotta - Consumer Lending Platform

Zotta is a full-stack consumer lending application built for the Trinidad and Tobago market. It provides a complete loan origination workflow from application to disbursement, with an AI-powered WhatsApp chatbot for customer support.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐
│  Consumer Portal │     │  Back-Office      │
│  (React/TS)      │     │  Portal (React/TS)│
└───────┬─────────┘     └───────┬──────────┘
        │                       │
        └───────┬───────────────┘
                │
        ┌───────▼───────────┐
        │  FastAPI Backend   │
        │  ┌──────────────┐ │     ┌──────────────┐
        │  │Decision Engine│ │────►│ AV Knowles   │
        │  │  Scoring      │ │     │ Credit Bureau │
        │  │  Rules        │ │     │ (Mocked)     │
        │  └──────────────┘ │     └──────────────┘
        │  ┌──────────────┐ │     ┌──────────────┐
        │  │WhatsApp Bot   │ │────►│ Twilio API   │
        │  └──────────────┘ │     └──────────────┘
        └───────┬───────────┘
                │
        ┌───────▼───┐  ┌─────────┐
        │ PostgreSQL │  │  Redis  │
        └───────────┘  └─────────┘
```

## Features

- **Consumer Portal**: Multi-step loan application, document upload, application status tracking
- **Back-Office Portal**: Underwriter queue, application review, decision controls with override capability
- **Decision Engine**: Two-phase evaluation with credit scoring (300-850) and configurable business rules
- **Credit Bureau Integration**: Adapter pattern with mock AV Knowles implementation (Trinidad)
- **ID Verification**: Mock verification service ready for real provider integration
- **Reporting**: Dashboard metrics, CSV export, risk distribution charts
- **AI WhatsApp Chatbot**: Twilio + OpenAI integration for applicant self-service
- **Audit Trail**: Full logging of all actions and state changes

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Alembic |
| Frontend | TypeScript, React 19, Vite, Tailwind CSS |
| Database | PostgreSQL 16 |
| Cache/Queue | Redis 7, Celery |
| AI | OpenAI GPT-4o-mini |
| WhatsApp | Twilio WhatsApp API |
| Infrastructure | Docker, AWS CDK (ECS Fargate, RDS, CloudFront) |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for frontend dev)
- Python 3.12+ (for backend dev)

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
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

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
├── backend/           # Python FastAPI backend
│   ├── app/
│   │   ├── api/       # API route handlers
│   │   ├── models/    # SQLAlchemy models
│   │   ├── services/  # Business logic
│   │   │   ├── decision_engine/   # Scoring + rules
│   │   │   └── credit_bureau/     # AV Knowles adapter
│   │   └── tasks/     # Celery async tasks
│   ├── tests/         # Pytest tests
│   └── seed.py        # Test data seeder
├── frontend/          # React TypeScript frontend
│   └── src/
│       ├── apps/
│       │   ├── consumer/     # Consumer portal pages
│       │   └── backoffice/   # Back-office pages
│       ├── components/       # Shared UI components
│       ├── api/              # API client
│       └── store/            # Zustand state
├── infrastructure/    # AWS CDK deployment
│   └── aws/
├── docs/              # Documentation
└── docker-compose.yml
```

## Deployment Options

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

- [Local Setup](docs/local-setup.md) - Run on your own machine (no AWS needed)
- [EC2 Deployment](docs/ec2-deployment.md) - Deploy to a single AWS server (cheapest)
- [Full AWS Deployment](docs/deployment.md) - Production-grade AWS deployment
- [Architecture](docs/architecture.md) - System design and component details
- [API Reference](http://localhost:8000/docs) - Auto-generated OpenAPI docs (run backend first)
- [User Guide](docs/user-guide.md) - How to use the consumer and back-office portals

## License

Proprietary - Zotta Financial Services
