"""Pydantic schemas for request/response validation."""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


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


class LoanApplicationUpdate(BaseModel):
    amount_requested: Optional[float] = None
    term_months: Optional[int] = None
    purpose: Optional[str] = None
    purpose_description: Optional[str] = None


class LoanApplicationResponse(BaseModel):
    id: int
    reference_number: str
    applicant_id: int
    amount_requested: float
    term_months: int
    purpose: str
    purpose_description: Optional[str]
    interest_rate: Optional[float]
    amount_approved: Optional[float]
    monthly_payment: Optional[float]
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
