"""SQLAlchemy models for Zotta lending application."""

from app.models.user import User, UserStatus
from app.models.rbac import (
    Role, Permission, RolePermission, UserRoleAssignment, PendingAction,
    PendingActionStatus,
)
from app.models.mfa import MFADevice, MFADeviceType
from app.models.session import UserSession, LoginAttempt
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
    ProductRateTier,
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
from app.models.scorecard import (
    Scorecard, ScorecardStatus, ScorecardCharacteristic, ScorecardBin,
    BinType, ScoreResult, ScorecardChangeLog, ScorecardChangeStatus,
    ScorecardPerformanceSnapshot, ScorecardAlert,
)
from app.models.collection_sequence import (
    CollectionSequence,
    SequenceStep,
    MessageTemplate,
    SequenceEnrollment,
    StepExecution,
    SequenceStatus,
    StepActionType,
    StepChannel,
    TemplateTone,
    TemplateCategory,
    DeliveryStatus,
)
from app.models.queue import (
    QueueConfig,
    QueueEntry,
    QueueStage,
    StaffQueueProfile,
    QueueEvent,
    QueueException,
    AssignmentMode,
    SLAMode,
    QueueEntryStatus,
    ExceptionStatus,
)
from app.models.pre_approval import (
    PreApproval,
    PreApprovalOTP,
    PreApprovalOutcome,
    PreApprovalStatus,
)
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
    "UserStatus",
    # RBAC
    "Role",
    "Permission",
    "RolePermission",
    "UserRoleAssignment",
    "PendingAction",
    "PendingActionStatus",
    # MFA
    "MFADevice",
    "MFADeviceType",
    # Sessions
    "UserSession",
    "LoginAttempt",
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
    "ProductRateTier",
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
    # Scorecards
    "Scorecard",
    "ScorecardStatus",
    "ScorecardCharacteristic",
    "ScorecardBin",
    "BinType",
    "ScoreResult",
    "ScorecardChangeLog",
    "ScorecardChangeStatus",
    "ScorecardPerformanceSnapshot",
    "ScorecardAlert",
    # Collection Sequences
    "CollectionSequence",
    "SequenceStep",
    "MessageTemplate",
    "SequenceEnrollment",
    "StepExecution",
    "SequenceStatus",
    "StepActionType",
    "StepChannel",
    "TemplateTone",
    "TemplateCategory",
    "DeliveryStatus",
    # Queue Management
    "QueueConfig",
    "QueueEntry",
    "QueueStage",
    "StaffQueueProfile",
    "QueueEvent",
    "QueueException",
    "AssignmentMode",
    "SLAMode",
    "QueueEntryStatus",
    "ExceptionStatus",
    # Pre-Approval
    "PreApproval",
    "PreApprovalOTP",
    "PreApprovalOutcome",
    "PreApprovalStatus",
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
