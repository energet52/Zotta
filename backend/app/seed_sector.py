"""Seed sector analysis data — policies, snapshots, alerts, alert rules."""

import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sector_analysis import (
    SectorSnapshot,
    SectorPolicy,
    SectorPolicyStatus,
    SectorRiskRating,
    SectorAlertRule,
    SectorAlertSeverity,
    SectorAlert,
    SectorAlertStatus,
)
from app.models.user import User, UserRole


EMPLOYER_SECTORS = [
    "Banking & Financial Services", "Insurance", "Hospitality & Tourism",
    "Agriculture & Agro-processing", "Oil & Gas / Energy", "Mining & Extractives",
    "Telecommunications", "Retail & Distribution", "Real Estate & Construction",
    "Manufacturing", "Transportation & Logistics", "Healthcare & Pharmaceuticals",
    "Education", "Government & Public Sector", "Utilities (Water & Electricity)",
]


async def seed_sector_data(db: AsyncSession) -> None:
    """Seed sector analysis data if not already present."""
    # Check if snapshots already seeded
    snap_count = (await db.execute(select(func.count()).select_from(SectorSnapshot))).scalar() or 0

    # Find admin user
    admin = (await db.execute(
        select(User).where(User.role == UserRole.ADMIN).limit(1)
    )).scalar_one_or_none()
    if not admin:
        return

    today = date.today()

    # ── Historical snapshots (12 months) ──
    if snap_count == 0:
        print("  Generating sector analysis snapshots...")
        for month_offset in range(12, 0, -1):
            snap_date = (today - timedelta(days=30 * month_offset)).replace(day=1)
            growth = 1.0 - (month_offset * 0.04)

            for sec in EMPLOYER_SECTORS:
                n = max(1, int(random.randint(5, 30) * growth))
                outstanding = round(random.uniform(50000, 500000) * growth, 2)
                disbursed = round(outstanding * 1.1, 2)
                exposure = round(random.uniform(2, 15), 2)
                default_rate_val = round(random.uniform(0, 8), 2)
                dpd_30 = max(0, int(n * random.uniform(0.02, 0.10)))
                dpd_60 = max(0, int(n * random.uniform(0.01, 0.05)))
                dpd_90 = max(0, int(n * random.uniform(0.00, 0.03)))

                snap = SectorSnapshot(
                    snapshot_date=snap_date,
                    sector=sec,
                    loan_count=n,
                    total_outstanding=Decimal(str(outstanding)),
                    total_disbursed=Decimal(str(disbursed)),
                    exposure_pct=exposure,
                    default_rate=default_rate_val,
                    npl_ratio=round(default_rate_val * 0.8, 2),
                    delinquency_rate=round(random.uniform(1, 12), 2),
                    dpd_30_count=dpd_30,
                    dpd_60_count=dpd_60,
                    dpd_90_count=dpd_90,
                )
                db.add(snap)

    # ── Policies ──
    existing_policies = (await db.execute(
        select(func.count()).select_from(SectorPolicy)
    )).scalar() or 0
    if existing_policies == 0:
        high_risk_sectors = ["Oil & Gas / Energy", "Hospitality & Tourism"]
        for sec in high_risk_sectors:
            pol = SectorPolicy(
                sector=sec,
                exposure_cap_pct=round(random.uniform(12, 20), 1),
                origination_paused=False,
                risk_rating=SectorRiskRating.HIGH,
                on_watchlist=True,
                watchlist_review_frequency="monthly",
                max_loan_amount_override=round(random.randint(50, 150) * 1000),
                min_credit_score_override=650,
                status=SectorPolicyStatus.ACTIVE,
                created_by=admin.id,
                approved_by=admin.id,
                justification=f"High-risk sector — elevated monitoring required for {sec}",
            )
            db.add(pol)

        # Paused sector
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

    # ── Alert rules ──
    existing_rules = (await db.execute(
        select(func.count()).select_from(SectorAlertRule)
    )).scalar() or 0
    if existing_rules == 0:
        rules_data = [
            ("High NPL Ratio", None, "npl_ratio", ">", 5.0, "critical",
             "Review sector policy and consider tightening criteria"),
            ("Exposure Concentration", None, "exposure_pct", ">", 20.0, "warning",
             "Monitor sector exposure — consider setting caps"),
            ("Rising Delinquency", None, "delinquency_rate", ">", 10.0, "warning",
             "Investigate root cause of delinquency increase"),
            ("Tourism Stress", "Hospitality & Tourism", "delinquency_rate", ">", 8.0, "critical",
             "Tourism sector under pressure — review all new applications"),
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

    # ── Sample alerts ──
    existing_alerts = (await db.execute(
        select(func.count()).select_from(SectorAlert)
    )).scalar() or 0
    if existing_alerts == 0:
        sample_alerts = [
            ("Hospitality & Tourism", "critical", "NPL Ratio Exceeded 5%",
             "npl_ratio", 6.2, 5.0, "Tighten origination criteria for hospitality"),
            ("Oil & Gas / Energy", "warning", "Exposure approaching cap",
             "exposure_pct", 18.5, 20.0, "Monitor closely — near concentration limit"),
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

    await db.commit()
    print("  Sector analysis data seeded.")
