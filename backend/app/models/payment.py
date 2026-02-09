"""Payment and PaymentSchedule models."""

import enum
from datetime import datetime, date
from sqlalchemy import (
    String, Numeric, Integer, Enum, DateTime, Date, ForeignKey, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PaymentType(str, enum.Enum):
    MANUAL = "manual"
    ONLINE = "online"
    BANK_TRANSFER = "bank_transfer"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


class ScheduleStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    DUE = "due"
    PAID = "paid"
    OVERDUE = "overdue"
    PARTIAL = "partial"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    loan_application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType), nullable=False
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.COMPLETED, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    loan_application = relationship("LoanApplication", backref="payments")


class PaymentSchedule(Base):
    __tablename__ = "payment_schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    loan_application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=False, index=True
    )
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    principal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    interest: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    amount_due: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    amount_paid: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0, nullable=False
    )
    status: Mapped[ScheduleStatus] = mapped_column(
        Enum(ScheduleStatus), default=ScheduleStatus.UPCOMING, nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    loan_application = relationship("LoanApplication", backref="payment_schedules")
