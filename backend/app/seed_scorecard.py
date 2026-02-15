"""Seed Scorecard1.csv into the database as the initial champion scorecard."""

import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scorecard import Scorecard, ScorecardStatus
from app.services.scorecard_engine import parse_scorecard_csv, build_scorecard_from_parsed


SCORECARD_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "Scorecard1.csv")

# Fallback: inline CSV if file not found (for Docker builds)
SCORECARD1_CSV = """\
Characteristic,Attribute,Points,Notes
BASE SCORE,Starting Score,536,Base score for all applicants
,,,
C01: Age,18-34 years,-16,Younger applicants - higher risk
,35-44 years,-8,Mid-age group
,45-54 years,8,Average risk
,55+ years,24,Lowest risk age group
,,,
C02: Occupation,Professional,47,Highest stability
,Managerial,16,
,Business Owner,16,
,Civil Servant,16,
,Clerical,0,Baseline
,Supervisor,0,
,Skilled Trade,0,
,Factory Worker,0,
,Domestic/Janitor,0,
,Nurse,-24,
,Teacher,-24,
,Security,-24,
,Police/Army/Prison Officer/Fire,-31,
,Driver/Courier,-39,
,Taxi Driver,-39,
,Minibus/Maxi Driver,-39,
,Manual/Laborer,-55,Highest risk occupation
,Other,-31,Default for unknown
,,,
C03: Payment Channel,Payroll,39,Most reliable
,Cash,16,
,Bank,8,
,Other/Missing,0,Default
,,,
C04: Payment Frequency,Weekly,39,More frequent = lower risk
,Monthly,8,
,Every Two Weeks,-30,Reduced from -63 (updated)
,Other/Missing,0,Default
,,,
C05: Residence Tenure,< 3 years,-8,Less stable
,3-9 years,39,Best performance
,10+ years,8,
,Missing,0,Default
,,,
C06: Employment Tenure,< 12 months,-31,New employees - higher risk
,12-23 months,-16,Still building tenure
,24-59 months,24,Good stability
,60+ months,16,Long tenure
,Missing,0,Default
,,,
C07: Residential Status,"Home Owner, No Mortgage",8,
,"Home Owner, Mortgage",8,
,Boarding/Living with Parents,4,
,Renting,4,
,Other,0,Baseline
,,,
C09: Geographic Location,Tier 1 (Low Risk),47,"Penal/Debe, San Juan/Laventille, Arima, Chaguanas, San Fernando, Tunapuna/Piarco, Champ Fleurs/St Joseph"
,Tier 2 (Medium Risk),0,All other locations
,Tier 3 (High Risk),-31,"Siparia, Port of Spain, Gran Couva/Tabaquite/Caparo, Princes Town, Cunupia/Las Lomas/St Helena"
"""


async def seed_scorecard_data(db: AsyncSession) -> None:
    """Seed Scorecard1.csv as the initial champion scorecard if none exists."""
    # Check if any scorecard already exists
    existing = await db.execute(select(Scorecard).limit(1))
    if existing.scalar_one_or_none():
        return  # Already seeded

    # Load CSV content
    csv_content = SCORECARD1_CSV
    if os.path.exists(SCORECARD_CSV_PATH):
        try:
            with open(SCORECARD_CSV_PATH, "r", encoding="utf-8-sig") as f:
                csv_content = f.read()
        except Exception:
            pass

    # Parse CSV
    parsed = parse_scorecard_csv(csv_content)
    if parsed["errors"]:
        print(f"Warning: Scorecard CSV had parse errors: {parsed['errors']}")

    # Build scorecard
    sc = build_scorecard_from_parsed(
        parsed,
        name="Personal Loan Scorecard",
        description="Production scorecard imported from Scorecard1.csv. Trinidad & Tobago consumer lending model.",
        auto_approve=650,
        manual_review=480,
        auto_decline=480,  # Below 480 = auto decline
    )

    # Set as champion
    sc.status = ScorecardStatus.CHAMPION
    sc.traffic_pct = 100
    sc.is_decisioning = True

    db.add(sc)
    await db.flush()
    await db.commit()
    print(f"  - Seeded scorecard: {sc.name} v{sc.version} (champion, {len(sc.characteristics)} characteristics)")
