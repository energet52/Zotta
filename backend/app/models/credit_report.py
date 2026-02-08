"""Credit report model for storing bureau pull results."""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CreditReport(Base):
    __tablename__ = "credit_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    loan_application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    national_id: Mapped[str] = mapped_column(String(20), nullable=False)

    # Bureau data
    bureau_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tradelines: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    inquiries: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    public_records: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    pulled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    loan_application = relationship("LoanApplication", back_populates="credit_reports")
