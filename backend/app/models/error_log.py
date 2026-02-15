"""Error log model — persists application errors for admin monitoring."""

import enum
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, Enum, Float, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ErrorSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorLog(Base):
    """Application error captured by middleware or explicit logging."""
    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # What happened
    severity: Mapped[ErrorSeverity] = mapped_column(
        Enum(ErrorSeverity), default=ErrorSeverity.ERROR, nullable=False,
    )
    error_type: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Where it happened
    module: Mapped[str | None] = mapped_column(String(300), nullable=True)
    function_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # HTTP context (populated by middleware for API errors)
    request_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    request_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Who triggered it
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Resolution tracking
    resolved: Mapped[bool] = mapped_column(default=False, nullable=False)
    resolved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
