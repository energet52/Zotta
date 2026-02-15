"""Credit Scoring Module — SQLAlchemy models.

Scorecard, Characteristic, Bin, ScoreResult, ChampionChallengerConfig.
"""

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Float, Numeric, Boolean,
    Enum, DateTime, Date, ForeignKey, Text, JSON,
    func, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ──────────────────────────────────────────────────────────

class ScorecardStatus(str, enum.Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    SHADOW = "shadow"
    CHALLENGER = "challenger"
    CHAMPION = "champion"
    RETIRED = "retired"


class BinType(str, enum.Enum):
    RANGE = "range"       # numeric range: min_value <= x < max_value
    CATEGORY = "category" # categorical: exact match on category_value
    DEFAULT = "default"   # catch-all / missing


class ScorecardChangeStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


# ── Scorecard ──────────────────────────────────────────────────────

class Scorecard(Base):
    __tablename__ = "scorecards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Target
    target_products: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["personal", "auto"]
    target_markets: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Status & lifecycle
    status: Mapped[ScorecardStatus] = mapped_column(
        Enum(ScorecardStatus), default=ScorecardStatus.DRAFT, nullable=False
    )

    # Score config
    base_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    min_score: Mapped[float] = mapped_column(Float, nullable=False, default=100)
    max_score: Mapped[float] = mapped_column(Float, nullable=False, default=850)

    # Cutoffs
    auto_approve_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_review_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    auto_decline_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Product-specific cutoffs (JSON: {"product_name": {"approve": X, "review": Y, "decline": Z}})
    product_cutoffs: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Champion-Challenger
    traffic_pct: Mapped[float] = mapped_column(Float, default=0)  # 0-100
    is_decisioning: Mapped[bool] = mapped_column(Boolean, default=False)
    shadow_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    challenger_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    champion_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    cloned_from_id: Mapped[int | None] = mapped_column(ForeignKey("scorecards.id"), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    characteristics: Mapped[list["ScorecardCharacteristic"]] = relationship(
        back_populates="scorecard", cascade="all, delete-orphan",
        order_by="ScorecardCharacteristic.sort_order",
    )
    score_results: Mapped[list["ScoreResult"]] = relationship(back_populates="scorecard")

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_scorecard_name_version"),
    )


# ── Characteristic ─────────────────────────────────────────────────

class ScorecardCharacteristic(Base):
    __tablename__ = "scorecard_characteristics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scorecard_id: Mapped[int] = mapped_column(ForeignKey("scorecards.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)        # "C01", "C02", ...
    name: Mapped[str] = mapped_column(String(200), nullable=False)       # "Age", "Occupation"
    data_field: Mapped[str] = mapped_column(String(100), nullable=False) # applicant profile field name
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    weight_multiplier: Mapped[float] = mapped_column(Float, default=1.0) # for weight scaling
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    scorecard: Mapped["Scorecard"] = relationship(back_populates="characteristics")
    bins: Mapped[list["ScorecardBin"]] = relationship(
        back_populates="characteristic", cascade="all, delete-orphan",
        order_by="ScorecardBin.sort_order",
    )


# ── Bin ────────────────────────────────────────────────────────────

class ScorecardBin(Base):
    __tablename__ = "scorecard_bins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    characteristic_id: Mapped[int] = mapped_column(
        ForeignKey("scorecard_characteristics.id", ondelete="CASCADE"), nullable=False
    )
    bin_type: Mapped[BinType] = mapped_column(Enum(BinType), nullable=False)

    # For RANGE bins
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)  # inclusive
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)  # exclusive (or None = unbounded)

    # For CATEGORY bins
    category_value: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Label for display
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    points: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    characteristic: Mapped["ScorecardCharacteristic"] = relationship(back_populates="bins")


# ── Score Result (per application per scorecard) ───────────────────

class ScoreResult(Base):
    __tablename__ = "score_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    loan_application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), nullable=False)
    scorecard_id: Mapped[int] = mapped_column(ForeignKey("scorecards.id"), nullable=False)
    scorecard_name: Mapped[str] = mapped_column(String(200), nullable=False)
    scorecard_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Score data
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    base_score_used: Mapped[float] = mapped_column(Float, nullable=False)

    # Per-characteristic breakdown: [{"code": "C01", "name": "Age", "value": "35", "bin_label": "35-44", "points": -8, "weighted_points": -8}]
    characteristic_scores: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Decision
    decision: Mapped[str | None] = mapped_column(String(30), nullable=True)  # AUTO_APPROVE, MANUAL_REVIEW, AUTO_DECLINE
    reason_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)   # ["RC01", "RC05"]

    # Was this the model that made the actual decision?
    is_decisioning: Mapped[bool] = mapped_column(Boolean, default=False)
    # Which champion-challenger role at time of scoring
    model_role: Mapped[str | None] = mapped_column(String(20), nullable=True)  # champion, challenger, shadow

    # Top factors
    top_positive_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    top_negative_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Percentile
    score_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)

    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    scorecard: Mapped["Scorecard"] = relationship(back_populates="score_results")

    __table_args__ = (
        Index("ix_score_results_app_scorecard", "loan_application_id", "scorecard_id"),
        Index("ix_score_results_scored_at", "scored_at"),
    )


# ── Scorecard Change Log (audit trail for edits) ──────────────────

class ScorecardChangeLog(Base):
    __tablename__ = "scorecard_change_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scorecard_id: Mapped[int] = mapped_column(ForeignKey("scorecards.id"), nullable=False)

    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g. "edit_points", "edit_bin", "add_characteristic", "remove_bin", "edit_cutoff", "edit_base_score"
    field_path: Mapped[str | None] = mapped_column(String(300), nullable=True)  # e.g. "C01.bin_2.points"
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    justification: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[ScorecardChangeStatus] = mapped_column(
        Enum(ScorecardChangeStatus), default=ScorecardChangeStatus.DRAFT
    )

    proposed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Scorecard Performance Snapshot (monthly metrics) ───────────────

class ScorecardPerformanceSnapshot(Base):
    __tablename__ = "scorecard_performance_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scorecard_id: Mapped[int] = mapped_column(ForeignKey("scorecards.id"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Counts
    total_scored: Mapped[int] = mapped_column(Integer, default=0)
    total_approved: Mapped[int] = mapped_column(Integer, default=0)
    total_declined: Mapped[int] = mapped_column(Integer, default=0)
    total_review: Mapped[int] = mapped_column(Integer, default=0)

    # Rates
    approval_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    default_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Model metrics
    gini_coefficient: Mapped[float | None] = mapped_column(Float, nullable=True)
    ks_statistic: Mapped[float | None] = mapped_column(Float, nullable=True)
    auc_roc: Mapped[float | None] = mapped_column(Float, nullable=True)
    psi: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Average scores
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_score_defaulters: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_score_non_defaulters: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Score distribution (histogram bins): [{"band": "100-200", "count": 50}, ...]
    score_distribution: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Characteristic-level metrics: [{"code": "C01", "iv": 0.35, "csi": 0.02}, ...]
    characteristic_metrics: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Score band analysis: [{"band": "500-549", "count": 200, "approved": 90, "default_rate": 0.078}, ...]
    score_band_analysis: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("scorecard_id", "snapshot_date", name="uq_perf_snapshot_scorecard_date"),
    )


# ── Scorecard Alert ────────────────────────────────────────────────

class ScorecardAlert(Base):
    __tablename__ = "scorecard_alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scorecard_id: Mapped[int] = mapped_column(ForeignKey("scorecards.id"), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # psi_breach, gini_decline, iv_degradation, approval_drift, default_spike, cutoff_misalignment, challenger_outperformance
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")  # warning, critical
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostic_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
