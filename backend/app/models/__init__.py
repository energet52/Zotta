"""SQLAlchemy models for Zotta lending application."""

from app.models.user import User
from app.models.loan import LoanApplication, ApplicantProfile, ApplicationItem
from app.models.decision import Decision, DecisionRulesConfig
from app.models.document import Document
from app.models.audit import AuditLog
from app.models.note import ApplicationNote
from app.models.comment import ApplicationComment
from app.models.reference import ApplicationReference
from app.models.credit_report import CreditReport
from app.models.chat import ChatSession, ChatMessage
from app.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationState,
    ConversationChannel,
    ConversationEntryPoint,
    MessageRole,
)
from app.models.payment import Payment, PaymentSchedule
from app.models.disbursement import Disbursement
from app.models.collection import CollectionRecord, CollectionChat
from app.models.collections_ext import (
    CollectionCase, PromiseToPay, SettlementOffer,
    ComplianceRule, SLAConfig, CollectionsDashboardSnapshot,
    CaseStatus, DelinquencyStage, PTPStatus,
    SettlementOfferType, SettlementStatus,
)
from app.models.report import ReportHistory
from app.models.bank_analysis import BankStatementAnalysis
from app.models.credit_bureau_alert import (
    CreditBureauAlert,
    AlertType,
    AlertSeverity,
    AlertStatus,
)
from app.models.catalog import (
    Merchant,
    Branch,
    ProductCategory,
    CreditProduct,
    ProductScoreRange,
    ProductFee,
)
from app.models.sector_analysis import (
    SectorPolicy,
    SectorAlertRule,
    SectorAlert,
    SectorSnapshot,
    SectorMacroIndicator,
    SectorPolicyStatus,
    SectorAlertSeverity,
    SectorAlertStatus,
    SectorRiskRating,
    SECTOR_TAXONOMY,
)
from app.models.error_log import ErrorLog, ErrorSeverity
from app.models.gl import (
    Currency,
    GLAccount,
    GLAccountAudit,
    AccountingPeriod,
    JournalEntry,
    JournalEntryLine,
    GLMappingTemplate,
    GLMappingTemplateLine,
    AccrualBatch,
    GLFilterPreset,
    GLExportSchedule,
    GLExportLog,
    GLAnomaly,
)

__all__ = [
    "User",
    "LoanApplication",
    "ApplicantProfile",
    "ApplicationItem",
    "Decision",
    "DecisionRulesConfig",
    "Document",
    "AuditLog",
    "ApplicationNote",
    "ApplicationComment",
    "ApplicationReference",
    "CreditReport",
    "ChatSession",
    "ChatMessage",
    "Conversation",
    "ConversationMessage",
    "ConversationState",
    "ConversationChannel",
    "ConversationEntryPoint",
    "MessageRole",
    "Payment",
    "PaymentSchedule",
    "Disbursement",
    "CollectionRecord",
    "CollectionChat",
    # Collections Extended
    "CollectionCase",
    "PromiseToPay",
    "SettlementOffer",
    "ComplianceRule",
    "SLAConfig",
    "CollectionsDashboardSnapshot",
    "CaseStatus",
    "DelinquencyStage",
    "PTPStatus",
    "SettlementOfferType",
    "SettlementStatus",
    "ReportHistory",
    "Merchant",
    "Branch",
    "ProductCategory",
    "CreditProduct",
    "ProductScoreRange",
    "ProductFee",
    "BankStatementAnalysis",
    "CreditBureauAlert",
    "AlertType",
    "AlertSeverity",
    "AlertStatus",
    # Sector Analysis
    "SectorPolicy",
    "SectorAlertRule",
    "SectorAlert",
    "SectorSnapshot",
    "SectorMacroIndicator",
    "SectorPolicyStatus",
    "SectorAlertSeverity",
    "SectorAlertStatus",
    "SectorRiskRating",
    "SECTOR_TAXONOMY",
    # Error Monitoring
    "ErrorLog",
    "ErrorSeverity",
    # General Ledger
    "Currency",
    "GLAccount",
    "GLAccountAudit",
    "AccountingPeriod",
    "JournalEntry",
    "JournalEntryLine",
    "GLMappingTemplate",
    "GLMappingTemplateLine",
    "AccrualBatch",
    "GLFilterPreset",
    "GLExportSchedule",
    "GLExportLog",
    "GLAnomaly",
]
