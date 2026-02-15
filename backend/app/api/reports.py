"""Reporting endpoints for dashboard, exports, and report generation."""

import base64
import csv
import io
from datetime import datetime, date, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, case, extract
from sqlalchemy.orm import aliased
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

    # ── Arrears / Delinquency summary ──
    from app.schemas import ArrearsBucket, ArrearsSummary

    today = date.today()
    # Get all disbursed application IDs
    disbursed_apps = await db.execute(
        select(LoanApplication.id, LoanApplication.amount_approved)
        .where(LoanApplication.status == LoanStatus.DISBURSED)
    )
    disbursed_list = disbursed_apps.all()

    # Aged buckets: 1-30, 31-60, 61-90, 90+
    bucket_defs = [
        ("1–30 days", 1, 30),
        ("31–60 days", 31, 60),
        ("61–90 days", 61, 90),
        ("90+ days", 91, 999999),
    ]
    buckets_data = {label: {"loan_ids": set(), "overdue": 0.0, "outstanding": 0.0} for label, _, _ in bucket_defs}

    if disbursed_list:
        app_ids = [row[0] for row in disbursed_list]
        # Fetch all schedules for disbursed loans that are not fully paid and past due
        overdue_sched = await db.execute(
            select(PaymentSchedule)
            .where(
                PaymentSchedule.loan_application_id.in_(app_ids),
                PaymentSchedule.due_date < today,
                PaymentSchedule.status != ScheduleStatus.PAID,
            )
        )
        overdue_items = overdue_sched.scalars().all()

        for s in overdue_items:
            dpd = (today - s.due_date).days
            owed = float(s.amount_due) - float(s.amount_paid)
            if owed <= 0:
                continue
            for label, lo, hi in bucket_defs:
                if lo <= dpd <= hi:
                    buckets_data[label]["loan_ids"].add(s.loan_application_id)
                    buckets_data[label]["overdue"] += owed
                    break

        # Calculate outstanding balance for delinquent loans
        delinquent_ids = set()
        for bd in buckets_data.values():
            delinquent_ids |= bd["loan_ids"]

        if delinquent_ids:
            outstanding_sched = await db.execute(
                select(
                    PaymentSchedule.loan_application_id,
                    func.sum(PaymentSchedule.amount_due - PaymentSchedule.amount_paid),
                )
                .where(
                    PaymentSchedule.loan_application_id.in_(list(delinquent_ids)),
                    PaymentSchedule.status != ScheduleStatus.PAID,
                )
                .group_by(PaymentSchedule.loan_application_id)
            )
            outstanding_by_app = {row[0]: float(row[1]) for row in outstanding_sched.all()}
        else:
            outstanding_by_app = {}

        # Assign outstanding to buckets (using highest bucket per loan)
        loan_bucket: dict[int, str] = {}
        for label, _, _ in reversed(bucket_defs):
            for lid in buckets_data[label]["loan_ids"]:
                if lid not in loan_bucket:
                    loan_bucket[lid] = label

        for lid, blabel in loan_bucket.items():
            buckets_data[blabel]["outstanding"] += outstanding_by_app.get(lid, 0.0)

    total_delinquent = len(set().union(*(bd["loan_ids"] for bd in buckets_data.values())))
    total_overdue_amt = sum(bd["overdue"] for bd in buckets_data.values())
    total_outstanding_risk = sum(bd["outstanding"] for bd in buckets_data.values())

    arrears_buckets = [
        ArrearsBucket(
            label=label,
            loan_count=len(buckets_data[label]["loan_ids"]),
            total_outstanding=round(buckets_data[label]["outstanding"], 2),
            total_overdue=round(buckets_data[label]["overdue"], 2),
        )
        for label, _, _ in bucket_defs
    ]

    arrears_summary = ArrearsSummary(
        total_delinquent_loans=total_delinquent,
        total_overdue_amount=round(total_overdue_amt, 2),
        total_outstanding_at_risk=round(total_outstanding_risk, 2),
        buckets=arrears_buckets,
    )

    # ── Live P&L: actual interest collected + expected losses ──
    interest_collected = 0.0
    if disbursed_list:
        interest_collected_q = await db.execute(
            select(func.coalesce(func.sum(PaymentSchedule.interest), 0))
            .where(
                PaymentSchedule.loan_application_id.in_(app_ids),
                PaymentSchedule.status == ScheduleStatus.PAID,
            )
        )
        interest_collected = float(interest_collected_q.scalar() or 0)

    # Expected loss: remaining principal on loans with 60+ DPD (assumed to default)
    loss_bucket_labels = ["61–90 days", "90+ days"]
    expected_default_loss = sum(
        buckets_data[label]["outstanding"]
        for label in loss_bucket_labels
    )

    net_pnl = interest_collected - expected_default_loss

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
        arrears_summary=arrears_summary,
        interest_collected=round(interest_collected, 2),
        expected_default_loss=round(expected_default_loss, 2),
        net_pnl=round(net_pnl, 2),
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

    if report_type == "loan_statement":
        if not params.application_id:
            raise HTTPException(
                status_code=400,
                detail="application_id is required for loan statement report. Enter an application ID in the App ID field.",
            )
        await _generate_loan_statement(writer, db, params.application_id)
    elif report_type == "aged":
        await _generate_aged_report(writer, db, date_from, date_to)
    elif report_type == "exposure":
        await _generate_exposure_report(writer, db, date_from, date_to)
    elif report_type == "interest_fees":
        await _generate_interest_fees_report(writer, db, date_from, date_to)
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
    loan_details = []  # (app, applicant_name, outstanding, max_dpd, bucket)

    for row in rows:
        app = row[0]
        applicant_name = f"{row[1]} {row[2]}"
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
            bucket = "Current"
            buckets["Current"].append(outstanding)
        elif max_dpd <= 30:
            bucket = "1-30 Days"
            buckets["1-30 Days"].append(outstanding)
        elif max_dpd <= 60:
            bucket = "31-60 Days"
            buckets["31-60 Days"].append(outstanding)
        elif max_dpd <= 90:
            bucket = "61-90 Days"
            buckets["61-90 Days"].append(outstanding)
        elif max_dpd <= 120:
            bucket = "91-120 Days"
            buckets["91-120 Days"].append(outstanding)
        else:
            bucket = "120+ Days"
            buckets["120+ Days"].append(outstanding)

        loan_details.append((app, applicant_name, outstanding, max_dpd, bucket))

    total_outstanding = sum(sum(v) for v in buckets.values())
    for bucket, amounts in buckets.items():
        count = len(amounts)
        total = sum(amounts)
        pct = (total / total_outstanding * 100) if total_outstanding > 0 else 0
        writer.writerow([bucket, count, f"{total:,.2f}", f"{pct:.1f}%"])

    writer.writerow([])
    writer.writerow(["Total", sum(len(v) for v in buckets.values()), f"{total_outstanding:,.2f}", "100%"])

    # Loan-level details
    writer.writerow([])
    writer.writerow(["=== Loan Details ==="])
    writer.writerow([
        "Reference", "Applicant", "Amount Approved", "Outstanding", "Days Past Due",
        "Bucket", "Purpose", "Term (months)", "Interest Rate", "Disbursed Date",
    ])
    for app, applicant_name, outstanding, max_dpd, bucket in loan_details:
        writer.writerow([
            app.reference_number, applicant_name,
            f"{float(app.amount_approved or 0):,.2f}",
            f"{outstanding:,.2f}", max_dpd, bucket,
            app.purpose.value if app.purpose else "",
            app.term_months or "",
            f"{float(app.interest_rate)}%" if app.interest_rate else "",
            app.decided_at.strftime("%Y-%m-%d") if app.decided_at else "",
        ])


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

    # Loan-level details
    writer.writerow([])
    writer.writerow(["=== Loan Details ==="])
    writer.writerow([
        "Reference", "Applicant", "Status", "Purpose", "Amount Requested", "Amount Approved",
        "Term (months)", "Interest Rate", "Risk Band", "Submitted", "Decided",
    ])
    latest_decision = select(
        Decision.loan_application_id, func.max(Decision.id).label("max_id")
    ).group_by(Decision.loan_application_id).subquery()
    loan_result = await db.execute(
        select(LoanApplication, User.first_name, User.last_name, Decision.risk_band)
        .join(User, LoanApplication.applicant_id == User.id)
        .outerjoin(latest_decision, latest_decision.c.loan_application_id == LoanApplication.id)
        .outerjoin(Decision, Decision.id == latest_decision.c.max_id)
        .order_by(LoanApplication.created_at.desc())
    )
    for row in loan_result.all():
        app, first, last, risk_band = row
        writer.writerow([
            app.reference_number, f"{first} {last}",
            app.status.value, app.purpose.value if app.purpose else "",
            f"{float(app.amount_requested):,.2f}",
            f"{float(app.amount_approved or 0):,.2f}" if app.amount_approved else "",
            app.term_months or "",
            f"{float(app.interest_rate)}%" if app.interest_rate else "",
            risk_band or "",
            app.submitted_at.strftime("%Y-%m-%d") if app.submitted_at else "",
            app.decided_at.strftime("%Y-%m-%d") if app.decided_at else "",
        ])


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

    # Loan-level details
    writer.writerow([])
    writer.writerow(["=== Loan Details ==="])
    writer.writerow([
        "Reference", "Applicant", "Amount Approved", "Interest Rate", "Term (months)",
        "Projected Interest", "Interest Earned", "Interest Outstanding", "Status",
    ])
    loan_result = await db.execute(
        select(LoanApplication, User.first_name, User.last_name)
        .join(User, LoanApplication.applicant_id == User.id)
        .where(
            LoanApplication.status.in_([LoanStatus.DISBURSED, LoanStatus.ACCEPTED]),
            LoanApplication.amount_approved.isnot(None),
            LoanApplication.interest_rate.isnot(None),
        )
        .order_by(LoanApplication.created_at.desc())
    )
    for row in loan_result.all():
        app, first, last = row
        proj = float(app.amount_approved or 0) * float(app.interest_rate or 0) / 100.0 * (app.term_months or 0) / 12.0
        earned_result = await db.execute(
            select(func.coalesce(func.sum(PaymentSchedule.interest), 0))
            .where(
                PaymentSchedule.loan_application_id == app.id,
                PaymentSchedule.status == "paid",
            )
        )
        earned_loan = float(earned_result.scalar() or 0)
        writer.writerow([
            app.reference_number, f"{first} {last}",
            f"{float(app.amount_approved or 0):,.2f}",
            f"{float(app.interest_rate)}%" if app.interest_rate else "",
            app.term_months or "",
            f"{proj:,.2f}", f"{earned_loan:,.2f}", f"{proj - earned_loan:,.2f}",
            app.status.value,
        ])


async def _generate_loan_statement(writer, db, application_id):
    """Individual loan statement."""
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

    # Loan-level details
    writer.writerow([])
    writer.writerow(["=== Loan Details ==="])
    writer.writerow([
        "Reference", "Applicant", "Status", "Amount Requested", "Amount Approved",
        "Term (months)", "Interest Rate", "Purpose", "Submitted", "Decided",
    ])
    loan_result = await db.execute(
        select(LoanApplication, User.first_name, User.last_name)
        .join(User, LoanApplication.applicant_id == User.id)
        .order_by(LoanApplication.created_at.desc())
    )
    for row in loan_result.all():
        app, first, last = row
        writer.writerow([
            app.reference_number, f"{first} {last}",
            app.status.value,
            f"{float(app.amount_requested):,.2f}",
            f"{float(app.amount_approved or 0):,.2f}" if app.amount_approved else "",
            app.term_months or "",
            f"{float(app.interest_rate)}%" if app.interest_rate else "",
            app.purpose.value if app.purpose else "",
            app.submitted_at.strftime("%Y-%m-%d") if app.submitted_at else "",
            app.decided_at.strftime("%Y-%m-%d") if app.decided_at else "",
        ])


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

    # Record-level details (per loan/application)
    writer.writerow([])
    writer.writerow(["=== Record Details ==="])
    writer.writerow([
        "Reference", "Applicant", "Outcome", "Channel", "Notes", "Action Taken",
        "Agent", "Created", "Next Action Date", "Promise Amount", "Promise Date",
    ])
    Agent = aliased(User)
    dt_from = datetime.combine(date_from, datetime.min.time())
    dt_to = datetime.combine(date_to, datetime.max.time())
    record_result = await db.execute(
        select(
            CollectionRecord, LoanApplication.reference_number,
            User.first_name, User.last_name,
            Agent.first_name, Agent.last_name,
        )
        .join(LoanApplication, CollectionRecord.loan_application_id == LoanApplication.id)
        .join(User, LoanApplication.applicant_id == User.id)
        .outerjoin(Agent, CollectionRecord.agent_id == Agent.id)
        .where(
            CollectionRecord.created_at >= dt_from,
            CollectionRecord.created_at <= dt_to,
        )
        .order_by(CollectionRecord.created_at.desc())
    )
    for row in record_result.all():
        rec, ref, app_first, app_last, agent_first, agent_last = row
        writer.writerow([
            ref, f"{app_first} {app_last}",
            rec.outcome.value, rec.channel.value,
            (rec.notes or "")[:200] if rec.notes else "",
            rec.action_taken or "",
            f"{agent_first or ''} {agent_last or ''}".strip() if agent_first or agent_last else "",
            rec.created_at.strftime("%Y-%m-%d %H:%M") if rec.created_at else "",
            rec.next_action_date.strftime("%Y-%m-%d") if rec.next_action_date else "",
            f"{float(rec.promise_amount):,.2f}" if rec.promise_amount else "",
            rec.promise_date.strftime("%Y-%m-%d") if rec.promise_date else "",
        ])


async def _generate_disbursement_report(writer, db, date_from, date_to):
    """Loans disbursed in period."""
    writer.writerow(["Disbursement Report", f"Period: {date_from} to {date_to}"])
    writer.writerow([])
    writer.writerow([
        "Reference", "Applicant", "Amount", "Rate", "Term", "Monthly Payment",
        "Purpose", "Disbursed Date", "Application ID",
    ])

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
            f"{float(app.monthly_payment):,.2f}" if app.monthly_payment else "",
            app.purpose.value if app.purpose else "",
            app.decided_at.strftime("%Y-%m-%d") if app.decided_at else "",
            app.id,
        ])

    writer.writerow([])
    writer.writerow(["Total Disbursed", f"{total_disbursed:,.2f}"])
