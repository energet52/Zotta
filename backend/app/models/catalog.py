"""Catalog models for hire-purchase administration."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    branches = relationship("Branch", back_populates="merchant", cascade="all, delete-orphan")
    categories = relationship("ProductCategory", back_populates="merchant", cascade="all, delete-orphan")
    credit_products = relationship("CreditProduct", back_populates="merchant")
    loan_applications = relationship("LoanApplication", back_populates="merchant")


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("merchant_id", "name", name="uq_branch_name_per_merchant"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    merchant = relationship("Merchant", back_populates="branches")
    loan_applications = relationship("LoanApplication", back_populates="branch")


class ProductCategory(Base):
    __tablename__ = "product_categories"
    __table_args__ = (UniqueConstraint("merchant_id", "name", name="uq_category_name_per_merchant"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    merchant = relationship("Merchant", back_populates="categories")
    application_items = relationship("ApplicationItem", back_populates="category")


class CreditProduct(Base):
    __tablename__ = "credit_products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), nullable=True, index=True)
    min_term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    max_term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    min_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    max_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    repayment_scheme: Mapped[str] = mapped_column(String(200), nullable=False, default="Monthly Equal Installment")
    grace_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Risk-based pricing tiers
    interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    # Eligibility criteria (JSON)
    eligibility_criteria: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Product lifecycle: draft | active | sunset | retired
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    # Version tracking
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    # Channel restrictions (JSON list, e.g. ["online","in-store","whatsapp"])
    channels: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Target customer segments (JSON list)
    target_segments: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Internal notes/tags
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Regulatory product code
    regulatory_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # AI-generated summary (cached)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Decision Strategy Management (nullable — null means legacy single-strategy mode)
    decision_tree_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_trees.id"), nullable=True,
    )
    default_strategy_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_strategies.id"), nullable=True,
    )

    merchant = relationship("Merchant", back_populates="credit_products")
    score_ranges = relationship("ProductScoreRange", back_populates="credit_product", cascade="all, delete-orphan")
    fees = relationship("ProductFee", back_populates="credit_product", cascade="all, delete-orphan")
    rate_tiers = relationship("ProductRateTier", back_populates="credit_product", cascade="all, delete-orphan")
    loan_applications = relationship("LoanApplication", back_populates="credit_product")
    decision_tree = relationship("DecisionTree", foreign_keys=[decision_tree_id])
    default_strategy = relationship("DecisionStrategy", foreign_keys=[default_strategy_id])


class ProductScoreRange(Base):
    __tablename__ = "product_score_ranges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    credit_product_id: Mapped[int] = mapped_column(ForeignKey("credit_products.id"), nullable=False, index=True)
    min_score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    credit_product = relationship("CreditProduct", back_populates="score_ranges")


class ProductFee(Base):
    __tablename__ = "product_fees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    credit_product_id: Mapped[int] = mapped_column(ForeignKey("credit_products.id"), nullable=False, index=True)
    fee_type: Mapped[str] = mapped_column(String(60), nullable=False)
    fee_base: Mapped[str] = mapped_column(String(60), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    credit_product = relationship("CreditProduct", back_populates="fees")


class ProductRateTier(Base):
    """Risk-based interest rate tiers within a product."""
    __tablename__ = "product_rate_tiers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    credit_product_id: Mapped[int] = mapped_column(ForeignKey("credit_products.id"), nullable=False, index=True)
    tier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    min_score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    max_ltv_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_dti_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    credit_product = relationship("CreditProduct", back_populates="rate_tiers")
