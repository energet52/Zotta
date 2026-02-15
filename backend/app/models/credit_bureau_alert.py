"""Credit Bureau Alert model.

Represents alerts received from a credit bureau monitoring service
about customer activity at other institutions.
"""

import enum
from datetime import datetime
from sqlalchemy import (
    String, Integer, Enum, DateTime, ForeignKey, Text, Boolean, Numeric, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AlertType(str, enum.Enum):
    NEW_INQUIRY = "new_inquiry"
    NEW_LOAN = "new_loan"
    NEW_DELINQUENCY = "new_delinquency"
    DEFAULT_ELSEWHERE = "default_elsewhere"
    COLLECTION_PAYMENT_ELSEWHERE = "collection_payment_elsewhere"


class AlertSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    ACTION_TAKEN = "action_taken"
    DISMISSED = "dismissed"


class CreditBureauAlert(Base):
    __tablename__ = "credit_bureau_alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    alert_type: Mapped[AlertType] = mapped_column(
        Enum(AlertType, values_callable=lambda e: [i.value for i in e]),
        nullable=False, index=True
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, values_callable=lambda e: [i.value for i in e]),
        nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, values_callable=lambda e: [i.value for i in e]),
        nullable=False, server_default="new"
    )

    # Bureau information
    bureau_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bureau_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Alert details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Entity at other institution
    other_institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    other_product_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    other_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    other_delinquency_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    other_delinquency_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Action taken
    action_taken: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    acted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    acted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    alert_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="credit_bureau_alerts")
    actor = relationship("User", foreign_keys=[acted_by])
