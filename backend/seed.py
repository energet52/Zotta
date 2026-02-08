"""Seed script to populate the database with test data."""

import asyncio
import random
from datetime import datetime, date, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base
from app.auth_utils import hash_password
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus, LoanPurpose, ApplicantProfile
from app.models.decision import Decision, DecisionOutcome, DecisionRulesConfig
from app.services.decision_engine.rules import DEFAULT_RULES


async def seed():
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        print("Seeding database...")

        # ── Users ──────────────────────────────────────
        admin = User(
            email="admin@zotta.tt",
            hashed_password=hash_password("Admin123!"),
            first_name="Admin",
            last_name="Zotta",
            role=UserRole.ADMIN,
        )
        senior_uw = User(
            email="sarah.uw@zotta.tt",
            hashed_password=hash_password("Underwriter1!"),
            first_name="Sarah",
            last_name="Mohammed",
            role=UserRole.SENIOR_UNDERWRITER,
        )
        junior_uw = User(
            email="kevin.uw@zotta.tt",
            hashed_password=hash_password("Underwriter1!"),
            first_name="Kevin",
            last_name="Singh",
            role=UserRole.JUNIOR_UNDERWRITER,
        )

        # Applicants
        applicants_data = [
            ("john.doe@email.com", "John", "Doe", "+18687001001"),
            ("maria.garcia@email.com", "Maria", "Garcia", "+18687001002"),
            ("andre.williams@email.com", "Andre", "Williams", "+18687001003"),
            ("priya.ramnath@email.com", "Priya", "Ramnath", "+18687001004"),
            ("marcus.joseph@email.com", "Marcus", "Joseph", "+18687001005"),
        ]

        applicants = []
        for email, first, last, phone in applicants_data:
            user = User(
                email=email,
                hashed_password=hash_password("Applicant1!"),
                first_name=first,
                last_name=last,
                phone=phone,
                role=UserRole.APPLICANT,
            )
            applicants.append(user)

        db.add_all([admin, senior_uw, junior_uw] + applicants)
        await db.flush()

        # ── Applicant Profiles ─────────────────────────
        profiles_data = [
            {
                "user_id": applicants[0].id,
                "date_of_birth": date(1988, 3, 15),
                "national_id": "19880315001",
                "gender": "male",
                "marital_status": "married",
                "address_line1": "42 Frederick Street",
                "city": "Port of Spain",
                "parish": "Port of Spain",
                "employer_name": "TSTT",
                "job_title": "Senior Engineer",
                "employment_type": "employed",
                "years_employed": 8,
                "monthly_income": 15000,
                "monthly_expenses": 5000,
                "existing_debt": 25000,
                "dependents": 2,
                "id_verified": True,
                "id_verification_status": "verified",
            },
            {
                "user_id": applicants[1].id,
                "date_of_birth": date(1995, 7, 22),
                "national_id": "19950722002",
                "gender": "female",
                "marital_status": "single",
                "address_line1": "88 Ariapita Avenue",
                "city": "Woodbrook",
                "parish": "Port of Spain",
                "employer_name": "Republic Bank",
                "job_title": "Teller",
                "employment_type": "employed",
                "years_employed": 3,
                "monthly_income": 8000,
                "monthly_expenses": 3500,
                "existing_debt": 10000,
                "dependents": 0,
                "id_verified": True,
                "id_verification_status": "verified",
            },
            {
                "user_id": applicants[2].id,
                "date_of_birth": date(1975, 11, 5),
                "national_id": "19751105003",
                "gender": "male",
                "marital_status": "divorced",
                "address_line1": "15 Main Road",
                "city": "San Fernando",
                "parish": "San Fernando",
                "employer_name": "Self-employed",
                "job_title": "Contractor",
                "employment_type": "self_employed",
                "years_employed": 12,
                "monthly_income": 20000,
                "monthly_expenses": 8000,
                "existing_debt": 75000,
                "dependents": 3,
                "id_verified": True,
                "id_verification_status": "verified",
            },
            {
                "user_id": applicants[3].id,
                "date_of_birth": date(2000, 1, 18),
                "national_id": "20000118004",
                "gender": "female",
                "marital_status": "single",
                "address_line1": "7 Trincity Avenue",
                "city": "Trincity",
                "parish": "Tunapuna-Piarco",
                "employer_name": "Massy Stores",
                "job_title": "Sales Associate",
                "employment_type": "employed",
                "years_employed": 1,
                "monthly_income": 4500,
                "monthly_expenses": 2000,
                "existing_debt": 0,
                "dependents": 0,
                "id_verified": False,
                "id_verification_status": "pending",
            },
            {
                "user_id": applicants[4].id,
                "date_of_birth": date(1992, 6, 30),
                "national_id": "19920630005",
                "gender": "male",
                "marital_status": "married",
                "address_line1": "22 Debe Road",
                "city": "Debe",
                "parish": "Penal-Debe",
                "employer_name": "bpTT",
                "job_title": "Process Technician",
                "employment_type": "employed",
                "years_employed": 6,
                "monthly_income": 12000,
                "monthly_expenses": 4500,
                "existing_debt": 40000,
                "dependents": 1,
                "id_verified": True,
                "id_verification_status": "verified",
            },
        ]

        for pdata in profiles_data:
            db.add(ApplicantProfile(**pdata))

        # ── Loan Applications ──────────────────────────
        purposes = list(LoanPurpose)
        statuses_sample = [
            LoanStatus.APPROVED,
            LoanStatus.SUBMITTED,
            LoanStatus.UNDER_REVIEW,
            LoanStatus.DECLINED,
            LoanStatus.DECISION_PENDING,
        ]

        apps = []
        for i, (applicant, status) in enumerate(zip(applicants, statuses_sample)):
            amount = random.choice([25000, 50000, 100000, 150000, 200000])
            term = random.choice([12, 24, 36, 48, 60])
            submitted = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))

            app = LoanApplication(
                reference_number=f"ZOT-2026-TEST{i+1:04d}",
                applicant_id=applicant.id,
                amount_requested=amount,
                term_months=term,
                purpose=random.choice(purposes),
                status=status,
                submitted_at=submitted,
            )

            if status in (LoanStatus.APPROVED, LoanStatus.DECLINED):
                app.decided_at = submitted + timedelta(days=random.randint(1, 5))
            if status == LoanStatus.APPROVED:
                app.amount_approved = amount
                app.interest_rate = random.choice([8.5, 12.0, 16.5])
                r = app.interest_rate / 100 / 12
                n = term
                pmt = amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
                app.monthly_payment = round(pmt, 2)

            apps.append(app)

        db.add_all(apps)
        await db.flush()

        # ── Decisions ──────────────────────────────────
        for app in apps:
            if app.status in (LoanStatus.APPROVED, LoanStatus.DECLINED, LoanStatus.DECISION_PENDING):
                score = random.randint(400, 800)
                bands = {(750, 850): "A", (680, 749): "B", (600, 679): "C", (500, 599): "D", (300, 499): "E"}
                risk_band = "C"
                for (lo, hi), band in bands.items():
                    if lo <= score <= hi:
                        risk_band = band
                        break

                outcome = (
                    DecisionOutcome.AUTO_APPROVE if app.status == LoanStatus.APPROVED
                    else DecisionOutcome.AUTO_DECLINE if app.status == LoanStatus.DECLINED
                    else DecisionOutcome.MANUAL_REVIEW
                )

                decision = Decision(
                    loan_application_id=app.id,
                    credit_score=score,
                    risk_band=risk_band,
                    engine_outcome=outcome,
                    engine_reasons={"reasons": ["Test seed data"]},
                    scoring_breakdown={"payment_history": 80, "debt_to_income": 70},
                    final_outcome=outcome.value,
                    rules_version=1,
                )
                db.add(decision)

        # ── Decision Rules Config ──────────────────────
        rules_config = DecisionRulesConfig(
            version=1,
            name=DEFAULT_RULES["name"],
            rules=DEFAULT_RULES["rules"],
            is_active=True,
            created_by=admin.id,
        )
        db.add(rules_config)

        await db.commit()
        print("Database seeded successfully!")
        print(f"  - Admin: admin@zotta.tt / Admin123!")
        print(f"  - Senior UW: sarah.uw@zotta.tt / Underwriter1!")
        print(f"  - Junior UW: kevin.uw@zotta.tt / Underwriter1!")
        print(f"  - Applicants: john.doe@email.com (etc.) / Applicant1!")
        print(f"  - {len(apps)} loan applications created")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
