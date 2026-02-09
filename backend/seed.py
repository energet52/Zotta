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
from app.models.payment import Payment, PaymentType, PaymentStatus, PaymentSchedule, ScheduleStatus
from app.models.audit import AuditLog
from app.services.decision_engine.rules import DEFAULT_RULES

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
