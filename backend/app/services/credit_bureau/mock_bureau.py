"""Mock credit bureau adapter for development and testing.

Generates realistic synthetic Trinidad credit data with configurable scenarios.
Enhanced with structured sections: Summary, Tradelines, Inquiries, Public Records,
Payment History, Delinquencies, and Court Judgments.
"""

import hashlib
import random
from datetime import datetime, timedelta
from typing import Dict, Any

from app.services.credit_bureau.adapter import CreditBureauAdapter


# Predefined scenarios based on national ID patterns
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


class MockBureauAdapter(CreditBureauAdapter):
    """Mock implementation that generates synthetic credit data."""

    @property
    def provider_name(self) -> str:
        return "mock_bureau"

    async def pull_credit_report(self, national_id: str) -> Dict[str, Any]:
        """Generate a synthetic credit report based on the national ID.

        The national ID is hashed to deterministically select a scenario,
        so the same ID always produces the same report.
        """
        # Deterministic scenario selection based on national ID
        hash_val = int(hashlib.md5(national_id.encode()).hexdigest(), 16)
        rng = random.Random(hash_val)

        # Pick scenario
        scenario_keys = list(SCENARIOS.keys())
        weights = [0.4, 0.3, 0.2, 0.1]  # good, fair, poor, thin
        scenario_name = rng.choices(scenario_keys, weights=weights, k=1)[0]
        scenario = SCENARIOS[scenario_name]

        # Generate credit score
        score = rng.randint(*scenario["score_range"])
        payment_history = round(rng.uniform(*scenario["payment_history"]), 3)
        total_debt = round(rng.uniform(*scenario["debt_range"]), 2)
        history_years = round(rng.uniform(*scenario["history_years"]), 1)
        num_inquiries = rng.randint(*scenario["inquiries"])
        num_tradelines = rng.randint(*scenario["tradelines_count"])

        # Generate tradelines
        tradelines = []
        total_monthly_obligations = 0
        for i in range(num_tradelines):
            opened = datetime.now() - timedelta(days=rng.randint(90, int(history_years * 365 + 180)))
            original_amount = round(rng.uniform(5000, 200000), 2)
            balance = round(original_amount * rng.uniform(0.1, 0.9), 2)
            is_delinquent = rng.random() < scenario["delinquent_chance"]
            monthly_pmt = round(original_amount / rng.randint(12, 60), 2)
            total_monthly_obligations += monthly_pmt

            tradelines.append({
                "id": i + 1,
                "lender": rng.choice(TRINIDAD_LENDERS),
                "type": rng.choice(TRADELINE_TYPES),
                "account_number": f"***{rng.randint(1000, 9999)}",
                "opened_date": opened.strftime("%Y-%m-%d"),
                "original_amount": original_amount,
                "credit_limit": round(original_amount * 1.1, 2) if "Credit" in TRADELINE_TYPES[i % len(TRADELINE_TYPES)] else None,
                "current_balance": balance,
                "monthly_payment": monthly_pmt,
                "status": "delinquent" if is_delinquent else "current",
                "days_past_due": rng.randint(30, 180) if is_delinquent else 0,
                "last_payment_date": (datetime.now() - timedelta(days=rng.randint(1, 60))).strftime("%Y-%m-%d"),
                "currency": "TTD",
            })

        # Generate inquiries
        inquiries = []
        for _ in range(num_inquiries):
            inq_date = datetime.now() - timedelta(days=rng.randint(1, 365))
            inquiries.append({
                "lender": rng.choice(TRINIDAD_LENDERS),
                "date": inq_date.strftime("%Y-%m-%d"),
                "purpose": rng.choice(["Personal Loan", "Credit Card", "Auto Loan", "Mortgage"]),
                "type": rng.choice(["hard", "soft"]),
            })

        # Public records (court judgments, bankruptcy, tax liens)
        public_records = []
        if rng.random() < scenario.get("judgment_chance", 0):
            public_records.append({
                "type": "Judgment",
                "court": rng.choice(["Port of Spain High Court", "San Fernando Magistrates Court", "Chaguanas Civil Court"]),
                "case_number": f"CV-{rng.randint(2018, 2025)}-{rng.randint(1000, 9999)}",
                "date": (datetime.now() - timedelta(days=rng.randint(180, 1800))).strftime("%Y-%m-%d"),
                "amount": round(rng.uniform(10000, 100000), 2),
                "plaintiff": rng.choice(TRINIDAD_LENDERS),
                "status": rng.choice(["active", "satisfied"]),
                "currency": "TTD",
            })
        if scenario_name == "poor" and rng.random() < 0.15:
            public_records.append({
                "type": "Tax Lien",
                "date": (datetime.now() - timedelta(days=rng.randint(90, 900))).strftime("%Y-%m-%d"),
                "amount": round(rng.uniform(5000, 50000), 2),
                "status": rng.choice(["active", "released"]),
                "currency": "TTD",
            })

        # Delinquency summary
        delinquent_accounts = sum(1 for t in tradelines if t["status"] == "delinquent")
        delinquency_summary = {
            "current_delinquent_accounts": delinquent_accounts,
            "historical_delinquencies": rng.randint(0, 3) if scenario_name != "good" else 0,
            "worst_delinquency": f"{rng.choice([30, 60, 90, 120])} days" if delinquent_accounts > 0 else "None",
            "total_past_due_amount": round(sum(t["current_balance"] * 0.1 for t in tradelines if t["status"] == "delinquent"), 2),
        }

        # Payment history summary
        payment_history_detail = {
            "on_time_percentage": round(payment_history * 100, 1),
            "total_accounts_ever": num_tradelines + rng.randint(0, 3),
            "accounts_in_good_standing": num_tradelines - delinquent_accounts,
            "accounts_delinquent": delinquent_accounts,
            "months_reviewed": min(int(history_years * 12), 84),
        }

        # AVK-specific data
        avk_data = {
            "has_outstanding_debt": rng.random() < scenario.get("avk_debt_chance", 0),
            "has_court_judgment": any(r["type"] == "Judgment" and r["status"] == "active" for r in public_records),
            "total_avk_debt": round(rng.uniform(5000, 80000), 2) if rng.random() < scenario.get("avk_debt_chance", 0) else 0,
            "last_check_date": datetime.now().strftime("%Y-%m-%d"),
        }

        # Summary / insights generation
        insights = []
        if num_tradelines > 0:
            insights.append(f"{num_tradelines} active tradeline{'s' if num_tradelines > 1 else ''}")
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

        # Risk level
        if score >= 720:
            risk_level = "Low"
        elif score >= 600:
            risk_level = "Medium"
        elif score >= 400:
            risk_level = "High"
        else:
            risk_level = "Very High"

        summary = {
            "score": score,
            "risk_level": risk_level,
            "scenario": scenario_name,
            "total_debt": total_debt,
            "total_monthly_obligations": round(total_monthly_obligations, 2),
            "active_accounts": num_tradelines,
            "delinquent_accounts": delinquent_accounts,
            "payment_history_rating": "Excellent" if payment_history >= 0.9 else "Good" if payment_history >= 0.75 else "Fair" if payment_history >= 0.6 else "Poor",
            "credit_utilization": round(rng.uniform(0.1, 0.85) * 100, 1),
            "oldest_account_years": history_years,
        }

        return {
            "score": score,
            "scenario": scenario_name,
            "risk_level": risk_level,
            "summary": summary,
            "payment_history_score": payment_history,
            "total_outstanding_debt": total_debt,
            "num_inquiries": num_inquiries,
            "credit_history_years": history_years,
            "tradelines": tradelines,
            "inquiries": inquiries,
            "public_records": public_records,
            "delinquency_summary": delinquency_summary,
            "payment_history_detail": payment_history_detail,
            "avk_data": avk_data,
            "insights": insights,
            "report_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "national_id_last4": national_id[-4:] if len(national_id) >= 4 else national_id,
            "currency": "TTD",
        }

    async def check_health(self) -> bool:
        return True
