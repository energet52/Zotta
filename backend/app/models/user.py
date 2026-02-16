"""User model for applicants and staff."""

import enum
from datetime import datetime

from sqlalchemy import String, Boolean, Enum, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    """Legacy enum kept for backward compatibility during migration."""
    APPLICANT = "applicant"
    JUNIOR_UNDERWRITER = "junior_underwriter"
    SENIOR_UNDERWRITER = "senior_underwriter"
    ADMIN = "admin"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    LOCKED = "locked"
    DEACTIVATED = "deactivated"
    PENDING_ACTIVATION = "pending_activation"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Legacy role column — kept for backward compatibility
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.APPLICANT, nullable=False,
    )

    # Extended profile fields
    employee_id: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    reporting_manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    timezone: Mapped[str] = mapped_column(String(50), default="America/Port_of_Spain", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    profile_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Status & security
    status: Mapped[str] = mapped_column(
        String(30), default=UserStatus.ACTIVE.value, nullable=False, index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # MFA
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    loan_applications = relationship(
        "LoanApplication", back_populates="applicant",
        foreign_keys="[LoanApplication.applicant_id]",
    )
    applicant_profile = relationship("ApplicantProfile", back_populates="user", uselist=False)
    reporting_manager = relationship("User", remote_side="User.id", foreign_keys=[reporting_manager_id])
    role_assignments = relationship(
        "UserRoleAssignment", back_populates="user",
        foreign_keys="[UserRoleAssignment.user_id]",
    )
    mfa_devices = relationship("MFADevice", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    login_attempts = relationship("LoginAttempt", back_populates="user")

    # ── Helpers ──────────────────────────────────────────

    @property
    def full_name(self) -> str:
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return " ".join(parts)

    @property
    def effective_display_name(self) -> str:
        return self.display_name or f"{self.first_name} {self.last_name}"

    def is_status_active(self) -> bool:
        return self.status == UserStatus.ACTIVE.value and self.is_active
