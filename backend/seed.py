"""Seed script to populate the database with 300+ test applications over 90 days."""

import asyncio
import random
import string
from datetime import datetime, date, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base
from app.auth_utils import hash_password
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus, LoanPurpose, ApplicantProfile
from app.models.decision import Decision, DecisionOutcome, DecisionRulesConfig
from app.models.disbursement import Disbursement, DisbursementMethod, DisbursementStatus
from app.models.payment import Payment, PaymentType, PaymentStatus, PaymentSchedule, ScheduleStatus
from app.models.audit import AuditLog
from app.services.decision_engine.rules import DEFAULT_RULES
from app.models.sector_analysis import (
    SectorSnapshot, SectorPolicy, SectorPolicyStatus, SectorRiskRating,
    SectorAlertRule, SectorAlertSeverity, SectorAlert, SectorAlertStatus,
    SECTOR_TAXONOMY,
)
from app.models.collections_ext import (
    CollectionCase, CaseStatus, DelinquencyStage,
    PromiseToPay, PTPStatus,
    SettlementOffer, SettlementOfferType, SettlementOfferStatus,
    ComplianceRule, SLAConfig, CollectionsDashboardSnapshot,
    dpd_to_stage,
)
from decimal import Decimal

# Trinidad names
FIRST_NAMES_M = ["Marcus", "Kevin", "Andre", "Ryan", "Daniel", "Jason", "Curtis", "Darren",
                  "Jerome", "Wayne", "Terrence", "Nigel", "Akeem", "Ravi", "Sunil"]
FIRST_NAMES_F = ["Maria", "Priya", "Samantha", "Asha", "Kavita", "Nicole", "Gabrielle",
                  "Alicia", "Stacey", "Camille", "Reshma", "Natasha", "Kerry", "Janelle", "Anika"]
LAST_NAMES = ["Mohammed", "Singh", "Williams", "Garcia", "Ramnath", "Joseph", "Ali",
              "Pierre", "Charles", "Thomas", "Persad", "Maharaj", "Baptiste", "Alexander",
              "Khan", "Narine", "Ramkissoon", "De Silva", "Richardson", "James"]

EMPLOYERS = ["TSTT", "Republic Bank", "bpTT", "Massy Stores", "Guardian Group",
             "First Citizens Bank", "NGC", "Atlantic LNG", "ANSA McAL",
             "Scotiabank Trinidad", "Courts", "Unicomer", "WASA", "T&TEC",
             "Ministry of Education", "Ministry of Health", "UWI",
             "RBC Royal Bank", "JMMB Bank", "Digicel"]

JOB_TITLES = ["Senior Engineer", "Teller", "Accountant", "Teacher", "Sales Associate",
              "Process Technician", "Manager", "Nurse", "Security Guard", "Driver",
              "IT Specialist", "Administrative Assistant", "Electrician", "Plumber",
              "Marketing Executive", "Mechanic", "Pharmacist", "Cashier", "Supervisor",
              "Construction Worker", "Chef", "Attorney", "Doctor"]

CITIES = ["Port of Spain", "San Fernando", "Chaguanas", "Arima", "Point Fortin",
          "Tunapuna", "Couva", "Sangre Grande", "Princes Town", "Siparia",
          "Diego Martin", "Maraval", "Woodbrook", "St. Augustine", "Debe"]

PARISHES = ["Port of Spain", "San Fernando", "Arima", "Chaguanas", "Point Fortin",
            "Diego Martin", "Tunapuna/Piarco", "San Juan/Laventille", "Sangre Grande",
            "Penal/Debe", "Couva/Tabaquite/Talparo", "Siparia", "Princes Town"]

EMP_TYPES = ["employed", "self_employed", "contract", "part_time"]

EMPLOYER_SECTORS = [
    "Banking & Financial Services", "Insurance", "Hospitality & Tourism",
    "Agriculture & Agro-processing", "Oil & Gas / Energy", "Mining & Extractives",
    "Telecommunications", "Retail & Distribution", "Real Estate & Construction",
    "Manufacturing", "Transportation & Logistics", "Healthcare & Pharmaceuticals",
    "Education", "Government & Public Sector", "Utilities (Water & Electricity)",
    "Creative Industries & Entertainment", "Maritime & Shipping",
    "Professional Services (Legal, Accounting, Consulting)",
    "Information Technology", "Microfinance & Credit Unions", "Other", "Not Applicable",
]

PURPOSES = list(LoanPurpose)


def random_ref(idx):
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=6))
    return f"ZOT-2026-{suffix}{idx:02d}"


def random_national_id(dob):
    return f"{dob.strftime('%Y%m%d')}{random.randint(100, 999)}"


async def seed():
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        print("Seeding database with 300+ applications...")

        # ── Staff Users ──────────────────────────────────
        admin = User(email="admin@zotta.tt", hashed_password=hash_password("Admin123!"),
                     first_name="Admin", last_name="Zotta", role=UserRole.ADMIN)
        senior_uw = User(email="sarah.uw@zotta.tt", hashed_password=hash_password("Underwriter1!"),
                         first_name="Sarah", last_name="Mohammed", role=UserRole.SENIOR_UNDERWRITER)
        junior_uw = User(email="kevin.uw@zotta.tt", hashed_password=hash_password("Underwriter1!"),
                         first_name="Kevin", last_name="Singh", role=UserRole.JUNIOR_UNDERWRITER)
        junior_uw2 = User(email="alicia.uw@zotta.tt", hashed_password=hash_password("Underwriter1!"),
                          first_name="Alicia", last_name="Pierre", role=UserRole.JUNIOR_UNDERWRITER)

        db.add_all([admin, senior_uw, junior_uw, junior_uw2])
        await db.flush()
        staff_ids = [admin.id, senior_uw.id, junior_uw.id, junior_uw2.id]

        # ── Generate 80 applicant users ──────────────────
        NUM_APPLICANTS = 80
        applicants = []
        for i in range(NUM_APPLICANTS):
            # First applicant is fixed for E2E/manual testing (marcus.mohammed0@email.com)
            if i == 0:
                first, last, gender = "Marcus", "Mohammed", "male"
                email = "marcus.mohammed0@email.com"
            else:
                gender = random.choice(["male", "female"])
                first = random.choice(FIRST_NAMES_M if gender == "male" else FIRST_NAMES_F)
                last = random.choice(LAST_NAMES)
                email = f"{first.lower()}.{last.lower()}{i}@email.com"
            phone = f"+1868{random.randint(3000000, 7999999)}"
            user = User(
                email=email, hashed_password=hash_password("Applicant1!"),
                first_name=first, last_name=last, phone=phone, role=UserRole.APPLICANT,
            )
            applicants.append((user, gender))

        db.add_all([u for u, _ in applicants])
        await db.flush()

        # ── Create profiles for all applicants ───────────
        for user, gender in applicants:
            age = random.randint(21, 62)
            dob = date.today() - timedelta(days=age * 365 + random.randint(0, 364))
            emp_type = random.choices(EMP_TYPES, weights=[0.65, 0.15, 0.10, 0.10])[0]
            income = random.choice([4000, 5000, 6000, 7000, 8000, 10000, 12000, 15000, 18000, 22000, 30000, 45000])
            expenses = round(income * random.uniform(0.2, 0.6), 2)
            debt = round(income * random.uniform(0, 3), 2)

            profile = ApplicantProfile(
                user_id=user.id,
                date_of_birth=dob,
                national_id=random_national_id(dob),
                gender=gender,
                marital_status=random.choice(["single", "married", "divorced", "widowed"]),
                address_line1=f"{random.randint(1, 200)} {random.choice(['Main Road', 'High Street', 'Frederick Street', 'Southern Main Road', 'Eastern Main Road'])}",
                city=random.choice(CITIES),
                parish=random.choice(PARISHES),
                employer_name=random.choice(EMPLOYERS) if emp_type != "self_employed" else "Self-employed",
                employer_sector=random.choice(EMPLOYER_SECTORS),
                job_title=random.choice(JOB_TITLES),
                employment_type=emp_type,
                years_employed=random.randint(0, 20),
                monthly_income=income,
                other_income=random.choice([0, 0, 0, 1000, 2000, 3000]),
                monthly_expenses=expenses,
                existing_debt=debt,
                dependents=random.randint(0, 5),
                id_verified=random.random() > 0.2,
                id_verification_status="verified" if random.random() > 0.2 else "pending",
            )
            db.add(profile)

        await db.flush()

        # ── Generate 320 loan applications over 90 days ──
        # Status distribution:
        # ~35% disbursed, ~15% approved, ~15% submitted/under_review, ~12% declined,
        # ~5% counter_proposed, ~8% accepted, ~5% decision_pending, ~5% other
        STATUS_WEIGHTS = {
            LoanStatus.DISBURSED: 0.35,
            LoanStatus.APPROVED: 0.12,
            LoanStatus.SUBMITTED: 0.08,
            LoanStatus.UNDER_REVIEW: 0.07,
            LoanStatus.DECLINED: 0.12,
            LoanStatus.COUNTER_PROPOSED: 0.04,
            LoanStatus.ACCEPTED: 0.07,
            LoanStatus.DECISION_PENDING: 0.05,
            LoanStatus.CREDIT_CHECK: 0.03,
            LoanStatus.REJECTED_BY_APPLICANT: 0.03,
            LoanStatus.CANCELLED: 0.02,
            LoanStatus.DRAFT: 0.02,
        }
        statuses_list = list(STATUS_WEIGHTS.keys())
        status_weights = list(STATUS_WEIGHTS.values())

        NUM_APPS = 320
        loan_apps = []
        now = datetime.now(timezone.utc)

        for i in range(NUM_APPS):
            applicant_user, _ = random.choice(applicants)
            status = random.choices(statuses_list, weights=status_weights, k=1)[0]

            days_ago = random.randint(0, 90)
            created = now - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))

            amount = random.choice([10000, 15000, 20000, 25000, 30000, 50000, 75000, 100000, 150000, 200000, 300000])
            term = random.choice([6, 12, 18, 24, 36, 48, 60])
            rate = random.choice([8.5, 10.0, 12.0, 14.0, 16.5, 18.0, 22.0])

            app = LoanApplication(
                reference_number=random_ref(i),
                applicant_id=applicant_user.id,
                amount_requested=amount,
                term_months=term,
                purpose=random.choice(PURPOSES),
                purpose_description=random.choice([None, "Need funds urgently", "Home renovation project", "Vehicle purchase", "Education fees"]),
                status=status,
                created_at=created,
                submitted_at=created + timedelta(hours=random.randint(0, 12)) if status != LoanStatus.DRAFT else None,
            )

            # Set fields based on status
            if status in (LoanStatus.APPROVED, LoanStatus.DISBURSED, LoanStatus.ACCEPTED):
                app.amount_approved = amount
                app.interest_rate = rate
                r_monthly = rate / 100 / 12
                n = term
                if r_monthly > 0:
                    pmt = amount * (r_monthly * (1 + r_monthly) ** n) / ((1 + r_monthly) ** n - 1)
                else:
                    pmt = amount / n
                app.monthly_payment = round(pmt, 2)
                app.decided_at = created + timedelta(days=random.randint(1, 7))
                app.assigned_underwriter_id = random.choice(staff_ids)

            elif status == LoanStatus.DECLINED:
                app.decided_at = created + timedelta(days=random.randint(1, 5))
                app.assigned_underwriter_id = random.choice(staff_ids)

            elif status == LoanStatus.COUNTER_PROPOSED:
                app.proposed_amount = round(amount * random.uniform(0.5, 0.9), 2)
                app.proposed_rate = rate + random.uniform(1, 4)
                app.proposed_term = max(6, term - random.choice([0, 6, 12]))
                app.counterproposal_reason = random.choice([
                    "Income insufficient for requested amount",
                    "High existing debt ratio",
                    "Shorter tenure recommended",
                ])
                app.assigned_underwriter_id = random.choice(staff_ids)

            elif status in (LoanStatus.UNDER_REVIEW, LoanStatus.DECISION_PENDING, LoanStatus.CREDIT_CHECK):
                app.assigned_underwriter_id = random.choice(staff_ids)

            # Contract for accepted/disbursed
            if status in (LoanStatus.ACCEPTED, LoanStatus.DISBURSED):
                app.contract_signed_at = (app.decided_at or created) + timedelta(days=random.randint(1, 3))
                app.contract_typed_name = f"{applicant_user.first_name} {applicant_user.last_name}"

            loan_apps.append(app)

        db.add_all(loan_apps)
        await db.flush()

        # ── Decisions for processed applications ─────────
        for app in loan_apps:
            if app.status in (LoanStatus.APPROVED, LoanStatus.DECLINED, LoanStatus.DECISION_PENDING,
                              LoanStatus.DISBURSED, LoanStatus.ACCEPTED, LoanStatus.COUNTER_PROPOSED):
                score = random.randint(350, 820)
                if app.status in (LoanStatus.APPROVED, LoanStatus.DISBURSED, LoanStatus.ACCEPTED):
                    score = random.randint(550, 820)
                elif app.status == LoanStatus.DECLINED:
                    score = random.randint(300, 500)
                else:
                    score = random.randint(400, 700)

                if score >= 720:
                    risk_band = "A"
                elif score >= 650:
                    risk_band = "B"
                elif score >= 580:
                    risk_band = "C"
                elif score >= 450:
                    risk_band = "D"
                else:
                    risk_band = "E"

                outcome_map = {
                    LoanStatus.APPROVED: DecisionOutcome.AUTO_APPROVE,
                    LoanStatus.DISBURSED: DecisionOutcome.AUTO_APPROVE,
                    LoanStatus.ACCEPTED: DecisionOutcome.AUTO_APPROVE,
                    LoanStatus.DECLINED: DecisionOutcome.AUTO_DECLINE,
                    LoanStatus.DECISION_PENDING: DecisionOutcome.MANUAL_REVIEW,
                    LoanStatus.COUNTER_PROPOSED: DecisionOutcome.MANUAL_REVIEW,
                }
                outcome = outcome_map.get(app.status, DecisionOutcome.MANUAL_REVIEW)

                decision = Decision(
                    loan_application_id=app.id,
                    credit_score=score,
                    risk_band=risk_band,
                    engine_outcome=outcome,
                    engine_reasons={"reasons": ["Seed data"], "dti_ratio": round(random.uniform(0.1, 0.7), 2)},
                    scoring_breakdown={
                        "payment_history": random.randint(50, 100),
                        "debt_to_income": random.randint(30, 95),
                        "employment_stability": random.randint(40, 100),
                        "credit_history": random.randint(20, 100),
                    },
                    rules_results={
                        "rules": [
                            {"id": "R01", "name": "Minimum Age", "passed": True, "message": "Age meets requirement", "severity": "hard"},
                            {"id": "R03", "name": "Minimum Income", "passed": True, "message": "Income sufficient", "severity": "hard"},
                            {"id": "R08", "name": "Extreme DSR", "passed": True, "message": "DSR within limit", "severity": "hard"},
                            {"id": "R20", "name": "Credit Score", "passed": score >= 400, "message": f"Score: {score}", "severity": "hard"},
                        ]
                    },
                    suggested_rate=float(app.interest_rate or random.choice([8.5, 12.0, 16.5])),
                    suggested_amount=float(app.amount_requested),
                    final_outcome=outcome.value,
                    rules_version=2,
                    underwriter_id=app.assigned_underwriter_id,
                    created_at=app.decided_at or app.created_at,
                )
                db.add(decision)

        await db.flush()

        # ── Payment schedules and payments for disbursed loans ──
        disbursed_apps = [a for a in loan_apps if a.status == LoanStatus.DISBURSED]
        print(f"  Creating payment schedules for {len(disbursed_apps)} disbursed loans...")

        for app in disbursed_apps:
            if not app.amount_approved or not app.interest_rate:
                continue

            principal = float(app.amount_approved)
            annual_rate = float(app.interest_rate)
            term = app.term_months
            monthly_rate = annual_rate / 100 / 12

            if monthly_rate > 0:
                pmt = principal * (monthly_rate * (1 + monthly_rate) ** term) / ((1 + monthly_rate) ** term - 1)
            else:
                pmt = principal / term

            balance = principal
            disburse_date = (app.decided_at or app.created_at).date()
            today = date.today()

            for inst in range(1, term + 1):
                interest = round(balance * monthly_rate, 2)
                principal_part = round(pmt - interest, 2)
                if inst == term:
                    principal_part = round(balance, 2)
                balance = max(0, balance - principal_part)
                due = disburse_date + timedelta(days=30 * inst)
                amount_due = round(principal_part + interest, 2)

                # Determine status
                if due < today:
                    # Some are paid, some overdue
                    if random.random() < 0.7:  # 70% chance of being paid
                        sched_status = ScheduleStatus.PAID
                        amount_paid = amount_due
                        paid_at = datetime.combine(due - timedelta(days=random.randint(0, 5)), datetime.min.time()).replace(tzinfo=timezone.utc)
                    elif random.random() < 0.5:
                        sched_status = ScheduleStatus.PARTIAL
                        amount_paid = round(amount_due * random.uniform(0.3, 0.8), 2)
                        paid_at = None
                    else:
                        sched_status = ScheduleStatus.OVERDUE
                        amount_paid = 0
                        paid_at = None
                else:
                    sched_status = ScheduleStatus.UPCOMING
                    amount_paid = 0
                    paid_at = None

                schedule = PaymentSchedule(
                    loan_application_id=app.id,
                    installment_number=inst,
                    due_date=due,
                    principal=principal_part,
                    interest=interest,
                    amount_due=amount_due,
                    amount_paid=amount_paid,
                    status=sched_status,
                    paid_at=paid_at,
                )
                db.add(schedule)

                # Create payment records for paid installments
                if sched_status in (ScheduleStatus.PAID, ScheduleStatus.PARTIAL) and amount_paid > 0:
                    payment = Payment(
                        loan_application_id=app.id,
                        amount=amount_paid,
                        payment_type=random.choice([PaymentType.MANUAL, PaymentType.ONLINE, PaymentType.BANK_TRANSFER]),
                        payment_date=paid_at.date() if paid_at else due,
                        reference_number=f"PAY-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}",
                        recorded_by=random.choice(staff_ids) if random.random() > 0.5 else None,
                        status=PaymentStatus.COMPLETED,
                    )
                    db.add(payment)

        await db.flush()

        # ── Guaranteed partly-repaid loan for E2E/test applicant (marcus.mohammed0@email.com) ──
        marcus_user = next((u for u, _ in applicants if u.email == "marcus.mohammed0@email.com"), None)
        if marcus_user:
            # Create a disbursed loan with 2 paid + 1 partial installments for payment calendar testing
            disb_time = now - timedelta(days=55)
            app_e2e = LoanApplication(
                reference_number=random_ref(999),
                applicant_id=marcus_user.id,
                amount_requested=18000,
                term_months=12,
                purpose=LoanPurpose.PERSONAL,
                purpose_description="E2E My Loans – payment calendar test",
                status=LoanStatus.DISBURSED,
                amount_approved=18000,
                interest_rate=12.0,
                monthly_payment=1600.0,
                decided_at=now - timedelta(days=60),
                disbursed_at=disb_time,
                assigned_underwriter_id=admin.id,
                contract_signed_at=now - timedelta(days=58),
                contract_typed_name="Marcus Mohammed",
            )
            db.add(app_e2e)
            await db.flush()

            dec_e2e = Decision(
                loan_application_id=app_e2e.id,
                credit_score=720,
                risk_band="A",
                engine_outcome=DecisionOutcome.AUTO_APPROVE,
                engine_reasons={"reasons": ["E2E seed"], "dti_ratio": 0.25},
                scoring_breakdown={"payment_history": 90, "debt_to_income": 85, "employment_stability": 95, "credit_history": 80},
                rules_results={"rules": []},
                suggested_rate=12.0,
                suggested_amount=18000,
                final_outcome="approve",
                rules_version=2,
                underwriter_id=admin.id,
                created_at=app_e2e.decided_at,
            )
            db.add(dec_e2e)

            disb_ref = f"DIS-E2E{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
            disb_e2e = Disbursement(
                loan_application_id=app_e2e.id,
                amount=18000,
                method=DisbursementMethod.MANUAL,
                status=DisbursementStatus.COMPLETED,
                reference_number=disb_ref,
                disbursed_by=admin.id,
                disbursed_at=disb_time,
            )
            db.add(disb_e2e)

            # Disbursement transaction
            db.add(Payment(
                loan_application_id=app_e2e.id,
                amount=18000,
                payment_type=PaymentType.DISBURSEMENT,
                payment_date=disb_time.date(),
                reference_number=disb_ref,
                recorded_by=admin.id,
                status=PaymentStatus.COMPLETED,
                notes="Loan disbursement — manual",
            ))

            principal = 18000.0
            monthly_rate = 0.12 / 12
            pmt = principal * (monthly_rate * (1 + monthly_rate) ** 12) / ((1 + monthly_rate) ** 12 - 1)
            disburse_date = disb_time.date()
            balance = principal

            for inst in range(1, 13):
                interest = round(balance * monthly_rate, 2)
                principal_part = round(pmt - interest, 2)
                if inst == 12:
                    principal_part = round(balance, 2)
                balance = max(0, balance - principal_part)
                due = disburse_date + timedelta(days=30 * inst)
                amount_due = round(principal_part + interest, 2)

                if inst <= 2:
                    sched_status = ScheduleStatus.PAID
                    amount_paid = amount_due
                    paid_at = datetime.combine(due - timedelta(days=2), datetime.min.time()).replace(tzinfo=timezone.utc)
                elif inst == 3:
                    sched_status = ScheduleStatus.PARTIAL
                    amount_paid = round(amount_due * 0.5, 2)
                    paid_at = None
                else:
                    sched_status = ScheduleStatus.UPCOMING
                    amount_paid = 0
                    paid_at = None

                schedule_e2e = PaymentSchedule(
                    loan_application_id=app_e2e.id,
                    installment_number=inst,
                    due_date=due,
                    principal=principal_part,
                    interest=interest,
                    amount_due=amount_due,
                    amount_paid=amount_paid,
                    status=sched_status,
                    paid_at=paid_at,
                )
                db.add(schedule_e2e)

                if sched_status in (ScheduleStatus.PAID, ScheduleStatus.PARTIAL) and amount_paid > 0:
                    pay_e2e = Payment(
                        loan_application_id=app_e2e.id,
                        amount=amount_paid,
                        payment_type=PaymentType.MANUAL,
                        payment_date=paid_at.date() if paid_at else due,
                        reference_number=f"PAY-E2E{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}",
                        recorded_by=admin.id,
                        status=PaymentStatus.COMPLETED,
                    )
                    db.add(pay_e2e)

            print(f"  Created E2E partly-repaid loan for marcus.mohammed0@email.com (ref: {app_e2e.reference_number})")

        await db.flush()

        # ══════════════════════════════════════════════════════════════
        # Deterministic loan scenarios for GL report testing
        # ══════════════════════════════════════════════════════════════

        scenario_applicants = [u for u, _ in applicants[:5]]  # reuse first 5 applicants

        def _amort(principal, annual_rate, term_months):
            """Return (monthly_payment, schedule_rows) for a standard amortising loan."""
            r = annual_rate / 100 / 12
            if r > 0:
                pmt = principal * (r * (1 + r) ** term_months) / ((1 + r) ** term_months - 1)
            else:
                pmt = principal / term_months
            rows = []
            bal = principal
            for inst in range(1, term_months + 1):
                interest = round(bal * r, 2)
                prin_part = round(pmt - interest, 2)
                if inst == term_months:
                    prin_part = round(bal, 2)
                bal = max(0.0, bal - prin_part)
                rows.append({"installment": inst, "principal": prin_part, "interest": interest,
                             "amount_due": round(prin_part + interest, 2)})
            return round(pmt, 2), rows

        # ── Helper to create a fully-seeded loan ────────────────────
        async def _create_scenario_loan(
            *,
            applicant,
            ref_suffix: str,
            amount: float,
            rate: float,
            term: int,
            purpose_desc: str,
            schedule_statuses: list,       # list of (ScheduleStatus, amount_paid_frac, paid_days_offset)
            disburse_days_ago: int,
            make_provision: bool = False,
            provision_frac: float = 0.0,
            make_write_off: bool = False,
            write_off_amount: float = 0.0,
        ):
            """Create a complete loan with decision, disbursement, schedule, and payments."""
            ref = f"ZOT-SCEN-{ref_suffix}"
            d_time = now - timedelta(days=disburse_days_ago)
            decide_time = d_time - timedelta(days=2)

            app_obj = LoanApplication(
                reference_number=ref,
                applicant_id=applicant.id,
                amount_requested=amount,
                term_months=term,
                purpose=LoanPurpose.PERSONAL,
                purpose_description=purpose_desc,
                status=LoanStatus.DISBURSED,
                amount_approved=amount,
                interest_rate=rate,
                monthly_payment=_amort(amount, rate, term)[0],
                decided_at=decide_time,
                disbursed_at=d_time,
                submitted_at=decide_time - timedelta(days=3),
                assigned_underwriter_id=admin.id,
                contract_signed_at=decide_time + timedelta(days=1),
                contract_typed_name=f"{applicant.first_name} {applicant.last_name}",
                created_at=decide_time - timedelta(days=3),
            )
            db.add(app_obj)
            await db.flush()

            # Decision
            db.add(Decision(
                loan_application_id=app_obj.id,
                credit_score=random.randint(650, 780),
                risk_band="B",
                engine_outcome=DecisionOutcome.AUTO_APPROVE,
                engine_reasons={"reasons": [purpose_desc], "dti_ratio": 0.3},
                scoring_breakdown={"payment_history": 85, "debt_to_income": 80,
                                   "employment_stability": 90, "credit_history": 75},
                rules_results={"rules": []},
                suggested_rate=rate,
                suggested_amount=amount,
                final_outcome="approve",
                rules_version=2,
                underwriter_id=admin.id,
                created_at=decide_time,
            ))

            # Disbursement
            disb_ref = f"DIS-SCEN-{ref_suffix}"
            db.add(Disbursement(
                loan_application_id=app_obj.id,
                amount=amount,
                method=DisbursementMethod.MANUAL,
                status=DisbursementStatus.COMPLETED,
                reference_number=disb_ref,
                disbursed_by=admin.id,
                disbursed_at=d_time,
            ))

            # Payment schedule + payments
            _, sched_rows = _amort(amount, rate, term)
            disburse_date = d_time.date()

            for idx, row in enumerate(sched_rows):
                due = disburse_date + timedelta(days=30 * (idx + 1))

                if idx < len(schedule_statuses):
                    s_status, paid_frac, paid_offset = schedule_statuses[idx]
                    amount_paid = round(row["amount_due"] * paid_frac, 2)
                    if s_status == ScheduleStatus.PAID:
                        paid_at = datetime.combine(due - timedelta(days=paid_offset),
                                                   datetime.min.time()).replace(tzinfo=timezone.utc)
                    elif s_status == ScheduleStatus.PARTIAL:
                        paid_at = datetime.combine(due, datetime.min.time()).replace(tzinfo=timezone.utc)
                    else:
                        paid_at = None
                else:
                    s_status = ScheduleStatus.UPCOMING
                    amount_paid = 0
                    paid_at = None

                db.add(PaymentSchedule(
                    loan_application_id=app_obj.id,
                    installment_number=idx + 1,
                    due_date=due,
                    principal=row["principal"],
                    interest=row["interest"],
                    amount_due=row["amount_due"],
                    amount_paid=amount_paid,
                    status=s_status,
                    paid_at=paid_at,
                ))

                if s_status in (ScheduleStatus.PAID, ScheduleStatus.PARTIAL) and amount_paid > 0:
                    db.add(Payment(
                        loan_application_id=app_obj.id,
                        amount=amount_paid,
                        payment_type=PaymentType.BANK_TRANSFER,
                        payment_date=paid_at.date() if paid_at else due,
                        reference_number=f"PAY-SCEN-{ref_suffix}-{idx + 1}",
                        recorded_by=admin.id,
                        status=PaymentStatus.COMPLETED,
                    ))

            await db.flush()
            return app_obj

        # ─────────────────────────────────────────────────────────────
        # SCENARIO A:  Repaid On-Time  ($75,000, 12 months, 14% p.a.)
        #   - All 12 installments paid exactly on the due date.
        # ─────────────────────────────────────────────────────────────
        print("  Creating scenario loans...")
        _, sched_a = _amort(75000, 14.0, 12)
        on_time_statuses = [(ScheduleStatus.PAID, 1.0, 0)] * 12   # paid_offset=0 → on the due date
        app_on_time = await _create_scenario_loan(
            applicant=scenario_applicants[0],
            ref_suffix="ONTIME",
            amount=75000,
            rate=14.0,
            term=12,
            purpose_desc="Repaid on-time scenario – all installments paid by due date",
            schedule_statuses=on_time_statuses,
            disburse_days_ago=370,   # >12 months ago so all installments are in the past
        )
        print(f"    [A] Repaid on-time:    {app_on_time.reference_number}  $75,000 × 12m @ 14%")

        # ─────────────────────────────────────────────────────────────
        # SCENARIO B:  Repaid In-Advance  ($120,000, 24 months, 16.5%)
        #   - First 8 installments paid 5-15 days early.
        #   - Remaining 16 installments paid off in a lump sum
        #     (simulated by marking them all PAID on inst 9's date).
        # ─────────────────────────────────────────────────────────────
        _, sched_b = _amort(120000, 16.5, 24)
        advance_statuses = []
        # First 8: paid 5-15 days early
        for i in range(8):
            advance_statuses.append((ScheduleStatus.PAID, 1.0, random.randint(5, 15)))
        # Remaining 16: lump-sum early payoff (paid on month 9, i.e. well before due)
        for i in range(8, 24):
            advance_statuses.append((ScheduleStatus.PAID, 1.0, 30 * (i - 7)))  # ~months early
        app_advance = await _create_scenario_loan(
            applicant=scenario_applicants[1],
            ref_suffix="ADVANCE",
            amount=120000,
            rate=16.5,
            term=24,
            purpose_desc="Repaid in-advance scenario – early payments + lump-sum payoff at month 9",
            schedule_statuses=advance_statuses,
            disburse_days_ago=750,   # ~2 years ago so all 24 months are past
        )
        print(f"    [B] Repaid in-advance: {app_advance.reference_number}  $120,000 × 24m @ 16.5%")

        # ─────────────────────────────────────────────────────────────
        # SCENARIO C:  Written-Off  ($50,000, 18 months, 22%)
        #   - First 3 installments paid on time.
        #   - Installment 4 partial (50%).
        #   - Installments 5-6 overdue (0% paid).
        #   - Remaining installments upcoming (never reached).
        #   This loan will be provisioned and written off by the GL
        #   backfill in seed_gl.py (provisions for overdue, write-off
        #   for the worst delinquent).
        # ─────────────────────────────────────────────────────────────
        wo_statuses = []
        # 3 paid on time
        for i in range(3):
            wo_statuses.append((ScheduleStatus.PAID, 1.0, 0))
        # 1 partial
        wo_statuses.append((ScheduleStatus.PARTIAL, 0.5, 0))
        # 2 overdue
        wo_statuses.append((ScheduleStatus.OVERDUE, 0.0, 0))
        wo_statuses.append((ScheduleStatus.OVERDUE, 0.0, 0))
        # rest upcoming
        for i in range(12):
            wo_statuses.append((ScheduleStatus.UPCOMING, 0.0, 0))
        app_written_off = await _create_scenario_loan(
            applicant=scenario_applicants[2],
            ref_suffix="WRITEOFF",
            amount=50000,
            rate=22.0,
            term=18,
            purpose_desc="Written-off scenario – defaulted after 3 payments",
            schedule_statuses=wo_statuses,
            disburse_days_ago=300,   # ~10 months ago
        )
        print(f"    [C] Written-off:       {app_written_off.reference_number}  $50,000 × 18m @ 22%")

        # ─────────────────────────────────────────────────────────────
        # SCENARIO D:  Repaid On-Time (small)  ($15,000, 6 months, 10%)
        #   - Short-term loan, all 6 installments paid exactly on time.
        # ─────────────────────────────────────────────────────────────
        on_time_6 = [(ScheduleStatus.PAID, 1.0, 0)] * 6
        app_on_time_small = await _create_scenario_loan(
            applicant=scenario_applicants[3],
            ref_suffix="ONTIME6M",
            amount=15000,
            rate=10.0,
            term=6,
            purpose_desc="Repaid on-time (short-term) – 6 months, all paid",
            schedule_statuses=on_time_6,
            disburse_days_ago=200,
        )
        print(f"    [D] Repaid on-time (short): {app_on_time_small.reference_number}  $15,000 × 6m @ 10%")

        # ─────────────────────────────────────────────────────────────
        # SCENARIO E:  Written-Off (severe)  ($200,000, 36 months, 18%)
        #   - 2 paid, 1 partial, 5 overdue, rest upcoming.
        #   - Large loan to make GL numbers visible in reports.
        # ─────────────────────────────────────────────────────────────
        wo2_statuses = []
        # 2 paid
        wo2_statuses.append((ScheduleStatus.PAID, 1.0, 1))
        wo2_statuses.append((ScheduleStatus.PAID, 1.0, 0))
        # 1 partial
        wo2_statuses.append((ScheduleStatus.PARTIAL, 0.4, 0))
        # 5 overdue
        for _ in range(5):
            wo2_statuses.append((ScheduleStatus.OVERDUE, 0.0, 0))
        # rest upcoming
        for _ in range(28):
            wo2_statuses.append((ScheduleStatus.UPCOMING, 0.0, 0))
        app_wo_severe = await _create_scenario_loan(
            applicant=scenario_applicants[4],
            ref_suffix="WOSEVER",
            amount=200000,
            rate=18.0,
            term=36,
            purpose_desc="Severe write-off scenario – large loan, 5 overdue installments",
            schedule_statuses=wo2_statuses,
            disburse_days_ago=320,
        )
        print(f"    [E] Written-off (severe):   {app_wo_severe.reference_number}  $200,000 × 36m @ 18%")

        await db.flush()

        # ══════════════════════════════════════════════════════════════
        # Delinquent loans for WhatsApp collections testing
        # Borrower phone: +447432723070
        # ══════════════════════════════════════════════════════════════
        print("  Creating WhatsApp collections test loans...")
        wa_phone = "+447432723070"

        # Create a dedicated borrower with the target phone number
        wa_borrower = User(
            email="delinquent.borrower@email.com",
            hashed_password=hash_password("Applicant1!"),
            first_name="Derrick",
            last_name="Wellington",
            phone=wa_phone,
            role=UserRole.APPLICANT,
        )
        db.add(wa_borrower)
        await db.flush()

        wa_dob = date(1988, 5, 14)
        wa_profile = ApplicantProfile(
            user_id=wa_borrower.id,
            date_of_birth=wa_dob,
            national_id=random_national_id(wa_dob),
            gender="male",
            marital_status="married",
            address_line1="42 Frederick Street",
            city="Port of Spain",
            parish="Port of Spain",
            employer_name="Massy Stores",
            employer_sector="Retail & Distribution",
            job_title="Supervisor",
            employment_type="employed",
            years_employed=6,
            monthly_income=12000,
            other_income=0,
            monthly_expenses=5000,
            existing_debt=8000,
            dependents=2,
            id_verified=True,
            id_verification_status="verified",
            whatsapp_number=wa_phone,
            mobile_phone=wa_phone,
        )
        db.add(wa_profile)
        await db.flush()

        # ── Loan F: 30 days overdue  ($25,000 × 12m @ 15%) ────────
        delinq_f_statuses = []
        for i in range(3):
            delinq_f_statuses.append((ScheduleStatus.PAID, 1.0, 0))
        # 2 overdue
        delinq_f_statuses.append((ScheduleStatus.OVERDUE, 0.0, 0))
        delinq_f_statuses.append((ScheduleStatus.OVERDUE, 0.0, 0))
        # rest upcoming
        for _ in range(7):
            delinq_f_statuses.append((ScheduleStatus.UPCOMING, 0.0, 0))

        app_delinq_f = await _create_scenario_loan(
            applicant=wa_borrower,
            ref_suffix="DELINQ30",
            amount=25000,
            rate=15.0,
            term=12,
            purpose_desc="Delinquent 30 days – personal loan, 2 missed payments",
            schedule_statuses=delinq_f_statuses,
            disburse_days_ago=160,
        )
        print(f"    [F] 30-day delinquent:  {app_delinq_f.reference_number}  $25,000 × 12m @ 15%  phone={wa_phone}")

        # ── Loan G: 60+ days overdue  ($40,000 × 18m @ 18%) ───────
        delinq_g_statuses = []
        for i in range(2):
            delinq_g_statuses.append((ScheduleStatus.PAID, 1.0, 0))
        # 1 partial
        delinq_g_statuses.append((ScheduleStatus.PARTIAL, 0.3, 0))
        # 3 overdue
        for _ in range(3):
            delinq_g_statuses.append((ScheduleStatus.OVERDUE, 0.0, 0))
        # rest upcoming
        for _ in range(12):
            delinq_g_statuses.append((ScheduleStatus.UPCOMING, 0.0, 0))

        app_delinq_g = await _create_scenario_loan(
            applicant=wa_borrower,
            ref_suffix="DELINQ60",
            amount=40000,
            rate=18.0,
            term=18,
            purpose_desc="Delinquent 60+ days – hire purchase, 3 missed + 1 partial",
            schedule_statuses=delinq_g_statuses,
            disburse_days_ago=210,
        )
        print(f"    [G] 60-day delinquent:  {app_delinq_g.reference_number}  $40,000 × 18m @ 18%  phone={wa_phone}")

        # ── Loan H: 90+ days overdue  ($65,000 × 24m @ 20%) ───────
        delinq_h_statuses = []
        # 1 paid
        delinq_h_statuses.append((ScheduleStatus.PAID, 1.0, 0))
        # 4 overdue
        for _ in range(4):
            delinq_h_statuses.append((ScheduleStatus.OVERDUE, 0.0, 0))
        # rest upcoming
        for _ in range(19):
            delinq_h_statuses.append((ScheduleStatus.UPCOMING, 0.0, 0))

        app_delinq_h = await _create_scenario_loan(
            applicant=wa_borrower,
            ref_suffix="DELINQ90",
            amount=65000,
            rate=20.0,
            term=24,
            purpose_desc="Delinquent 90+ days – business loan, severe arrears",
            schedule_statuses=delinq_h_statuses,
            disburse_days_ago=270,
        )
        print(f"    [H] 90-day delinquent:  {app_delinq_h.reference_number}  $65,000 × 24m @ 20%  phone={wa_phone}")

        await db.flush()

        # ── Audit logs ─────────────────────────────────
        for app in loan_apps[:50]:  # First 50 apps get audit logs
            audit = AuditLog(
                entity_type="loan_application",
                entity_id=app.id,
                action="decision_engine_run" if app.decided_at else "submitted",
                user_id=app.assigned_underwriter_id,
                new_values={"status": app.status.value},
                created_at=app.created_at,
            )
            db.add(audit)

        # ── Decision Rules Config ──────────────────────
        rules_config = DecisionRulesConfig(
            version=2,
            name=DEFAULT_RULES["name"],
            rules=DEFAULT_RULES["rules"],
            is_active=True,
            created_by=admin.id,
        )
        db.add(rules_config)

        # ── Sector Analysis: historical snapshots (12 months) ──
        print("\n  Generating sector analysis snapshots...")

        # Gather current sector distribution from seeded loans
        sector_loan_map: dict[str, list] = {}
        for app in loan_apps:
            if app.status == LoanStatus.DISBURSED:
                for prof in profiles:
                    if prof.user_id == app.applicant_id:
                        sec = prof.employer_sector or "MISSING"
                        sector_loan_map.setdefault(sec, []).append(app)
                        break

        total_outstanding_all = sum(
            float(a.amount_approved or 0) for apps in sector_loan_map.values() for a in apps
        )

        for month_offset in range(12, 0, -1):
            snap_date = (today - timedelta(days=30 * month_offset)).replace(day=1)
            growth = 1.0 - (month_offset * 0.04)  # portfolio grew ~4% per month
            for sec, sec_apps in sector_loan_map.items():
                n = max(1, int(len(sec_apps) * growth))
                outstanding = sum(float(a.amount_approved or 0) for a in sec_apps[:n]) * growth
                exposure = (outstanding / (total_outstanding_all * growth)) * 100 if total_outstanding_all > 0 else 0
                base_delinq = random.uniform(1, 15)
                dpd_30 = max(0, int(n * random.uniform(0.02, 0.10)))
                dpd_60 = max(0, int(n * random.uniform(0.01, 0.05)))
                dpd_90 = max(0, int(n * random.uniform(0.00, 0.03)))

                snap = SectorSnapshot(
                    snapshot_date=snap_date,
                    sector=sec,
                    loan_count=n,
                    total_outstanding=round(outstanding, 2),
                    total_disbursed=round(outstanding * 1.1, 2),
                    avg_loan_size=round(outstanding / n, 2) if n else 0,
                    exposure_pct=round(exposure, 2),
                    current_count=n - dpd_30 - dpd_60 - dpd_90,
                    dpd_30_count=dpd_30,
                    dpd_60_count=dpd_60,
                    dpd_90_count=dpd_90,
                    dpd_30_amount=round(dpd_30 * random.uniform(2000, 8000), 2),
                    dpd_60_amount=round(dpd_60 * random.uniform(3000, 10000), 2),
                    dpd_90_amount=round(dpd_90 * random.uniform(4000, 15000), 2),
                    delinquency_rate=round(base_delinq, 2),
                    npl_ratio=round(random.uniform(0, 5), 2),
                    default_rate=round(random.uniform(0, 3), 2),
                    risk_rating="medium",
                )
                db.add(snap)

        # ── Seed some sector policies ──
        high_risk_sectors = ["Oil, Gas & Energy", "Mining & Extractives", "Hospitality & Tourism"]
        for sec in high_risk_sectors:
            pol = SectorPolicy(
                sector=sec,
                exposure_cap_pct=round(random.uniform(12, 20), 1),
                origination_paused=False,
                risk_rating=SectorRiskRating.HIGH,
                on_watchlist=True,
                watchlist_review_frequency="monthly",
                status=SectorPolicyStatus.ACTIVE,
                created_by=admin.id,
                approved_by=admin.id,
                justification="High macroeconomic sensitivity — enhanced monitoring required",
            )
            db.add(pol)

        # One paused sector
        paused_pol = SectorPolicy(
            sector="Mining & Extractives",
            exposure_cap_pct=8.0,
            origination_paused=True,
            pause_effective_date=today - timedelta(days=14),
            pause_expiry_date=today + timedelta(days=60),
            pause_reason="Commodity price crash — bauxite sector under stress",
            risk_rating=SectorRiskRating.CRITICAL,
            on_watchlist=True,
            watchlist_review_frequency="weekly",
            max_loan_amount_override=25000,
            min_credit_score_override=700,
            status=SectorPolicyStatus.ACTIVE,
            created_by=admin.id,
            approved_by=admin.id,
            justification="Q4 stress test flagged Mining sector — pause origination until review",
        )
        db.add(paused_pol)

        # ── Seed alert rules ──
        rules_data = [
            ("High NPL Ratio", None, "npl_ratio", ">", 5.0, "critical", "Review sector policy and consider tightening criteria"),
            ("Exposure Concentration", None, "exposure_pct", ">", 20.0, "warning", "Monitor sector exposure — consider setting caps"),
            ("Rising Delinquency", None, "delinquency_rate", ">", 10.0, "warning", "Investigate root cause of delinquency increase"),
            ("Tourism Stress", "Hospitality & Tourism", "delinquency_rate", ">", 8.0, "critical", "Tourism sector under pressure — review all new applications"),
        ]
        for name, sec, metric, op, thresh, sev, action in rules_data:
            rule = SectorAlertRule(
                name=name,
                sector=sec,
                metric=metric,
                operator=op,
                threshold=thresh,
                severity=SectorAlertSeverity(sev),
                recommended_action=action,
                is_active=True,
                created_by=admin.id,
            )
            db.add(rule)

        # ── Seed a few sample alerts ──
        sample_alerts = [
            ("Hospitality & Tourism", "critical", "NPL Ratio Exceeded 5%", "npl_ratio", 6.2, 5.0, "Tighten origination criteria for hospitality"),
            ("Oil, Gas & Energy", "warning", "Exposure approaching cap", "exposure_pct", 18.5, 20.0, "Monitor closely — near concentration limit"),
        ]
        for sec, sev, title, mn, mv, tv, ra in sample_alerts:
            alert = SectorAlert(
                sector=sec,
                severity=SectorAlertSeverity(sev),
                title=title,
                description=f"{mn} is {mv} (threshold: > {tv})",
                metric_name=mn,
                metric_value=mv,
                threshold_value=tv,
                recommended_action=ra,
                status=SectorAlertStatus.NEW,
            )
            db.add(alert)

        print(f"  - Sector snapshots: {12 * len(sector_loan_map)} records (12 months)")
        print(f"  - Sector policies: {len(high_risk_sectors) + 1}")
        print(f"  - Alert rules: {len(rules_data)}")
        print(f"  - Sample alerts: {len(sample_alerts)}")

        # ══════════════════════════════════════════════════════════════════
        # COLLECTIONS MODULE SEED DATA
        # ══════════════════════════════════════════════════════════════════
        print("\n=== Seeding collections module data ===")

        # 1. Compliance Rules
        jurisdictions = [
            ("TT", 8, 20, 3, 10, 4),
            ("JM", 8, 19, 3, 12, 4),
            ("BB", 9, 18, 2, 8, 6),
            ("GY", 8, 20, 4, 15, 3),
        ]
        for jur, start, end, per_day, per_week, cooloff in jurisdictions:
            db.add(ComplianceRule(
                jurisdiction=jur,
                contact_start_hour=start,
                contact_end_hour=end,
                max_contacts_per_day=per_day,
                max_contacts_per_week=per_week,
                cooling_off_hours=cooloff,
                is_active=True,
            ))
        print(f"  - Compliance rules: {len(jurisdictions)}")

        # 2. SLA Configs
        sla_configs = [
            ("First Contact — Early", "early_1_30", 24, "auto_whatsapp_reminder"),
            ("First Contact — Mid", "mid_31_60", 12, "assign_agent_call"),
            ("First Contact — Late", "late_61_90", 8, "escalate_supervisor"),
            ("First Contact — Severe", "severe_90_plus", 4, "escalate_legal"),
            ("Follow-up — Early", "early_1_30", 72, "send_sms_reminder"),
            ("Follow-up — Mid", "mid_31_60", 48, "call_now"),
        ]
        for name, stage, hours, action in sla_configs:
            db.add(SLAConfig(name=name, delinquency_stage=stage, hours_allowed=hours, escalation_action=action, is_active=True))
        print(f"  - SLA configs: {len(sla_configs)}")

        # 3. Collection Cases for overdue disbursed loans
        today = date.today()
        overdue_apps = [a for a in disbursed_apps if any(
            getattr(s, "status", None) in (ScheduleStatus.OVERDUE,) for s in getattr(a, "_schedules", [])
        )]
        # Fallback: use all disbursed apps and just create cases for a subset
        case_apps = disbursed_apps[:min(len(disbursed_apps), 20)]
        staff_ids = [staff_admin.id, staff_senior.id, staff_junior.id, staff_junior2.id]
        cases_created = 0
        ptp_created = 0
        settlement_created = 0

        for i, app_obj in enumerate(case_apps):
            dpd = random.choice([3, 7, 15, 25, 35, 45, 55, 70, 85, 95, 120])
            stage = dpd_to_stage(dpd)
            total_overdue = round(random.uniform(200, 8000), 2)
            agent_id = random.choice(staff_ids) if random.random() > 0.2 else None

            cc = CollectionCase(
                loan_application_id=app_obj.id,
                assigned_agent_id=agent_id,
                status=random.choice([CaseStatus.OPEN, CaseStatus.IN_PROGRESS, CaseStatus.IN_PROGRESS]),
                delinquency_stage=stage,
                priority_score=round(random.uniform(0.1, 0.9), 4),
                dpd=dpd,
                total_overdue=Decimal(str(total_overdue)),
                dispute_active=random.random() < 0.1,
                vulnerability_flag=random.random() < 0.05,
                do_not_contact=random.random() < 0.03,
                hardship_flag=random.random() < 0.08,
                next_best_action=random.choice([
                    "send_whatsapp_reminder", "call_now", "send_demand_letter",
                    "escalate_supervisor", "escalate_legal", None,
                ]),
                nba_confidence=round(random.uniform(0.6, 1.0), 2) if random.random() > 0.2 else None,
                nba_reasoning="Rule-based recommendation",
                jurisdiction="TT",
                first_contact_at=datetime.now(timezone.utc) - timedelta(days=dpd - 2) if dpd > 5 and random.random() > 0.3 else None,
                last_contact_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, min(dpd, 10))) if dpd > 3 and random.random() > 0.3 else None,
            )
            db.add(cc)
            await db.flush()
            cases_created += 1

            # Create PTPs for some cases
            if random.random() < 0.5:
                num_ptps = random.randint(1, 3)
                for j in range(num_ptps):
                    ptp_status = random.choice([PTPStatus.PENDING, PTPStatus.KEPT, PTPStatus.BROKEN, PTPStatus.PARTIALLY_KEPT])
                    ptp = PromiseToPay(
                        collection_case_id=cc.id,
                        loan_application_id=app_obj.id,
                        agent_id=random.choice(staff_ids),
                        amount_promised=Decimal(str(round(random.uniform(100, total_overdue * 0.5), 2))),
                        promise_date=today - timedelta(days=random.randint(0, 30)),
                        payment_method=random.choice(["bank_transfer", "online", "cash", None]),
                        status=ptp_status,
                        amount_received=Decimal(str(round(random.uniform(50, 500), 2))) if ptp_status in (PTPStatus.KEPT, PTPStatus.PARTIALLY_KEPT) else Decimal("0"),
                        broken_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 10)) if ptp_status == PTPStatus.BROKEN else None,
                        notes=random.choice(["Called and agreed", "Verbal agreement on phone", "WhatsApp confirmation", None]),
                    )
                    db.add(ptp)
                    ptp_created += 1

            # Create settlement offers for some cases
            if random.random() < 0.3:
                offer_type = random.choice([SettlementOfferType.FULL_PAYMENT, SettlementOfferType.SHORT_PLAN, SettlementOfferType.PARTIAL_SETTLEMENT])
                discount = random.choice([0, 5, 10, 15]) if offer_type == SettlementOfferType.PARTIAL_SETTLEMENT else 0
                settlement_amt = round(total_overdue * (100 - discount) / 100, 2)
                db.add(SettlementOffer(
                    collection_case_id=cc.id,
                    loan_application_id=app_obj.id,
                    offer_type=offer_type,
                    original_balance=Decimal(str(total_overdue)),
                    settlement_amount=Decimal(str(settlement_amt)),
                    discount_pct=discount,
                    plan_months=random.choice([3, 6]) if offer_type == SettlementOfferType.SHORT_PLAN else None,
                    plan_monthly_amount=Decimal(str(round(settlement_amt / 3, 2))) if offer_type == SettlementOfferType.SHORT_PLAN else None,
                    lump_sum=Decimal(str(settlement_amt)) if offer_type != SettlementOfferType.SHORT_PLAN else None,
                    status=random.choice([SettlementOfferStatus.DRAFT, SettlementOfferStatus.OFFERED, SettlementOfferStatus.APPROVED]),
                    offered_by=random.choice(staff_ids),
                    approval_required=discount > 5,
                    notes="Auto-generated seed offer",
                ))
                settlement_created += 1

        print(f"  - Collection cases: {cases_created}")
        print(f"  - Promises to pay: {ptp_created}")
        print(f"  - Settlement offers: {settlement_created}")

        # 4. Dashboard Snapshots (last 30 days)
        for d in range(30):
            snap_date = today - timedelta(days=29 - d)
            base_accounts = random.randint(10, 25)
            base_overdue = round(random.uniform(15000, 80000), 2)
            db.add(CollectionsDashboardSnapshot(
                snapshot_date=snap_date,
                total_delinquent_accounts=base_accounts,
                total_overdue_amount=Decimal(str(base_overdue)),
                by_stage={
                    "early_1_30": {"count": random.randint(3, 10), "amount": round(random.uniform(2000, 15000), 2)},
                    "mid_31_60": {"count": random.randint(2, 6), "amount": round(random.uniform(3000, 20000), 2)},
                    "late_61_90": {"count": random.randint(1, 4), "amount": round(random.uniform(2000, 15000), 2)},
                    "severe_90_plus": {"count": random.randint(0, 3), "amount": round(random.uniform(1000, 10000), 2)},
                },
                by_outcome={
                    "promise_to_pay": random.randint(2, 8),
                    "no_answer": random.randint(3, 12),
                    "payment_arranged": random.randint(1, 5),
                },
                cure_rate=round(random.uniform(0.15, 0.45), 4),
                ptp_rate=round(random.uniform(0.3, 0.7), 4),
                ptp_kept_rate=round(random.uniform(0.4, 0.8), 4),
                avg_days_to_collect=round(random.uniform(15, 60), 2),
                total_recovered_mtd=Decimal(str(round(random.uniform(5000, 30000), 2))),
            ))
        print(f"  - Dashboard snapshots: 30 days")

        await db.commit()

        # Summary
        status_counts = {}
        for app in loan_apps:
            s = app.status.value
            status_counts[s] = status_counts.get(s, 0) + 1

        print("\nDatabase seeded successfully!")
        print(f"  - Staff: admin@zotta.tt / Admin123!")
        print(f"  - Senior UW: sarah.uw@zotta.tt / Underwriter1!")
        print(f"  - Junior UW: kevin.uw@zotta.tt / Underwriter1!")
        print(f"  - Junior UW2: alicia.uw@zotta.tt / Underwriter1!")
        print(f"  - Applicants: {NUM_APPLICANTS} users (password: Applicant1!)")
        print(f"  - Applications: {NUM_APPS}")
        print(f"  - Status distribution:")
        for status, count in sorted(status_counts.items()):
            print(f"      {status}: {count}")
        print(f"  - Disbursed with schedules: {len(disbursed_apps)}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
