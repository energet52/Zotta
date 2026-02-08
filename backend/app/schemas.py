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
