# Collections Module — Upgraded Documentation

## Overview

The Zotta Collections Module manages the end-to-end recovery process for delinquent loans. This document describes the pragmatic upgrade that extends the original minimal module with case management, promise-to-pay tracking, settlement workflows, compliance guardrails, analytics dashboards, and AI next-best-action recommendations.

## Architecture

```
Backend                          Frontend
├── Models                       ├── CollectionsDashboard.tsx (KPIs, charts)
│   ├── CollectionCase           ├── Collections.tsx (enhanced queue)
│   ├── PromiseToPay             ├── CollectionDetail.tsx (6-tab detail)
│   ├── SettlementOffer          └── MyLoans.tsx (consumer self-service)
│   ├── ComplianceRule
│   ├── SLAConfig
│   └── CollectionsDashboardSnapshot
├── Services
│   └── collections_engine.py
├── API
│   └── collections.py (30+ endpoints)
├── Tasks
│   └── collection_reminders.py (4 Celery tasks)
└── Seed Data
```

## Database Tables

| Table | Purpose |
|---|---|
| `collection_cases` | One case per delinquent loan — DPD, stage, flags, NBA, SLA |
| `promises_to_pay` | PTP tracking with fulfillment status |
| `settlement_offers` | Settlement/restructuring offer lifecycle |
| `compliance_rules` | Per-jurisdiction contact rules (hours, caps, cooling-off) |
| `sla_configs` | SLA timers per delinquency stage |
| `collections_dashboard_snapshots` | Daily portfolio snapshots for trend analysis |

Migration: `backend/app/migrations/versions/017_collections_upgrade.py`

## Delinquency Stages

| Stage | DPD Range | Description |
|---|---|---|
| `early_1_30` | 1–30 days | SMS/WhatsApp reminders |
| `mid_31_60` | 31–60 days | Phone outreach, escalation |
| `late_61_90` | 61–90 days | Demand letters, settlement |
| `severe_90_plus` | 90+ days | Legal escalation |

## Case Statuses

- `open` — Newly created, no action yet
- `in_progress` — Agent assigned or contact made
- `settled` — Settlement accepted
- `closed` — Fully repaid or cured
- `legal` — Escalated to legal proceedings
- `written_off` — Written off as bad debt

## Next-Best-Action (NBA) Engine

The rule-based NBA engine evaluates each case and recommends the optimal action:

| Condition | Action | Confidence |
|---|---|---|
| DNC flag | `hold_do_not_contact` | 1.0 |
| Active dispute | `hold_dispute` | 1.0 |
| Vulnerability flag | `hold_vulnerability_review` | 0.95 |
| Hardship flag | `offer_hardship_plan` | 0.90 |
| DPD < 7, no contact | `send_whatsapp_reminder` | 0.85 |
| DPD < 7, contacted | `send_sms_reminder` | 0.80 |
| DPD 8–30 | `call_now` | 0.80 |
| DPD 8–30, 2+ broken PTP | `escalate_supervisor` | 0.85 |
| DPD 31–60 | `call_now` | 0.75 |
| DPD 31–60, 2+ broken PTP | `escalate_field` | 0.85 |
| DPD 61–90 | `send_demand_letter` | 0.80 |
| DPD 90+ | `escalate_legal` | 0.90 |

Agents can override NBA with a reason via `POST /cases/{id}/nba-override`.

## Settlement Calculator

Discount tiers based on DPD:

| DPD Range | Max Discount |
|---|---|
| 0–30 | 0% |
| 31–60 | 5% |
| 61–90 | 10% |
| 90+ | 20% |

Settlement options generated:
1. **Full Payment** — no discount, immediate
2. **Partial Settlement** — discounted lump sum (if DPD > 30)
3. **Short Plan** — 3 or 6 months, no discount
4. **Long Plan** — 12 months, requires approval (amounts > $1,000)

Discounts > 10% require supervisor approval.

## Compliance Rules

Per-jurisdiction rules enforce:
- **Contact hours** — e.g., 8:00–20:00 for Trinidad
- **Daily contact cap** — e.g., max 3 per day
- **Weekly contact cap** — e.g., max 10 per week
- **Cooling-off period** — e.g., 4 hours between contacts
- **Hard blocks** — Do Not Contact flag, active disputes

Pre-seeded jurisdictions: TT, JM, BB, GY.

## API Endpoints

### Queue & Cases
| Method | Path | Description |
|---|---|---|
| GET | `/collections/queue` | Enhanced queue with search, filters, NBA |
| GET | `/collections/cases` | List collection cases |
| GET | `/collections/cases/{id}` | Case detail |
| PATCH | `/collections/cases/{id}` | Update flags, assign agent |
| POST | `/collections/cases/{id}/nba-override` | Override NBA |
| POST | `/collections/cases/bulk-assign` | Bulk assign to agent |
| POST | `/collections/sync-cases` | Manual trigger sync + NBA |
| GET | `/collections/export-csv` | Export queue to CSV |

### Promise to Pay
| Method | Path | Description |
|---|---|---|
| POST | `/collections/cases/{id}/ptp` | Create PTP |
| GET | `/collections/cases/{id}/ptps` | List PTPs |
| PATCH | `/collections/ptps/{id}` | Update PTP status |

### Settlements
| Method | Path | Description |
|---|---|---|
| POST | `/collections/cases/{id}/settlement` | Create (auto-calc or manual) |
| GET | `/collections/cases/{id}/settlements` | List offers |
| PATCH | `/collections/settlements/{id}/approve` | Approve (supervisor+) |
| PATCH | `/collections/settlements/{id}/accept` | Accept offer |

### Dashboard & Compliance
| Method | Path | Description |
|---|---|---|
| GET | `/collections/dashboard` | Analytics KPIs + trend |
| GET | `/collections/dashboard/agent-performance` | Per-agent metrics |
| GET | `/collections/compliance-rules` | List rules |
| POST | `/collections/compliance-rules` | Create/update rule |
| POST | `/collections/check-compliance` | Check if contact allowed |

## Celery Tasks

| Task | Schedule | Description |
|---|---|---|
| `sync_cases` | Every 15 min | Sync overdue loans → collection cases, compute NBA |
| `check_ptps` | Daily 8:30 AM | Mark broken PTPs past grace period |
| `daily_snapshot` | Daily 11:55 PM | Generate portfolio snapshot |
| `check_overdue_and_notify` | Daily 9:00 AM | (Existing) Send WhatsApp reminders |

## Frontend Pages

### Back Office
- **Collections Queue** (`/backoffice/collections`) — Search, filters, sort, pagination, NBA badges, bulk assign, CSV export
- **Collections Dashboard** (`/backoffice/collections-dashboard`) — KPI cards, DPD aging chart, trend line, agent performance table
- **Collection Detail** (`/backoffice/collections/:id`) — 6 tabs:
  1. Case Overview (NBA, flags, SLA timers, compliance)
  2. Interaction History (legacy + new)
  3. WhatsApp Chat
  4. Promises to Pay (create, track, mark kept/broken)
  5. Settlements (auto-calculate, approve, accept)
  6. Compliance (contact status, history, rules)

### Consumer Self-Service
- **My Loans** (`/my-loans`) — Enhanced with:
  - Overdue alert banner with balance breakdown (principal, interest, fees)
  - "Request Payment Plan" button
  - "Raise Dispute" form with category and description

## Testing

### Backend Unit Tests
File: `backend/tests/test_collections_engine.py`
- DPD-to-stage mapping
- Priority score calculation
- NBA engine (all rule paths including flags, DPD ranges, broken promises)
- Settlement calculator (discount tiers, plan types, approval requirements)
- Model and enum coverage

### E2E API Tests
File: `e2e/zotta.spec.ts` (Collections Module section)
- Queue endpoint with search
- Cases CRUD and filtering
- PTP lifecycle
- Settlement auto-calculation
- Dashboard analytics
- Compliance rules CRUD
- Compliance check
- Case sync trigger
- Authorization checks

## Seed Data

The `seed.py` script creates:
- 4 compliance rules (TT, JM, BB, GY)
- 6 SLA configs
- ~20 collection cases with varied DPD, stages, and flags
- PTPs (mix of pending, kept, broken)
- Settlement offers
- 30 days of dashboard snapshots
