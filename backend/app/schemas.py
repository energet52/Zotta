"""Pydantic schemas for request/response validation."""

from datetime import datetime, date
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field, model_validator


# ── Auth ──────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Applicant Profile ────────────────────────────────

class ApplicantProfileCreate(BaseModel):
    date_of_birth: Optional[date] = None
    national_id: Optional[str] = None
    gender: Optional[str] = None
    marital_status: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    parish: Optional[str] = None
    employer_name: Optional[str] = None
    job_title: Optional[str] = None
    employment_type: Optional[str] = None
    years_employed: Optional[int] = None
    monthly_income: Optional[float] = None
    other_income: Optional[float] = None
    monthly_expenses: Optional[float] = None
    existing_debt: Optional[float] = None
    dependents: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def empty_strings_to_none(cls, values: dict) -> dict:  # type: ignore[override]
        """Convert empty strings to None so Optional fields don't choke."""
        if isinstance(values, dict):
            return {k: (None if v == "" else v) for k, v in values.items()}
        return values


class ApplicantProfileResponse(ApplicantProfileCreate):
    id: int
    user_id: int
    id_verified: Optional[bool]
    id_verification_status: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Loan Application ─────────────────────────────────

class LoanApplicationCreate(BaseModel):
    amount_requested: float = Field(gt=0, le=500000)
    term_months: int = Field(ge=3, le=84)
    purpose: str
    purpose_description: Optional[str] = None
    merchant_id: Optional[int] = None
    branch_id: Optional[int] = None
    credit_product_id: Optional[int] = None
    downpayment: Optional[float] = None
    total_financed: Optional[float] = None
    items: list["ApplicationItemCreate"] = []


class LoanApplicationUpdate(BaseModel):
    amount_requested: Optional[float] = None
    term_months: Optional[int] = None
    purpose: Optional[str] = None
    purpose_description: Optional[str] = None
    merchant_id: Optional[int] = None
    branch_id: Optional[int] = None
    credit_product_id: Optional[int] = None
    downpayment: Optional[float] = None
    total_financed: Optional[float] = None


class LoanApplicationResponse(BaseModel):
    id: int
    reference_number: str
    applicant_id: int
    applicant_name: Optional[str] = None  # populated by back-office endpoints
    amount_requested: float
    term_months: int
    purpose: str
    purpose_description: Optional[str]
    interest_rate: Optional[float]
    amount_approved: Optional[float]
    monthly_payment: Optional[float]
    merchant_id: Optional[int] = None
    branch_id: Optional[int] = None
    credit_product_id: Optional[int] = None
    downpayment: Optional[float] = None
    total_financed: Optional[float] = None
    status: str
    assigned_underwriter_id: Optional[int]
    # Counterproposal
    proposed_amount: Optional[float] = None
    proposed_rate: Optional[float] = None
    proposed_term: Optional[int] = None
    counterproposal_reason: Optional[str] = None
    # Contract
    contract_signed_at: Optional[datetime] = None
    contract_typed_name: Optional[str] = None
    # Timestamps
    submitted_at: Optional[datetime]
    decided_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoanSubmitResponse(BaseModel):
    id: int
    reference_number: str
    status: str
    message: str


class ApplicationItemCreate(BaseModel):
    category_id: int
    description: Optional[str] = None
    price: float = Field(gt=0)
    quantity: int = Field(ge=1, default=1)


class ApplicationItemResponse(BaseModel):
    id: int
    loan_application_id: int
    category_id: int
    category_name: Optional[str] = None
    description: Optional[str]
    price: float
    quantity: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Catalog / Admin ──────────────────────────────────

FeeTypeLiteral = Literal[
    "admin_fee_pct",
    "credit_fee_pct",
    "origination_fee_pct",
    "origination_fee_flat",
    "late_payment_fee_flat",
]
FeeBaseLiteral = Literal["purchase_amount", "financed_amount", "flat"]


class MerchantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    is_active: bool = True


class MerchantUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    is_active: Optional[bool] = None


class MerchantResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    address: Optional[str] = Field(default=None, max_length=255)
    is_online: bool = False
    is_active: bool = True


class BranchUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    address: Optional[str] = Field(default=None, max_length=255)
    is_online: Optional[bool] = None
    is_active: Optional[bool] = None


class BranchResponse(BaseModel):
    id: int
    merchant_id: int
    name: str
    address: Optional[str]
    is_online: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProductCategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProductCategoryResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductScoreRangeCreate(BaseModel):
    min_score: int = Field(ge=0, le=1000)
    max_score: int = Field(ge=0, le=1000)


class ProductScoreRangeUpdate(BaseModel):
    min_score: Optional[int] = Field(default=None, ge=0, le=1000)
    max_score: Optional[int] = Field(default=None, ge=0, le=1000)


class ProductScoreRangeResponse(BaseModel):
    id: int
    credit_product_id: int
    min_score: int
    max_score: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductFeeCreate(BaseModel):
    fee_type: FeeTypeLiteral
    fee_base: FeeBaseLiteral
    fee_amount: float = Field(ge=0)
    is_available: bool = True


class ProductFeeUpdate(BaseModel):
    fee_type: Optional[FeeTypeLiteral] = None
    fee_base: Optional[FeeBaseLiteral] = None
    fee_amount: Optional[float] = Field(default=None, ge=0)
    is_available: Optional[bool] = None


class ProductFeeResponse(BaseModel):
    id: int
    credit_product_id: int
    fee_type: str
    fee_base: str
    fee_amount: float
    is_available: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreditProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: Optional[str] = None
    merchant_id: Optional[int] = None
    min_term_months: int = Field(ge=1, le=120)
    max_term_months: int = Field(ge=1, le=120)
    min_amount: float = Field(gt=0)
    max_amount: float = Field(gt=0)
    repayment_scheme: str = Field(min_length=1, max_length=200)
    grace_period_days: int = Field(ge=0, le=365, default=0)
    is_active: bool = True
    score_ranges: list[ProductScoreRangeCreate] = []
    fees: list[ProductFeeCreate] = []


class CreditProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=180)
    description: Optional[str] = None
    merchant_id: Optional[int] = None
    min_term_months: Optional[int] = Field(default=None, ge=1, le=120)
    max_term_months: Optional[int] = Field(default=None, ge=1, le=120)
    min_amount: Optional[float] = Field(default=None, gt=0)
    max_amount: Optional[float] = Field(default=None, gt=0)
    repayment_scheme: Optional[str] = Field(default=None, min_length=1, max_length=200)
    grace_period_days: Optional[int] = Field(default=None, ge=0, le=365)
    is_active: Optional[bool] = None


class CreditProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    merchant_id: Optional[int]
    merchant_name: Optional[str] = None
    min_term_months: int
    max_term_months: int
    min_amount: float
    max_amount: float
    repayment_scheme: str
    grace_period_days: int
    is_active: bool
    score_ranges: list[ProductScoreRangeResponse] = []
    fees: list[ProductFeeResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaymentCalculationRequest(BaseModel):
    product_id: int
    total_amount: float = Field(gt=0)
    term_months: int = Field(ge=1, le=120)


class PaymentCalendarEntry(BaseModel):
    installment_number: int
    due_date: date
    principal: float
    interest: float
    fees: float
    amount_due: float


class FeeBreakdownEntry(BaseModel):
    fee_type: str
    fee_base: str
    fee_amount: float


class PaymentCalculationResponse(BaseModel):
    product_id: int
    total_amount: float
    total_financed: float
    downpayment: float
    fees_due_upfront: float
    term_months: int
    monthly_payment: float
    fees_breakdown: list[FeeBreakdownEntry]
    payment_calendar: list[PaymentCalendarEntry]


# ── Decision ──────────────────────────────────────────

class DecisionResponse(BaseModel):
    id: int
    loan_application_id: int
    credit_score: Optional[int]
    risk_band: Optional[str]
    engine_outcome: Optional[str]
    engine_reasons: Optional[dict]
    scoring_breakdown: Optional[dict]
    rules_results: Optional[dict]
    suggested_rate: Optional[float]
    suggested_amount: Optional[float]
    underwriter_action: Optional[str]
    override_reason: Optional[str]
    final_outcome: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class UnderwriterDecision(BaseModel):
    action: str  # approve, decline, refer, request_info
    reason: str = Field(min_length=5)
    approved_amount: Optional[float] = None
    approved_rate: Optional[float] = None


# ── Document ──────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: int
    loan_application_id: int
    document_type: str
    file_name: str
    file_size: int
    status: str
    rejection_reason: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Verification ──────────────────────────────────────

class VerificationRequest(BaseModel):
    national_id: str
    document_type: str  # national_id, passport, drivers_license
    document_id: int


class VerificationResponse(BaseModel):
    status: str
    verified: bool
    details: Optional[dict] = None
    message: str


# ── Reports ───────────────────────────────────────────

class DashboardMetrics(BaseModel):
    total_applications: int
    pending_review: int
    approved: int
    declined: int
    total_disbursed: float
    approval_rate: float
    avg_processing_days: float
    avg_loan_amount: float
    applications_by_status: dict
    risk_distribution: dict
    monthly_volume: list
    # Enhanced metrics
    projected_interest_income: float = 0.0
    total_principal_disbursed: float = 0.0
    projected_profit: float = 0.0
    daily_volume: list = []


# ── Credit Report ─────────────────────────────────────

class CreditReportResponse(BaseModel):
    id: int
    provider: str
    bureau_score: Optional[int]
    report_data: Optional[dict]
    tradelines: Optional[dict]
    inquiries: Optional[dict]
    status: str
    pulled_at: datetime

    model_config = {"from_attributes": True}


# ── Counterproposal ──────────────────────────────────

class CounterproposalRequest(BaseModel):
    proposed_amount: float = Field(gt=0)
    proposed_rate: float = Field(gt=0)
    proposed_term: int = Field(ge=3, le=84)
    reason: str = Field(min_length=5)


# ── Contract ─────────────────────────────────────────

class ContractSignRequest(BaseModel):
    signature_data: str  # base64 PNG
    typed_name: str = Field(min_length=2, max_length=200)
    agreed: bool


class ContractResponse(BaseModel):
    signature_data: Optional[str] = None
    typed_name: Optional[str] = None
    signed_at: Optional[datetime] = None


# ── Audit Log ────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    action: str
    user_id: Optional[int]
    user_name: Optional[str] = None
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    details: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Full Application (extended review) ───────────────

class FullApplicationResponse(BaseModel):
    application: LoanApplicationResponse
    profile: Optional[ApplicantProfileResponse] = None
    documents: list[DocumentResponse] = []
    decisions: list[DecisionResponse] = []
    audit_log: list[AuditLogResponse] = []
    contract: Optional[ContractResponse] = None


# ── Application Edit ─────────────────────────────────

class ApplicationEditRequest(BaseModel):
    """Fields that an underwriter can edit on an application.
    Only non-None fields will be updated."""
    term_months: Optional[int] = None
    purpose: Optional[str] = None
    purpose_description: Optional[str] = None
    # Profile fields the underwriter can correct
    monthly_income: Optional[float] = None
    monthly_expenses: Optional[float] = None
    existing_debt: Optional[float] = None
    employer_name: Optional[str] = None
    job_title: Optional[str] = None
    employment_type: Optional[str] = None
    years_employed: Optional[int] = None


# ── Loan Book ────────────────────────────────────────

class LoanBookEntry(BaseModel):
    id: int
    reference_number: str
    applicant_name: str
    amount_requested: float
    amount_approved: Optional[float]
    term_months: int
    interest_rate: Optional[float]
    monthly_payment: Optional[float]
    status: str
    risk_band: Optional[str] = None
    credit_score: Optional[int] = None
    disbursed_date: Optional[datetime] = None
    outstanding_balance: Optional[float] = None
    days_past_due: int = 0
    next_payment_date: Optional[date] = None
    purpose: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Payment ──────────────────────────────────────────

class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    payment_type: str = "manual"
    payment_date: date
    reference_number: Optional[str] = None
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    id: int
    loan_application_id: int
    amount: float
    payment_type: str
    payment_date: date
    reference_number: Optional[str]
    recorded_by: Optional[int]
    status: str
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentScheduleResponse(BaseModel):
    id: int
    loan_application_id: int
    installment_number: int
    due_date: date
    principal: float
    interest: float
    amount_due: float
    amount_paid: float
    status: str
    paid_at: Optional[datetime]

    model_config = {"from_attributes": True}


class OnlinePaymentRequest(BaseModel):
    amount: float = Field(gt=0)


# ── Collection ───────────────────────────────────────

class CollectionRecordCreate(BaseModel):
    channel: str
    notes: Optional[str] = None
    action_taken: Optional[str] = None
    outcome: str
    next_action_date: Optional[date] = None
    promise_amount: Optional[float] = None
    promise_date: Optional[date] = None


class CollectionRecordResponse(BaseModel):
    id: int
    loan_application_id: int
    agent_id: int
    agent_name: Optional[str] = None
    channel: str
    notes: Optional[str]
    action_taken: Optional[str]
    outcome: str
    next_action_date: Optional[date]
    promise_amount: Optional[float]
    promise_date: Optional[date]
    created_at: datetime

    model_config = {"from_attributes": True}


class CollectionChatCreate(BaseModel):
    message: str


class CollectionChatResponse(BaseModel):
    id: int
    loan_application_id: int
    agent_id: Optional[int]
    phone_number: Optional[str]
    direction: str
    message: str
    channel: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CollectionQueueEntry(BaseModel):
    id: int
    reference_number: str
    applicant_name: str
    amount_approved: Optional[float]
    amount_due: float = 0
    days_past_due: int = 0
    last_contact: Optional[datetime] = None
    next_action: Optional[date] = None
    total_paid: float = 0
    outstanding_balance: float = 0
    phone: Optional[str] = None


# ── Report History ───────────────────────────────────

class ReportGenerateRequest(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    application_id: Optional[int] = None  # For loan statement


class ReportHistoryResponse(BaseModel):
    id: int
    report_type: str
    report_name: str
    generated_by: int
    parameters: Optional[dict]
    file_format: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Staff Create Application ─────────────────────────

class StaffCreateApplicationRequest(BaseModel):
    # Applicant info
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: Optional[str] = None
    # Profile info
    date_of_birth: Optional[date] = None
    national_id: Optional[str] = None
    gender: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    parish: Optional[str] = None
    employer_name: Optional[str] = None
    job_title: Optional[str] = None
    employment_type: Optional[str] = None
    years_employed: Optional[int] = None
    monthly_income: Optional[float] = None
    monthly_expenses: Optional[float] = None
    existing_debt: Optional[float] = None
    # Loan details
    amount_requested: float = Field(gt=0, le=500000)
    term_months: int = Field(ge=3, le=84)
    purpose: str
    purpose_description: Optional[str] = None
