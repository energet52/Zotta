"""Mock credit bureau adapter for development and testing.

Generates realistic synthetic Trinidad credit data with configurable scenarios.
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
    },
    "fair": {
        "score_range": (600, 719),
        "payment_history": (0.65, 0.84),
        "debt_range": (20000, 80000),
        "history_years": (2, 7),
        "inquiries": (2, 5),
        "tradelines_count": (2, 6),
        "delinquent_chance": 0.2,
    },
    "poor": {
        "score_range": (400, 599),
        "payment_history": (0.3, 0.64),
        "debt_range": (50000, 200000),
        "history_years": (1, 4),
        "inquiries": (4, 10),
        "tradelines_count": (1, 5),
        "delinquent_chance": 0.5,
    },
    "thin": {
        "score_range": (500, 650),
        "payment_history": (0.7, 0.9),
        "debt_range": (0, 5000),
        "history_years": (0, 1),
        "inquiries": (0, 1),
        "tradelines_count": (0, 1),
        "delinquent_chance": 0.0,
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
        for _ in range(num_tradelines):
            opened = datetime.now() - timedelta(days=rng.randint(90, int(history_years * 365 + 180)))
            original_amount = round(rng.uniform(5000, 200000), 2)
            balance = round(original_amount * rng.uniform(0.1, 0.9), 2)
            is_delinquent = rng.random() < scenario["delinquent_chance"]

            tradelines.append({
                "lender": rng.choice(TRINIDAD_LENDERS),
                "type": rng.choice(TRADELINE_TYPES),
                "opened_date": opened.strftime("%Y-%m-%d"),
                "original_amount": original_amount,
                "current_balance": balance,
                "monthly_payment": round(original_amount / rng.randint(12, 60), 2),
                "status": "delinquent" if is_delinquent else "current",
                "days_past_due": rng.randint(30, 180) if is_delinquent else 0,
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
            })

        # Public records
        public_records = []
        if scenario_name == "poor" and rng.random() < 0.3:
            public_records.append({
                "type": rng.choice(["Judgment", "Bankruptcy", "Tax Lien"]),
                "date": (datetime.now() - timedelta(days=rng.randint(180, 1800))).strftime("%Y-%m-%d"),
                "amount": round(rng.uniform(10000, 100000), 2),
                "status": rng.choice(["active", "satisfied"]),
            })

        return {
            "score": score,
            "scenario": scenario_name,
            "payment_history_score": payment_history,
            "total_outstanding_debt": total_debt,
            "num_inquiries": num_inquiries,
            "credit_history_years": history_years,
            "tradelines": tradelines,
            "inquiries": inquiries,
            "public_records": public_records,
            "report_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "national_id_last4": national_id[-4:] if len(national_id) >= 4 else national_id,
            "currency": "TTD",
        }

    async def check_health(self) -> bool:
        return True
