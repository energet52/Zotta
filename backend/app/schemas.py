"""Pydantic schemas for request/response validation."""

from datetime import datetime, date
from typing import Any, Optional, Literal
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
    must_change_password: bool = False


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    display_name: Optional[str] = None
    phone: Optional[str]
    role: str
    status: str = "active"
    employee_id: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    timezone: str = "America/Port_of_Spain"
    language: str = "en"
    profile_photo_url: Optional[str] = None
    mfa_enabled: bool = False
    last_login_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Optional fields for updating current user profile."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)


# ── Applicant Profile ────────────────────────────────

class ApplicantProfileCreate(BaseModel):
    date_of_birth: Optional[date] = None
    id_type: Optional[str] = None  # national_id, passport, drivers_license, tax_number
    national_id: Optional[str] = None  # stores the actual ID number
    gender: Optional[str] = None
    marital_status: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    parish: Optional[str] = None
    whatsapp_number: Optional[str] = None
    contact_email: Optional[str] = None
    mobile_phone: Optional[str] = None
    home_phone: Optional[str] = None
    employer_phone: Optional[str] = None
    employer_name: Optional[str] = None
    employer_sector: Optional[str] = None
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
    merchant_name: Optional[str] = None  # populated when relations loaded
    branch_name: Optional[str] = None
    credit_product_name: Optional[str] = None
    downpayment: Optional[float] = None
    total_financed: Optional[float] = None
    items: list["ApplicationItemResponse"] = []  # populated when relations loaded
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

    @model_validator(mode="before")
    @classmethod
    def _safe_relations(cls, data: Any) -> Any:  # type: ignore[override]
        """Prevent lazy-load errors on unloaded ORM relationships.

        When model_validate is called on an ORM object whose relationships
        (merchant, branch, credit_product, items) were NOT eagerly loaded,
        accessing them raises MissingGreenlet in async SQLAlchemy.  This
        validator catches those errors and falls back to safe defaults.
        """
        if not isinstance(data, dict):
            # ORM object – read safe attrs
            d: dict = {}
            for field_name in cls.model_fields:
                try:
                    val = getattr(data, field_name, None)
                    # Resolve enums
                    if hasattr(val, "value"):
                        val = val.value
                    d[field_name] = val
                except Exception:
                    # Lazy-load failure → use default
                    pass
            return d
        return data


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


# Resolve forward ref for LoanApplicationResponse.items
LoanApplicationResponse.model_rebuild()


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

class ArrearsBucket(BaseModel):
    label: str
    loan_count: int
    total_outstanding: float
    total_overdue: float

class ArrearsSummary(BaseModel):
    total_delinquent_loans: int
    total_overdue_amount: float
    total_outstanding_at_risk: float
    buckets: list[ArrearsBucket]

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
    # Arrears / delinquency summary
    arrears_summary: Optional[ArrearsSummary] = None
    # Live P&L
    interest_collected: float = 0.0
    expected_default_loss: float = 0.0
    net_pnl: float = 0.0


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


class SubmitWithConsentRequest(BaseModel):
    """Submit a draft application together with signed consent/contract."""
    signature_data: str  # base64 PNG from canvas
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
    employer_sector: Optional[str] = None
    job_title: Optional[str] = None
    employment_type: Optional[str] = None
    years_employed: Optional[int] = None
    whatsapp_number: Optional[str] = None
    contact_email: Optional[str] = None
    mobile_phone: Optional[str] = None
    home_phone: Optional[str] = None
    employer_phone: Optional[str] = None


# ── Loan Book ────────────────────────────────────────

class LoanBookEntry(BaseModel):
    id: int
    reference_number: str
    applicant_id: int
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
    fee: float = 0
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
    applicant_id: int
    applicant_name: str
    amount_approved: Optional[float]
    amount_due: float = 0
    days_past_due: int = 0
    last_contact: Optional[datetime] = None
    next_action: Optional[date] = None
    total_paid: float = 0
    outstanding_balance: float = 0
    phone: Optional[str] = None
    # Enhanced fields from CollectionCase
    case_id: Optional[int] = None
    case_status: Optional[str] = None
    delinquency_stage: Optional[str] = None
    assigned_agent_id: Optional[int] = None
    assigned_agent_name: Optional[str] = None
    next_best_action: Optional[str] = None
    nba_confidence: Optional[float] = None
    nba_reasoning: Optional[str] = None
    dispute_active: bool = False
    vulnerability_flag: bool = False
    do_not_contact: bool = False
    hardship_flag: bool = False
    priority_score: float = 0.0
    compliance_ok: Optional[bool] = None
    # New enhanced fields
    employer_name: Optional[str] = None
    sector: Optional[str] = None
    sector_risk_rating: Optional[str] = None
    product_type: Optional[str] = None
    ptp_status: Optional[str] = None
    ptp_amount: Optional[float] = None
    ptp_date: Optional[date] = None
    last_contact_channel: Optional[str] = None
    last_contact_outcome: Optional[str] = None
    sla_deadline: Optional[datetime] = None
    sla_hours_remaining: Optional[float] = None
    propensity_score: Optional[int] = None
    propensity_trend: Optional[str] = None


# ── Collection Case ──────────────────────────────────

class CollectionCaseResponse(BaseModel):
    id: int
    loan_application_id: int
    assigned_agent_id: Optional[int] = None
    assigned_agent_name: Optional[str] = None
    status: str
    delinquency_stage: str
    priority_score: float
    dpd: int
    total_overdue: float
    dispute_active: bool
    vulnerability_flag: bool
    do_not_contact: bool
    hardship_flag: bool
    next_best_action: Optional[str] = None
    nba_confidence: float = 0
    nba_reasoning: Optional[str] = None
    first_contact_at: Optional[datetime] = None
    last_contact_at: Optional[datetime] = None
    sla_first_contact_deadline: Optional[datetime] = None
    sla_next_contact_deadline: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CollectionCaseUpdate(BaseModel):
    assigned_agent_id: Optional[int] = None
    status: Optional[str] = None
    dispute_active: Optional[bool] = None
    vulnerability_flag: Optional[bool] = None
    do_not_contact: Optional[bool] = None
    hardship_flag: Optional[bool] = None


class NBAOverrideRequest(BaseModel):
    action: str
    reason: str = Field(min_length=5)


# ── Promise to Pay ───────────────────────────────────

class PromiseToPayCreate(BaseModel):
    amount_promised: float = Field(gt=0)
    promise_date: date
    payment_method: Optional[str] = None
    notes: Optional[str] = None


class PromiseToPayResponse(BaseModel):
    id: int
    collection_case_id: int
    loan_application_id: int
    agent_id: int
    agent_name: Optional[str] = None
    amount_promised: float
    promise_date: date
    payment_method: Optional[str]
    status: str
    amount_received: float
    reminded_at: Optional[datetime] = None
    broken_at: Optional[datetime] = None
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PromiseToPayUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


# ── Settlement Offer ─────────────────────────────────

class SettlementOfferCreate(BaseModel):
    offer_type: str
    settlement_amount: float = Field(gt=0)
    discount_pct: float = 0
    plan_months: Optional[int] = None
    plan_monthly_amount: Optional[float] = None
    lump_sum: Optional[float] = None
    notes: Optional[str] = None
    auto_calculate: bool = False  # If true, ignore amounts and auto-calc


class SettlementOfferResponse(BaseModel):
    id: int
    collection_case_id: int
    loan_application_id: int
    offer_type: str
    original_balance: float
    settlement_amount: float
    discount_pct: float
    plan_months: Optional[int]
    plan_monthly_amount: Optional[float]
    lump_sum: Optional[float]
    status: str
    offered_by: int
    offered_by_name: Optional[str] = None
    approved_by: Optional[int] = None
    approved_by_name: Optional[str] = None
    approval_required: bool
    expires_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Compliance Rule ──────────────────────────────────

class ComplianceRuleCreate(BaseModel):
    jurisdiction: str = Field(min_length=2, max_length=10)
    contact_start_hour: int = Field(ge=0, le=23, default=8)
    contact_end_hour: int = Field(ge=1, le=24, default=20)
    max_contacts_per_day: int = Field(ge=1, default=3)
    max_contacts_per_week: int = Field(ge=1, default=10)
    cooling_off_hours: int = Field(ge=0, default=4)
    is_active: bool = True


class ComplianceRuleResponse(BaseModel):
    id: int
    jurisdiction: str
    contact_start_hour: int
    contact_end_hour: int
    max_contacts_per_day: int
    max_contacts_per_week: int
    cooling_off_hours: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ComplianceCheckRequest(BaseModel):
    case_id: int
    jurisdiction: str = "TT"


class ComplianceCheckResponse(BaseModel):
    allowed: bool
    reasons: list[str]
    next_allowed_at: Optional[str] = None


# ── Collections Dashboard ────────────────────────────

class CollectionsDashboardResponse(BaseModel):
    total_delinquent_accounts: int = 0
    total_overdue_amount: float = 0
    by_stage: dict = {}
    trend: list[dict] = []
    cure_rate: float = 0
    ptp_rate: float = 0
    ptp_kept_rate: float = 0
    recovered_mtd: float = 0


class BulkAssignRequest(BaseModel):
    case_ids: list[int]
    agent_id: int


# ── Draft Message ────────────────────────────────────

class DraftMessageRequest(BaseModel):
    case_id: int
    channel: str = "whatsapp"  # whatsapp, sms, email
    template_type: str = "reminder"  # reminder, demand, follow_up, promise_reminder, broken_promise, payment_link, settlement_offer


class DraftMessageResponse(BaseModel):
    message: str
    source: str  # "ai" or "template"
    template_type: str


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


# ── Disbursement ────────────────────────────────────

class DisbursementRequest(BaseModel):
    """Request to disburse funds for an approved/accepted loan.

    method: 'manual' for now. Future: 'bank_transfer', 'mobile_money', etc.
    Bank fields are optional — required when method is bank_transfer.
    """
    method: str = "manual"
    notes: Optional[str] = None
    # Bank transfer fields (for future integrations)
    recipient_account_name: Optional[str] = None
    recipient_account_number: Optional[str] = None
    recipient_bank: Optional[str] = None
    recipient_bank_branch: Optional[str] = None


class DisbursementResponse(BaseModel):
    id: int
    loan_application_id: int
    amount: float
    method: str
    status: str
    reference_number: Optional[str]
    provider: Optional[str]
    provider_reference: Optional[str]
    recipient_account_name: Optional[str]
    recipient_account_number: Optional[str]
    recipient_bank: Optional[str]
    recipient_bank_branch: Optional[str]
    disbursed_by: int
    disbursed_by_name: Optional[str] = None
    notes: Optional[str]
    disbursed_at: datetime
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
    id_type: Optional[str] = None  # national_id, passport, drivers_license, tax_number
    national_id: Optional[str] = None  # stores the actual ID number
    gender: Optional[str] = None
    marital_status: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    parish: Optional[str] = None
    whatsapp_number: Optional[str] = None
    contact_email: Optional[str] = None
    mobile_phone: Optional[str] = None
    home_phone: Optional[str] = None
    employer_phone: Optional[str] = None
    employer_name: Optional[str] = None
    employer_sector: Optional[str] = None
    job_title: Optional[str] = None
    employment_type: Optional[str] = None
    years_employed: Optional[int] = None
    monthly_income: Optional[float] = None
    other_income: Optional[float] = None
    monthly_expenses: Optional[float] = None
    existing_debt: Optional[float] = None
    dependents: Optional[int] = None
    # Loan details
    amount_requested: float = Field(gt=0, le=500000)
    term_months: int = Field(ge=3, le=84)
    purpose: str
    purpose_description: Optional[str] = None
    # Shopping / hire-purchase (optional)
    merchant_id: Optional[int] = None
    branch_id: Optional[int] = None
    credit_product_id: Optional[int] = None
    downpayment: Optional[float] = None
    total_financed: Optional[float] = None
    items: Optional[list[dict]] = None  # [{category_id, description, price, quantity}]


# ── Bank Statement Analysis ──────────────────────────

class BankAnalysisFlag(BaseModel):
    type: str
    severity: str
    detail: str
    amount_involved: Optional[float] = None
    occurrences: Optional[int] = None

class BankAnalysisMonthlyStat(BaseModel):
    month: str
    total_inflow: float = 0
    total_outflow: float = 0
    net: float = 0
    min_balance: Optional[float] = None

class BankAnalysisResponse(BaseModel):
    id: int
    loan_application_id: int
    document_id: int
    status: str
    summary: Optional[str] = None
    cashflow_data: Optional[dict] = None
    flags: Optional[list[BankAnalysisFlag]] = None
    volatility_score: Optional[float] = None
    monthly_stats: Optional[list[BankAnalysisMonthlyStat]] = None
    risk_assessment: Optional[str] = None
    income_stability: Optional[str] = None
    avg_monthly_inflow: Optional[float] = None
    avg_monthly_outflow: Optional[float] = None
    avg_monthly_net: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── ID Parsing (OCR) ─────────────────────────────────

class ParsedIdResponse(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None  # ISO YYYY-MM-DD
    id_type: Optional[str] = None  # national_id, passport, drivers_license, tax_number
    national_id: Optional[str] = None  # the actual ID number
    gender: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    parish: Optional[str] = None
    raw_text: Optional[str] = None  # debug: full extracted text


# ── Conversations (Customer Support) ───────────────────

class ConversationCreate(BaseModel):
    channel: Optional[str] = "web"
    entry_point: Optional[str] = None  # cold_start, pre_qualified, returning_applicant, existing_customer, servicing
    entry_context: Optional[dict] = None  # e.g. product_id, max_amount for pre_qualified


class ConversationResponse(BaseModel):
    id: int
    channel: str
    current_state: str
    loan_application_id: Optional[int] = None
    entry_point: Optional[str] = None
    assigned_agent_id: Optional[int] = None
    escalated_at: Optional[datetime] = None
    escalation_reason: Optional[str] = None
    created_at: datetime
    last_activity_at: datetime

    model_config = {"from_attributes": True}


class ConversationMessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(ConversationResponse):
    messages: list[ConversationMessageResponse] = []
    application_summary: Optional[dict] = None
class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class StartApplicationRequest(BaseModel):
    amount_requested: float = Field(..., gt=0)
    term_months: int = Field(..., ge=3, le=84)
    purpose: str = Field(default="personal")


# ── MFA ──────────────────────────────────────────────────────

class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    device_id: int


class MFAVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)
    mfa_token: str = ""  # only needed for login flow, empty for confirm


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Roles & Permissions ─────────────────────────────────────

class PermissionResponse(BaseModel):
    id: int
    code: str
    module: str
    object: str
    action: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    parent_role_id: Optional[int] = None
    permission_codes: list[str] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    parent_role_id: Optional[int] = None
    is_active: Optional[bool] = None
    permission_codes: Optional[list[str]] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    parent_role_id: Optional[int] = None
    is_system: bool
    is_active: bool
    permissions: list[PermissionResponse] = []
    user_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoleBriefResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_system: bool
    is_active: bool

    model_config = {"from_attributes": True}


class UserRoleAssignmentResponse(BaseModel):
    id: int
    role_id: int
    role_name: str
    granted_by: Optional[int] = None
    granted_at: datetime
    expires_at: Optional[datetime] = None
    is_primary: bool

    model_config = {"from_attributes": True}


# ── User Management (admin) ─────────────────────────────────

class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    middle_name: Optional[str] = None
    phone: Optional[str] = None
    role: str = "applicant"
    employee_id: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    timezone: str = "America/Port_of_Spain"
    language: str = "en"
    role_ids: list[int] = []
    must_change_password: bool = True


class AdminUserUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    middle_name: Optional[str] = None
    display_name: Optional[str] = None
    phone: Optional[str] = None
    employee_id: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


class UserDetailResponse(UserResponse):
    """Extended user response with roles, sessions, and login history."""
    roles: list[UserRoleAssignmentResponse] = []
    effective_permissions: list[str] = []
    active_sessions_count: int = 0
    recent_login_attempts: list[dict] = []

    model_config = {"from_attributes": True}


class AssignRolesRequest(BaseModel):
    role_ids: list[int]


class PendingActionResponse(BaseModel):
    id: int
    action_type: str
    target_user_id: Optional[int] = None
    payload: dict
    requested_by: int
    requester_name: Optional[str] = None
    approved_by: Optional[int] = None
    approver_name: Optional[str] = None
    status: str
    rejection_reason: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PendingActionDecision(BaseModel):
    approved: bool
    rejection_reason: Optional[str] = None