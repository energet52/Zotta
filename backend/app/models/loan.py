"""Loan application and applicant profile models."""

import enum
from datetime import datetime, date
from sqlalchemy import (
    String, Numeric, Integer, Enum, DateTime, Date, ForeignKey, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LoanStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    AWAITING_DOCUMENTS = "awaiting_documents"
    CREDIT_CHECK = "credit_check"
    DECISION_PENDING = "decision_pending"
    APPROVED = "approved"
    DECLINED = "declined"
    OFFER_SENT = "offer_sent"
    ACCEPTED = "accepted"
    REJECTED_BY_APPLICANT = "rejected_by_applicant"
    DISBURSED = "disbursed"
    CANCELLED = "cancelled"


class LoanPurpose(str, enum.Enum):
    DEBT_CONSOLIDATION = "debt_consolidation"
    HOME_IMPROVEMENT = "home_improvement"
    MEDICAL = "medical"
    EDUCATION = "education"
    VEHICLE = "vehicle"
    PERSONAL = "personal"
    BUSINESS = "business"
    OTHER = "other"


class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reference_number: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Loan details
    amount_requested: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[LoanPurpose] = mapped_column(Enum(LoanPurpose), nullable=False)
    purpose_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Interest & offer
    interest_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    amount_approved: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    monthly_payment: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Status
    status: Mapped[LoanStatus] = mapped_column(
        Enum(LoanStatus), default=LoanStatus.DRAFT, nullable=False
    )
    assigned_underwriter_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Timestamps
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    applicant = relationship("User", back_populates="loan_applications", foreign_keys=[applicant_id])
    documents = relationship("Document", back_populates="loan_application")
    decisions = relationship("Decision", back_populates="loan_application")
    credit_reports = relationship("CreditReport", back_populates="loan_application")


class ApplicantProfile(Base):
    __tablename__ = "applicant_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)

    # Personal
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    national_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    marital_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Address
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parish: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(50), default="Trinidad and Tobago")

    # Employment
    employer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    years_employed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_income: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    other_income: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Financial
    monthly_expenses: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    existing_debt: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    dependents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Verification
    id_verified: Mapped[bool | None] = mapped_column(default=False)
    id_verification_status: Mapped[str | None] = mapped_column(String(20), default="pending")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="applicant_profile")
