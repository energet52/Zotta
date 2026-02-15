"""Models for the Sectorial Analysis module.

Tracks sector policies, alerts, snapshots, and macro indicators
for portfolio concentration risk management.
"""

import enum
from datetime import datetime, date
from sqlalchemy import (
    String, Numeric, Integer, Enum, DateTime, Date,
    ForeignKey, Text, Boolean, Float, JSON, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ────────────────────────────────────────────────────

class SectorPolicyStatus(str, enum.Enum):
    ACTIVE = "active"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class SectorAlertSeverity(str, enum.Enum):
    INFORMATIONAL = "informational"
    WARNING = "warning"
    CRITICAL = "critical"


class SectorAlertStatus(str, enum.Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    ACTION_TAKEN = "action_taken"
    DISMISSED = "dismissed"


class SectorRiskRating(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"


# ── Standardized sector list ─────────────────────────────────

SECTOR_TAXONOMY = [
    "Banking & Financial Services",
    "Hospitality & Tourism",
    "Agriculture & Agro-processing",
    "Oil, Gas & Energy",
    "Mining & Extractives",
    "Telecommunications",
    "Retail & Distribution",
    "Real Estate & Construction",
    "Manufacturing",
    "Transportation & Logistics",
    "Healthcare & Pharmaceuticals",
    "Education",
    "Government & Public Sector",
    "Utilities (Water & Electricity)",
    "Creative Industries & Entertainment",
    "Maritime & Shipping",
    "Professional Services",
    "Information Technology",
    "Insurance",
    "Microfinance & Credit Unions",
    "Other",
    "Not Applicable",
    "MISSING",
]


# ── Sector Policy ────────────────────────────────────────────

class SectorPolicy(Base):
    """Configurable policy for a specific sector (caps, pauses, criteria)."""
    __tablename__ = "sector_policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sector: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Exposure cap
    exposure_cap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    exposure_cap_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    # Origination pause
    origination_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    pause_effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pause_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Criteria overlays (tighten underwriting for this sector)
    max_loan_amount_override: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    min_credit_score_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_term_months_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    require_collateral: Mapped[bool] = mapped_column(Boolean, default=False)
    require_guarantor: Mapped[bool] = mapped_column(Boolean, default=False)

    # Risk rating
    risk_rating: Mapped[SectorRiskRating] = mapped_column(
        Enum(SectorRiskRating), default=SectorRiskRating.MEDIUM,
    )

    # Watchlist
    on_watchlist: Mapped[bool] = mapped_column(Boolean, default=False)
    watchlist_review_frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Maker-checker
    status: Mapped[SectorPolicyStatus] = mapped_column(
        Enum(SectorPolicyStatus), default=SectorPolicyStatus.ACTIVE,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Sector Alert Rule ────────────────────────────────────────

class SectorAlertRule(Base):
    """Threshold-based rule that triggers alerts for a sector."""
    __tablename__ = "sector_alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)  # NULL = all sectors

    # Rule definition
    metric: Mapped[str] = mapped_column(String(50), nullable=False)  # npl_ratio, delinquency_rate, exposure_pct, etc.
    operator: Mapped[str] = mapped_column(String(10), nullable=False)  # >, <, >=, <=, ==
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    consecutive_months: Mapped[int] = mapped_column(Integer, default=1)

    severity: Mapped[SectorAlertSeverity] = mapped_column(
        Enum(SectorAlertSeverity), default=SectorAlertSeverity.WARNING,
    )
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Sector Alert ─────────────────────────────────────────────

class SectorAlert(Base):
    """Fired alert for a sector threshold breach."""
    __tablename__ = "sector_alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("sector_alert_rules.id"), nullable=True)
    sector: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    severity: Mapped[SectorAlertSeverity] = mapped_column(Enum(SectorAlertSeverity), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[SectorAlertStatus] = mapped_column(
        Enum(SectorAlertStatus), default=SectorAlertStatus.NEW,
    )
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    action_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Sector Snapshot (monthly) ────────────────────────────────

class SectorSnapshot(Base):
    """Monthly portfolio snapshot per sector for time-series analysis."""
    __tablename__ = "sector_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sector: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Portfolio metrics
    loan_count: Mapped[int] = mapped_column(Integer, default=0)
    total_outstanding: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_disbursed: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    avg_loan_size: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    exposure_pct: Mapped[float] = mapped_column(Float, default=0)

    # Delinquency buckets
    current_count: Mapped[int] = mapped_column(Integer, default=0)
    dpd_30_count: Mapped[int] = mapped_column(Integer, default=0)
    dpd_60_count: Mapped[int] = mapped_column(Integer, default=0)
    dpd_90_count: Mapped[int] = mapped_column(Integer, default=0)
    dpd_30_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    dpd_60_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    dpd_90_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    # Rates
    delinquency_rate: Mapped[float] = mapped_column(Float, default=0)
    npl_ratio: Mapped[float] = mapped_column(Float, default=0)
    default_rate: Mapped[float] = mapped_column(Float, default=0)
    write_off_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    # Risk
    risk_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    avg_credit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Sector Macro Indicator ───────────────────────────────────

class SectorMacroIndicator(Base):
    """Manual macroeconomic data points linked to a sector."""
    __tablename__ = "sector_macro_indicators"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sector: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    indicator_name: Mapped[str] = mapped_column(String(200), nullable=False)
    indicator_value: Mapped[float] = mapped_column(Float, nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
