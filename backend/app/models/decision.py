"""Decision engine output and rules configuration models."""

import enum
from datetime import datetime
from sqlalchemy import String, Integer, Numeric, Enum, DateTime, ForeignKey, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DecisionOutcome(str, enum.Enum):
    AUTO_APPROVE = "auto_approve"
    AUTO_DECLINE = "auto_decline"
    MANUAL_REVIEW = "manual_review"


class UnderwriterAction(str, enum.Enum):
    APPROVE = "approve"
    DECLINE = "decline"
    REFER = "refer"
    REQUEST_INFO = "request_info"


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    loan_application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=False
    )

    # Engine output
    credit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_band: Mapped[str | None] = mapped_column(String(5), nullable=True)
    engine_outcome: Mapped[DecisionOutcome | None] = mapped_column(
        Enum(DecisionOutcome), nullable=True
    )
    engine_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scoring_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rules_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Suggested terms
    suggested_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    suggested_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Underwriter override
    underwriter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    underwriter_action: Mapped[UnderwriterAction | None] = mapped_column(
        Enum(UnderwriterAction), nullable=True
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Rules version used
    rules_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    loan_application = relationship("LoanApplication", back_populates="decisions")


class DecisionRulesConfig(Base):
    __tablename__ = "decision_rules_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rules: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
