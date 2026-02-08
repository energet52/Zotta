"""Reporting endpoints for dashboard and exports."""

import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, case, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus
from app.models.decision import Decision
from app.schemas import DashboardMetrics
from app.auth_utils import require_roles

router = APIRouter()

STAFF_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)


@router.get("/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard metrics for the back-office portal."""
    # Total applications
    total = await db.execute(select(func.count(LoanApplication.id)))
    total_count = total.scalar() or 0

    # By status
    status_query = await db.execute(
        select(LoanApplication.status, func.count(LoanApplication.id))
        .group_by(LoanApplication.status)
    )
    status_counts = {row[0].value: row[1] for row in status_query.all()}

    pending = status_counts.get("submitted", 0) + status_counts.get("under_review", 0)
    approved = status_counts.get("approved", 0) + status_counts.get("disbursed", 0)
    declined = status_counts.get("declined", 0)

    # Disbursed total
    disbursed = await db.execute(
        select(func.coalesce(func.sum(LoanApplication.amount_approved), 0))
        .where(LoanApplication.status == LoanStatus.DISBURSED)
    )
    total_disbursed = float(disbursed.scalar() or 0)

    # Approval rate
    decided = approved + declined
    approval_rate = (approved / decided * 100) if decided > 0 else 0

    # Average processing time (submitted to decided)
    avg_proc = await db.execute(
        select(
            func.avg(
                extract("epoch", LoanApplication.decided_at) -
                extract("epoch", LoanApplication.submitted_at)
            )
        ).where(
            LoanApplication.decided_at.isnot(None),
            LoanApplication.submitted_at.isnot(None),
        )
    )
    avg_seconds = avg_proc.scalar() or 0
    avg_days = float(avg_seconds) / 86400 if avg_seconds else 0

    # Average loan amount
    avg_amount = await db.execute(
        select(func.avg(LoanApplication.amount_requested))
    )
    avg_loan = float(avg_amount.scalar() or 0)

    # Risk distribution from decisions
    risk_query = await db.execute(
        select(Decision.risk_band, func.count(Decision.id))
        .where(Decision.risk_band.isnot(None))
        .group_by(Decision.risk_band)
    )
    risk_dist = {row[0]: row[1] for row in risk_query.all()}

    # Monthly volume (last 12 months)
    twelve_months_ago = datetime.now(timezone.utc) - timedelta(days=365)
    monthly = await db.execute(
        select(
            extract("year", LoanApplication.created_at).label("year"),
            extract("month", LoanApplication.created_at).label("month"),
            func.count(LoanApplication.id),
            func.coalesce(func.sum(LoanApplication.amount_requested), 0),
        )
        .where(LoanApplication.created_at >= twelve_months_ago)
        .group_by("year", "month")
        .order_by("year", "month")
    )
    monthly_data = [
        {"year": int(row[0]), "month": int(row[1]), "count": row[2], "volume": float(row[3])}
        for row in monthly.all()
    ]

    return DashboardMetrics(
        total_applications=total_count,
        pending_review=pending,
        approved=approved,
        declined=declined,
        total_disbursed=total_disbursed,
        approval_rate=round(approval_rate, 1),
        avg_processing_days=round(avg_days, 1),
        avg_loan_amount=round(avg_loan, 2),
        applications_by_status=status_counts,
        risk_distribution=risk_dist,
        monthly_volume=monthly_data,
    )


@router.get("/export/loan-book")
async def export_loan_book(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Export loan book as CSV."""
    result = await db.execute(
        select(LoanApplication).order_by(LoanApplication.created_at.desc())
    )
    applications = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Reference", "Status", "Amount Requested", "Amount Approved",
        "Term (months)", "Interest Rate", "Purpose", "Submitted", "Decided",
    ])
    for app in applications:
        writer.writerow([
            app.reference_number, app.status.value, float(app.amount_requested),
            float(app.amount_approved) if app.amount_approved else "",
            app.term_months, float(app.interest_rate) if app.interest_rate else "",
            app.purpose.value, app.submitted_at or "", app.decided_at or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=loan_book.csv"},
    )
