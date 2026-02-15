"""Extended collection models — cases, PTP, settlements, compliance, SLAs, snapshots."""

import enum
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Enum, DateTime, Date, ForeignKey, Text,
    Float, Numeric, Boolean, JSON, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ───────────────────────────────────────────────────

class CaseStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    SETTLED = "settled"
    CLOSED = "closed"
    LEGAL = "legal"
    WRITTEN_OFF = "written_off"


class DelinquencyStage(str, enum.Enum):
    EARLY_1_30 = "early_1_30"
    MID_31_60 = "mid_31_60"
    LATE_61_90 = "late_61_90"
    SEVERE_90_PLUS = "severe_90_plus"
    DEFAULT = "default"
    WRITE_OFF = "write_off"


class PTPStatus(str, enum.Enum):
    PENDING = "pending"
    KEPT = "kept"
    BROKEN = "broken"
    PARTIALLY_KEPT = "partially_kept"
    CANCELLED = "cancelled"


class SettlementOfferType(str, enum.Enum):
    FULL_PAYMENT = "full_payment"
    SHORT_PLAN = "short_plan"
    LONG_PLAN = "long_plan"
    PARTIAL_SETTLEMENT = "partial_settlement"
    COMBINATION = "combination"


class SettlementOfferStatus(str, enum.Enum):
    DRAFT = "draft"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    APPROVED = "approved"
    NEEDS_APPROVAL = "needs_approval"


# Backward-compat alias used by __init__.py
SettlementStatus = SettlementOfferStatus


# ── Helper ──────────────────────────────────────────────────

def dpd_to_stage(dpd: int) -> DelinquencyStage:
    """Convert days-past-due to a delinquency stage bucket."""
    if dpd <= 30:
        return DelinquencyStage.EARLY_1_30
    if dpd <= 60:
        return DelinquencyStage.MID_31_60
    if dpd <= 90:
        return DelinquencyStage.LATE_61_90
    return DelinquencyStage.SEVERE_90_PLUS


# ── Models ──────────────────────────────────────────────────

class CollectionCase(Base):
    """Wraps a delinquent loan with case-level metadata for collections."""
    __tablename__ = "collection_cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    loan_application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=False, unique=True, index=True,
    )
    assigned_agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True,
    )
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus), default=CaseStatus.OPEN, nullable=False,
    )
    delinquency_stage: Mapped[DelinquencyStage] = mapped_column(
        Enum(DelinquencyStage), default=DelinquencyStage.EARLY_1_30, nullable=False,
    )
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    dpd: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_overdue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=0, nullable=False,
    )

    # Flags
    dispute_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vulnerability_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hardship_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # AI next-best-action
    next_best_action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nba_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    nba_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Contact tracking
    first_contact_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_contact_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # SLA deadlines
    sla_first_contact_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    sla_next_contact_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    jurisdiction: Mapped[str | None] = mapped_column(String(5), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    loan_application = relationship("LoanApplication", backref="collection_case")
    assigned_agent = relationship("User", foreign_keys=[assigned_agent_id])
    promises = relationship("PromiseToPay", back_populates="collection_case", order_by="PromiseToPay.created_at.desc()")
    settlements = relationship("SettlementOffer", back_populates="collection_case", order_by="SettlementOffer.created_at.desc()")


class PromiseToPay(Base):
    """Tracks borrower promises with fulfilment status."""
    __tablename__ = "promises_to_pay"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    collection_case_id: Mapped[int] = mapped_column(
        ForeignKey("collection_cases.id"), nullable=False, index=True,
    )
    loan_application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=False, index=True,
    )
    agent_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    amount_promised: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    promise_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[PTPStatus] = mapped_column(
        Enum(PTPStatus), default=PTPStatus.PENDING, nullable=False,
    )
    amount_received: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=0, nullable=False,
    )
    reminded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    broken_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    collection_case = relationship("CollectionCase", back_populates="promises")
    agent = relationship("User")


class SettlementOffer(Base):
    """Tracks settlement/restructuring offers and their lifecycle."""
    __tablename__ = "settlement_offers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    collection_case_id: Mapped[int] = mapped_column(
        ForeignKey("collection_cases.id"), nullable=False, index=True,
    )
    loan_application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=False, index=True,
    )

    offer_type: Mapped[SettlementOfferType] = mapped_column(
        Enum(SettlementOfferType), nullable=False,
    )
    original_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    settlement_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    plan_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plan_monthly_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True,
    )
    lump_sum: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    status: Mapped[SettlementOfferStatus] = mapped_column(
        Enum(SettlementOfferStatus), default=SettlementOfferStatus.DRAFT, nullable=False,
    )
    offered_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    collection_case = relationship("CollectionCase", back_populates="settlements")
    offered_by_user = relationship("User", foreign_keys=[offered_by])
    approved_by_user = relationship("User", foreign_keys=[approved_by])


class ComplianceRule(Base):
    """Contact rules per jurisdiction (hours, frequency caps, cooling-off)."""
    __tablename__ = "compliance_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    jurisdiction: Mapped[str] = mapped_column(String(5), nullable=False, unique=True)
    contact_start_hour: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    contact_end_hour: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_contacts_per_day: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_contacts_per_week: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    cooling_off_hours: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class SLAConfig(Base):
    """Configurable SLA timers per delinquency stage."""
    __tablename__ = "sla_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    delinquency_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    hours_allowed: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_action: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CollectionsDashboardSnapshot(Base):
    """Daily aggregate of collections portfolio metrics for trend analysis."""
    __tablename__ = "collections_dashboard_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    total_delinquent_accounts: Mapped[int] = mapped_column(Integer, default=0)
    total_overdue_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False,
    )
    by_stage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    by_outcome: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cure_rate: Mapped[float] = mapped_column(Float, default=0.0)
    ptp_rate: Mapped[float] = mapped_column(Float, default=0.0)
    ptp_kept_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_days_to_collect: Mapped[float] = mapped_column(Float, default=0.0)
    total_recovered_mtd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
