"""Collection sequence models -- multi-step automated notification workflows."""

import enum
from datetime import datetime, time as dt_time
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Enum, DateTime, Time, Date, ForeignKey, Text,
    Float, Numeric, Boolean, JSON, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ────────────────────────────────────────────────────

class SequenceStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    GRADUATED = "graduated"


class StepActionType(str, enum.Enum):
    SEND_MESSAGE = "send_message"
    CREATE_TASK = "create_task"
    ESCALATE = "escalate"
    CREATE_PTP_REQUEST = "create_ptp_request"
    SETTLEMENT_OFFER = "settlement_offer"


class StepChannel(str, enum.Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"
    PHONE = "phone"


class TemplateTone(str, enum.Enum):
    FRIENDLY = "friendly"
    FIRM = "firm"
    URGENT = "urgent"
    FINAL = "final"


class TemplateCategory(str, enum.Enum):
    REMINDER = "reminder"
    DEMAND = "demand"
    FOLLOW_UP = "follow_up"
    PROMISE_REMINDER = "promise_reminder"
    BROKEN_PROMISE = "broken_promise"
    PAYMENT_LINK = "payment_link"
    SETTLEMENT_OFFER = "settlement_offer"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


# ── Models ───────────────────────────────────────────────────

class CollectionSequence(Base):
    """A named multi-step collection notification strategy."""
    __tablename__ = "collection_sequences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    delinquency_stage: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    channels: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    steps = relationship(
        "SequenceStep", back_populates="sequence",
        cascade="all, delete-orphan", order_by="SequenceStep.step_number",
    )
    enrollments = relationship(
        "SequenceEnrollment", back_populates="sequence",
        cascade="all, delete-orphan",
    )


class SequenceStep(Base):
    """A single step inside a collection sequence."""
    __tablename__ = "sequence_steps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sequence_id: Mapped[int] = mapped_column(
        ForeignKey("collection_sequences.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    day_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="whatsapp")
    action_type: Mapped[str] = mapped_column(String(30), nullable=False, default="send_message")

    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("message_templates.id"), nullable=True,
    )
    custom_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    condition_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    send_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    wait_for_response_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_effectiveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    sequence = relationship("CollectionSequence", back_populates="steps")
    template = relationship("MessageTemplate", foreign_keys=[template_id])
    executions = relationship("StepExecution", back_populates="step")


class MessageTemplate(Base):
    """Reusable message template with variable placeholders."""
    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="whatsapp")
    tone: Mapped[str] = mapped_column(String(20), nullable=False, default="friendly")
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="reminder")

    body: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    variables: Mapped[list | None] = mapped_column(JSON, nullable=True)

    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class SequenceEnrollment(Base):
    """Tracks a collection case's progression through a sequence."""
    __tablename__ = "sequence_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("collection_cases.id"), nullable=False, index=True,
    )
    sequence_id: Mapped[int] = mapped_column(
        ForeignKey("collection_sequences.id"), nullable=False, index=True,
    )

    current_step_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    paused_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sequence = relationship("CollectionSequence", back_populates="enrollments")
    collection_case = relationship("CollectionCase", backref="sequence_enrollments")
    step_executions = relationship(
        "StepExecution", back_populates="enrollment",
        cascade="all, delete-orphan", order_by="StepExecution.executed_at",
    )


class StepExecution(Base):
    """Records when a step was executed for an enrollment."""
    __tablename__ = "step_executions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("sequence_enrollments.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    step_id: Mapped[int] = mapped_column(
        ForeignKey("sequence_steps.id"), nullable=False, index=True,
    )

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    message_sent: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(20), default="sent", nullable=False)

    borrower_responded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_after: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    enrollment = relationship("SequenceEnrollment", back_populates="step_executions")
    step = relationship("SequenceStep", back_populates="executions")
