"""Reporting endpoints for dashboard, exports, and report generation."""

import base64
import csv
import io
from datetime import datetime, date, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, case, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus
from app.models.decision import Decision
from app.models.payment import Payment, PaymentSchedule, ScheduleStatus
from app.models.collection import CollectionRecord
from app.models.report import ReportHistory
from app.schemas import (
    DashboardMetrics,
    ReportGenerateRequest,
    ReportHistoryResponse,
)
from app.auth_utils import require_roles

router = APIRouter()

STAFF_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)

REPORT_TYPES = {
    "aged": {"name": "Aged Report", "description": "Outstanding loans grouped by days past due"},
    "exposure": {"name": "Exposure Report", "description": "Total exposure by risk band, status, purpose"},
    "interest_fees": {"name": "Interest & Fees Report", "description": "Projected and earned interest summary"},
    "loan_statement": {"name": "Loan Statement", "description": "Individual loan statement"},
    "portfolio_summary": {"name": "Portfolio Summary", "description": "Overview of loan portfolio health"},
    "loan_book": {"name": "Loan Book", "description": "Complete loan book export"},
    "decision_audit": {"name": "Decision Audit", "description": "Engine decisions and underwriter overrides"},
    "underwriter_performance": {"name": "Underwriter Performance", "description": "Processed counts and avg time"},
    "collection_report": {"name": "Collection Report", "description": "Collection activity summary"},
    "disbursement": {"name": "Disbursement Report", "description": "Loans disbursed in period"},
}


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

    # ── Enhanced metrics ──
    # Projected interest income from disbursed/accepted loans
    interest_query = await db.execute(
        select(
            func.coalesce(func.sum(
                LoanApplication.amount_approved * LoanApplication.interest_rate / 100.0
                * LoanApplication.term_months / 12.0
            ), 0)
        ).where(
            LoanApplication.status.in_([LoanStatus.DISBURSED, LoanStatus.ACCEPTED]),
            LoanApplication.amount_approved.isnot(None),
            LoanApplication.interest_rate.isnot(None),
        )
    )
    projected_interest = float(interest_query.scalar() or 0)

    # Total principal disbursed
    principal_query = await db.execute(
        select(func.coalesce(func.sum(LoanApplication.amount_approved), 0))
        .where(LoanApplication.status.in_([LoanStatus.DISBURSED, LoanStatus.ACCEPTED]))
    )
    total_principal = float(principal_query.scalar() or 0)

    # Simple profit projection (interest - estimated 30% operating cost)
    projected_profit = projected_interest - (total_principal * 0.02)  # ~2% provision cost

    # Daily volume (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    daily = await db.execute(
        select(
            func.date(LoanApplication.created_at).label("day"),
            func.count(LoanApplication.id),
            func.coalesce(func.sum(LoanApplication.amount_requested), 0),
        )
        .where(LoanApplication.created_at >= thirty_days_ago)
        .group_by("day")
        .order_by("day")
    )
    daily_data = [
        {"date": str(row[0]), "count": row[1], "volume": float(row[2])}
        for row in daily.all()
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
        projected_interest_income=round(projected_interest, 2),
        total_principal_disbursed=round(total_principal, 2),
        projected_profit=round(projected_profit, 2),
        daily_volume=daily_data,
    )


# ── Report Types ───────────────────────────────────────

@router.get("/types")
async def get_report_types(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Get available report types."""
    return REPORT_TYPES


@router.post("/generate/{report_type}")
async def generate_report(
    report_type: str,
    params: ReportGenerateRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Generate a report and store it in history."""
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")

    date_from = params.date_from or (date.today() - timedelta(days=90))
    date_to = params.date_to or date.today()

    # Generate the CSV content based on type
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "aged":
        await _generate_aged_report(writer, db, date_from, date_to)
    elif report_type == "exposure":
        await _generate_exposure_report(writer, db, date_from, date_to)
    elif report_type == "interest_fees":
        await _generate_interest_fees_report(writer, db, date_from, date_to)
    elif report_type == "loan_statement":
        await _generate_loan_statement(writer, db, params.application_id)
    elif report_type == "portfolio_summary":
        await _generate_portfolio_summary(writer, db, date_from, date_to)
    elif report_type == "loan_book":
        await _generate_loan_book(writer, db)
    elif report_type == "decision_audit":
        await _generate_decision_audit(writer, db, date_from, date_to)
    elif report_type == "underwriter_performance":
        await _generate_underwriter_performance(writer, db, date_from, date_to)
    elif report_type == "collection_report":
        await _generate_collection_report(writer, db, date_from, date_to)
    elif report_type == "disbursement":
        await _generate_disbursement_report(writer, db, date_from, date_to)

    csv_content = output.getvalue()
    encoded = base64.b64encode(csv_content.encode()).decode()

    report_name = f"{REPORT_TYPES[report_type]['name']} - {date_from} to {date_to}"

    # Save to history
    history = ReportHistory(
        report_type=report_type,
        report_name=report_name,
        generated_by=current_user.id,
        parameters={"date_from": str(date_from), "date_to": str(date_to), "application_id": params.application_id},
        file_data=encoded,
        file_format="csv",
    )
    db.add(history)
    await db.flush()
    await db.refresh(history)

    return {
        "id": history.id,
        "report_type": report_type,
        "report_name": report_name,
        "file_data": encoded,
        "file_format": "csv",
        "created_at": history.created_at.isoformat() if history.created_at else None,
    }


@router.get("/history", response_model=list[ReportHistoryResponse])
async def get_report_history(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get history of generated reports."""
    result = await db.execute(
        select(ReportHistory).order_by(ReportHistory.created_at.desc()).limit(100)
    )
    return result.scalars().all()


@router.get("/history/{report_id}/download")
async def download_historical_report(
    report_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Re-download a previously generated report."""
    result = await db.execute(
        select(ReportHistory).where(ReportHistory.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    content = base64.b64decode(report.file_data).decode()
    filename = f"{report.report_type}_{report.id}.{report.file_format}"

    return StreamingResponse(
        iter([content]),
        media_type="text/csv" if report.file_format == "csv" else "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
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


# ── Report generation helpers ────────────────────────

async def _generate_aged_report(writer, db, date_from, date_to):
    """Outstanding loans grouped by days past due (current, 30, 60, 90, 120+)."""
    writer.writerow(["Aged Report", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow([])
    writer.writerow(["Bucket", "Count", "Total Outstanding", "% of Portfolio"])

    result = await db.execute(
        select(LoanApplication, User.first_name, User.last_name)
        .join(User, LoanApplication.applicant_id == User.id)
        .where(LoanApplication.status == LoanStatus.DISBURSED)
    )
    rows = result.all()
    today = date.today()

    buckets = {"Current": [], "1-30 Days": [], "31-60 Days": [], "61-90 Days": [], "91-120 Days": [], "120+ Days": []}

    for row in rows:
        app = row[0]
        # Get overdue days from schedule
        sched_result = await db.execute(
            select(PaymentSchedule).where(
                PaymentSchedule.loan_application_id == app.id,
                PaymentSchedule.status != "paid",
            ).order_by(PaymentSchedule.due_date)
        )
        schedules = sched_result.scalars().all()
        max_dpd = 0
        outstanding = 0
        for s in schedules:
            outstanding += float(s.amount_due) - float(s.amount_paid)
            if s.due_date <= today:
                dpd = (today - s.due_date).days
                max_dpd = max(max_dpd, dpd)

        if not outstanding:
            outstanding = float(app.amount_approved or 0)

        if max_dpd == 0:
            buckets["Current"].append(outstanding)
        elif max_dpd <= 30:
            buckets["1-30 Days"].append(outstanding)
        elif max_dpd <= 60:
            buckets["31-60 Days"].append(outstanding)
        elif max_dpd <= 90:
            buckets["61-90 Days"].append(outstanding)
        elif max_dpd <= 120:
            buckets["91-120 Days"].append(outstanding)
        else:
            buckets["120+ Days"].append(outstanding)

    total_outstanding = sum(sum(v) for v in buckets.values())
    for bucket, amounts in buckets.items():
        count = len(amounts)
        total = sum(amounts)
        pct = (total / total_outstanding * 100) if total_outstanding > 0 else 0
        writer.writerow([bucket, count, f"{total:,.2f}", f"{pct:.1f}%"])

    writer.writerow([])
    writer.writerow(["Total", sum(len(v) for v in buckets.values()), f"{total_outstanding:,.2f}", "100%"])


async def _generate_exposure_report(writer, db, date_from, date_to):
    """Total exposure by risk band, status, purpose."""
    writer.writerow(["Exposure Report", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow([])

    # By Status
    writer.writerow(["=== By Status ==="])
    writer.writerow(["Status", "Count", "Total Requested", "Total Approved"])
    result = await db.execute(
        select(
            LoanApplication.status,
            func.count(LoanApplication.id),
            func.coalesce(func.sum(LoanApplication.amount_requested), 0),
            func.coalesce(func.sum(LoanApplication.amount_approved), 0),
        ).group_by(LoanApplication.status)
    )
    for row in result.all():
        writer.writerow([row[0].value, row[1], f"{float(row[2]):,.2f}", f"{float(row[3]):,.2f}"])

    writer.writerow([])

    # By Purpose
    writer.writerow(["=== By Purpose ==="])
    writer.writerow(["Purpose", "Count", "Total Requested"])
    result = await db.execute(
        select(
            LoanApplication.purpose,
            func.count(LoanApplication.id),
            func.coalesce(func.sum(LoanApplication.amount_requested), 0),
        ).group_by(LoanApplication.purpose)
    )
    for row in result.all():
        writer.writerow([row[0].value, row[1], f"{float(row[2]):,.2f}"])

    writer.writerow([])

    # By Risk Band
    writer.writerow(["=== By Risk Band ==="])
    writer.writerow(["Risk Band", "Count", "Avg Score"])
    result = await db.execute(
        select(
            Decision.risk_band,
            func.count(Decision.id),
            func.avg(Decision.credit_score),
        ).where(Decision.risk_band.isnot(None))
        .group_by(Decision.risk_band)
    )
    for row in result.all():
        writer.writerow([row[0], row[1], f"{float(row[2] or 0):.0f}"])


async def _generate_interest_fees_report(writer, db, date_from, date_to):
    """Projected and earned interest summary."""
    writer.writerow(["Interest & Fees Report", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow([])
    writer.writerow(["Metric", "Amount (TTD)"])

    # Projected interest
    result = await db.execute(
        select(
            func.coalesce(func.sum(
                LoanApplication.amount_approved * LoanApplication.interest_rate / 100.0
                * LoanApplication.term_months / 12.0
            ), 0)
        ).where(
            LoanApplication.status.in_([LoanStatus.DISBURSED, LoanStatus.ACCEPTED]),
            LoanApplication.amount_approved.isnot(None),
        )
    )
    projected = float(result.scalar() or 0)

    # Total interest from schedule
    sched_result = await db.execute(
        select(
            func.coalesce(func.sum(PaymentSchedule.interest), 0),
        ).where(PaymentSchedule.status == "paid")
    )
    earned = float(sched_result.scalar() or 0)

    writer.writerow(["Projected Total Interest", f"{projected:,.2f}"])
    writer.writerow(["Interest Earned (Paid)", f"{earned:,.2f}"])
    writer.writerow(["Interest Outstanding", f"{projected - earned:,.2f}"])


async def _generate_loan_statement(writer, db, application_id):
    """Individual loan statement."""
    if not application_id:
        writer.writerow(["Error: application_id is required for loan statement"])
        return

    result = await db.execute(
        select(LoanApplication, User.first_name, User.last_name)
        .join(User, LoanApplication.applicant_id == User.id)
        .where(LoanApplication.id == application_id)
    )
    row = result.first()
    if not row:
        writer.writerow(["Error: Application not found"])
        return

    app, first, last = row
    writer.writerow(["Loan Statement"])
    writer.writerow(["Reference", app.reference_number])
    writer.writerow(["Applicant", f"{first} {last}"])
    writer.writerow(["Amount Approved", float(app.amount_approved) if app.amount_approved else "N/A"])
    writer.writerow(["Interest Rate", f"{float(app.interest_rate)}%" if app.interest_rate else "N/A"])
    writer.writerow(["Term", f"{app.term_months} months"])
    writer.writerow(["Status", app.status.value])
    writer.writerow([])

    # Payment schedule
    writer.writerow(["=== Payment Schedule ==="])
    writer.writerow(["#", "Due Date", "Principal", "Interest", "Amount Due", "Amount Paid", "Status"])
    sched_result = await db.execute(
        select(PaymentSchedule)
        .where(PaymentSchedule.loan_application_id == application_id)
        .order_by(PaymentSchedule.installment_number)
    )
    for s in sched_result.scalars().all():
        writer.writerow([
            s.installment_number, s.due_date, f"{float(s.principal):,.2f}",
            f"{float(s.interest):,.2f}", f"{float(s.amount_due):,.2f}",
            f"{float(s.amount_paid):,.2f}", s.status.value,
        ])

    writer.writerow([])

    # Payments
    writer.writerow(["=== Payment History ==="])
    writer.writerow(["Date", "Amount", "Type", "Reference", "Status"])
    pay_result = await db.execute(
        select(Payment)
        .where(Payment.loan_application_id == application_id)
        .order_by(Payment.payment_date)
    )
    for p in pay_result.scalars().all():
        writer.writerow([p.payment_date, f"{float(p.amount):,.2f}", p.payment_type.value, p.reference_number, p.status.value])


async def _generate_portfolio_summary(writer, db, date_from, date_to):
    """Overview of entire loan portfolio health."""
    writer.writerow(["Portfolio Summary", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow([])

    total = await db.execute(select(func.count(LoanApplication.id)))
    total_count = total.scalar() or 0

    disbursed = await db.execute(
        select(func.count(LoanApplication.id))
        .where(LoanApplication.status == LoanStatus.DISBURSED)
    )
    disbursed_count = disbursed.scalar() or 0

    total_approved = await db.execute(
        select(func.coalesce(func.sum(LoanApplication.amount_approved), 0))
        .where(LoanApplication.amount_approved.isnot(None))
    )

    total_disbursed_amt = await db.execute(
        select(func.coalesce(func.sum(LoanApplication.amount_approved), 0))
        .where(LoanApplication.status == LoanStatus.DISBURSED)
    )

    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Applications", total_count])
    writer.writerow(["Active Loans (Disbursed)", disbursed_count])
    writer.writerow(["Total Approved Amount", f"{float(total_approved.scalar() or 0):,.2f}"])
    writer.writerow(["Total Disbursed Amount", f"{float(total_disbursed_amt.scalar() or 0):,.2f}"])

    # Average metrics
    avg_rate = await db.execute(
        select(func.avg(LoanApplication.interest_rate))
        .where(LoanApplication.interest_rate.isnot(None))
    )
    writer.writerow(["Average Interest Rate", f"{float(avg_rate.scalar() or 0):.2f}%"])

    avg_term = await db.execute(select(func.avg(LoanApplication.term_months)))
    writer.writerow(["Average Term (months)", f"{float(avg_term.scalar() or 0):.1f}"])


async def _generate_loan_book(writer, db):
    """Complete loan book export."""
    writer.writerow(["Loan Book", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow([])
    writer.writerow([
        "Reference", "Applicant", "Status", "Amount Requested", "Amount Approved",
        "Term", "Rate", "Monthly Payment", "Purpose", "Created", "Decided",
    ])
    result = await db.execute(
        select(LoanApplication, User.first_name, User.last_name)
        .join(User, LoanApplication.applicant_id == User.id)
        .order_by(LoanApplication.created_at.desc())
    )
    for row in result.all():
        app = row[0]
        writer.writerow([
            app.reference_number, f"{row[1]} {row[2]}",
            app.status.value, float(app.amount_requested),
            float(app.amount_approved) if app.amount_approved else "",
            app.term_months,
            float(app.interest_rate) if app.interest_rate else "",
            float(app.monthly_payment) if app.monthly_payment else "",
            app.purpose.value, app.created_at.strftime("%Y-%m-%d") if app.created_at else "",
            app.decided_at.strftime("%Y-%m-%d") if app.decided_at else "",
        ])


async def _generate_decision_audit(writer, db, date_from, date_to):
    """Engine decisions and underwriter overrides."""
    writer.writerow(["Decision Audit Report", f"Period: {date_from} to {date_to}"])
    writer.writerow([])
    writer.writerow([
        "Application", "Score", "Risk Band", "Engine Outcome",
        "Underwriter Action", "Override Reason", "Final Outcome", "Date",
    ])
    result = await db.execute(
        select(Decision, LoanApplication.reference_number)
        .join(LoanApplication, Decision.loan_application_id == LoanApplication.id)
        .where(Decision.created_at >= datetime.combine(date_from, datetime.min.time()))
        .where(Decision.created_at <= datetime.combine(date_to, datetime.max.time()))
        .order_by(Decision.created_at.desc())
    )
    for row in result.all():
        d = row[0]
        writer.writerow([
            row[1], d.credit_score, d.risk_band,
            d.engine_outcome.value if d.engine_outcome else "",
            d.underwriter_action.value if d.underwriter_action else "",
            d.override_reason or "",
            d.final_outcome or "",
            d.created_at.strftime("%Y-%m-%d") if d.created_at else "",
        ])


async def _generate_underwriter_performance(writer, db, date_from, date_to):
    """Underwriter performance stats."""
    writer.writerow(["Underwriter Performance Report", f"Period: {date_from} to {date_to}"])
    writer.writerow([])
    writer.writerow(["Underwriter", "Applications Processed", "Avg Processing Days", "Approvals", "Declines", "Overrides"])

    result = await db.execute(
        select(
            User.first_name, User.last_name,
            func.count(Decision.id),
            func.sum(case((Decision.underwriter_action == "approve", 1), else_=0)),
            func.sum(case((Decision.underwriter_action == "decline", 1), else_=0)),
            func.sum(case(
                (Decision.underwriter_action.isnot(None), 1), else_=0
            )),
        )
        .join(User, Decision.underwriter_id == User.id)
        .where(Decision.created_at >= datetime.combine(date_from, datetime.min.time()))
        .group_by(User.id, User.first_name, User.last_name)
    )
    for row in result.all():
        writer.writerow([f"{row[0]} {row[1]}", row[2], "N/A", row[3] or 0, row[4] or 0, row[5] or 0])


async def _generate_collection_report(writer, db, date_from, date_to):
    """Collection activity summary."""
    writer.writerow(["Collection Report", f"Period: {date_from} to {date_to}"])
    writer.writerow([])

    result = await db.execute(
        select(func.count(CollectionRecord.id))
        .where(CollectionRecord.created_at >= datetime.combine(date_from, datetime.min.time()))
    )
    total_interactions = result.scalar() or 0

    writer.writerow(["Total Interactions", total_interactions])
    writer.writerow([])

    # By outcome
    writer.writerow(["Outcome", "Count"])
    outcome_result = await db.execute(
        select(CollectionRecord.outcome, func.count(CollectionRecord.id))
        .where(CollectionRecord.created_at >= datetime.combine(date_from, datetime.min.time()))
        .group_by(CollectionRecord.outcome)
    )
    for row in outcome_result.all():
        writer.writerow([row[0].value, row[1]])

    writer.writerow([])

    # By channel
    writer.writerow(["Channel", "Count"])
    channel_result = await db.execute(
        select(CollectionRecord.channel, func.count(CollectionRecord.id))
        .where(CollectionRecord.created_at >= datetime.combine(date_from, datetime.min.time()))
        .group_by(CollectionRecord.channel)
    )
    for row in channel_result.all():
        writer.writerow([row[0].value, row[1]])


async def _generate_disbursement_report(writer, db, date_from, date_to):
    """Loans disbursed in period."""
    writer.writerow(["Disbursement Report", f"Period: {date_from} to {date_to}"])
    writer.writerow([])
    writer.writerow(["Reference", "Applicant", "Amount", "Rate", "Term", "Disbursed Date"])

    result = await db.execute(
        select(LoanApplication, User.first_name, User.last_name)
        .join(User, LoanApplication.applicant_id == User.id)
        .where(
            LoanApplication.status == LoanStatus.DISBURSED,
            LoanApplication.decided_at >= datetime.combine(date_from, datetime.min.time()),
            LoanApplication.decided_at <= datetime.combine(date_to, datetime.max.time()),
        )
        .order_by(LoanApplication.decided_at.desc())
    )
    total_disbursed = 0
    for row in result.all():
        app = row[0]
        amt = float(app.amount_approved or 0)
        total_disbursed += amt
        writer.writerow([
            app.reference_number, f"{row[1]} {row[2]}",
            f"{amt:,.2f}",
            f"{float(app.interest_rate)}%" if app.interest_rate else "N/A",
            f"{app.term_months} months",
            app.decided_at.strftime("%Y-%m-%d") if app.decided_at else "",
        ])

    writer.writerow([])
    writer.writerow(["Total Disbursed", f"{total_disbursed:,.2f}"])
