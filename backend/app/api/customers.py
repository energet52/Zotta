"""Customer 360 API — staff-only endpoints for the full customer view.

Provides:
- GET  /{user_id}/360       — aggregated customer data
- GET  /{user_id}/timeline  — unified activity timeline
- POST /{user_id}/ai-summary — AI-generated account narrative
- POST /{user_id}/ask-ai    — conversational AI Q&A about the customer
- GET  /{user_id}/alerts     — credit bureau alerts
- PATCH /{user_id}/alerts/{alert_id} — update alert (acknowledge / take action)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth_utils import require_roles
from app.models.user import User, UserRole
from app.models.audit import AuditLog
from app.models.credit_bureau_alert import (
    CreditBureauAlert, AlertStatus,
)
from app.services.customer360 import (
    get_customer_360,
    get_customer_timeline,
    generate_ai_summary,
    ask_ai_about_customer,
    _row_to_dict, _ser,
)

logger = logging.getLogger(__name__)

router = APIRouter()

STAFF_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)


# ---------------------------------------------------------------------------
# GET /{user_id}/360
# ---------------------------------------------------------------------------

@router.get("/{user_id}/360")
async def customer_360(
    user_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Return the full Customer 360 payload."""
    data = await get_customer_360(user_id, db)
    if data is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return data


# ---------------------------------------------------------------------------
# GET /{user_id}/timeline
# ---------------------------------------------------------------------------

@router.get("/{user_id}/timeline")
async def customer_timeline(
    user_id: int,
    categories: Optional[str] = Query(None, description="Comma-separated category filter"),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Return a paginated, filterable timeline of customer events."""
    cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
    events = await get_customer_timeline(
        user_id, db,
        categories=cat_list,
        search=search,
        offset=offset,
        limit=limit,
    )
    return {"events": events, "offset": offset, "limit": limit}


# ---------------------------------------------------------------------------
# POST /{user_id}/ai-summary
# ---------------------------------------------------------------------------

@router.post("/{user_id}/ai-summary")
async def customer_ai_summary(
    user_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Generate (or regenerate) the AI account summary."""
    data = await get_customer_360(user_id, db)
    if data is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    summary = await generate_ai_summary(data)
    return summary


# ---------------------------------------------------------------------------
# POST /{user_id}/ask-ai
# ---------------------------------------------------------------------------

class AskAIRequest(BaseModel):
    question: str
    history: list[dict] | None = None


@router.post("/{user_id}/ask-ai")
async def customer_ask_ai(
    user_id: int,
    body: AskAIRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Ask a free-form question about a customer and get an AI answer."""
    data = await get_customer_360(user_id, db)
    if data is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    result = await ask_ai_about_customer(data, body.question, body.history)

    # Log to audit trail
    audit = AuditLog(
        entity_type="user",
        entity_id=user_id,
        action="ask_ai",
        user_id=current_user.id,
        details=f"Q: {body.question[:200]}",
    )
    db.add(audit)
    await db.flush()

    return result


# ---------------------------------------------------------------------------
# GET /{user_id}/alerts — Credit Bureau Alerts
# ---------------------------------------------------------------------------

ALERT_FIELDS = [
    "id", "user_id", "alert_type", "severity", "status",
    "bureau_name", "bureau_reference",
    "title", "description",
    "other_institution", "other_product_type", "other_amount",
    "other_delinquency_days", "other_delinquency_amount",
    "action_taken", "action_notes", "acted_by", "acted_at",
    "alert_date", "received_at", "created_at",
]


@router.get("/{user_id}/alerts")
async def customer_alerts(
    user_id: int,
    status_filter: Optional[str] = Query(None, description="Comma-separated status filter (new,acknowledged,action_taken,dismissed)"),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Return credit bureau alerts for a customer."""
    q = select(CreditBureauAlert).where(
        CreditBureauAlert.user_id == user_id,
    ).order_by(CreditBureauAlert.alert_date.desc())

    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
        if statuses:
            q = q.where(CreditBureauAlert.status.in_(statuses))

    result = await db.execute(q)
    alerts = result.scalars().all()
    return [_row_to_dict(a, ALERT_FIELDS) for a in alerts]


# ---------------------------------------------------------------------------
# PATCH /{user_id}/alerts/{alert_id} — Update alert status / take action
# ---------------------------------------------------------------------------

class AlertActionRequest(BaseModel):
    status: str | None = None  # "acknowledged", "action_taken", "dismissed"
    action_taken: str | None = None  # e.g. "reassess_credit_limit", "freeze_account"
    action_notes: str | None = None


@router.patch("/{user_id}/alerts/{alert_id}")
async def update_alert(
    user_id: int,
    alert_id: int,
    body: AlertActionRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Update a credit bureau alert — acknowledge, take action, or dismiss."""
    result = await db.execute(
        select(CreditBureauAlert).where(
            CreditBureauAlert.id == alert_id,
            CreditBureauAlert.user_id == user_id,
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if body.status:
        try:
            alert.status = AlertStatus(body.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")

    if body.action_taken:
        alert.action_taken = body.action_taken
        alert.status = AlertStatus.ACTION_TAKEN
    if body.action_notes:
        alert.action_notes = body.action_notes
    if body.action_taken or body.status:
        alert.acted_by = current_user.id
        alert.acted_at = datetime.now(timezone.utc)

    await db.flush()

    # Audit
    db.add(AuditLog(
        entity_type="credit_bureau_alert",
        entity_id=alert_id,
        action=f"alert_{body.action_taken or body.status or 'updated'}",
        user_id=current_user.id,
        details=body.action_notes or f"Alert {alert_id} updated",
    ))
    await db.flush()

    return _row_to_dict(alert, ALERT_FIELDS)
