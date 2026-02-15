"""Conversation and message models for Customer Support chat."""

import enum
from datetime import datetime
from sqlalchemy import (
    String, Integer, Enum, DateTime, ForeignKey, Text, func, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ConversationChannel(str, enum.Enum):
    WEB = "web"
    WHATSAPP = "whatsapp"
    SMS = "sms"


class ConversationEntryPoint(str, enum.Enum):
    COLD_START = "cold_start"
    PRE_QUALIFIED = "pre_qualified"
    RETURNING_APPLICANT = "returning_applicant"
    EXISTING_CUSTOMER = "existing_customer"
    SERVICING = "servicing"


class ConversationState(str, enum.Enum):
    INITIATED = "initiated"
    DISCOVERY = "discovery"
    APPLICATION_IN_PROGRESS = "application_in_progress"
    DOCUMENTS_PENDING = "documents_pending"
    VERIFICATION_IN_PROGRESS = "verification_in_progress"
    CREDIT_CHECK_CONSENT = "credit_check_consent"
    CREDIT_CHECK_IN_PROGRESS = "credit_check_in_progress"
    DECISION_RENDERED = "decision_rendered"
    OFFER_PRESENTED = "offer_presented"
    OFFER_ACCEPTED = "offer_accepted"
    DISBURSEMENT_PROCESSING = "disbursement_processing"
    DISBURSED = "disbursed"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    ESCALATED_TO_HUMAN = "escalated_to_human"
    SERVICING = "servicing"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    AGENT = "agent"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel: Mapped[ConversationChannel] = mapped_column(
        Enum(ConversationChannel), default=ConversationChannel.WEB, nullable=False
    )
    participant_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    participant_phone: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)

    current_state: Mapped[ConversationState] = mapped_column(
        Enum(ConversationState), default=ConversationState.INITIATED, nullable=False
    )
    loan_application_id: Mapped[int | None] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=True, index=True
    )
    entry_point: Mapped[ConversationEntryPoint | None] = mapped_column(
        Enum(ConversationEntryPoint), nullable=True
    )
    entry_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    assigned_agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages = relationship(
        "ConversationMessage",
        back_populates="conversation",
        order_by="ConversationMessage.created_at",
    )
    participant_user = relationship("User", foreign_keys=[participant_user_id])
    assigned_agent = relationship("User", foreign_keys=[assigned_agent_id])
    loan_application = relationship(
        "LoanApplication",
        foreign_keys=[loan_application_id],
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation = relationship("Conversation", back_populates="messages")
