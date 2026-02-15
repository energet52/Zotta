"""Seed 5 realistic Customer 360 personas for development and testing.

Run: python -m seed_customer360
Or:  cd backend && python seed_customer360.py

Each persona has realistic: User + Profile, LoanApplications, Decisions,
PaymentSchedules + Payments, CollectionRecords + Chats, Documents, CreditReports,
AuditLog entries, ApplicationComments, ApplicationNotes, Conversations.
"""

import asyncio
import random
import string
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base
from app.auth_utils import hash_password
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus, LoanPurpose, ApplicantProfile
from app.models.decision import Decision, DecisionOutcome, UnderwriterAction
from app.models.disbursement import Disbursement, DisbursementMethod, DisbursementStatus
from app.models.payment import Payment, PaymentType, PaymentStatus, PaymentSchedule, ScheduleStatus
from app.models.collection import CollectionRecord, CollectionChat, CollectionChannel, CollectionOutcome, ChatDirection, ChatMessageStatus
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.credit_report import CreditReport
from app.models.audit import AuditLog
from app.models.comment import ApplicationComment
from app.models.note import ApplicationNote
from app.models.conversation import Conversation, ConversationMessage, ConversationChannel, ConversationState, ConversationEntryPoint, MessageRole
from app.models.credit_bureau_alert import CreditBureauAlert, AlertType, AlertSeverity, AlertStatus


# ── Helpers ─────────────────────────────────────────

def _ts(d: date | datetime) -> datetime:
    """Ensure we have a timezone-aware datetime."""
    if isinstance(d, datetime):
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
    return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)


def _ref() -> str:
    chars = string.ascii_uppercase + string.digits
    return f"ZOT-2026-{''.join(random.choices(chars, k=8))}"


def _make_schedule(
    app_id: int, principal: float, rate: float, term: int,
    start_date: date, paid_through: int = 0, overdue_from: int | None = None,
    partial_at: list[int] | None = None,
) -> tuple[list[PaymentSchedule], list[Payment]]:
    """Generate an amortisation schedule and matching payments."""
    monthly_rate = rate / 100 / 12
    if monthly_rate > 0:
        pmt = principal * monthly_rate / (1 - (1 + monthly_rate) ** -term)
    else:
        pmt = principal / term

    schedules: list[PaymentSchedule] = []
    payments: list[Payment] = []
    balance = principal
    partial_set = set(partial_at or [])
    today = date.today()

    for i in range(1, term + 1):
        due = start_date + timedelta(days=30 * i)
        interest = round(balance * monthly_rate, 2)
        princ = round(pmt - interest, 2)
        if princ > balance:
            princ = balance
        amount_due = round(princ + interest, 2)
        balance = max(0, balance - princ)

        if i <= paid_through and i not in partial_set:
            status = ScheduleStatus.PAID
            amount_paid = amount_due
            paid_at = _ts(due + timedelta(days=random.randint(-2, 3)))
        elif i in partial_set:
            status = ScheduleStatus.PARTIAL
            amount_paid = round(amount_due * random.uniform(0.3, 0.6), 2)
            paid_at = _ts(due + timedelta(days=random.randint(5, 15)))
        elif overdue_from and i >= overdue_from and due <= today:
            status = ScheduleStatus.OVERDUE
            amount_paid = 0
            paid_at = None
        elif due > today:
            status = ScheduleStatus.UPCOMING
            amount_paid = 0
            paid_at = None
        else:
            status = ScheduleStatus.PAID
            amount_paid = amount_due
            paid_at = _ts(due + timedelta(days=random.randint(-1, 2)))

        s = PaymentSchedule(
            loan_application_id=app_id,
            installment_number=i,
            due_date=due,
            principal=princ,
            interest=interest,
            fee=0,
            amount_due=amount_due,
            amount_paid=amount_paid,
            status=status,
            paid_at=paid_at,
        )
        schedules.append(s)

        if amount_paid > 0:
            payments.append(Payment(
                loan_application_id=app_id,
                amount=amount_paid,
                payment_type=random.choice([PaymentType.ONLINE, PaymentType.BANK_TRANSFER, PaymentType.MANUAL]),
                payment_date=paid_at.date() if paid_at else due,
                reference_number=f"PAY-{random.randint(10000, 99999)}",
                status=PaymentStatus.COMPLETED,
                notes=None,
            ))

    return schedules, payments


async def seed_personas():
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        # Ensure a staff user exists for agent_id references
        staff_result = await db.execute(
            select(User).where(User.role != UserRole.APPLICANT).limit(1)
        )
        staff = staff_result.scalar_one_or_none()
        if not staff:
            staff = User(
                email="admin@zotta.tt", hashed_password=hash_password("Admin123!"),
                first_name="Admin", last_name="Zotta", role=UserRole.ADMIN,
            )
            db.add(staff)
            await db.flush()

        print("Seeding 5 Customer 360 personas...")

        await _persona_perfect_borrower(db, staff.id)
        await _persona_recovering(db, staff.id)
        await _persona_deteriorating(db, staff.id)
        await _persona_new_customer(db, staff.id)
        await _persona_complex(db, staff.id)

        await db.commit()
        print("Done! 5 personas created.")


# ══════════════════════════════════════════════════════════════════════════
# PERSONA 1: The Perfect Borrower
# ══════════════════════════════════════════════════════════════════════════

async def _persona_perfect_borrower(db: AsyncSession, staff_id: int):
    print("  1/5 Perfect Borrower — Angela Maharaj")
    today = date.today()
    start = today - timedelta(days=3 * 365)  # 3 years ago

    user = User(
        email="angela.maharaj@email.com", hashed_password=hash_password("Test1234!"),
        first_name="Angela", last_name="Maharaj", phone="+18687001001", role=UserRole.APPLICANT,
    )
    db.add(user)
    await db.flush()

    profile = ApplicantProfile(
        user_id=user.id, date_of_birth=date(1988, 3, 15),
        id_type="national_id", national_id="19880315421",
        gender="female", marital_status="married",
        address_line1="14 St. Ann's Road", city="Port of Spain", parish="Port of Spain", country="Trinidad and Tobago",
        employer_name="Republic Bank", job_title="Senior Accountant",
        employment_type="employed", years_employed=8,
        monthly_income=18500, other_income=2000, monthly_expenses=7500,
        existing_debt=5000, dependents=2,
        whatsapp_number="+18687001001", contact_email="angela.maharaj@email.com",
        mobile_phone="+18687001001",
        id_verified=True, id_verification_status="verified",
    )
    db.add(profile)

    # ── Loan 1 (completed) ─────────────────────────────────
    loan1 = LoanApplication(
        reference_number=_ref(), applicant_id=user.id,
        amount_requested=50000, term_months=24, purpose=LoanPurpose.PERSONAL,
        interest_rate=12.5, amount_approved=50000, monthly_payment=2373,
        status=LoanStatus.DISBURSED,
        submitted_at=_ts(start), decided_at=_ts(start + timedelta(days=1)),
        disbursed_at=_ts(start + timedelta(days=3)),
        created_at=_ts(start),
    )
    db.add(loan1)
    await db.flush()
    schedules1, payments1 = _make_schedule(loan1.id, 50000, 12.5, 24, start, paid_through=24)
    db.add_all(schedules1 + payments1)

    db.add(Decision(
        loan_application_id=loan1.id, credit_score=720, risk_band="A",
        engine_outcome=DecisionOutcome.AUTO_APPROVE, underwriter_action=UnderwriterAction.APPROVE,
        final_outcome="approved", created_at=_ts(start + timedelta(days=1)),
    ))
    db.add(Disbursement(
        loan_application_id=loan1.id, amount=50000, method=DisbursementMethod.BANK_TRANSFER,
        status=DisbursementStatus.COMPLETED, disbursed_by=staff_id,
        disbursed_at=_ts(start + timedelta(days=3)),
    ))
    db.add(CreditReport(
        loan_application_id=loan1.id, provider="mock", national_id="19880315421",
        bureau_score=720, report_data={"summary": "Excellent credit"}, status="success",
        pulled_at=_ts(start),
    ))

    # ── Loan 2 (completed) ─────────────────────────────────
    loan2_start = start + timedelta(days=365)
    loan2 = LoanApplication(
        reference_number=_ref(), applicant_id=user.id,
        amount_requested=80000, term_months=36, purpose=LoanPurpose.HOME_IMPROVEMENT,
        interest_rate=11.0, amount_approved=80000, monthly_payment=2618,
        status=LoanStatus.DISBURSED,
        submitted_at=_ts(loan2_start), decided_at=_ts(loan2_start + timedelta(days=1)),
        disbursed_at=_ts(loan2_start + timedelta(days=2)),
        created_at=_ts(loan2_start),
    )
    db.add(loan2)
    await db.flush()
    months_since_l2 = (today - loan2_start).days // 30
    schedules2, payments2 = _make_schedule(loan2.id, 80000, 11.0, 36, loan2_start, paid_through=min(months_since_l2, 36))
    db.add_all(schedules2 + payments2)

    db.add(Decision(
        loan_application_id=loan2.id, credit_score=735, risk_band="A",
        engine_outcome=DecisionOutcome.AUTO_APPROVE, underwriter_action=UnderwriterAction.APPROVE,
        final_outcome="approved", created_at=_ts(loan2_start + timedelta(days=1)),
    ))
    db.add(CreditReport(
        loan_application_id=loan2.id, provider="mock", national_id="19880315421",
        bureau_score=735, status="success", pulled_at=_ts(loan2_start),
    ))

    # ── Loan 3 (completed) ─────────────────────────────────
    loan3_start = start + timedelta(days=730)
    loan3 = LoanApplication(
        reference_number=_ref(), applicant_id=user.id,
        amount_requested=30000, term_months=12, purpose=LoanPurpose.EDUCATION,
        interest_rate=10.5, amount_approved=30000, monthly_payment=2647,
        status=LoanStatus.DISBURSED,
        submitted_at=_ts(loan3_start), decided_at=_ts(loan3_start + timedelta(days=1)),
        disbursed_at=_ts(loan3_start + timedelta(days=2)),
        created_at=_ts(loan3_start),
    )
    db.add(loan3)
    await db.flush()
    months_since_l3 = (today - loan3_start).days // 30
    schedules3, payments3 = _make_schedule(loan3.id, 30000, 10.5, 12, loan3_start, paid_through=min(months_since_l3, 12))
    db.add_all(schedules3 + payments3)

    # ── Loan 4 (active) ────────────────────────────────────
    loan4_start = today - timedelta(days=120)
    loan4 = LoanApplication(
        reference_number=_ref(), applicant_id=user.id,
        amount_requested=120000, term_months=48, purpose=LoanPurpose.VEHICLE,
        interest_rate=13.0, amount_approved=120000, monthly_payment=3220,
        status=LoanStatus.DISBURSED,
        submitted_at=_ts(loan4_start), decided_at=_ts(loan4_start + timedelta(days=1)),
        disbursed_at=_ts(loan4_start + timedelta(days=3)),
        created_at=_ts(loan4_start),
    )
    db.add(loan4)
    await db.flush()
    months_l4 = (today - loan4_start).days // 30
    schedules4, payments4 = _make_schedule(loan4.id, 120000, 13.0, 48, loan4_start, paid_through=months_l4)
    db.add_all(schedules4 + payments4)
    db.add(Decision(
        loan_application_id=loan4.id, credit_score=742, risk_band="A",
        engine_outcome=DecisionOutcome.AUTO_APPROVE, underwriter_action=UnderwriterAction.APPROVE,
        final_outcome="approved", created_at=_ts(loan4_start + timedelta(days=1)),
    ))
    db.add(CreditReport(
        loan_application_id=loan4.id, provider="mock", national_id="19880315421",
        bureau_score=742, status="success", pulled_at=_ts(loan4_start),
    ))

    # Documents
    for lid in [loan1.id, loan2.id, loan3.id, loan4.id]:
        for dt in [DocumentType.NATIONAL_ID, DocumentType.PROOF_OF_INCOME]:
            db.add(Document(
                loan_application_id=lid, uploaded_by=user.id, document_type=dt,
                file_name=f"{dt.value}_{lid}.pdf", file_path=f"/uploads/{dt.value}_{lid}.pdf",
                file_size=random.randint(50000, 200000), mime_type="application/pdf",
                status=DocumentStatus.VERIFIED,
            ))

    # Audit logs
    for lid in [loan1.id, loan2.id, loan3.id, loan4.id]:
        db.add(AuditLog(entity_type="loan_application", entity_id=lid, action="submitted", user_id=user.id))
        db.add(AuditLog(entity_type="loan_application", entity_id=lid, action="approved", user_id=staff_id))
        db.add(AuditLog(entity_type="loan_application", entity_id=lid, action="disbursed", user_id=staff_id))

    # Conversation
    conv = Conversation(
        channel=ConversationChannel.WEB, participant_user_id=user.id,
        current_state=ConversationState.DISBURSED, entry_point=ConversationEntryPoint.RETURNING_APPLICANT,
        loan_application_id=loan4.id, created_at=_ts(loan4_start - timedelta(days=1)),
    )
    db.add(conv)
    await db.flush()
    db.add(ConversationMessage(conversation_id=conv.id, role=MessageRole.USER, content="Hi, I'd like to apply for a vehicle loan."))
    db.add(ConversationMessage(conversation_id=conv.id, role=MessageRole.ASSISTANT, content="Welcome back Angela! Great to see you again. I see you have an excellent track record with us. Let me help you with a vehicle loan."))

    await db.flush()
    print(f"    Created user #{user.id} with 4 loans, {len(payments1)+len(payments2)+len(payments3)+len(payments4)} payments")


# ══════════════════════════════════════════════════════════════════════════
# PERSONA 2: The Recovering Customer
# ══════════════════════════════════════════════════════════════════════════

async def _persona_recovering(db: AsyncSession, staff_id: int):
    print("  2/5 Recovering Customer — Darren Baptiste")
    today = date.today()
    start = today - timedelta(days=2 * 365)

    user = User(
        email="darren.baptiste@email.com", hashed_password=hash_password("Test1234!"),
        first_name="Darren", last_name="Baptiste", phone="+18687002002", role=UserRole.APPLICANT,
    )
    db.add(user)
    await db.flush()

    profile = ApplicantProfile(
        user_id=user.id, date_of_birth=date(1985, 7, 22),
        id_type="national_id", national_id="19850722310",
        gender="male", marital_status="divorced",
        address_line1="82 Churchill Roosevelt Hwy", city="Tunapuna", parish="Tunapuna/Piarco",
        employer_name="TSTT", job_title="Network Technician",
        employment_type="employed", years_employed=5,
        monthly_income=12000, other_income=0, monthly_expenses=6000,
        existing_debt=15000, dependents=1,
        mobile_phone="+18687002002",
        id_verified=True, id_verification_status="verified",
    )
    db.add(profile)

    # Loan 1 — had 90+ DPD, restructured
    loan = LoanApplication(
        reference_number=_ref(), applicant_id=user.id,
        amount_requested=75000, term_months=36, purpose=LoanPurpose.DEBT_CONSOLIDATION,
        interest_rate=16.0, amount_approved=75000, monthly_payment=2637,
        status=LoanStatus.DISBURSED,
        submitted_at=_ts(start), decided_at=_ts(start + timedelta(days=2)),
        disbursed_at=_ts(start + timedelta(days=5)),
        created_at=_ts(start),
    )
    db.add(loan)
    await db.flush()

    # First 12 months on time, then 3 months missed (months 13-15), then restructured, paying since
    months_total = (today - start).days // 30
    schedules = []
    payments_list = []

    # Build manual schedule: paid 1-12, overdue 13-15 (then cleared), paid 16-now
    monthly_rate = 0.16 / 12
    pmt = 75000 * monthly_rate / (1 - (1 + monthly_rate) ** -36)
    balance = 75000
    for i in range(1, min(months_total + 1, 37)):
        due = start + timedelta(days=30 * i)
        interest = round(balance * monthly_rate, 2)
        princ = round(pmt - interest, 2)
        if princ > balance:
            princ = balance
        amount_due = round(princ + interest, 2)
        balance = max(0, balance - princ)

        if i <= 12:
            status = ScheduleStatus.PAID
            amt_paid = amount_due
            paid_at = _ts(due + timedelta(days=random.randint(-1, 3)))
        elif 13 <= i <= 15:
            # Was overdue but eventually paid (hardship period, then caught up)
            status = ScheduleStatus.PAID
            amt_paid = amount_due
            paid_at = _ts(start + timedelta(days=30 * 16 + random.randint(0, 10)))  # Paid late in bulk
        elif i <= months_total:
            status = ScheduleStatus.PAID
            amt_paid = amount_due
            paid_at = _ts(due + timedelta(days=random.randint(-1, 2)))
        else:
            status = ScheduleStatus.UPCOMING
            amt_paid = 0
            paid_at = None

        s = PaymentSchedule(
            loan_application_id=loan.id, installment_number=i, due_date=due,
            principal=princ, interest=interest, fee=0,
            amount_due=amount_due, amount_paid=amt_paid,
            status=status, paid_at=paid_at,
        )
        schedules.append(s)
        if amt_paid > 0:
            payments_list.append(Payment(
                loan_application_id=loan.id, amount=amt_paid,
                payment_type=PaymentType.BANK_TRANSFER, payment_date=paid_at.date() if paid_at else due,
                reference_number=f"PAY-{random.randint(10000, 99999)}",
                status=PaymentStatus.COMPLETED,
            ))

    db.add_all(schedules + payments_list)

    db.add(Decision(
        loan_application_id=loan.id, credit_score=645, risk_band="C",
        engine_outcome=DecisionOutcome.MANUAL_REVIEW, underwriter_action=UnderwriterAction.APPROVE,
        override_reason="Debt consolidation with stable income", final_outcome="approved",
    ))
    db.add(CreditReport(
        loan_application_id=loan.id, provider="mock", national_id="19850722310",
        bureau_score=645, status="success", pulled_at=_ts(start),
    ))
    # Score improved after recovery
    db.add(CreditReport(
        loan_application_id=loan.id, provider="mock", national_id="19850722310",
        bureau_score=672, status="success", pulled_at=_ts(today - timedelta(days=60)),
    ))

    # Collection records during arrears
    arrears_start = start + timedelta(days=30 * 13 + 10)
    for offset_days, channel, outcome, notes in [
        (0, CollectionChannel.PHONE, CollectionOutcome.NO_ANSWER, "Called, no answer"),
        (5, CollectionChannel.SMS, CollectionOutcome.OTHER, "SMS reminder sent"),
        (12, CollectionChannel.PHONE, CollectionOutcome.PROMISE_TO_PAY, "Spoke with borrower. Says lost job, will pay once new job starts."),
        (30, CollectionChannel.WHATSAPP, CollectionOutcome.PAYMENT_ARRANGED, "New job confirmed. Arranged catch-up payments."),
    ]:
        db.add(CollectionRecord(
            loan_application_id=loan.id, agent_id=staff_id,
            channel=channel, notes=notes, action_taken="Follow up",
            outcome=outcome,
            promise_amount=7900 if outcome == CollectionOutcome.PROMISE_TO_PAY else None,
            promise_date=(arrears_start + timedelta(days=offset_days + 14)) if outcome == CollectionOutcome.PROMISE_TO_PAY else None,
            created_at=_ts(arrears_start + timedelta(days=offset_days)),
        ))

    # Collection chats
    db.add(CollectionChat(
        loan_application_id=loan.id, agent_id=staff_id, phone_number="+18687002002",
        direction=ChatDirection.OUTBOUND, message="Hi Darren, this is Zotta regarding your overdue payment. Please contact us.",
        channel="whatsapp", status=ChatMessageStatus.DELIVERED, created_at=_ts(arrears_start + timedelta(days=5)),
    ))
    db.add(CollectionChat(
        loan_application_id=loan.id, phone_number="+18687002002",
        direction=ChatDirection.INBOUND, message="Sorry about that, I lost my job. Starting a new one next month. Can we work something out?",
        channel="whatsapp", status=ChatMessageStatus.DELIVERED, created_at=_ts(arrears_start + timedelta(days=6)),
    ))

    # Documents
    db.add(Document(
        loan_application_id=loan.id, uploaded_by=user.id, document_type=DocumentType.NATIONAL_ID,
        file_name="darren_id.pdf", file_path="/uploads/darren_id.pdf",
        file_size=120000, mime_type="application/pdf", status=DocumentStatus.VERIFIED,
    ))

    # Audit
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="submitted", user_id=user.id))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="approved", user_id=staff_id))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="disbursed", user_id=staff_id))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="arrears_flagged", user_id=staff_id, details="90+ DPD reached"))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="restructure_offered", user_id=staff_id))

    # Notes
    db.add(ApplicationNote(application_id=loan.id, user_id=staff_id, content="Borrower experienced job loss. New employment confirmed at TSTT."))
    db.add(ApplicationNote(application_id=loan.id, user_id=staff_id, content="Catch-up payments received. Account normalising."))

    await db.flush()
    print(f"    Created user #{user.id} with 1 loan, recovery arc")


# ══════════════════════════════════════════════════════════════════════════
# PERSONA 3: The Deteriorating Account
# ══════════════════════════════════════════════════════════════════════════

async def _persona_deteriorating(db: AsyncSession, staff_id: int):
    print("  3/5 Deteriorating Account — Kevin Persad")
    today = date.today()
    start = today - timedelta(days=2 * 365)

    user = User(
        email="kevin.persad360@email.com", hashed_password=hash_password("Test1234!"),
        first_name="Kevin", last_name="Persad", phone="+18687003003", role=UserRole.APPLICANT,
    )
    db.add(user)
    await db.flush()

    profile = ApplicantProfile(
        user_id=user.id, date_of_birth=date(1990, 11, 5),
        id_type="national_id", national_id="19901105289",
        gender="male", marital_status="single",
        address_line1="45 Maraval Road", city="Maraval", parish="Port of Spain",
        employer_name="Massy Stores", job_title="Store Manager",
        employment_type="employed", years_employed=4,
        monthly_income=14000, other_income=1500, monthly_expenses=8000,
        existing_debt=20000, dependents=0,
        mobile_phone="+18687003003",
        id_verified=True, id_verification_status="verified",
    )
    db.add(profile)

    # Loan — was good for 20 months, then started missing last 2 months
    loan = LoanApplication(
        reference_number=_ref(), applicant_id=user.id,
        amount_requested=100000, term_months=36, purpose=LoanPurpose.PERSONAL,
        interest_rate=14.5, amount_approved=100000, monthly_payment=3444,
        status=LoanStatus.DISBURSED,
        submitted_at=_ts(start), decided_at=_ts(start + timedelta(days=1)),
        disbursed_at=_ts(start + timedelta(days=3)),
        created_at=_ts(start),
    )
    db.add(loan)
    await db.flush()

    months_total = (today - start).days // 30
    paid_through = max(0, months_total - 2)  # Last 2 months missed
    schedules, payments_list = _make_schedule(
        loan.id, 100000, 14.5, 36, start,
        paid_through=paid_through, overdue_from=paid_through + 1,
    )
    db.add_all(schedules + payments_list)

    db.add(Decision(
        loan_application_id=loan.id, credit_score=695, risk_band="B",
        engine_outcome=DecisionOutcome.AUTO_APPROVE, underwriter_action=UnderwriterAction.APPROVE,
        final_outcome="approved",
    ))
    db.add(CreditReport(
        loan_application_id=loan.id, provider="mock", national_id="19901105289",
        bureau_score=695, status="success", pulled_at=_ts(start),
    ))
    # Score dropping
    db.add(CreditReport(
        loan_application_id=loan.id, provider="mock", national_id="19901105289",
        bureau_score=670, status="success", pulled_at=_ts(today - timedelta(days=45)),
    ))
    db.add(CreditReport(
        loan_application_id=loan.id, provider="mock", national_id="19901105289",
        bureau_score=652, status="success", pulled_at=_ts(today - timedelta(days=10)),
    ))

    # Recent collection attempts — no answer
    for d, ch, outcome in [
        (today - timedelta(days=20), CollectionChannel.PHONE, CollectionOutcome.NO_ANSWER),
        (today - timedelta(days=10), CollectionChannel.PHONE, CollectionOutcome.NO_ANSWER),
    ]:
        db.add(CollectionRecord(
            loan_application_id=loan.id, agent_id=staff_id,
            channel=ch, notes="Attempted call, no answer", action_taken="Call attempt",
            outcome=outcome, created_at=_ts(d),
        ))

    # WhatsApp sent, no reply
    db.add(CollectionChat(
        loan_application_id=loan.id, agent_id=staff_id, phone_number="+18687003003",
        direction=ChatDirection.OUTBOUND, message="Hi Kevin, we noticed your last 2 payments are overdue. Please get in touch with us to discuss options.",
        channel="whatsapp", status=ChatMessageStatus.DELIVERED, created_at=_ts(today - timedelta(days=8)),
    ))

    # Documents
    db.add(Document(
        loan_application_id=loan.id, uploaded_by=user.id, document_type=DocumentType.NATIONAL_ID,
        file_name="kevin_id.pdf", file_path="/uploads/kevin_id.pdf",
        file_size=95000, mime_type="application/pdf", status=DocumentStatus.VERIFIED,
    ))
    db.add(Document(
        loan_application_id=loan.id, uploaded_by=user.id, document_type=DocumentType.BANK_STATEMENT,
        file_name="kevin_bank_stmt.pdf", file_path="/uploads/kevin_bank_stmt.pdf",
        file_size=180000, mime_type="application/pdf", status=DocumentStatus.VERIFIED,
    ))

    # Audit
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="submitted", user_id=user.id))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="approved", user_id=staff_id))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="disbursed", user_id=staff_id))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="payment_missed", details="First missed payment detected"))

    # Comment from customer (unanswered)
    db.add(ApplicationComment(
        application_id=loan.id, user_id=user.id, content="I've been having some financial difficulties. Is there any way to defer my next payment?",
        is_from_applicant=True,
    ))

    await db.flush()
    print(f"    Created user #{user.id} with 1 loan, deteriorating (2 months overdue)")


# ══════════════════════════════════════════════════════════════════════════
# PERSONA 4: The New Customer
# ══════════════════════════════════════════════════════════════════════════

async def _persona_new_customer(db: AsyncSession, staff_id: int):
    print("  4/5 New Customer — Priya Ramnath")
    today = date.today()
    start = today - timedelta(days=35)

    user = User(
        email="priya.ramnath@email.com", hashed_password=hash_password("Test1234!"),
        first_name="Priya", last_name="Ramnath", phone="+18687004004", role=UserRole.APPLICANT,
    )
    db.add(user)
    await db.flush()

    profile = ApplicantProfile(
        user_id=user.id, date_of_birth=date(1996, 1, 20),
        id_type="national_id", national_id="19960120567",
        gender="female", marital_status="single",
        address_line1="12 Henry St", city="Chaguanas", parish="Chaguanas",
        employer_name="Digicel", job_title="Marketing Executive",
        employment_type="employed", years_employed=2,
        monthly_income=10000, other_income=0, monthly_expenses=5500,
        existing_debt=0, dependents=0,
        mobile_phone="+18687004004", whatsapp_number="+18687004004",
        id_verified=True, id_verification_status="verified",
    )
    db.add(profile)

    loan = LoanApplication(
        reference_number=_ref(), applicant_id=user.id,
        amount_requested=40000, term_months=24, purpose=LoanPurpose.PERSONAL,
        interest_rate=15.0, amount_approved=40000, monthly_payment=1941,
        status=LoanStatus.DISBURSED,
        submitted_at=_ts(start), decided_at=_ts(start + timedelta(days=1)),
        disbursed_at=_ts(start + timedelta(days=3)),
        created_at=_ts(start),
    )
    db.add(loan)
    await db.flush()

    # Only 1 payment due so far (or 0 if less than 30 days)
    months_active = max(0, (today - start).days // 30)
    schedules, payments_list = _make_schedule(loan.id, 40000, 15.0, 24, start, paid_through=months_active)
    db.add_all(schedules + payments_list)

    db.add(Decision(
        loan_application_id=loan.id, credit_score=660, risk_band="B",
        engine_outcome=DecisionOutcome.AUTO_APPROVE, underwriter_action=UnderwriterAction.APPROVE,
        final_outcome="approved",
    ))
    db.add(CreditReport(
        loan_application_id=loan.id, provider="mock", national_id="19960120567",
        bureau_score=660, status="success", pulled_at=_ts(start),
    ))
    db.add(Disbursement(
        loan_application_id=loan.id, amount=40000, method=DisbursementMethod.BANK_TRANSFER,
        status=DisbursementStatus.COMPLETED, disbursed_by=staff_id,
        disbursed_at=_ts(start + timedelta(days=3)),
    ))

    # Documents
    db.add(Document(
        loan_application_id=loan.id, uploaded_by=user.id, document_type=DocumentType.NATIONAL_ID,
        file_name="priya_id.jpg", file_path="/uploads/priya_id.jpg",
        file_size=250000, mime_type="image/jpeg", status=DocumentStatus.VERIFIED,
    ))
    db.add(Document(
        loan_application_id=loan.id, uploaded_by=user.id, document_type=DocumentType.EMPLOYMENT_LETTER,
        file_name="priya_employment.pdf", file_path="/uploads/priya_employment.pdf",
        file_size=88000, mime_type="application/pdf", status=DocumentStatus.VERIFIED,
    ))

    # Conversation (how she found us)
    conv = Conversation(
        channel=ConversationChannel.WEB, participant_user_id=user.id,
        current_state=ConversationState.DISBURSED, entry_point=ConversationEntryPoint.COLD_START,
        loan_application_id=loan.id, created_at=_ts(start - timedelta(days=2)),
    )
    db.add(conv)
    await db.flush()
    db.add(ConversationMessage(conversation_id=conv.id, role=MessageRole.USER, content="Hi, I'm interested in getting a personal loan."))
    db.add(ConversationMessage(conversation_id=conv.id, role=MessageRole.ASSISTANT, content="Welcome to Zotta! I'd be happy to help you explore your loan options. How much were you thinking of borrowing?"))
    db.add(ConversationMessage(conversation_id=conv.id, role=MessageRole.USER, content="Around $40,000 for about 2 years."))
    db.add(ConversationMessage(conversation_id=conv.id, role=MessageRole.ASSISTANT, content="Great! Based on a $40,000 loan over 24 months, your estimated monthly payment would be around $1,941. Would you like to proceed with an application?"))

    # Audit
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="submitted", user_id=user.id))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="approved", user_id=staff_id))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan.id, action="disbursed", user_id=staff_id))

    await db.flush()
    print(f"    Created user #{user.id} with 1 new loan, minimal history")


# ══════════════════════════════════════════════════════════════════════════
# PERSONA 5: The Complex Case
# ══════════════════════════════════════════════════════════════════════════

async def _persona_complex(db: AsyncSession, staff_id: int):
    print("  5/5 Complex Case — Marcus Williams")
    today = date.today()
    start = today - timedelta(days=int(2.5 * 365))

    user = User(
        email="marcus.williams360@email.com", hashed_password=hash_password("Test1234!"),
        first_name="Marcus", last_name="Williams", phone="+18687005005", role=UserRole.APPLICANT,
    )
    db.add(user)
    await db.flush()

    profile = ApplicantProfile(
        user_id=user.id, date_of_birth=date(1982, 5, 10),
        id_type="national_id", national_id="19820510198",
        gender="male", marital_status="married",
        address_line1="88 Ariapita Avenue", city="Woodbrook", parish="Port of Spain",
        employer_name="Self-Employed", job_title="Building Contractor",
        employment_type="self_employed", years_employed=10,
        monthly_income=22000, other_income=5000, monthly_expenses=12000,
        existing_debt=45000, dependents=3,
        mobile_phone="+18687005005", whatsapp_number="+18687005005",
        home_phone="+18686221234",
        id_verified=True, id_verification_status="verified",
    )
    db.add(profile)

    # ── Loan 1 — Completed personal loan ───────────────────
    l1_start = start
    loan1 = LoanApplication(
        reference_number=_ref(), applicant_id=user.id,
        amount_requested=60000, term_months=24, purpose=LoanPurpose.BUSINESS,
        interest_rate=15.0, amount_approved=60000, monthly_payment=2912,
        status=LoanStatus.DISBURSED,
        submitted_at=_ts(l1_start), decided_at=_ts(l1_start + timedelta(days=2)),
        disbursed_at=_ts(l1_start + timedelta(days=4)),
        created_at=_ts(l1_start),
    )
    db.add(loan1)
    await db.flush()
    s1, p1 = _make_schedule(loan1.id, 60000, 15.0, 24, l1_start, paid_through=24)
    db.add_all(s1 + p1)

    db.add(Decision(
        loan_application_id=loan1.id, credit_score=687, risk_band="B",
        engine_outcome=DecisionOutcome.MANUAL_REVIEW, underwriter_action=UnderwriterAction.APPROVE,
        final_outcome="approved",
    ))

    # ── Loan 2 — Active, in arrears with collections ───────
    l2_start = start + timedelta(days=300)
    loan2 = LoanApplication(
        reference_number=_ref(), applicant_id=user.id,
        amount_requested=150000, term_months=48, purpose=LoanPurpose.HOME_IMPROVEMENT,
        interest_rate=14.0, amount_approved=150000, monthly_payment=4103,
        status=LoanStatus.DISBURSED,
        submitted_at=_ts(l2_start), decided_at=_ts(l2_start + timedelta(days=3)),
        disbursed_at=_ts(l2_start + timedelta(days=5)),
        created_at=_ts(l2_start),
    )
    db.add(loan2)
    await db.flush()
    months_l2 = (today - l2_start).days // 30
    paid_l2 = max(0, months_l2 - 4)  # 4 months overdue
    s2, p2 = _make_schedule(loan2.id, 150000, 14.0, 48, l2_start, paid_through=paid_l2, overdue_from=paid_l2 + 1)
    db.add_all(s2 + p2)

    db.add(Decision(
        loan_application_id=loan2.id, credit_score=670, risk_band="B",
        engine_outcome=DecisionOutcome.AUTO_APPROVE, underwriter_action=UnderwriterAction.APPROVE,
        final_outcome="approved",
    ))

    # ── Loan 3 — Active, current ──────────────────────────
    l3_start = today - timedelta(days=180)
    loan3 = LoanApplication(
        reference_number=_ref(), applicant_id=user.id,
        amount_requested=45000, term_months=12, purpose=LoanPurpose.VEHICLE,
        interest_rate=13.5, amount_approved=45000, monthly_payment=4028,
        status=LoanStatus.DISBURSED,
        submitted_at=_ts(l3_start), decided_at=_ts(l3_start + timedelta(days=1)),
        disbursed_at=_ts(l3_start + timedelta(days=2)),
        created_at=_ts(l3_start),
    )
    db.add(loan3)
    await db.flush()
    months_l3 = (today - l3_start).days // 30
    s3, p3 = _make_schedule(loan3.id, 45000, 13.5, 12, l3_start, paid_through=months_l3, partial_at=[months_l3 - 1] if months_l3 > 1 else [])
    db.add_all(s3 + p3)

    # ── Loan 4 — Declined application ─────────────────────
    l4_start = today - timedelta(days=90)
    loan4 = LoanApplication(
        reference_number=_ref(), applicant_id=user.id,
        amount_requested=200000, term_months=60, purpose=LoanPurpose.BUSINESS,
        status=LoanStatus.DECLINED,
        submitted_at=_ts(l4_start), decided_at=_ts(l4_start + timedelta(days=2)),
        created_at=_ts(l4_start),
    )
    db.add(loan4)
    await db.flush()
    db.add(Decision(
        loan_application_id=loan4.id, credit_score=640, risk_band="C",
        engine_outcome=DecisionOutcome.AUTO_DECLINE, underwriter_action=UnderwriterAction.DECLINE,
        override_reason="Exposure limit exceeded with existing arrears", final_outcome="declined",
    ))

    # Credit reports (showing decline)
    for score, pulled_at in [(687, l1_start), (670, l2_start), (655, l3_start), (640, l4_start), (632, today - timedelta(days=15))]:
        db.add(CreditReport(
            loan_application_id=loan1.id, provider="mock", national_id="19820510198",
            bureau_score=score, status="success", pulled_at=_ts(pulled_at),
        ))

    # Disbursements
    for lid, amt, d in [(loan1.id, 60000, l1_start + timedelta(days=4)), (loan2.id, 150000, l2_start + timedelta(days=5)), (loan3.id, 45000, l3_start + timedelta(days=2))]:
        db.add(Disbursement(
            loan_application_id=lid, amount=amt, method=DisbursementMethod.BANK_TRANSFER,
            status=DisbursementStatus.COMPLETED, disbursed_by=staff_id, disbursed_at=_ts(d),
        ))

    # Heavy collection activity on loan2
    collection_events = [
        (today - timedelta(days=100), CollectionChannel.SMS, CollectionOutcome.OTHER, "SMS reminder sent"),
        (today - timedelta(days=90), CollectionChannel.PHONE, CollectionOutcome.PROMISE_TO_PAY, "Spoke with Marcus. Promised to pay by end of month."),
        (today - timedelta(days=75), CollectionChannel.PHONE, CollectionOutcome.NO_ANSWER, "Promise broken. Call attempt — no answer."),
        (today - timedelta(days=60), CollectionChannel.PHONE, CollectionOutcome.DISPUTED, "Marcus disputes the amount owed. Escalating."),
        (today - timedelta(days=50), CollectionChannel.EMAIL, CollectionOutcome.ESCALATED, "Account escalated to senior collections. Legal notice drafted."),
        (today - timedelta(days=40), CollectionChannel.IN_PERSON, CollectionOutcome.PROMISE_TO_PAY, "Field visit. Marcus acknowledges debt. Promise $20,000 within 2 weeks."),
        (today - timedelta(days=25), CollectionChannel.PHONE, CollectionOutcome.PAYMENT_ARRANGED, "Partial payment $10,000 received. New plan agreed."),
        (today - timedelta(days=10), CollectionChannel.WHATSAPP, CollectionOutcome.OTHER, "Follow-up. Second instalment pending."),
    ]
    for d, ch, outcome, notes in collection_events:
        db.add(CollectionRecord(
            loan_application_id=loan2.id, agent_id=staff_id,
            channel=ch, notes=notes, action_taken="Follow up",
            outcome=outcome,
            promise_amount=20000 if outcome == CollectionOutcome.PROMISE_TO_PAY else None,
            promise_date=(d + timedelta(days=14)) if outcome == CollectionOutcome.PROMISE_TO_PAY else None,
            next_action_date=d + timedelta(days=7),
            created_at=_ts(d),
        ))

    # Collection chats (WhatsApp)
    chat_msgs = [
        (today - timedelta(days=95), ChatDirection.OUTBOUND, "Good day Mr Williams, your payment on your home improvement loan is now overdue. Please contact us."),
        (today - timedelta(days=93), ChatDirection.INBOUND, "I know, things are tight right now. Will sort it out."),
        (today - timedelta(days=60), ChatDirection.OUTBOUND, "Mr Williams, your account is now 60 days overdue. We need to arrange payment to avoid further action."),
        (today - timedelta(days=59), ChatDirection.INBOUND, "I don't think I owe that much. I need to see a statement."),
        (today - timedelta(days=58), ChatDirection.OUTBOUND, "Certainly. I've emailed your full loan statement. Please review and call us."),
        (today - timedelta(days=40), ChatDirection.OUTBOUND, "Following up on our field visit today. Thank you for your time. Please ensure the agreed payment is made by the 28th."),
        (today - timedelta(days=39), ChatDirection.INBOUND, "Will do. Thanks for being understanding."),
        (today - timedelta(days=10), ChatDirection.OUTBOUND, "Hi Marcus, just checking in on the second instalment. When can we expect it?"),
        (today - timedelta(days=9), ChatDirection.INBOUND, "Next week. Waiting on a client payment."),
    ]
    for d, direction, msg in chat_msgs:
        db.add(CollectionChat(
            loan_application_id=loan2.id,
            agent_id=staff_id if direction == ChatDirection.OUTBOUND else None,
            phone_number="+18687005005",
            direction=direction, message=msg,
            channel="whatsapp", status=ChatMessageStatus.DELIVERED,
            created_at=_ts(d),
        ))

    # Documents across loans
    docs = [
        (loan1.id, DocumentType.NATIONAL_ID, "marcus_id_front.jpg", "image/jpeg", DocumentStatus.VERIFIED),
        (loan1.id, DocumentType.PROOF_OF_INCOME, "marcus_tax_return.pdf", "application/pdf", DocumentStatus.VERIFIED),
        (loan2.id, DocumentType.BANK_STATEMENT, "marcus_bank_6mo.pdf", "application/pdf", DocumentStatus.VERIFIED),
        (loan2.id, DocumentType.UTILITY_BILL, "marcus_wasa_bill.pdf", "application/pdf", DocumentStatus.VERIFIED),
        (loan3.id, DocumentType.PROOF_OF_INCOME, "marcus_invoices.pdf", "application/pdf", DocumentStatus.VERIFIED),
        (loan4.id, DocumentType.BANK_STATEMENT, "marcus_bank_recent.pdf", "application/pdf", DocumentStatus.PENDING_REVIEW),
    ]
    for lid, dt, fname, mime, st in docs:
        db.add(Document(
            loan_application_id=lid, uploaded_by=user.id, document_type=dt,
            file_name=fname, file_path=f"/uploads/{fname}",
            file_size=random.randint(80000, 300000), mime_type=mime, status=st,
        ))

    # Comments (customer ↔ staff)
    db.add(ApplicationComment(application_id=loan2.id, user_id=user.id, content="Can I get a copy of my loan statement? I'm not sure the balance is correct.", is_from_applicant=True))
    db.add(ApplicationComment(application_id=loan2.id, user_id=staff_id, content="Hi Marcus, I've emailed your full statement. Please review and let us know if you have questions.", is_from_applicant=False))
    db.add(ApplicationComment(application_id=loan4.id, user_id=staff_id, content="Unfortunately we cannot approve additional credit at this time due to existing exposure and arrears on your home improvement loan.", is_from_applicant=False))
    db.add(ApplicationComment(application_id=loan4.id, user_id=user.id, content="I understand. Once I clear the arrears can I reapply?", is_from_applicant=True))
    db.add(ApplicationComment(application_id=loan4.id, user_id=staff_id, content="Absolutely. Once your account is current for 3 consecutive months we'd be happy to reconsider.", is_from_applicant=False))

    # Notes
    db.add(ApplicationNote(application_id=loan2.id, user_id=staff_id, content="Complex case. Self-employed contractor with irregular cash flow. Multiple interactions. Borrower cooperative but cash-constrained."))
    db.add(ApplicationNote(application_id=loan2.id, user_id=staff_id, content="Field visit conducted 40 days ago. Borrower's residence verified. Appears genuine hardship, not willful default."))
    db.add(ApplicationNote(application_id=loan4.id, user_id=staff_id, content="Declined per exposure policy. Recommend revisiting once loan2 arrears are cleared."))

    # Audit logs
    for lid in [loan1.id, loan2.id, loan3.id, loan4.id]:
        db.add(AuditLog(entity_type="loan_application", entity_id=lid, action="submitted", user_id=user.id))
    for lid in [loan1.id, loan2.id, loan3.id]:
        db.add(AuditLog(entity_type="loan_application", entity_id=lid, action="approved", user_id=staff_id))
        db.add(AuditLog(entity_type="loan_application", entity_id=lid, action="disbursed", user_id=staff_id))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan4.id, action="declined", user_id=staff_id, details="Exposure limit"))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan2.id, action="collections_escalated", user_id=staff_id, details="60+ DPD, legal notice"))
    db.add(AuditLog(entity_type="loan_application", entity_id=loan2.id, action="field_visit", user_id=staff_id, details="In-person visit conducted"))

    # Conversation
    conv = Conversation(
        channel=ConversationChannel.WEB, participant_user_id=user.id,
        current_state=ConversationState.DECLINED, entry_point=ConversationEntryPoint.EXISTING_CUSTOMER,
        loan_application_id=loan4.id, created_at=_ts(l4_start - timedelta(days=1)),
    )
    db.add(conv)
    await db.flush()
    db.add(ConversationMessage(conversation_id=conv.id, role=MessageRole.USER, content="I need another loan for my business. About $200,000."))
    db.add(ConversationMessage(conversation_id=conv.id, role=MessageRole.ASSISTANT, content="I see you're an existing customer, Marcus. Let me check your profile... I notice you have an outstanding balance on your home improvement loan that's currently overdue. This may affect your eligibility for additional credit."))
    db.add(ConversationMessage(conversation_id=conv.id, role=MessageRole.USER, content="I'm sorting that out. Can I still apply?"))
    db.add(ConversationMessage(conversation_id=conv.id, role=MessageRole.ASSISTANT, content="You can certainly submit an application, but I want to be upfront that our policy requires all existing accounts to be current before approving new credit. Would you still like to proceed?"))

    await db.flush()
    total_payments = len(p1) + len(p2) + len(p3)
    print(f"    Created user #{user.id} with 4 loans (1 declined), {total_payments} payments, {len(collection_events)} collection records, {len(chat_msgs)} chat messages")


# ── Credit Bureau Alerts seeding ─────────────────────

async def seed_bureau_alerts():
    """Seed credit bureau alerts for existing personas."""
    engine = create_async_engine(settings.database_url, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    async with sf() as db:
        # Find personas by email
        persona_emails = {
            "angela": "angela.maharaj@email.com",
            "darren": "darren.baptiste@email.com",
            "kevin": "kevin.persad360@email.com",
            "priya": "priya.ramnath@email.com",
            "marcus": "marcus.williams360@email.com",
        }
        user_ids: dict[str, int] = {}
        for name, email in persona_emails.items():
            result = await db.execute(select(User).where(User.email == email))
            u = result.scalar_one_or_none()
            if u:
                user_ids[name] = u.id

        if not user_ids:
            print("  No personas found — skipping bureau alerts")
            await engine.dispose()
            return

        # Clear existing alerts for these users
        from sqlalchemy import delete
        await db.execute(
            delete(CreditBureauAlert).where(CreditBureauAlert.user_id.in_(user_ids.values()))
        )
        staff = await db.execute(select(User).where(User.role != UserRole.APPLICANT).limit(1))
        staff_user = staff.scalar_one_or_none()
        staff_id = staff_user.id if staff_user else 1

        alerts: list[CreditBureauAlert] = []

        # ─ Angela (Perfect Borrower) — low-risk monitoring alerts
        if "angela" in user_ids:
            aid = user_ids["angela"]
            alerts.extend([
                CreditBureauAlert(
                    user_id=aid, alert_type=AlertType.NEW_INQUIRY, severity=AlertSeverity.LOW,
                    status=AlertStatus.NEW, bureau_name="TransUnion Caribbean",
                    bureau_reference="TU-INQ-2026-44821",
                    title="New Credit Inquiry Detected",
                    description="A new credit inquiry was made by Republic Bank Trinidad on 2026-02-10. The customer may be shopping for a personal loan or credit card.",
                    other_institution="Republic Bank Trinidad", other_product_type="Personal Loan",
                    alert_date=now - timedelta(days=4),
                ),
                CreditBureauAlert(
                    user_id=aid, alert_type=AlertType.NEW_LOAN, severity=AlertSeverity.MEDIUM,
                    status=AlertStatus.NEW, bureau_name="TransUnion Caribbean",
                    bureau_reference="TU-NL-2026-44822",
                    title="New Loan Opened at Another Institution",
                    description="Customer opened a new vehicle loan at Scotiabank T&T for 185,000 TTD with a 60-month term. Total credit exposure has increased.",
                    other_institution="Scotiabank Trinidad & Tobago", other_product_type="Vehicle Loan",
                    other_amount=Decimal("185000.00"),
                    alert_date=now - timedelta(days=2),
                ),
            ])

        # ─ Marcus (Deteriorating) — high/critical risk alerts
        if "marcus" in user_ids:
            mid = user_ids["marcus"]
            alerts.extend([
                CreditBureauAlert(
                    user_id=mid, alert_type=AlertType.NEW_DELINQUENCY, severity=AlertSeverity.HIGH,
                    status=AlertStatus.NEW, bureau_name="TransUnion Caribbean",
                    bureau_reference="TU-DEL-2026-55901",
                    title="New Delinquency Reported at JMMB",
                    description="Customer is now 45 days past due on a personal loan at JMMB Trinidad with an outstanding balance of 72,500 TTD.",
                    other_institution="JMMB Trinidad", other_product_type="Personal Loan",
                    other_amount=Decimal("72500.00"), other_delinquency_days=45,
                    other_delinquency_amount=Decimal("8400.00"),
                    alert_date=now - timedelta(days=1),
                ),
                CreditBureauAlert(
                    user_id=mid, alert_type=AlertType.DEFAULT_ELSEWHERE, severity=AlertSeverity.CRITICAL,
                    status=AlertStatus.NEW, bureau_name="TransUnion Caribbean",
                    bureau_reference="TU-DEF-2026-55902",
                    title="Default Reported at First Citizens Bank",
                    description="Customer reported in default (90+ DPD) on a credit card at First Citizens Bank. Outstanding 28,300 TTD. Account written off.",
                    other_institution="First Citizens Bank", other_product_type="Credit Card",
                    other_amount=Decimal("28300.00"), other_delinquency_days=95,
                    other_delinquency_amount=Decimal("28300.00"),
                    alert_date=now - timedelta(hours=6),
                ),
                CreditBureauAlert(
                    user_id=mid, alert_type=AlertType.COLLECTION_PAYMENT_ELSEWHERE, severity=AlertSeverity.HIGH,
                    status=AlertStatus.NEW, bureau_name="TransUnion Caribbean",
                    bureau_reference="TU-CP-2026-55903",
                    title="Collection Payment Made to Another Creditor",
                    description="While in arrears with your institution, the customer made a 15,000 TTD payment to Guardian Life Insurance.",
                    other_institution="Guardian Life Insurance", other_product_type="Policy Loan",
                    other_amount=Decimal("15000.00"),
                    alert_date=now - timedelta(hours=3),
                ),
                CreditBureauAlert(
                    user_id=mid, alert_type=AlertType.NEW_INQUIRY, severity=AlertSeverity.MEDIUM,
                    status=AlertStatus.ACKNOWLEDGED, bureau_name="TransUnion Caribbean",
                    bureau_reference="TU-INQ-2026-55900",
                    title="New Credit Inquiry from RBC Royal Bank",
                    description="A new credit inquiry was made by RBC Royal Bank Caribbean on 2026-02-01.",
                    other_institution="RBC Royal Bank Caribbean", other_product_type="Line of Credit",
                    alert_date=now - timedelta(days=13),
                    acted_by=staff_id, acted_at=now - timedelta(days=12),
                ),
            ])

        # ─ Kevin — moderate alert
        if "kevin" in user_ids:
            kid = user_ids["kevin"]
            alerts.append(CreditBureauAlert(
                user_id=kid, alert_type=AlertType.NEW_LOAN, severity=AlertSeverity.MEDIUM,
                status=AlertStatus.NEW, bureau_name="TransUnion Caribbean",
                bureau_reference="TU-NL-2026-66701",
                title="New Hire Purchase Agreement at Courts",
                description="Customer entered into a new hire purchase agreement at Courts Trinidad for 12,500 TTD.",
                other_institution="Courts Trinidad", other_product_type="Hire Purchase",
                other_amount=Decimal("12500.00"),
                alert_date=now - timedelta(days=7),
            ))

        # ─ Priya (Recovering) — already resolved alert
        if "priya" in user_ids:
            pid = user_ids["priya"]
            alerts.append(CreditBureauAlert(
                user_id=pid, alert_type=AlertType.NEW_DELINQUENCY, severity=AlertSeverity.MEDIUM,
                status=AlertStatus.ACTION_TAKEN, bureau_name="TransUnion Caribbean",
                bureau_reference="TU-DEL-2026-77801",
                title="30-Day Delinquency at Scotia Trinidad",
                description="Customer was reported 30 days past due on a small personal loan at Scotiabank T&T (5,000 TTD outstanding).",
                other_institution="Scotiabank Trinidad & Tobago", other_product_type="Personal Loan",
                other_amount=Decimal("5000.00"), other_delinquency_days=30,
                other_delinquency_amount=Decimal("850.00"),
                alert_date=now - timedelta(days=45),
                action_taken="increase_monitoring",
                action_notes="Increased monitoring frequency. Customer subsequently brought account current.",
                acted_by=staff_id, acted_at=now - timedelta(days=40),
            ))

        for a in alerts:
            db.add(a)
        await db.commit()
        print(f"  Seeded {len(alerts)} credit bureau alerts for {len(user_ids)} personas")

    await engine.dispose()


# ── Main ────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(seed_personas())
    asyncio.run(seed_bureau_alerts())
