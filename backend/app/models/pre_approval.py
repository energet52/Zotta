"""Pre-approval models for quick eligibility checks."""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, Date, ForeignKey, Integer, JSON, Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PreApprovalOutcome(str, enum.Enum):
    PRE_APPROVED = "pre_approved"
    CONDITIONALLY_APPROVED = "conditionally_approved"
    REFERRED = "referred"
    DECLINED = "declined"


class PreApprovalStatus(str, enum.Enum):
    PENDING = "pending"  # Created but not yet decided
    ACTIVE = "active"  # Decision made, still valid
    EXPIRED = "expired"  # Past expiry date
    CONVERTED = "converted"  # Linked to a full application
    PURGED = "purged"  # Data purged per retention policy


class PreApproval(Base):
    __tablename__ = "pre_approvals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reference_code: Mapped[str] = mapped_column(
        String(12), unique=True, index=True, nullable=False
    )

    # Consumer identity
    phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    national_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # Item & merchant
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id"), nullable=True, index=True
    )
    merchant_name_manual: Mapped[str | None] = mapped_column(String(200), nullable=True)
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id"), nullable=True
    )
    item_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    goods_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(5), nullable=False, default="TTD")
    downpayment: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )

    # Financial info
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    income_frequency: Mapped[str] = mapped_column(
        String(20), nullable=False, default="monthly"
    )
    employment_status: Mapped[str] = mapped_column(String(50), nullable=False)
    employment_tenure: Mapped[str | None] = mapped_column(String(30), nullable=True)
    employer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    monthly_expenses: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    existing_loan_payments: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )

    # Computed / result
    financing_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_monthly_payment: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    estimated_tenure_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    credit_product_id: Mapped[int | None] = mapped_column(
        ForeignKey("credit_products.id"), nullable=True
    )

    # Decision
    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True)
    outcome_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dti_ratio: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    ndi_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    bureau_data_cached: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    decision_strategy_version: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    # Consent
    consent_given_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_soft_inquiry: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    consent_data_processing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    otp_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Photo
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    photo_extraction_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    linked_application_id: Mapped[int | None] = mapped_column(
        ForeignKey("loan_applications.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    merchant = relationship("Merchant", foreign_keys=[merchant_id], lazy="selectin")
    branch = relationship("Branch", foreign_keys=[branch_id], lazy="selectin")
    credit_product = relationship(
        "CreditProduct", foreign_keys=[credit_product_id], lazy="selectin"
    )
    linked_application = relationship(
        "LoanApplication", foreign_keys=[linked_application_id], lazy="selectin"
    )


class PreApprovalOTP(Base):
    __tablename__ = "pre_approval_otps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
