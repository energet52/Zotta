"""Occupation-based income and expense benchmarks for Trinidad and Tobago.

These benchmarks are used by the decision engine to flag suspicious income
inflation or understated expenses relative to stated occupation.
All values are in TTD (Trinidad & Tobago Dollars) per month.
"""

from typing import Optional


OCCUPATION_BENCHMARKS: dict[str, dict[str, float]] = {
    # Education
    "teacher": {
        "income_min": 5000, "income_max": 12000,
        "expense_min": 3000, "expense_max": 7000,
    },
    "professor": {
        "income_min": 10000, "income_max": 22000,
        "expense_min": 5000, "expense_max": 12000,
    },
    "lecturer": {
        "income_min": 8000, "income_max": 18000,
        "expense_min": 4000, "expense_max": 10000,
    },

    # Healthcare
    "nurse": {
        "income_min": 5000, "income_max": 15000,
        "expense_min": 3000, "expense_max": 8000,
    },
    "doctor": {
        "income_min": 15000, "income_max": 45000,
        "expense_min": 6000, "expense_max": 18000,
    },
    "pharmacist": {
        "income_min": 8000, "income_max": 20000,
        "expense_min": 4000, "expense_max": 10000,
    },

    # Engineering & Technical
    "engineer": {
        "income_min": 8000, "income_max": 25000,
        "expense_min": 4000, "expense_max": 10000,
    },
    "technician": {
        "income_min": 4000, "income_max": 12000,
        "expense_min": 3000, "expense_max": 7000,
    },
    "it professional": {
        "income_min": 7000, "income_max": 22000,
        "expense_min": 3500, "expense_max": 10000,
    },
    "software developer": {
        "income_min": 8000, "income_max": 25000,
        "expense_min": 3500, "expense_max": 10000,
    },

    # Business & Finance
    "accountant": {
        "income_min": 6000, "income_max": 20000,
        "expense_min": 3500, "expense_max": 9000,
    },
    "banker": {
        "income_min": 6000, "income_max": 22000,
        "expense_min": 3500, "expense_max": 10000,
    },
    "manager": {
        "income_min": 8000, "income_max": 30000,
        "expense_min": 4000, "expense_max": 12000,
    },
    "business owner": {
        "income_min": 5000, "income_max": 60000,
        "expense_min": 4000, "expense_max": 20000,
    },

    # Law & Government
    "lawyer": {
        "income_min": 10000, "income_max": 40000,
        "expense_min": 5000, "expense_max": 15000,
    },
    "civil servant": {
        "income_min": 4000, "income_max": 15000,
        "expense_min": 3000, "expense_max": 8000,
    },
    "police officer": {
        "income_min": 5000, "income_max": 12000,
        "expense_min": 3000, "expense_max": 7000,
    },

    # Trades & Services
    "mechanic": {
        "income_min": 3500, "income_max": 10000,
        "expense_min": 2500, "expense_max": 6000,
    },
    "electrician": {
        "income_min": 4000, "income_max": 12000,
        "expense_min": 2500, "expense_max": 7000,
    },
    "plumber": {
        "income_min": 3500, "income_max": 10000,
        "expense_min": 2500, "expense_max": 6000,
    },
    "driver": {
        "income_min": 3000, "income_max": 8000,
        "expense_min": 2500, "expense_max": 5000,
    },
    "security guard": {
        "income_min": 3000, "income_max": 6000,
        "expense_min": 2500, "expense_max": 4500,
    },
    "chef": {
        "income_min": 4000, "income_max": 12000,
        "expense_min": 3000, "expense_max": 7000,
    },

    # Retail & Sales
    "sales representative": {
        "income_min": 3500, "income_max": 12000,
        "expense_min": 2500, "expense_max": 6000,
    },
    "cashier": {
        "income_min": 2800, "income_max": 5000,
        "expense_min": 2000, "expense_max": 4000,
    },
    "clerk": {
        "income_min": 3000, "income_max": 7000,
        "expense_min": 2500, "expense_max": 5000,
    },

    # Agriculture & Energy
    "farmer": {
        "income_min": 2500, "income_max": 12000,
        "expense_min": 2000, "expense_max": 6000,
    },
    "oil and gas worker": {
        "income_min": 8000, "income_max": 30000,
        "expense_min": 4000, "expense_max": 12000,
    },
}

# Fallback benchmark when occupation is not found
DEFAULT_BENCHMARK = {
    "income_min": 3000,
    "income_max": 20000,
    "expense_min": 2500,
    "expense_max": 10000,
}

# Thresholds for flagging
INCOME_INFLATION_THRESHOLD = 1.5     # 150% of benchmark max
EXPENSE_DEFLATION_THRESHOLD = 0.5    # 50% of benchmark min


def find_benchmark(job_title: Optional[str]) -> tuple[dict[str, float], bool]:
    """Find the benchmark data for a given job title.

    Returns (benchmark_dict, exact_match_found).
    Uses fuzzy matching by lowercasing and checking substring containment.
    """
    if not job_title:
        return DEFAULT_BENCHMARK, False

    title_lower = job_title.strip().lower()

    # Exact match first
    if title_lower in OCCUPATION_BENCHMARKS:
        return OCCUPATION_BENCHMARKS[title_lower], True

    # Substring match
    for occ, bench in OCCUPATION_BENCHMARKS.items():
        if occ in title_lower or title_lower in occ:
            return bench, True

    return DEFAULT_BENCHMARK, False


def check_income_benchmark(
    monthly_income: float,
    job_title: Optional[str],
) -> dict:
    """Check if stated income is suspicious relative to occupation benchmark.

    Returns a dict with:
      - flagged: bool
      - benchmark: the benchmark data
      - match_found: whether we found a benchmark for this occupation
      - ratio: income / benchmark_max
      - message: human-readable explanation
    """
    benchmark, match_found = find_benchmark(job_title)
    benchmark_max = benchmark["income_max"]
    ratio = monthly_income / benchmark_max if benchmark_max > 0 else 0

    flagged = ratio > INCOME_INFLATION_THRESHOLD

    if flagged:
        message = (
            f"Stated income TTD {monthly_income:,.0f} is {ratio:.1f}x the benchmark max "
            f"TTD {benchmark_max:,.0f} for '{job_title or 'unknown'}'. "
            f"Benchmark range: TTD {benchmark['income_min']:,.0f} - TTD {benchmark_max:,.0f}"
        )
    else:
        message = (
            f"Income TTD {monthly_income:,.0f} is within expected range for '{job_title or 'unknown'}'. "
            f"Benchmark: TTD {benchmark['income_min']:,.0f} - TTD {benchmark_max:,.0f}"
        )

    return {
        "flagged": flagged,
        "benchmark": benchmark,
        "match_found": match_found,
        "ratio": round(ratio, 2),
        "message": message,
    }


def check_expense_benchmark(
    monthly_expenses: float,
    job_title: Optional[str],
) -> dict:
    """Check if stated expenses are suspiciously low relative to occupation benchmark.

    Returns a dict with:
      - flagged: bool
      - benchmark: the benchmark data
      - match_found: whether we found a benchmark for this occupation
      - ratio: expenses / benchmark_min
      - message: human-readable explanation
    """
    benchmark, match_found = find_benchmark(job_title)
    benchmark_min = benchmark["expense_min"]
    ratio = monthly_expenses / benchmark_min if benchmark_min > 0 else 0

    flagged = ratio < EXPENSE_DEFLATION_THRESHOLD

    if flagged:
        message = (
            f"Stated expenses TTD {monthly_expenses:,.0f} is only {ratio:.1f}x the benchmark min "
            f"TTD {benchmark_min:,.0f} for '{job_title or 'unknown'}'. "
            f"Benchmark range: TTD {benchmark_min:,.0f} - TTD {benchmark['expense_max']:,.0f}"
        )
    else:
        message = (
            f"Expenses TTD {monthly_expenses:,.0f} is within expected range for '{job_title or 'unknown'}'. "
            f"Benchmark: TTD {benchmark_min:,.0f} - TTD {benchmark['expense_max']:,.0f}"
        )

    return {
        "flagged": flagged,
        "benchmark": benchmark,
        "match_found": match_found,
        "ratio": round(ratio, 2),
        "message": message,
    }
