"""Collection endpoints for managing overdue loan recovery."""

import csv
import io
import logging
import random
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.whatsapp_notifier import send_whatsapp_message
from app.services.error_logger import log_error
from app.services.collections_engine import (
    sync_collection_cases,
    compute_next_best_action,
    update_case_nba,
    check_compliance,
    calculate_settlement,
    check_ptp_status,
    generate_daily_snapshot,
    get_collections_analytics,
    get_agent_performance,
)

logger = logging.getLogger(__name__)
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus, ApplicantProfile
from app.models.payment import Payment, PaymentSchedule, ScheduleStatus, PaymentStatus
from app.models.collection import (
    CollectionRecord, CollectionChannel, CollectionOutcome,
    CollectionChat, ChatDirection, ChatMessageStatus,
)
from app.models.collections_ext import (
    CollectionCase, CaseStatus, DelinquencyStage,
    PromiseToPay, PTPStatus,
    SettlementOffer, SettlementOfferType, SettlementStatus,
    ComplianceRule, SLAConfig,
    CollectionsDashboardSnapshot,
)
from app.schemas import (
    CollectionRecordCreate,
    CollectionRecordResponse,
    CollectionChatCreate,
    CollectionChatResponse,
    CollectionQueueEntry,
    CollectionCaseResponse,
    CollectionCaseUpdate,
    NBAOverrideRequest,
    PromiseToPayCreate,
    PromiseToPayResponse,
    PromiseToPayUpdate,
    SettlementOfferCreate,
    SettlementOfferResponse,
    ComplianceRuleCreate,
    ComplianceRuleResponse,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    CollectionsDashboardResponse,
    BulkAssignRequest,
)
from app.auth_utils import require_roles

router = APIRouter()

STAFF_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)
SENIOR_ROLES = (UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)

# Simulated auto-reply messages
AUTO_REPLIES = [
    "Thank you for reaching out. I'll review my account and get back to you.",
    "I understand. Can we discuss a payment arrangement?",
    "I'm aware of the outstanding balance. I'll make a payment this week.",
    "Could you send me the details of what's owed?",
    "I'm having financial difficulties right now. Can we work something out?",
    "Thanks for the reminder. I'll log in to check my account.",
]


# ══════════════════════════════════════════════════════════════════════════
# Enhanced Queue
# ══════════════════════════════════════════════════════════════════════════

@router.get("/queue", response_model=list[CollectionQueueEntry])
async def get_collection_queue(
    search: Optional[str] = Query(None, description="Search by name, reference, phone"),
    stage: Optional[str] = Query(None, description="Filter by delinquency stage"),
    status: Optional[str] = Query(None, description="Filter by case status"),
    agent_id: Optional[int] = Query(None, description="Filter by assigned agent"),
    sort_by: str = Query("days_past_due", description="Sort field"),
    sort_dir: str = Query("desc", description="Sort direction: asc or desc"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get overdue loans needing collection action — enhanced with search, filters, and NBA."""
    try:
        # Get disbursed loans
        query = (
            select(LoanApplication, User.first_name, User.last_name, User.phone)
            .join(User, LoanApplication.applicant_id == User.id)
            .where(LoanApplication.status == LoanStatus.DISBURSED)
        )

        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    (User.first_name + " " + User.last_name).ilike(search_pattern),
                    LoanApplication.reference_number.ilike(search_pattern),
                    User.phone.ilike(search_pattern),
                )
            )

        result = await db.execute(query.order_by(LoanApplication.decided_at.asc()))
        rows = result.all()

        entries = []
        today = date.today()
        for row in rows:
            app = row[0]
            first_name = row[1]
            last_name = row[2]
            phone = row[3]

            # Calculate overdue info from payment schedule
            sched_result = await db.execute(
                select(PaymentSchedule).where(
                    PaymentSchedule.loan_application_id == app.id
                ).order_by(PaymentSchedule.installment_number)
            )
            schedules = sched_result.scalars().all()

            total_due = 0
            days_past_due = 0
            total_paid = 0
            outstanding = float(app.amount_approved or app.amount_requested)

            for s in schedules:
                total_paid += float(s.amount_paid)
                if s.status in (ScheduleStatus.OVERDUE, ScheduleStatus.DUE) or (
                    s.due_date <= today and s.status != ScheduleStatus.PAID
                ):
                    overdue_amount = float(s.amount_due) - float(s.amount_paid)
                    if overdue_amount > 0:
                        total_due += overdue_amount
                        dpd = (today - s.due_date).days
                        if dpd > days_past_due:
                            days_past_due = dpd

            outstanding = outstanding - total_paid

            if days_past_due <= 0 and total_due <= 0:
                continue  # Not overdue

            # Get CollectionCase if exists
            case_result = await db.execute(
                select(CollectionCase).where(
                    CollectionCase.loan_application_id == app.id
                )
            )
            case = case_result.scalar_one_or_none()

            # Apply stage filter
            if stage and case:
                if case.delinquency_stage.value != stage:
                    continue
            elif stage and not case:
                continue

            # Apply status filter
            if status and case:
                if case.status.value != status:
                    continue
            elif status and not case:
                continue

            # Apply agent filter
            if agent_id is not None and case:
                if case.assigned_agent_id != agent_id:
                    continue
            elif agent_id is not None and not case:
                continue

            # Last contact
            last_record = await db.execute(
                select(CollectionRecord)
                .where(CollectionRecord.loan_application_id == app.id)
                .order_by(CollectionRecord.created_at.desc())
                .limit(1)
            )
            last = last_record.scalar_one_or_none()
            last_contact = last.created_at if last else None
            next_action = last.next_action_date if last else None

            # Agent name
            agent_name = None
            if case and case.assigned_agent_id:
                agent_result = await db.execute(
                    select(User.first_name, User.last_name).where(User.id == case.assigned_agent_id)
                )
                agent_row = agent_result.one_or_none()
                if agent_row:
                    agent_name = f"{agent_row[0]} {agent_row[1]}"

            entries.append(CollectionQueueEntry(
                id=app.id,
                reference_number=app.reference_number,
                applicant_id=app.applicant_id,
                applicant_name=f"{first_name} {last_name}",
                amount_approved=float(app.amount_approved) if app.amount_approved else None,
                amount_due=total_due,
                days_past_due=days_past_due,
                last_contact=last_contact,
                next_action=next_action,
                total_paid=total_paid,
                outstanding_balance=max(outstanding, 0),
                phone=phone,
                # Enhanced fields
                case_id=case.id if case else None,
                case_status=case.status.value if case else None,
                delinquency_stage=case.delinquency_stage.value if case else None,
                assigned_agent_id=case.assigned_agent_id if case else None,
                assigned_agent_name=agent_name,
                next_best_action=case.next_best_action if case else None,
                nba_confidence=case.nba_confidence if case else None,
                dispute_active=case.dispute_active if case else False,
                vulnerability_flag=case.vulnerability_flag if case else False,
                do_not_contact=case.do_not_contact if case else False,
                hardship_flag=case.hardship_flag if case else False,
                priority_score=case.priority_score if case else 0,
            ))

        # Sort
        reverse = sort_dir.lower() == "desc"
        sort_key = sort_by if sort_by in ("days_past_due", "amount_due", "outstanding_balance", "priority_score") else "days_past_due"
        entries.sort(key=lambda x: getattr(x, sort_key, 0) or 0, reverse=reverse)

        # Pagination
        return entries[offset:offset + limit]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="get_collection_queue")
        raise


# ══════════════════════════════════════════════════════════════════════════
# Collection Cases CRUD
# ══════════════════════════════════════════════════════════════════════════

@router.get("/cases", response_model=list[CollectionCaseResponse])
async def list_collection_cases(
    status: Optional[str] = None,
    stage: Optional[str] = None,
    agent_id: Optional[int] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List collection cases with filters."""
    try:
        query = select(CollectionCase)
        if status:
            query = query.where(CollectionCase.status == CaseStatus(status))
        if stage:
            query = query.where(CollectionCase.delinquency_stage == DelinquencyStage(stage))
        if agent_id:
            query = query.where(CollectionCase.assigned_agent_id == agent_id)

        query = query.order_by(CollectionCase.priority_score.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        cases = result.scalars().all()

        responses = []
        for c in cases:
            agent_name = None
            if c.assigned_agent_id:
                ar = await db.execute(
                    select(User.first_name, User.last_name).where(User.id == c.assigned_agent_id)
                )
                agent_row = ar.one_or_none()
                if agent_row:
                    agent_name = f"{agent_row[0]} {agent_row[1]}"

            responses.append(CollectionCaseResponse(
                id=c.id,
                loan_application_id=c.loan_application_id,
                assigned_agent_id=c.assigned_agent_id,
                assigned_agent_name=agent_name,
                status=c.status.value,
                delinquency_stage=c.delinquency_stage.value,
                priority_score=c.priority_score,
                dpd=c.dpd,
                total_overdue=float(c.total_overdue),
                dispute_active=c.dispute_active,
                vulnerability_flag=c.vulnerability_flag,
                do_not_contact=c.do_not_contact,
                hardship_flag=c.hardship_flag,
                next_best_action=c.next_best_action,
                nba_confidence=c.nba_confidence,
                nba_reasoning=c.nba_reasoning,
                first_contact_at=c.first_contact_at,
                last_contact_at=c.last_contact_at,
                sla_first_contact_deadline=c.sla_first_contact_deadline,
                sla_next_contact_deadline=c.sla_next_contact_deadline,
                created_at=c.created_at,
                updated_at=c.updated_at,
            ))
        return responses
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="list_collection_cases")
        raise


@router.get("/cases/{case_id}", response_model=CollectionCaseResponse)
async def get_collection_case(
    case_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get full case detail."""
    try:
        result = await db.execute(
            select(CollectionCase).where(CollectionCase.id == case_id)
        )
        c = result.scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Collection case not found")

        agent_name = None
        if c.assigned_agent_id:
            ar = await db.execute(
                select(User.first_name, User.last_name).where(User.id == c.assigned_agent_id)
            )
            agent_row = ar.one_or_none()
            if agent_row:
                agent_name = f"{agent_row[0]} {agent_row[1]}"

        return CollectionCaseResponse(
            id=c.id,
            loan_application_id=c.loan_application_id,
            assigned_agent_id=c.assigned_agent_id,
            assigned_agent_name=agent_name,
            status=c.status.value,
            delinquency_stage=c.delinquency_stage.value,
            priority_score=c.priority_score,
            dpd=c.dpd,
            total_overdue=float(c.total_overdue),
            dispute_active=c.dispute_active,
            vulnerability_flag=c.vulnerability_flag,
            do_not_contact=c.do_not_contact,
            hardship_flag=c.hardship_flag,
            next_best_action=c.next_best_action,
            nba_confidence=c.nba_confidence,
            nba_reasoning=c.nba_reasoning,
            first_contact_at=c.first_contact_at,
            last_contact_at=c.last_contact_at,
            sla_first_contact_deadline=c.sla_first_contact_deadline,
            sla_next_contact_deadline=c.sla_next_contact_deadline,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="get_collection_case")
        raise


@router.patch("/cases/{case_id}", response_model=CollectionCaseResponse)
async def update_collection_case(
    case_id: int,
    data: CollectionCaseUpdate,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Update case — assign agent, set flags."""
    try:
        result = await db.execute(
            select(CollectionCase).where(CollectionCase.id == case_id)
        )
        c = result.scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Collection case not found")

        if data.assigned_agent_id is not None:
            c.assigned_agent_id = data.assigned_agent_id
            if c.status == CaseStatus.OPEN:
                c.status = CaseStatus.IN_PROGRESS
        if data.status is not None:
            c.status = CaseStatus(data.status)
        if data.dispute_active is not None:
            c.dispute_active = data.dispute_active
        if data.vulnerability_flag is not None:
            c.vulnerability_flag = data.vulnerability_flag
        if data.do_not_contact is not None:
            c.do_not_contact = data.do_not_contact
        if data.hardship_flag is not None:
            c.hardship_flag = data.hardship_flag

        c.updated_at = datetime.now(timezone.utc)

        # Recompute NBA after flag changes
        await update_case_nba(c, db)
        await db.flush()

        return await get_collection_case(case_id, current_user, db)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="update_collection_case")
        raise


@router.post("/cases/{case_id}/nba-override")
async def override_nba(
    case_id: int,
    data: NBAOverrideRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Agent overrides NBA recommendation."""
    try:
        result = await db.execute(
            select(CollectionCase).where(CollectionCase.id == case_id)
        )
        c = result.scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Case not found")

        c.next_best_action = data.action
        c.nba_confidence = 1.0
        c.nba_reasoning = f"Manual override by {current_user.first_name} {current_user.last_name}: {data.reason}"
        c.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {"status": "ok", "action": data.action}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="override_nba")
        raise


@router.post("/cases/bulk-assign")
async def bulk_assign_cases(
    data: BulkAssignRequest,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Bulk assign cases to an agent."""
    try:
        assigned = 0
        for cid in data.case_ids:
            result = await db.execute(
                select(CollectionCase).where(CollectionCase.id == cid)
            )
            c = result.scalar_one_or_none()
            if c:
                c.assigned_agent_id = data.agent_id
                if c.status == CaseStatus.OPEN:
                    c.status = CaseStatus.IN_PROGRESS
                c.updated_at = datetime.now(timezone.utc)
                assigned += 1
        await db.flush()
        return {"assigned": assigned}
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="bulk_assign_cases")
        raise


# ══════════════════════════════════════════════════════════════════════════
# Promise to Pay
# ══════════════════════════════════════════════════════════════════════════

@router.post("/cases/{case_id}/ptp", response_model=PromiseToPayResponse)
async def create_ptp(
    case_id: int,
    data: PromiseToPayCreate,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Create a promise-to-pay."""
    try:
        result = await db.execute(
            select(CollectionCase).where(CollectionCase.id == case_id)
        )
        c = result.scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Case not found")

        ptp = PromiseToPay(
            collection_case_id=case_id,
            loan_application_id=c.loan_application_id,
            agent_id=current_user.id,
            amount_promised=Decimal(str(data.amount_promised)),
            promise_date=data.promise_date,
            payment_method=data.payment_method,
            notes=data.notes,
        )
        db.add(ptp)
        await db.flush()
        await db.refresh(ptp)

        return PromiseToPayResponse(
            id=ptp.id,
            collection_case_id=ptp.collection_case_id,
            loan_application_id=ptp.loan_application_id,
            agent_id=ptp.agent_id,
            agent_name=f"{current_user.first_name} {current_user.last_name}",
            amount_promised=float(ptp.amount_promised),
            promise_date=ptp.promise_date,
            payment_method=ptp.payment_method,
            status=ptp.status.value,
            amount_received=float(ptp.amount_received),
            reminded_at=ptp.reminded_at,
            broken_at=ptp.broken_at,
            notes=ptp.notes,
            created_at=ptp.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="create_ptp")
        raise


@router.get("/cases/{case_id}/ptps", response_model=list[PromiseToPayResponse])
async def list_ptps(
    case_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List promises-to-pay for a case."""
    try:
        result = await db.execute(
            select(PromiseToPay, User.first_name, User.last_name)
            .join(User, PromiseToPay.agent_id == User.id)
            .where(PromiseToPay.collection_case_id == case_id)
            .order_by(PromiseToPay.created_at.desc())
        )
        entries = []
        for row in result.all():
            ptp = row[0]
            entries.append(PromiseToPayResponse(
                id=ptp.id,
                collection_case_id=ptp.collection_case_id,
                loan_application_id=ptp.loan_application_id,
                agent_id=ptp.agent_id,
                agent_name=f"{row[1]} {row[2]}",
                amount_promised=float(ptp.amount_promised),
                promise_date=ptp.promise_date,
                payment_method=ptp.payment_method,
                status=ptp.status.value,
                amount_received=float(ptp.amount_received),
                reminded_at=ptp.reminded_at,
                broken_at=ptp.broken_at,
                notes=ptp.notes,
                created_at=ptp.created_at,
            ))
        return entries
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="list_ptps")
        raise


@router.patch("/ptps/{ptp_id}", response_model=PromiseToPayResponse)
async def update_ptp(
    ptp_id: int,
    data: PromiseToPayUpdate,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Update PTP status."""
    try:
        result = await db.execute(
            select(PromiseToPay).where(PromiseToPay.id == ptp_id)
        )
        ptp = result.scalar_one_or_none()
        if not ptp:
            raise HTTPException(status_code=404, detail="PTP not found")

        if data.status:
            ptp.status = PTPStatus(data.status)
            if data.status == "broken":
                ptp.broken_at = datetime.now(timezone.utc)
        if data.notes is not None:
            ptp.notes = data.notes

        await db.flush()

        # Re-fetch with agent name
        agent_result = await db.execute(
            select(User.first_name, User.last_name).where(User.id == ptp.agent_id)
        )
        agent_row = agent_result.one_or_none()
        aname = f"{agent_row[0]} {agent_row[1]}" if agent_row else None

        return PromiseToPayResponse(
            id=ptp.id,
            collection_case_id=ptp.collection_case_id,
            loan_application_id=ptp.loan_application_id,
            agent_id=ptp.agent_id,
            agent_name=aname,
            amount_promised=float(ptp.amount_promised),
            promise_date=ptp.promise_date,
            payment_method=ptp.payment_method,
            status=ptp.status.value,
            amount_received=float(ptp.amount_received),
            reminded_at=ptp.reminded_at,
            broken_at=ptp.broken_at,
            notes=ptp.notes,
            created_at=ptp.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="update_ptp")
        raise


# ══════════════════════════════════════════════════════════════════════════
# Settlement Offers
# ══════════════════════════════════════════════════════════════════════════

@router.post("/cases/{case_id}/settlement", response_model=list[SettlementOfferResponse])
async def create_settlement(
    case_id: int,
    data: SettlementOfferCreate,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Create settlement offer(s). If auto_calculate=true, returns computed options."""
    try:
        result = await db.execute(
            select(CollectionCase).where(CollectionCase.id == case_id)
        )
        c = result.scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Case not found")

        if data.auto_calculate:
            options = calculate_settlement(c.total_overdue, c.dpd)
            offers = []
            for opt in options:
                offer = SettlementOffer(
                    collection_case_id=case_id,
                    loan_application_id=c.loan_application_id,
                    offer_type=SettlementOfferType(opt["offer_type"]),
                    original_balance=c.total_overdue,
                    settlement_amount=Decimal(str(opt["settlement_amount"])),
                    discount_pct=opt["discount_pct"],
                    plan_months=opt.get("plan_months"),
                    plan_monthly_amount=Decimal(str(opt["plan_monthly_amount"])) if opt.get("plan_monthly_amount") else None,
                    lump_sum=Decimal(str(opt["lump_sum"])) if opt.get("lump_sum") else None,
                    status=SettlementStatus.DRAFT,
                    offered_by=current_user.id,
                    approval_required=opt.get("approval_required", False),
                    notes=data.notes,
                )
                db.add(offer)
                offers.append(offer)
            await db.flush()
            for o in offers:
                await db.refresh(o)
        else:
            offer = SettlementOffer(
                collection_case_id=case_id,
                loan_application_id=c.loan_application_id,
                offer_type=SettlementOfferType(data.offer_type),
                original_balance=c.total_overdue,
                settlement_amount=Decimal(str(data.settlement_amount)),
                discount_pct=data.discount_pct,
                plan_months=data.plan_months,
                plan_monthly_amount=Decimal(str(data.plan_monthly_amount)) if data.plan_monthly_amount else None,
                lump_sum=Decimal(str(data.lump_sum)) if data.lump_sum else None,
                status=SettlementStatus.DRAFT,
                offered_by=current_user.id,
                approval_required=data.discount_pct > 5,
                notes=data.notes,
            )
            db.add(offer)
            await db.flush()
            await db.refresh(offer)
            offers = [offer]

        responses = []
        for o in offers:
            responses.append(SettlementOfferResponse(
                id=o.id,
                collection_case_id=o.collection_case_id,
                loan_application_id=o.loan_application_id,
                offer_type=o.offer_type.value,
                original_balance=float(o.original_balance),
                settlement_amount=float(o.settlement_amount),
                discount_pct=o.discount_pct,
                plan_months=o.plan_months,
                plan_monthly_amount=float(o.plan_monthly_amount) if o.plan_monthly_amount else None,
                lump_sum=float(o.lump_sum) if o.lump_sum else None,
                status=o.status.value,
                offered_by=o.offered_by,
                offered_by_name=f"{current_user.first_name} {current_user.last_name}",
                approved_by=o.approved_by,
                approval_required=o.approval_required,
                expires_at=o.expires_at,
                accepted_at=o.accepted_at,
                notes=o.notes,
                created_at=o.created_at,
            ))
        return responses
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="create_settlement")
        raise


@router.get("/cases/{case_id}/settlements", response_model=list[SettlementOfferResponse])
async def list_settlements(
    case_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List settlement offers for a case."""
    try:
        result = await db.execute(
            select(SettlementOffer)
            .where(SettlementOffer.collection_case_id == case_id)
            .order_by(SettlementOffer.created_at.desc())
        )
        offers = result.scalars().all()

        responses = []
        for o in offers:
            # Get names
            offered_result = await db.execute(
                select(User.first_name, User.last_name).where(User.id == o.offered_by)
            )
            offered_row = offered_result.one_or_none()
            offered_name = f"{offered_row[0]} {offered_row[1]}" if offered_row else None

            approved_name = None
            if o.approved_by:
                approved_result = await db.execute(
                    select(User.first_name, User.last_name).where(User.id == o.approved_by)
                )
                approved_row = approved_result.one_or_none()
                if approved_row:
                    approved_name = f"{approved_row[0]} {approved_row[1]}"

            responses.append(SettlementOfferResponse(
                id=o.id,
                collection_case_id=o.collection_case_id,
                loan_application_id=o.loan_application_id,
                offer_type=o.offer_type.value,
                original_balance=float(o.original_balance),
                settlement_amount=float(o.settlement_amount),
                discount_pct=o.discount_pct,
                plan_months=o.plan_months,
                plan_monthly_amount=float(o.plan_monthly_amount) if o.plan_monthly_amount else None,
                lump_sum=float(o.lump_sum) if o.lump_sum else None,
                status=o.status.value,
                offered_by=o.offered_by,
                offered_by_name=offered_name,
                approved_by=o.approved_by,
                approved_by_name=approved_name,
                approval_required=o.approval_required,
                expires_at=o.expires_at,
                accepted_at=o.accepted_at,
                notes=o.notes,
                created_at=o.created_at,
            ))
        return responses
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="list_settlements")
        raise


@router.patch("/settlements/{settlement_id}/approve")
async def approve_settlement(
    settlement_id: int,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Approve a settlement offer (supervisor+)."""
    try:
        result = await db.execute(
            select(SettlementOffer).where(SettlementOffer.id == settlement_id)
        )
        o = result.scalar_one_or_none()
        if not o:
            raise HTTPException(status_code=404, detail="Settlement not found")

        o.status = SettlementStatus.APPROVED
        o.approved_by = current_user.id
        await db.flush()
        return {"status": "approved", "id": o.id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="approve_settlement")
        raise


@router.patch("/settlements/{settlement_id}/accept")
async def accept_settlement(
    settlement_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Borrower accepts a settlement offer."""
    try:
        result = await db.execute(
            select(SettlementOffer).where(SettlementOffer.id == settlement_id)
        )
        o = result.scalar_one_or_none()
        if not o:
            raise HTTPException(status_code=404, detail="Settlement not found")

        if o.approval_required and o.status != SettlementStatus.APPROVED:
            raise HTTPException(status_code=400, detail="Settlement requires approval before acceptance")

        o.status = SettlementStatus.ACCEPTED
        o.accepted_at = datetime.now(timezone.utc)

        # Update case status
        case_result = await db.execute(
            select(CollectionCase).where(CollectionCase.id == o.collection_case_id)
        )
        case = case_result.scalar_one_or_none()
        if case:
            case.status = CaseStatus.SETTLED
            case.updated_at = datetime.now(timezone.utc)

        await db.flush()
        return {"status": "accepted", "id": o.id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="accept_settlement")
        raise


# ══════════════════════════════════════════════════════════════════════════
# Dashboard & Analytics
# ══════════════════════════════════════════════════════════════════════════

@router.get("/dashboard", response_model=CollectionsDashboardResponse)
async def get_dashboard(
    period_days: int = Query(30, ge=7, le=365),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Collections analytics dashboard data."""
    try:
        analytics = await get_collections_analytics(db, period_days)
        kpis = analytics["kpis"]

        return CollectionsDashboardResponse(
            total_delinquent_accounts=kpis.get("total_delinquent_accounts", 0),
            total_overdue_amount=kpis.get("total_overdue_amount", 0),
            by_stage=kpis.get("by_stage", {}),
            trend=analytics.get("trend", []),
            cure_rate=kpis.get("cure_rate", 0),
            ptp_rate=kpis.get("ptp_rate", 0) if "ptp_rate" in kpis else 0,
            ptp_kept_rate=kpis.get("ptp_kept_rate", 0),
            recovered_mtd=kpis.get("total_recovered_mtd", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="get_dashboard")
        raise


@router.get("/dashboard/agent-performance")
async def dashboard_agent_performance(
    period_days: int = Query(30, ge=7, le=365),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Per-agent metrics for the collections dashboard."""
    try:
        return await get_agent_performance(db)
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="dashboard_agent_performance")
        raise


# ══════════════════════════════════════════════════════════════════════════
# Compliance Rules
# ══════════════════════════════════════════════════════════════════════════

@router.get("/compliance-rules", response_model=list[ComplianceRuleResponse])
async def list_compliance_rules(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List all compliance rules."""
    try:
        result = await db.execute(
            select(ComplianceRule).order_by(ComplianceRule.jurisdiction)
        )
        return result.scalars().all()
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="list_compliance_rules")
        raise


@router.post("/compliance-rules", response_model=ComplianceRuleResponse)
async def create_compliance_rule(
    data: ComplianceRuleCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Create or update a compliance rule (admin only)."""
    try:
        # Upsert by jurisdiction
        existing_result = await db.execute(
            select(ComplianceRule).where(ComplianceRule.jurisdiction == data.jurisdiction)
        )
        rule = existing_result.scalar_one_or_none()

        if rule:
            for field, value in data.model_dump().items():
                setattr(rule, field, value)
        else:
            rule = ComplianceRule(**data.model_dump())
            db.add(rule)

        await db.flush()
        await db.refresh(rule)
        return rule
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="create_compliance_rule")
        raise


@router.post("/check-compliance", response_model=ComplianceCheckResponse)
async def check_compliance_endpoint(
    data: ComplianceCheckRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Check if contacting a borrower is allowed right now."""
    try:
        result = await db.execute(
            select(CollectionCase).where(CollectionCase.id == data.case_id)
        )
        case = result.scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        compliance = await check_compliance(case, data.jurisdiction, db)
        return ComplianceCheckResponse(**compliance)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="check_compliance_endpoint")
        raise


# ══════════════════════════════════════════════════════════════════════════
# Export
# ══════════════════════════════════════════════════════════════════════════

@router.get("/export-csv")
async def export_queue_csv(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Export collection queue to CSV."""
    try:
        entries = await get_collection_queue(
            search=None, stage=None, status=None, agent_id=None,
            sort_by="days_past_due", sort_dir="desc", limit=10000, offset=0,
            current_user=current_user, db=db,
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Reference", "Applicant", "Amount Due", "Days Past Due",
            "Outstanding Balance", "Stage", "Status", "NBA", "Phone",
        ])
        for e in entries:
            writer.writerow([
                e.reference_number, e.applicant_name, f"{e.amount_due:.2f}",
                e.days_past_due, f"{e.outstanding_balance:.2f}",
                e.delinquency_stage or "", e.case_status or "",
                e.next_best_action or "", e.phone or "",
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=collections_queue.csv"},
        )
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="export_queue_csv")
        raise


# ══════════════════════════════════════════════════════════════════════════
# Sync Cases (manual trigger)
# ══════════════════════════════════════════════════════════════════════════

@router.post("/sync-cases")
async def trigger_sync_cases(
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger case sync + NBA computation."""
    try:
        result = await sync_collection_cases(db)

        # Compute NBA for all open cases
        case_result = await db.execute(
            select(CollectionCase).where(
                CollectionCase.status.in_([CaseStatus.OPEN, CaseStatus.IN_PROGRESS])
            )
        )
        cases = case_result.scalars().all()
        for c in cases:
            await compute_next_best_action(c, db)
        await db.flush()

        result["nba_computed"] = len(cases)
        return result
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="trigger_sync_cases")
        raise


# ══════════════════════════════════════════════════════════════════════════
# Legacy endpoints (preserved for backward compat)
# ══════════════════════════════════════════════════════════════════════════

@router.get("/{application_id}/history", response_model=list[CollectionRecordResponse])
async def get_collection_history(
    application_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get all collection interaction records for a loan."""
    try:
        result = await db.execute(
            select(CollectionRecord, User.first_name, User.last_name)
            .join(User, CollectionRecord.agent_id == User.id)
            .where(CollectionRecord.loan_application_id == application_id)
            .order_by(CollectionRecord.created_at.desc())
        )
        entries = []
        for row in result.all():
            record = row[0]
            entries.append(CollectionRecordResponse(
                id=record.id,
                loan_application_id=record.loan_application_id,
                agent_id=record.agent_id,
                agent_name=f"{row[1]} {row[2]}",
                channel=record.channel.value,
                notes=record.notes,
                action_taken=record.action_taken,
                outcome=record.outcome.value,
                next_action_date=record.next_action_date,
                promise_amount=float(record.promise_amount) if record.promise_amount else None,
                promise_date=record.promise_date,
                created_at=record.created_at,
            ))
        return entries
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="get_collection_history")
        raise


@router.post("/{application_id}/record", response_model=CollectionRecordResponse)
async def add_collection_record(
    application_id: int,
    data: CollectionRecordCreate,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Add a collection interaction record."""
    try:
        # Find collection case (if exists) to link
        case_result = await db.execute(
            select(CollectionCase).where(CollectionCase.loan_application_id == application_id)
        )
        case = case_result.scalar_one_or_none()

        record = CollectionRecord(
            loan_application_id=application_id,
            agent_id=current_user.id,
            collection_case_id=case.id if case else None,
            channel=CollectionChannel(data.channel),
            notes=data.notes,
            action_taken=data.action_taken,
            outcome=CollectionOutcome(data.outcome),
            next_action_date=data.next_action_date,
            promise_amount=data.promise_amount,
            promise_date=data.promise_date,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)

        # Update case contact tracking
        if case:
            now = datetime.now(timezone.utc)
            if not case.first_contact_at:
                case.first_contact_at = now
            case.last_contact_at = now
            case.updated_at = now

        return CollectionRecordResponse(
            id=record.id,
            loan_application_id=record.loan_application_id,
            agent_id=record.agent_id,
            agent_name=f"{current_user.first_name} {current_user.last_name}",
            channel=record.channel.value,
            notes=record.notes,
            action_taken=record.action_taken,
            outcome=record.outcome.value,
            next_action_date=record.next_action_date,
            promise_amount=float(record.promise_amount) if record.promise_amount else None,
            promise_date=record.promise_date,
            created_at=record.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="add_collection_record")
        raise


@router.get("/{application_id}/chat", response_model=list[CollectionChatResponse])
async def get_chat_history(
    application_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get WhatsApp chat history for a loan."""
    try:
        result = await db.execute(
            select(CollectionChat)
            .where(CollectionChat.loan_application_id == application_id)
            .order_by(CollectionChat.created_at.asc())
        )
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="get_chat_history")
        raise


@router.post("/{application_id}/send-whatsapp", response_model=list[CollectionChatResponse])
async def send_whatsapp(
    application_id: int,
    data: CollectionChatCreate,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Send a WhatsApp message via Twilio."""
    try:
        app_result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == application_id)
        )
        app = app_result.scalar_one_or_none()
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")

        user_result = await db.execute(
            select(User).where(User.id == app.applicant_id)
        )
        applicant = user_result.scalar_one_or_none()
        phone = applicant.phone if applicant else "+1868-555-0000"

        twilio_result = await send_whatsapp_message(phone, data.message)
        twilio_error = twilio_result.get("error")
        status = ChatMessageStatus.FAILED if twilio_error else ChatMessageStatus.SENT

        outbound = CollectionChat(
            loan_application_id=application_id,
            agent_id=current_user.id,
            phone_number=phone,
            direction=ChatDirection.OUTBOUND,
            message=data.message,
            channel="whatsapp",
            status=status,
        )
        db.add(outbound)
        await db.flush()
        await db.refresh(outbound)

        if twilio_error:
            logger.warning("WhatsApp send failed for app %s: %s", application_id, twilio_error)

        return [outbound]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collections", function_name="send_whatsapp")
        raise
