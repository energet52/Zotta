"""Report history model for tracking generated reports."""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReportHistory(Base):
    __tablename__ = "report_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    report_name: Mapped[str] = mapped_column(String(200), nullable=False)
    generated_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # base64 encoded
    file_format: Mapped[str] = mapped_column(String(10), default="csv")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user = relationship("User")
