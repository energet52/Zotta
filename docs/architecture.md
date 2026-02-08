# Zotta Architecture

## System Overview

Zotta is a monorepo containing a Python FastAPI backend, React/TypeScript frontend, and AWS CDK infrastructure code. The system follows a layered architecture with clear separation between API, business logic, and data access layers.

## Component Architecture

### Backend (FastAPI)

The backend is organized into three layers:

1. **API Layer** (`app/api/`) - HTTP route handlers, request validation, response serialization
2. **Service Layer** (`app/services/`) - Business logic, decision engine, external integrations
3. **Data Layer** (`app/models/`) - SQLAlchemy ORM models, database schema

### Frontend (React/TypeScript)

The frontend uses a multi-app structure within a single Vite project:

- `apps/consumer/` - Consumer-facing loan application portal
- `apps/backoffice/` - Internal underwriter portal
- `components/` - Shared UI components (Button, Card, Badge, Input, Select)
- `store/` - Zustand state management (auth store)
- `api/` - Axios HTTP client with JWT interceptors

### Decision Engine

The decision engine runs in two phases:

**Phase A: Credit Scoring (`scoring.py`)**
- Weighted scorecard model with 7 factors
- Blends internal scoring (60%) with bureau score (40%)
- Output: 300-850 score mapped to risk bands A-E

**Phase B: Business Rules (`rules.py`)**
- Configurable rules stored as JSON in database
- 8 rules evaluated: age, income, DTI ratio, LTI ratio, employment, loan amount, blacklist, ID verification
- Rules have severity: "hard" (blocks approval) or "soft" (warning)
- Output: auto_approve, auto_decline, or manual_review

### Credit Bureau Integration

Uses the Adapter pattern:
- `CreditBureauAdapter` - Abstract base class
- `MockBureauAdapter` - Generates synthetic Trinidad credit data (deterministic per national ID)
- `AVKnowlesAdapter` - Stub ready for real API integration
- Toggled via `CREDIT_BUREAU_PROVIDER` environment variable

### Authentication & Authorization

- JWT-based authentication (access + refresh tokens)
- Role-Based Access Control (RBAC): applicant, junior_underwriter, senior_underwriter, admin
- `require_roles()` dependency factory for endpoint-level authorization

## Database Schema

### Key Tables

| Table | Purpose |
|-------|---------|
| `users` | All users (applicants + staff) with roles |
| `applicant_profiles` | Personal, employment, financial details |
| `loan_applications` | Core application with status workflow |
| `documents` | Uploaded file metadata |
| `credit_reports` | Bureau pull results (JSON) |
| `decisions` | Engine output + underwriter override |
| `decision_rules_config` | Versioned business rules |
| `audit_log` | All state changes |
| `chat_sessions` / `chat_messages` | WhatsApp conversation history |

### Loan Status Workflow

```
DRAFT → SUBMITTED → UNDER_REVIEW → CREDIT_CHECK → DECISION_PENDING
                                                          │
                                          ┌───────────────┼───────────────┐
                                          ▼               ▼               ▼
                                     APPROVED        DECLINED      AWAITING_DOCUMENTS
                                          │                              │
                                     OFFER_SENT                     (re-submit)
                                          │
                                  ┌───────┴───────┐
                                  ▼               ▼
                              ACCEPTED     REJECTED_BY_APPLICANT
                                  │
                              DISBURSED
```

## AWS Deployment Architecture

- **Frontend**: S3 + CloudFront (CDN with SPA routing)
- **Backend API**: ECS Fargate behind Application Load Balancer
- **Celery Workers**: ECS Fargate (separate service)
- **Database**: RDS PostgreSQL (private subnet)
- **Cache/Broker**: ElastiCache Redis (private subnet)
- **Documents**: S3 bucket (encrypted)
- **Secrets**: AWS Secrets Manager
- **IaC**: AWS CDK (Python)

## Security Considerations

- Passwords hashed with bcrypt
- JWT tokens with configurable expiry
- CORS restricted to known origins
- File upload size limits
- Role-based access control on all endpoints
- Secrets managed via environment variables (AWS Secrets Manager in production)
- Database in private subnet (production)
- S3 buckets with block public access
