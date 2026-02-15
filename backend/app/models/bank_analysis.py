"""Bank statement AI analysis model."""

import enum
from datetime import datetime
from sqlalchemy import String, Integer, Numeric, Enum, DateTime, ForeignKey, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class BankStatementAnalysis(Base):
    __tablename__ = "bank_statement_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    loan_application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=False
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), nullable=False
    )
    analyzed_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus), default=AnalysisStatus.PENDING
    )

    # AI analysis results
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cashflow_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    flags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    volatility_score: Mapped[float | None] = mapped_column(
        Numeric(5, 1), nullable=True
    )
    monthly_stats: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risk_assessment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    loan_application = relationship("LoanApplication")
    document = relationship("Document")
