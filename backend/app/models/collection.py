"""Collection models for managing overdue loan recovery."""

import enum
from datetime import datetime, date
from sqlalchemy import (
    String, Integer, Enum, DateTime, Date, ForeignKey, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CollectionChannel(str, enum.Enum):
    PHONE = "phone"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    IN_PERSON = "in_person"
    SMS = "sms"


class CollectionOutcome(str, enum.Enum):
    PROMISE_TO_PAY = "promise_to_pay"
    NO_ANSWER = "no_answer"
    DISPUTED = "disputed"
    PAYMENT_ARRANGED = "payment_arranged"
    ESCALATED = "escalated"
    OTHER = "other"


class ChatDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ChatMessageStatus(str, enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class CollectionRecord(Base):
    __tablename__ = "collection_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    loan_application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=False, index=True
    )
    collection_case_id: Mapped[int | None] = mapped_column(
        ForeignKey("collection_cases.id"), nullable=True, index=True
    )
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    channel: Mapped[CollectionChannel] = mapped_column(
        Enum(CollectionChannel), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[CollectionOutcome] = mapped_column(
        Enum(CollectionOutcome), nullable=False
    )
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    promise_amount: Mapped[float | None] = mapped_column(nullable=True)
    promise_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    loan_application = relationship("LoanApplication", backref="collection_records")
    agent = relationship("User")


class CollectionChat(Base):
    __tablename__ = "collection_chats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    loan_application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=False, index=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    direction: Mapped[ChatDirection] = mapped_column(
        Enum(ChatDirection), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    status: Mapped[ChatMessageStatus] = mapped_column(
        Enum(ChatMessageStatus), default=ChatMessageStatus.SENT, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    loan_application = relationship("LoanApplication", backref="collection_chats")
    agent = relationship("User")
