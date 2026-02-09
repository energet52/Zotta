"""SQLAlchemy models for Zotta lending application."""

from app.models.user import User
from app.models.loan import LoanApplication, ApplicantProfile
from app.models.decision import Decision, DecisionRulesConfig
from app.models.document import Document
from app.models.audit import AuditLog
from app.models.credit_report import CreditReport
from app.models.chat import ChatSession, ChatMessage
from app.models.payment import Payment, PaymentSchedule
from app.models.collection import CollectionRecord, CollectionChat
from app.models.report import ReportHistory

__all__ = [
    "User",
    "LoanApplication",
    "ApplicantProfile",
    "Decision",
    "DecisionRulesConfig",
    "Document",
    "AuditLog",
    "CreditReport",
    "ChatSession",
    "ChatMessage",
    "Payment",
    "PaymentSchedule",
    "CollectionRecord",
    "CollectionChat",
    "ReportHistory",
]
