"""Application Queue Management models.

Provides: QueueConfig (feature toggles), QueueEntry (per-app queue state),
QueueStage (opt-in pipeline stages), StaffQueueProfile (skills/authority),
QueueEvent (audit trail), QueueException (formal exceptions).
"""

import enum
from datetime import datetime, time

from sqlalchemy import (
    String, Integer, Float, Numeric, Boolean, Enum, DateTime, Time,
    ForeignKey, Text, JSON, func, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ────────────────────────────────────────────────────

class AssignmentMode(str, enum.Enum):
    PULL = "pull"
    AUTO = "auto"
    HYBRID = "hybrid"
    MANAGER = "manager"


class SLAMode(str, enum.Enum):
    NONE = "none"
    SOFT = "soft"
    ACTIVE = "active"


class QueueEntryStatus(str, enum.Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_BORROWER = "waiting_borrower"
    ON_HOLD = "on_hold"
    DECIDED = "decided"
    EXPIRED = "expired"


class ExceptionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    EXPIRED = "expired"


# ── QueueConfig (singleton) ─────────────────────────────────

class QueueConfig(Base):
    __tablename__ = "queue_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Assignment
    assignment_mode: Mapped[str] = mapped_column(
        String(20), default=AssignmentMode.PULL.value, nullable=False,
    )

    # Feature toggles
    stages_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sla_mode: Mapped[str] = mapped_column(
        String(10), default=SLAMode.NONE.value, nullable=False,
    )
    authority_limits_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    skills_routing_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    exceptions_formal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    segregation_of_duties: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Turnaround
    target_turnaround_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Business hours
    business_hours_start: Mapped[time] = mapped_column(
        Time, default=time(8, 0), nullable=False,
    )
    business_hours_end: Mapped[time] = mapped_column(
        Time, default=time(17, 0), nullable=False,
    )
    business_days: Mapped[dict | None] = mapped_column(
        JSON, default=[1, 2, 3, 4, 5], nullable=False,
    )
    holidays: Mapped[dict | None] = mapped_column(JSON, default=[], nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(50), default="America/Port_of_Spain", nullable=False,
    )

    # Auto-expire
    auto_expire_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    follow_up_days: Mapped[dict | None] = mapped_column(
        JSON, default=[1, 3, 7], nullable=False,
    )

    # AI weights and advanced config
    ai_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )


# ── QueueStage ───────────────────────────────────────────────

class QueueStage(Base):
    __tablename__ = "queue_stages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    assignment_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    allowed_roles: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    skip_conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    can_parallel_with: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    sla_target_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sla_warning_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    entries = relationship("QueueEntry", back_populates="queue_stage")


# ── QueueEntry ───────────────────────────────────────────────

class QueueEntry(Base):
    __tablename__ = "queue_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"), unique=True, nullable=False, index=True,
    )

    # Priority
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    priority_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default=QueueEntryStatus.NEW.value, nullable=False, index=True,
    )

    # Stage (opt-in)
    queue_stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("queue_stages.id"), nullable=True,
    )

    # Assignment
    assigned_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True,
    )
    suggested_for_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )

    # Borrower wait
    waiting_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    waiting_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # SLA
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_warning_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_elapsed_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Tracking
    stage_entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_stuck: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    flag_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # AI
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    completeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    complexity_estimate_hours: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Metadata
    channel: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    application = relationship("LoanApplication", foreign_keys=[application_id])
    queue_stage = relationship("QueueStage", back_populates="entries", foreign_keys=[queue_stage_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    suggested_for = relationship("User", foreign_keys=[suggested_for_id])
    claimed_by = relationship("User", foreign_keys=[claimed_by_id])
    events = relationship(
        "QueueEvent", back_populates="queue_entry",
        cascade="all, delete-orphan", order_by="QueueEvent.created_at",
    )
    exceptions = relationship(
        "QueueException", back_populates="queue_entry",
        cascade="all, delete-orphan",
    )


# ── StaffQueueProfile ────────────────────────────────────────

class StaffQueueProfile(Base):
    __tablename__ = "staff_queue_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False, index=True,
    )

    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_concurrent: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Skills
    skills: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Authority limits
    authority_max_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    authority_risk_grades: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    authority_products: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Shift
    shift_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    shift_end: Mapped[time | None] = mapped_column(Time, nullable=True)

    # Performance
    current_load_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_processing_hours: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    user = relationship("User", foreign_keys=[user_id])


# ── QueueEvent ───────────────────────────────────────────────

class QueueEvent(Base):
    __tablename__ = "queue_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    queue_entry_id: Mapped[int] = mapped_column(
        ForeignKey("queue_entries.id"), nullable=False, index=True,
    )
    application_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    from_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    to_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    queue_entry = relationship("QueueEntry", back_populates="events")
    actor = relationship("User", foreign_keys=[actor_id])


# ── QueueException ───────────────────────────────────────────

class QueueException(Base):
    __tablename__ = "queue_exceptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    queue_entry_id: Mapped[int] = mapped_column(
        ForeignKey("queue_entries.id"), nullable=False, index=True,
    )
    application_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    exception_type: Mapped[str] = mapped_column(String(40), nullable=False)
    raised_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_approver_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20), default=ExceptionStatus.PENDING.value, nullable=False,
    )
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    approver_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_precedent: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    queue_entry = relationship("QueueEntry", back_populates="exceptions")
    raised_by = relationship("User", foreign_keys=[raised_by_id])
    assigned_approver = relationship("User", foreign_keys=[assigned_approver_id])
