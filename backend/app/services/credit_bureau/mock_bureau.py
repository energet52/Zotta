"""Mock credit bureau adapter for development and testing.

Generates realistic synthetic credit data modelled after the EveryData
ReportPlus format used by Caribbean credit bureaus.

Sections generated:
 - Subject info (name, address, contacts, DOB, tax number)
 - EveryData-style score, risk grade (A1–E2) and probability of default
 - Open / closed contracts table (sector, type, creditor, dates, amounts)
 - Score history (last 12 months)
 - Inquiry counts (1 / 3 / 6 / 12 / 24 months) + detailed inquiry list
 - Payment calendar (last 12 months)
 - Collaterals, disputes, public records
 - Legacy fields kept for backward-compat with decision engine
"""

import hashlib
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.services.credit_bureau.adapter import CreditBureauAdapter

# ── Reference data ────────────────────────────────────

SCENARIOS = {
    "good": {
        "score_range": (720, 820),
        "payment_history": (0.85, 0.98),
        "debt_range": (5000, 30000),
        "history_years": (5, 15),
        "inquiries": (0, 2),
        "tradelines_count": (3, 8),
        "delinquent_chance": 0.05,
        "judgment_chance": 0.0,
        "avk_debt_chance": 0.0,
    },
    "fair": {
        "score_range": (600, 719),
        "payment_history": (0.65, 0.84),
        "debt_range": (20000, 80000),
        "history_years": (2, 7),
        "inquiries": (2, 5),
        "tradelines_count": (2, 6),
        "delinquent_chance": 0.2,
        "judgment_chance": 0.05,
        "avk_debt_chance": 0.1,
    },
    "poor": {
        "score_range": (400, 599),
        "payment_history": (0.3, 0.64),
        "debt_range": (50000, 200000),
        "history_years": (1, 4),
        "inquiries": (4, 10),
        "tradelines_count": (1, 5),
        "delinquent_chance": 0.5,
        "judgment_chance": 0.3,
        "avk_debt_chance": 0.4,
    },
    "thin": {
        "score_range": (500, 650),
        "payment_history": (0.7, 0.9),
        "debt_range": (0, 5000),
        "history_years": (0, 1),
        "inquiries": (0, 1),
        "tradelines_count": (0, 1),
        "delinquent_chance": 0.0,
        "judgment_chance": 0.0,
        "avk_debt_chance": 0.0,
    },
}

TRINIDAD_LENDERS = [
    "Republic Bank Limited",
    "First Citizens Bank",
    "Scotiabank Trinidad",
    "RBC Royal Bank",
    "JMMB Bank",
    "Citibank Trinidad",
    "Courts",
    "Unicomer",
]

TRADELINE_TYPES = [
    "Personal Loan",
    "Credit Card",
    "Auto Loan",
    "Hire Purchase",
    "Mortgage",
    "Line of Credit",
]

SECTORS = [
    "Banking",
    "MFI Other",
    "Insurance",
    "Telecommunications",
    "Retail Finance",
]

INQUIRY_REASONS = [
    "Application For Credit or Amendment of Credit Terms",
    "Account Review",
    "Pre-Approved Offer",
    "Employment Verification",
    "Insurance Underwriting",
]

FIRST_NAMES = [
    "Andre", "Keisha", "Marcus", "Aisha", "Devon", "Camille",
    "Darnell", "Tamika", "Jason", "Rhonda", "Curtis", "Nadia",
]
LAST_NAMES = [
    "Williams", "Mohammed", "Singh", "Charles", "Baptiste",
    "Rampersad", "Thomas", "Ali", "Pierre", "De Silva",
]

STREET_NAMES = [
    "Frederick Street", "Ariapita Avenue", "Maraval Road",
    "Independence Square", "San Fernando Hill Road",
    "Southern Main Road", "Churchill Roosevelt Highway",
    "Wrightson Road", "Chaguanas Main Road", "Eastern Main Road",
]
AREAS = [
    "Port of Spain", "San Fernando", "Chaguanas",
    "Arima", "Tunapuna", "Couva", "Scarborough",
    "Diego Martin", "Maraval", "St. Augustine",
]


# ── Risk grade helpers ────────────────────────────────

def _score_to_risk_grade(score: int) -> tuple[str, str, float]:
    """Return (grade, description, probability_of_default %) for a score."""
    if score >= 800:
        return "A1", "Very Low Risk", round(random.uniform(0.5, 2.0), 2)
    if score >= 770:
        return "A2", "Very Low Risk", round(random.uniform(2.0, 4.0), 2)
    if score >= 740:
        return "A3", "Very Low Risk", round(random.uniform(4.0, 6.0), 2)
    if score >= 720:
        return "B1", "Low Risk", round(random.uniform(5.0, 8.0), 2)
    if score >= 700:
        return "B2", "Low Risk", round(random.uniform(7.0, 10.0), 2)
    if score >= 680:
        return "B3", "Low Risk", round(random.uniform(9.0, 12.0), 2)
    if score >= 650:
        return "C1", "Average Risk", round(random.uniform(11.0, 15.0), 2)
    if score >= 620:
        return "C2", "Average Risk", round(random.uniform(14.0, 18.0), 2)
    if score >= 600:
        return "C3", "Average Risk", round(random.uniform(17.0, 22.0), 2)
    if score >= 550:
        return "D1", "High Risk", round(random.uniform(20.0, 30.0), 2)
    if score >= 500:
        return "D2", "High Risk", round(random.uniform(28.0, 40.0), 2)
    if score >= 450:
        return "D3", "High Risk", round(random.uniform(38.0, 50.0), 2)
    if score >= 400:
        return "E1", "Very High Risk", round(random.uniform(48.0, 65.0), 2)
    return "E2", "Very High Risk", round(random.uniform(60.0, 85.0), 2)


class MockBureauAdapter(CreditBureauAdapter):
    """Mock implementation that generates synthetic EveryData-style credit data."""

    @property
    def provider_name(self) -> str:
        return "mock_bureau"

    # ── helpers ───────────────────────────────────────

    def _gen_subject_info(self, rng: random.Random, national_id: str) -> Dict[str, Any]:
        """Generate personal / contact information as it would appear on a bureau report."""
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        house = rng.randint(1, 250)
        street = rng.choice(STREET_NAMES)
        area = rng.choice(AREAS)
        dob = datetime(
            rng.randint(1965, 2002),
            rng.randint(1, 12),
            rng.randint(1, 28),
        )
        return {
            "first_name": first,
            "last_name": last,
            "full_name": f"{first} {last}",
            "date_of_birth": dob.strftime("%Y-%m-%d"),
            "tax_number_masked": f"{'*' * (len(national_id) - 4)}{national_id[-4:]}" if len(national_id) >= 4 else national_id,
            "contact_address": f"{house} {street}, {area}",
            "email": f"{first.lower()}.{last.lower()}@{'gmail' if rng.random() > 0.5 else 'yahoo'}.com",
            "mobile": f"+1-868-{rng.randint(300,799)}-{rng.randint(1000,9999)}",
            "fixed_line": f"+1-868-{rng.randint(600,699)}-{rng.randint(1000,9999)}" if rng.random() > 0.6 else None,
            "gender": rng.choice(["Male", "Female"]),
            "marital_status": rng.choice(["Single", "Married", "Not Specified"]),
            "citizenship": "Trinidad and Tobago",
            "residency": "Yes",
            "employment": rng.choice(["Employed", "Self-Employed", "Not Specified"]),
            "education": rng.choice(["Tertiary", "Secondary", "Not Specified"]),
        }

    def _gen_contracts(
        self, rng: random.Random, num: int, history_years: float, delinquent_chance: float, *, closed: bool = False
    ) -> List[Dict[str, Any]]:
        """Generate open or closed contract entries."""
        contracts: List[Dict[str, Any]] = []
        for _ in range(num):
            opened = datetime.now() - timedelta(days=rng.randint(90, int(history_years * 365 + 180)))
            original = round(rng.uniform(5_000, 500_000), 2)
            is_delinquent = rng.random() < delinquent_chance
            balance = 0.0 if closed else round(original * rng.uniform(0.05, 0.85), 2)
            monthly_pmt = round(original / rng.randint(12, 60), 2)
            past_due = round(balance * rng.uniform(0.05, 0.3), 2) if is_delinquent else 0.0
            arrears_days = rng.randint(30, 180) if is_delinquent else 0
            creditor = rng.choice(TRINIDAD_LENDERS)
            sector = rng.choice(SECTORS)
            ctype = rng.choice(TRADELINE_TYPES)
            last_updated = (datetime.now() - timedelta(days=rng.randint(1, 60))).strftime("%Y-%m-%d")

            contracts.append({
                "sector": sector,
                "type": ctype,
                "creditor": creditor,
                "opened_date": opened.strftime("%Y-%m-%d"),
                "last_updated": last_updated,
                "expected_end_date": (opened + timedelta(days=rng.randint(365, 365 * 7))).strftime("%Y-%m-%d") if ctype != "Credit Card" else None,
                "real_end_date": (datetime.now() - timedelta(days=rng.randint(30, 365))).strftime("%Y-%m-%d") if closed else None,
                "total_amount": original,
                "balance": balance,
                "past_due": past_due,
                "arrears_days": arrears_days,
                "monthly_payment": monthly_pmt,
                "status": "Closed" if closed else ("Delinquent" if is_delinquent else "Granted And Activated"),
                "phase": "Closed" if closed else "Open",
                "currency": "TTD",
                "role": "Main Debtor",
            })
        return contracts

    def _gen_score_history(self, rng: random.Random, current_score: int) -> List[Dict[str, Any]]:
        """Generate monthly score history for the last 12 months."""
        history: List[Dict[str, Any]] = []
        now = datetime.now()
        score = current_score
        for i in range(12):
            dt = now - timedelta(days=30 * i)
            month_label = f"{dt.month}/{dt.year}"
            drift = rng.randint(-15, 15)
            score = max(300, min(850, score + drift))
            grade, desc, pd = _score_to_risk_grade(score)
            history.append({
                "month": month_label,
                "score": score,
                "risk_grade": grade,
                "probability_of_default": pd,
            })
        history.reverse()
        return history

    def _gen_inquiries(self, rng: random.Random, count: int) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
        """Generate inquiry details and period counts."""
        inquiries: List[Dict[str, Any]] = []
        now = datetime.now()
        for _ in range(count):
            days_ago = rng.randint(1, 730)
            inq_date = now - timedelta(days=days_ago)
            inquiries.append({
                "date": inq_date.strftime("%Y-%m-%d"),
                "reason": rng.choice(INQUIRY_REASONS),
                "sector": rng.choice(SECTORS),
            })
        inquiries.sort(key=lambda x: x["date"], reverse=True)

        # Counts by period
        counts = {"1_month": 0, "3_months": 0, "6_months": 0, "12_months": 0, "24_months": 0}
        for inq in inquiries:
            d = (now - datetime.strptime(inq["date"], "%Y-%m-%d")).days
            if d <= 30:
                counts["1_month"] += 1
            if d <= 90:
                counts["3_months"] += 1
            if d <= 180:
                counts["6_months"] += 1
            if d <= 365:
                counts["12_months"] += 1
            if d <= 730:
                counts["24_months"] += 1
        return inquiries, counts

    def _gen_payment_calendar(self, rng: random.Random, contracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate a 12-month payment calendar resembling EveryData layout."""
        calendar: List[Dict[str, Any]] = []
        now = datetime.now()
        for i in range(12):
            dt = now - timedelta(days=30 * i)
            month_label = f"{dt.month}/{dt.year}"
            num_contracts = len(contracts) if i < 11 else 0  # last month "No Data"
            if num_contracts == 0:
                calendar.append({
                    "period": month_label,
                    "contracts_submitted": 0,
                    "past_due_days": None,
                    "past_due": None,
                    "not_paid_installments": None,
                    "outstanding": None,
                    "total_monthly_payments": None,
                })
            else:
                total_monthly = sum(c["monthly_payment"] for c in contracts)
                variation = rng.uniform(0.7, 1.3)
                calendar.append({
                    "period": month_label,
                    "contracts_submitted": num_contracts,
                    "past_due_days": 0,
                    "past_due": 0.0,
                    "not_paid_installments": 0,
                    "outstanding": 0.0,
                    "total_monthly_payments": round(total_monthly * variation, 2),
                })
        calendar.reverse()
        return calendar

    # ── main entry point ──────────────────────────────

    async def pull_credit_report(self, national_id: str) -> Dict[str, Any]:
        """Generate a synthetic EveryData-style credit report."""
        hash_val = int(hashlib.md5(national_id.encode()).hexdigest(), 16)
        rng = random.Random(hash_val)

        # Scenario
        scenario_name = rng.choices(
            list(SCENARIOS.keys()),
            weights=[0.4, 0.3, 0.2, 0.1],
            k=1,
        )[0]
        sc = SCENARIOS[scenario_name]

        # Core metrics
        score = rng.randint(*sc["score_range"])
        payment_history = round(rng.uniform(*sc["payment_history"]), 3)
        total_debt = round(rng.uniform(*sc["debt_range"]), 2)
        history_years = round(rng.uniform(*sc["history_years"]), 1)
        num_inquiries = rng.randint(*sc["inquiries"])
        num_open = rng.randint(*sc["tradelines_count"])
        num_closed = rng.randint(0, 3)

        # Risk grade (EveryData style)
        risk_grade, risk_description, probability_of_default = _score_to_risk_grade(score)

        # Subject info
        subject_info = self._gen_subject_info(rng, national_id)

        # Contracts
        open_contracts = self._gen_contracts(rng, num_open, history_years, sc["delinquent_chance"])
        closed_contracts = self._gen_contracts(rng, num_closed, history_years, 0.0, closed=True)

        # Score history
        score_history = self._gen_score_history(rng, score)

        # Inquiries
        inquiries_detail, inquiry_counts = self._gen_inquiries(rng, num_inquiries)

        # Payment calendar
        payment_calendar = self._gen_payment_calendar(rng, open_contracts)

        # Delinquency summary
        delinquent_accounts = sum(1 for c in open_contracts if c["status"] == "Delinquent")
        delinquency_summary = {
            "current_delinquent_accounts": delinquent_accounts,
            "historical_delinquencies": rng.randint(0, 3) if scenario_name != "good" else 0,
            "worst_delinquency": f"{rng.choice([30, 60, 90, 120])} days" if delinquent_accounts > 0 else "None",
            "total_past_due_amount": round(sum(c["past_due"] for c in open_contracts), 2),
        }

        # Payment history detail
        payment_history_detail = {
            "on_time_percentage": round(payment_history * 100, 1),
            "total_accounts_ever": num_open + num_closed + rng.randint(0, 3),
            "accounts_in_good_standing": num_open - delinquent_accounts,
            "accounts_delinquent": delinquent_accounts,
            "months_reviewed": min(int(history_years * 12), 84),
        }

        # Payments profile (EveryData style)
        payments_profile = {
            "past_due_amount_sum_open": round(sum(c["past_due"] for c in open_contracts), 2),
            "worst_current_arrears_days": max((c["arrears_days"] for c in open_contracts), default=0),
            "worst_arrears_12m_days": max((c["arrears_days"] for c in open_contracts), default=0),
            "worst_arrears_24m_days": max((c["arrears_days"] for c in open_contracts), default=0),
            "installment_amount_sum": round(sum(c["monthly_payment"] for c in open_contracts), 2),
            "number_of_creditors": len(set(c["creditor"] for c in open_contracts)),
        }

        # Collaterals
        num_collaterals = rng.randint(0, 2) if scenario_name != "thin" else 0
        collateral_value = round(rng.uniform(50_000, 500_000), 2) if num_collaterals else 0
        collaterals = {
            "count": num_collaterals,
            "total_value": collateral_value,
            "highest_value": collateral_value,
            "type": rng.choice(["Motor Vehicle", "Property", "Savings"]) if num_collaterals else None,
        }

        # Disputes
        disputes = {
            "active_disputes": 0,
            "false_disputes_past": 0,
            "court_cases_registered": 0,
        }

        # Public records
        public_records = []
        if rng.random() < sc.get("judgment_chance", 0):
            public_records.append({
                "type": "Judgment",
                "court": rng.choice([
                    "Port of Spain High Court",
                    "San Fernando Magistrates Court",
                    "Chaguanas Civil Court",
                ]),
                "case_number": f"CV-{rng.randint(2018, 2025)}-{rng.randint(1000, 9999)}",
                "date": (datetime.now() - timedelta(days=rng.randint(180, 1800))).strftime("%Y-%m-%d"),
                "amount": round(rng.uniform(10_000, 100_000), 2),
                "plaintiff": rng.choice(TRINIDAD_LENDERS),
                "status": rng.choice(["active", "satisfied"]),
                "currency": "TTD",
            })

        # AVK data (legacy compat)
        avk_data = {
            "has_outstanding_debt": rng.random() < sc.get("avk_debt_chance", 0),
            "has_court_judgment": any(r["type"] == "Judgment" and r["status"] == "active" for r in public_records),
            "total_avk_debt": round(rng.uniform(5000, 80000), 2) if rng.random() < sc.get("avk_debt_chance", 0) else 0,
            "last_check_date": datetime.now().strftime("%Y-%m-%d"),
        }

        # Contracts summary (for the summary card)
        total_open_amount = sum(c["total_amount"] for c in open_contracts)
        total_open_balance = sum(c["balance"] for c in open_contracts)
        total_open_past_due = sum(c["past_due"] for c in open_contracts)
        total_monthly = sum(c["monthly_payment"] for c in open_contracts)

        contracts_summary = {
            "open_count": len(open_contracts),
            "closed_count": len(closed_contracts),
            "total_amount": round(total_open_amount, 2),
            "total_balance": round(total_open_balance, 2),
            "total_past_due": round(total_open_past_due, 2),
            "total_monthly_payments": round(total_monthly, 2),
        }

        # Insights
        insights = []
        if num_open > 0:
            insights.append(f"{num_open} active contract{'s' if num_open > 1 else ''}")
        if delinquent_accounts == 0:
            insights.append("No current delinquencies")
        else:
            insights.append(f"{delinquent_accounts} delinquent account{'s' if delinquent_accounts > 1 else ''}")
        if not public_records:
            insights.append("No court judgments or public records")
        else:
            insights.append(f"{len(public_records)} public record{'s' if len(public_records) > 1 else ''} found")
        if num_inquiries <= 2:
            insights.append(f"Low inquiry activity ({num_inquiries} in last 12 months)")
        else:
            insights.append(f"{num_inquiries} inquiries in last 12 months (elevated)")
        insights.append(f"Payment history: {round(payment_history * 100, 1)}% on-time")
        insights.append(f"Credit history length: {history_years} years")

        # Risk level (legacy compat)
        risk_level = {
            "Very Low Risk": "Low",
            "Low Risk": "Low",
            "Average Risk": "Medium",
            "High Risk": "High",
            "Very High Risk": "Very High",
        }.get(risk_description, "Medium")

        summary = {
            "score": score,
            "risk_level": risk_level,
            "risk_grade": risk_grade,
            "risk_description": risk_description,
            "probability_of_default": probability_of_default,
            "scenario": scenario_name,
            "total_debt": total_debt,
            "total_monthly_obligations": round(total_monthly, 2),
            "active_accounts": num_open,
            "delinquent_accounts": delinquent_accounts,
            "payment_history_rating": (
                "Excellent" if payment_history >= 0.9
                else "Good" if payment_history >= 0.75
                else "Fair" if payment_history >= 0.6
                else "Poor"
            ),
            "credit_utilization": round(rng.uniform(0.1, 0.85) * 100, 1),
            "oldest_account_years": history_years,
        }

        # Legacy tradelines (for decision engine backward compat)
        tradelines_legacy = []
        total_monthly_obligations = 0
        for c in open_contracts:
            total_monthly_obligations += c["monthly_payment"]
            tradelines_legacy.append({
                "id": len(tradelines_legacy) + 1,
                "lender": c["creditor"],
                "type": c["type"],
                "account_number": f"***{rng.randint(1000, 9999)}",
                "opened_date": c["opened_date"],
                "original_amount": c["total_amount"],
                "credit_limit": round(c["total_amount"] * 1.1, 2) if "Credit" in c["type"] else None,
                "current_balance": c["balance"],
                "monthly_payment": c["monthly_payment"],
                "status": "delinquent" if c["status"] == "Delinquent" else "current",
                "days_past_due": c["arrears_days"],
                "last_payment_date": c["last_updated"],
                "currency": "TTD",
            })

        # Legacy inquiries
        inquiries_legacy = [
            {"lender": inq.get("sector", "Unknown"), "date": inq["date"], "purpose": inq["reason"], "type": "hard"}
            for inq in inquiries_detail
        ]

        return {
            # Core scoring
            "score": score,
            "risk_grade": risk_grade,
            "risk_description": risk_description,
            "probability_of_default": probability_of_default,
            "scenario": scenario_name,
            "risk_level": risk_level,

            # Subject info
            "subject_info": subject_info,

            # EveryData-style sections
            "open_contracts": open_contracts,
            "closed_contracts": closed_contracts,
            "contracts_summary": contracts_summary,
            "score_history": score_history,
            "inquiry_counts": inquiry_counts,
            "inquiries_detail": inquiries_detail,
            "payment_calendar": payment_calendar,
            "payments_profile": payments_profile,
            "collaterals": collaterals,
            "disputes": disputes,

            # Legacy fields (backward compat with decision engine)
            "summary": summary,
            "payment_history_score": payment_history,
            "total_outstanding_debt": total_debt,
            "num_inquiries": num_inquiries,
            "credit_history_years": history_years,
            "tradelines": tradelines_legacy,
            "inquiries": inquiries_legacy,
            "public_records": public_records,
            "delinquency_summary": delinquency_summary,
            "payment_history_detail": payment_history_detail,
            "avk_data": avk_data,
            "insights": insights,

            # Metadata
            "report_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reference_number": f"{hashlib.md5(national_id.encode()).hexdigest()[:4].upper()}-{hashlib.md5(national_id.encode()).hexdigest()[4:8].upper()}-{hashlib.md5(national_id.encode()).hexdigest()[8:12].upper()}-{hashlib.md5(national_id.encode()).hexdigest()[12:16].upper()}",
            "national_id_last4": national_id[-4:] if len(national_id) >= 4 else national_id,
            "currency": "TTD",
        }

    async def check_health(self) -> bool:
        return True
