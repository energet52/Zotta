"""General Ledger models.

Implements a full double-entry bookkeeping system with:
- Multi-currency support (JMD, USD, TTD, BBD)
- Hierarchical Chart of Accounts (5 levels)
- Immutable journal entries with maker-checker workflow
- Accounting period management
- GL mapping templates for automated loan-lifecycle entries
- Accrual batch tracking
- Anomaly tracking for AI-powered auditing
- Named filter presets and export schedules
"""

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    String,
    Numeric,
    Integer,
    Boolean,
    Enum,
    DateTime,
    Date,
    ForeignKey,
    Text,
    JSON,
    Index,
    CheckConstraint,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ===================================================================
# Enumerations
# ===================================================================


class AccountCategory(str, enum.Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class AccountType(str, enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class PeriodStatus(str, enum.Enum):
    OPEN = "open"
    SOFT_CLOSE = "soft_close"
    CLOSED = "closed"
    LOCKED = "locked"


class JournalEntryStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    POSTED = "posted"
    REVERSED = "reversed"
    REJECTED = "rejected"


class JournalSourceType(str, enum.Enum):
    MANUAL = "manual"
    LOAN_DISBURSEMENT = "loan_disbursement"
    REPAYMENT = "repayment"
    INTEREST_ACCRUAL = "interest_accrual"
    FEE = "fee"
    PROVISION = "provision"
    WRITE_OFF = "write_off"
    RECOVERY = "recovery"
    REVERSAL = "reversal"
    ADJUSTMENT = "adjustment"
    SYSTEM = "system"


class AccrualBatchType(str, enum.Enum):
    INTEREST_ACCRUAL = "interest_accrual"
    PROVISION = "provision"
    FEE = "fee"


class AccrualBatchStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MappingLineType(str, enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class MappingAmountSource(str, enum.Enum):
    PRINCIPAL = "principal"
    INTEREST = "interest"
    FEE = "fee"
    FULL_AMOUNT = "full_amount"
    CUSTOM = "custom"


class AnomalyType(str, enum.Enum):
    AMOUNT = "amount"
    PATTERN = "pattern"
    SEQUENCE = "sequence"
    BALANCE = "balance"
    VELOCITY = "velocity"


class AnomalyStatus(str, enum.Enum):
    OPEN = "open"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


# ===================================================================
# Phase 1 — Foundation Models
# ===================================================================


class Currency(Base):
    """Supported currencies with ISO 4217 codes."""

    __tablename__ = "gl_currencies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    decimal_places: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    is_base: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    accounts = relationship("GLAccount", back_populates="currency")


class GLAccount(Base):
    """Chart of Accounts — hierarchical, multi-level account structure."""

    __tablename__ = "gl_accounts"
    __table_args__ = (
        Index("ix_gl_accounts_code", "account_code"),
        Index("ix_gl_accounts_category", "account_category"),
        Index("ix_gl_accounts_parent", "parent_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_code: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    account_category: Mapped[AccountCategory] = mapped_column(
        Enum(AccountCategory), nullable=False
    )
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType), nullable=False
    )
    currency_id: Mapped[int] = mapped_column(
        ForeignKey("gl_currencies.id"), nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("gl_accounts.id"), nullable=True
    )
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    is_control_account: Mapped[bool] = mapped_column(Boolean, default=False)
    is_system_account: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False
    )

    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    currency = relationship("Currency", back_populates="accounts")
    parent = relationship("GLAccount", remote_side="GLAccount.id", backref="children")
    journal_lines = relationship("JournalEntryLine", back_populates="gl_account")
    audit_trail = relationship(
        "GLAccountAudit", back_populates="account", order_by="GLAccountAudit.changed_at.desc()"
    )


class GLAccountAudit(Base):
    """Append-only audit trail for Chart of Accounts modifications."""

    __tablename__ = "gl_account_audit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    gl_account_id: Mapped[int] = mapped_column(
        ForeignKey("gl_accounts.id"), nullable=False, index=True
    )
    field_changed: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    account = relationship("GLAccount", back_populates="audit_trail")


class AccountingPeriod(Base):
    """Fiscal year accounting periods (typically monthly)."""

    __tablename__ = "gl_accounting_periods"
    __table_args__ = (
        UniqueConstraint("fiscal_year", "period_number", name="uq_fiscal_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PeriodStatus] = mapped_column(
        Enum(PeriodStatus), default=PeriodStatus.OPEN, nullable=False
    )

    closed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    journal_entries = relationship("JournalEntry", back_populates="accounting_period")


class JournalEntry(Base):
    """Immutable double-entry journal entry header.

    Once posted, entries cannot be modified — corrections are made via
    reversing entries only.
    """

    __tablename__ = "gl_journal_entries"
    __table_args__ = (
        Index("ix_gl_je_entry_number", "entry_number"),
        Index("ix_gl_je_transaction_date", "transaction_date"),
        Index("ix_gl_je_source", "source_type", "source_reference"),
        Index("ix_gl_je_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    posting_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    accounting_period_id: Mapped[int | None] = mapped_column(
        ForeignKey("gl_accounting_periods.id"), nullable=True
    )
    source_type: Mapped[JournalSourceType] = mapped_column(
        Enum(JournalSourceType), nullable=False
    )
    source_reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    currency_id: Mapped[int] = mapped_column(
        ForeignKey("gl_currencies.id"), nullable=False
    )
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("1.000000"), nullable=False
    )

    status: Mapped[JournalEntryStatus] = mapped_column(
        Enum(JournalEntryStatus), default=JournalEntryStatus.DRAFT, nullable=False
    )

    # User tracking
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    posted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Reversal linkage
    reversal_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("gl_journal_entries.id"), nullable=True
    )
    reversed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("gl_journal_entries.id"), nullable=True
    )

    # AI / metadata
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Rejection reason
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    accounting_period = relationship("AccountingPeriod", back_populates="journal_entries")
    currency = relationship("Currency")
    lines = relationship(
        "JournalEntryLine",
        back_populates="journal_entry",
        cascade="all, delete-orphan",
        order_by="JournalEntryLine.line_number",
    )
    reversal_of = relationship(
        "JournalEntry",
        foreign_keys=[reversal_of_id],
        remote_side="JournalEntry.id",
        uselist=False,
    )
    reversed_by = relationship(
        "JournalEntry",
        foreign_keys=[reversed_by_id],
        remote_side="JournalEntry.id",
        uselist=False,
    )
    anomalies = relationship("GLAnomaly", back_populates="journal_entry")

    @property
    def total_debits(self) -> Decimal:
        return sum((ln.debit_amount or Decimal("0")) for ln in self.lines)

    @property
    def total_credits(self) -> Decimal:
        return sum((ln.credit_amount or Decimal("0")) for ln in self.lines)

    @property
    def is_balanced(self) -> bool:
        return self.total_debits == self.total_credits


class JournalEntryLine(Base):
    """Individual debit or credit line within a journal entry."""

    __tablename__ = "gl_journal_entry_lines"
    __table_args__ = (
        CheckConstraint(
            "(debit_amount = 0 AND credit_amount > 0) OR "
            "(debit_amount > 0 AND credit_amount = 0) OR "
            "(debit_amount = 0 AND credit_amount = 0)",
            name="ck_je_line_debit_or_credit",
        ),
        Index("ix_gl_jel_account", "gl_account_id"),
        Index("ix_gl_jel_entry", "journal_entry_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    journal_entry_id: Mapped[int] = mapped_column(
        ForeignKey("gl_journal_entries.id", ondelete="CASCADE"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    gl_account_id: Mapped[int] = mapped_column(
        ForeignKey("gl_accounts.id"), nullable=False
    )

    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    base_currency_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    loan_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="lines")
    gl_account = relationship("GLAccount", back_populates="journal_lines")


# ===================================================================
# Phase 2 — Automation Models
# ===================================================================


class GLMappingTemplate(Base):
    """Configurable mapping from loan lifecycle events to GL journal entries."""

    __tablename__ = "gl_mapping_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[JournalSourceType] = mapped_column(
        Enum(JournalSourceType), nullable=False
    )
    credit_product_id: Mapped[int | None] = mapped_column(
        ForeignKey("credit_products.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    lines = relationship(
        "GLMappingTemplateLine",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="GLMappingTemplateLine.id",
    )


class GLMappingTemplateLine(Base):
    """Individual debit/credit line within a GL mapping template."""

    __tablename__ = "gl_mapping_template_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("gl_mapping_templates.id", ondelete="CASCADE"), nullable=False
    )
    line_type: Mapped[MappingLineType] = mapped_column(
        Enum(MappingLineType), nullable=False
    )
    gl_account_id: Mapped[int] = mapped_column(
        ForeignKey("gl_accounts.id"), nullable=False
    )
    amount_source: Mapped[MappingAmountSource] = mapped_column(
        Enum(MappingAmountSource), nullable=False
    )
    description_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    template = relationship("GLMappingTemplate", back_populates="lines")
    gl_account = relationship("GLAccount")


class AccrualBatch(Base):
    """Tracks batch processing for interest accruals, provisioning, etc."""

    __tablename__ = "gl_accrual_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_type: Mapped[AccrualBatchType] = mapped_column(
        Enum(AccrualBatchType), nullable=False
    )
    period_id: Mapped[int] = mapped_column(
        ForeignKey("gl_accounting_periods.id"), nullable=False
    )
    status: Mapped[AccrualBatchStatus] = mapped_column(
        Enum(AccrualBatchStatus), default=AccrualBatchStatus.PENDING, nullable=False
    )
    loan_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    journal_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("gl_journal_entries.id"), nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    period = relationship("AccountingPeriod")
    journal_entry = relationship("JournalEntry")


# ===================================================================
# Phase 3 — Filter Presets
# ===================================================================


class GLFilterPreset(Base):
    """Named filter presets for GL views."""

    __tablename__ = "gl_filter_presets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ===================================================================
# Phase 4 — Export Schedules
# ===================================================================


class GLExportSchedule(Base):
    """Scheduled recurring exports."""

    __tablename__ = "gl_export_schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)  # csv, xlsx, pdf, json, xml
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    columns: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schedule_cron: Mapped[str] = mapped_column(String(100), nullable=False)
    recipients: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GLExportLog(Base):
    """Audit log for every export operation."""

    __tablename__ = "gl_export_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    export_type: Mapped[str] = mapped_column(String(50), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ===================================================================
# Phase 5 — AI Anomaly Tracking
# ===================================================================


class GLAnomaly(Base):
    """AI-detected anomalies on journal entries."""

    __tablename__ = "gl_anomalies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    journal_entry_id: Mapped[int] = mapped_column(
        ForeignKey("gl_journal_entries.id"), nullable=False, index=True
    )
    anomaly_type: Mapped[AnomalyType] = mapped_column(
        Enum(AnomalyType), nullable=False
    )
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AnomalyStatus] = mapped_column(
        Enum(AnomalyStatus), default=AnomalyStatus.OPEN, nullable=False
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="anomalies")
