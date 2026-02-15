"""Customer 360 data aggregation, timeline builder, and AI intelligence.

Assembles a complete customer profile from all data sources, builds a
unified activity timeline, and provides AI-powered summary & Q&A.
"""

import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.services.error_logger import log_error
from app.models.user import User
from app.models.loan import LoanApplication, ApplicantProfile, LoanStatus
from app.models.payment import Payment, PaymentSchedule, PaymentStatus, ScheduleStatus
from app.models.collection import CollectionRecord, CollectionChat
from app.models.decision import Decision
from app.models.document import Document
from app.models.credit_report import CreditReport
from app.models.audit import AuditLog
from app.models.conversation import Conversation, ConversationMessage
from app.models.comment import ApplicationComment
from app.models.note import ApplicationNote
from app.models.disbursement import Disbursement
from app.models.credit_bureau_alert import CreditBureauAlert

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ser(val: Any) -> Any:
    """JSON-safe serialiser for dates, Decimals, enums."""
    if val is None:
        return None
    if isinstance(val, (datetime,)):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if hasattr(val, "value"):
        return val.value
    return val


def _row_to_dict(obj: Any, fields: list[str]) -> dict:
    """Convert an ORM object to a dict picking *fields*."""
    return {f: _ser(getattr(obj, f, None)) for f in fields}


# ---------------------------------------------------------------------------
# 1. Full Customer 360 aggregation
# ---------------------------------------------------------------------------

async def get_customer_360(user_id: int, db: AsyncSession) -> dict:
    """Return the complete customer 360 payload."""

    # ── User + Profile ──────────────────────────────────────────
    user_result = await db.execute(
        select(User)
        .options(selectinload(User.applicant_profile))
        .where(User.id == user_id)
    )
    user: User | None = user_result.scalar_one_or_none()
    if not user:
        return None

    profile: ApplicantProfile | None = user.applicant_profile

    user_data = _row_to_dict(user, [
        "id", "email", "first_name", "last_name", "phone",
        "role", "is_active", "created_at",
    ])
    profile_data = {}
    if profile:
        profile_data = _row_to_dict(profile, [
            "id", "user_id", "date_of_birth", "id_type", "national_id",
            "gender", "marital_status",
            "address_line1", "address_line2", "city", "parish", "country",
            "employer_name", "job_title", "employment_type",
            "years_employed", "monthly_income", "other_income",
            "monthly_expenses", "existing_debt", "dependents",
            "whatsapp_number", "contact_email", "mobile_phone",
            "home_phone", "employer_phone",
            "id_verified", "id_verification_status",
            "created_at", "updated_at",
        ])

    # ── Loan Applications ───────────────────────────────────────
    loans_result = await db.execute(
        select(LoanApplication)
        .where(LoanApplication.applicant_id == user_id)
        .order_by(LoanApplication.created_at.desc())
    )
    loans = loans_result.scalars().all()

    loan_fields = [
        "id", "reference_number", "amount_requested", "term_months",
        "purpose", "purpose_description", "interest_rate",
        "amount_approved", "monthly_payment", "downpayment", "total_financed",
        "status", "assigned_underwriter_id",
        "proposed_amount", "proposed_rate", "proposed_term",
        "counterproposal_reason",
        "contract_signed_at", "submitted_at", "decided_at",
        "disbursed_at", "created_at", "updated_at",
        "merchant_id", "branch_id", "credit_product_id",
    ]
    loans_data = [_row_to_dict(ln, loan_fields) for ln in loans]
    loan_ids = [ln.id for ln in loans]

    # ── Payments ────────────────────────────────────────────────
    payments_data = []
    if loan_ids:
        pay_result = await db.execute(
            select(Payment)
            .where(Payment.loan_application_id.in_(loan_ids))
            .order_by(Payment.payment_date.desc())
        )
        payments = pay_result.scalars().all()
        payments_data = [
            _row_to_dict(p, [
                "id", "loan_application_id", "amount", "payment_type",
                "payment_date", "reference_number", "recorded_by",
                "status", "notes", "created_at",
            ])
            for p in payments
        ]

    # ── Payment Schedules ───────────────────────────────────────
    schedules_data = []
    if loan_ids:
        sched_result = await db.execute(
            select(PaymentSchedule)
            .where(PaymentSchedule.loan_application_id.in_(loan_ids))
            .order_by(PaymentSchedule.loan_application_id, PaymentSchedule.installment_number)
        )
        schedules = sched_result.scalars().all()
        schedules_data = [
            _row_to_dict(s, [
                "id", "loan_application_id", "installment_number",
                "due_date", "principal", "interest", "fee",
                "amount_due", "amount_paid", "status", "paid_at",
            ])
            for s in schedules
        ]

    # ── Decisions ───────────────────────────────────────────────
    decisions_data = []
    if loan_ids:
        dec_result = await db.execute(
            select(Decision)
            .where(Decision.loan_application_id.in_(loan_ids))
            .order_by(Decision.created_at.desc())
        )
        decisions = dec_result.scalars().all()
        decisions_data = [
            _row_to_dict(d, [
                "id", "loan_application_id", "credit_score", "risk_band",
                "engine_outcome", "engine_reasons", "scoring_breakdown",
                "rules_results", "suggested_rate", "suggested_amount",
                "underwriter_id", "underwriter_action", "override_reason",
                "final_outcome", "created_at",
            ])
            for d in decisions
        ]

    # ── Disbursements ───────────────────────────────────────────
    disbursements_data = []
    if loan_ids:
        dis_result = await db.execute(
            select(Disbursement)
            .where(Disbursement.loan_application_id.in_(loan_ids))
            .order_by(Disbursement.disbursed_at.desc())
        )
        disbursements = dis_result.scalars().all()
        disbursements_data = [
            _row_to_dict(d, [
                "id", "loan_application_id", "amount", "method",
                "status", "reference_number", "disbursed_by",
                "disbursed_at", "created_at",
            ])
            for d in disbursements
        ]

    # ── Collection Records ──────────────────────────────────────
    collection_records_data = []
    if loan_ids:
        cr_result = await db.execute(
            select(CollectionRecord)
            .where(CollectionRecord.loan_application_id.in_(loan_ids))
            .order_by(CollectionRecord.created_at.desc())
        )
        crs = cr_result.scalars().all()
        collection_records_data = [
            _row_to_dict(r, [
                "id", "loan_application_id", "agent_id", "channel",
                "notes", "action_taken", "outcome",
                "next_action_date", "promise_amount", "promise_date",
                "created_at",
            ])
            for r in crs
        ]

    # ── Collection Chats ────────────────────────────────────────
    collection_chats_data = []
    if loan_ids:
        cc_result = await db.execute(
            select(CollectionChat)
            .where(CollectionChat.loan_application_id.in_(loan_ids))
            .order_by(CollectionChat.created_at.desc())
        )
        ccs = cc_result.scalars().all()
        collection_chats_data = [
            _row_to_dict(c, [
                "id", "loan_application_id", "agent_id", "phone_number",
                "direction", "message", "channel", "status", "created_at",
            ])
            for c in ccs
        ]

    # ── Documents ───────────────────────────────────────────────
    documents_data = []
    if loan_ids:
        doc_result = await db.execute(
            select(Document)
            .where(Document.loan_application_id.in_(loan_ids))
            .order_by(Document.created_at.desc())
        )
        docs = doc_result.scalars().all()
        documents_data = [
            _row_to_dict(d, [
                "id", "loan_application_id", "uploaded_by",
                "document_type", "file_name", "file_size", "mime_type",
                "status", "rejection_reason", "created_at",
            ])
            for d in docs
        ]

    # ── Credit Reports ──────────────────────────────────────────
    credit_reports_data = []
    if loan_ids:
        cred_result = await db.execute(
            select(CreditReport)
            .where(CreditReport.loan_application_id.in_(loan_ids))
            .order_by(CreditReport.pulled_at.desc())
        )
        creds = cred_result.scalars().all()
        credit_reports_data = [
            _row_to_dict(cr, [
                "id", "loan_application_id", "provider", "national_id",
                "bureau_score", "report_data", "tradelines", "inquiries",
                "public_records", "status", "error_message", "pulled_at",
            ])
            for cr in creds
        ]

    # ── Conversations ───────────────────────────────────────────
    conv_result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.participant_user_id == user_id)
        .order_by(Conversation.last_activity_at.desc())
    )
    convos = conv_result.scalars().all()
    conversations_data = []
    for conv in convos:
        cd = _row_to_dict(conv, [
            "id", "channel", "current_state", "loan_application_id",
            "entry_point", "created_at", "last_activity_at",
        ])
        cd["messages"] = [
            _row_to_dict(m, ["id", "role", "content", "created_at"])
            for m in conv.messages
        ]
        conversations_data.append(cd)

    # ── Comments ────────────────────────────────────────────────
    comments_data = []
    if loan_ids:
        com_result = await db.execute(
            select(ApplicationComment)
            .where(ApplicationComment.application_id.in_(loan_ids))
            .order_by(ApplicationComment.created_at.desc())
        )
        comments = com_result.scalars().all()
        comments_data = [
            _row_to_dict(c, [
                "id", "application_id", "user_id", "content",
                "is_from_applicant", "read_at", "created_at",
            ])
            for c in comments
        ]

    # ── Notes ───────────────────────────────────────────────────
    notes_data = []
    if loan_ids:
        note_result = await db.execute(
            select(ApplicationNote)
            .where(ApplicationNote.application_id.in_(loan_ids))
            .order_by(ApplicationNote.created_at.desc())
        )
        notes = note_result.scalars().all()
        notes_data = [
            _row_to_dict(n, [
                "id", "application_id", "user_id", "content", "created_at",
            ])
            for n in notes
        ]

    # ── Credit Bureau Alerts ────────────────────────────────────
    alert_result = await db.execute(
        select(CreditBureauAlert)
        .where(CreditBureauAlert.user_id == user_id)
        .order_by(CreditBureauAlert.alert_date.desc())
    )
    alerts = alert_result.scalars().all()
    alerts_data = [
        _row_to_dict(a, [
            "id", "user_id", "alert_type", "severity", "status",
            "bureau_name", "bureau_reference",
            "title", "description",
            "other_institution", "other_product_type", "other_amount",
            "other_delinquency_days", "other_delinquency_amount",
            "action_taken", "action_notes", "acted_by", "acted_at",
            "alert_date", "received_at", "created_at",
        ])
        for a in alerts
    ]

    # ── Audit Logs ──────────────────────────────────────────────
    # Audit entries that relate to this customer's entities
    audit_data = []
    if loan_ids:
        # loans + the user entity itself
        audit_result = await db.execute(
            select(AuditLog)
            .where(
                (
                    (AuditLog.entity_type == "loan_application")
                    & AuditLog.entity_id.in_(loan_ids)
                )
                | (
                    (AuditLog.entity_type == "user")
                    & (AuditLog.entity_id == user_id)
                )
            )
            .order_by(AuditLog.created_at.desc())
            .limit(500)
        )
        audits = audit_result.scalars().all()
        audit_data = [
            _row_to_dict(a, [
                "id", "entity_type", "entity_id", "action",
                "user_id", "old_values", "new_values", "details",
                "ip_address", "created_at",
            ])
            for a in audits
        ]

    # ── Quick Stats ─────────────────────────────────────────────
    quick_stats = _compute_quick_stats(
        user, loans, payments_data, schedules_data,
        collection_records_data, collection_chats_data,
        comments_data, conversations_data,
    )

    return {
        "user": user_data,
        "profile": profile_data,
        "applications": loans_data,
        "payments": payments_data,
        "payment_schedules": schedules_data,
        "decisions": decisions_data,
        "disbursements": disbursements_data,
        "collection_records": collection_records_data,
        "collection_chats": collection_chats_data,
        "documents": documents_data,
        "credit_reports": credit_reports_data,
        "conversations": conversations_data,
        "comments": comments_data,
        "notes": notes_data,
        "credit_bureau_alerts": alerts_data,
        "audit_logs": audit_data,
        "quick_stats": quick_stats,
    }


def _compute_quick_stats(
    user: User,
    loans: list,
    payments: list[dict],
    schedules: list[dict],
    collection_records: list[dict],
    collection_chats: list[dict],
    comments: list[dict],
    conversations: list[dict],
) -> dict:
    """Compute the 6 KPI cards from pre-fetched data."""
    today = date.today()

    # 1. Total Lifetime Value  — interest + fees paid
    total_interest = 0.0
    total_fees = 0.0
    for s in schedules:
        if s.get("status") in ("paid", "partial"):
            total_interest += float(s.get("interest") or 0)
            total_fees += float(s.get("fee") or 0)
    total_lifetime_value = round(total_interest + total_fees, 2)

    # 2. Active Products
    active_loans = [
        ln for ln in loans if _ser(ln.status) == "disbursed"
    ]
    active_count = len(active_loans)
    total_outstanding = 0.0
    for ln in active_loans:
        # outstanding = sum of (amount_due - amount_paid) for remaining schedule entries
        for s in schedules:
            if s.get("loan_application_id") == ln.id and s.get("status") in ("upcoming", "due", "overdue", "partial"):
                total_outstanding += float(s.get("amount_due") or 0) - float(s.get("amount_paid") or 0)
    total_outstanding = round(total_outstanding, 2)

    # 3. Worst DPD
    worst_dpd = 0
    for ln in active_loans:
        for s in schedules:
            if (
                s.get("loan_application_id") == ln.id
                and s.get("status") in ("overdue", "partial")
            ):
                due = s.get("due_date")
                if due:
                    if isinstance(due, str):
                        due = date.fromisoformat(due)
                    dpd = (today - due).days
                    if dpd > worst_dpd:
                        worst_dpd = dpd

    # 4. Payment Success Rate
    total_due = 0
    on_time = 0
    for s in schedules:
        if s.get("status") in ("paid", "overdue", "partial"):
            total_due += 1
            if s.get("status") == "paid":
                on_time += 1
    payment_success_rate = round((on_time / total_due * 100) if total_due > 0 else 100, 1)

    # 5. Relationship Length
    first_created = None
    for ln in loans:
        ca = _ser(ln.created_at) if hasattr(ln, "created_at") else ln.get("created_at") if isinstance(ln, dict) else None
        # loans here are ORM objects
        if hasattr(ln, "created_at") and ln.created_at:
            ts = ln.created_at.date() if isinstance(ln.created_at, datetime) else ln.created_at
            if first_created is None or ts < first_created:
                first_created = ts
    relationship_length_days = (today - first_created).days if first_created else 0

    # 6. Last Contact
    last_contact = None
    last_contact_channel = None
    last_contact_direction = None

    # Check collection chats
    for ch in collection_chats:
        ca = ch.get("created_at")
        if ca and (last_contact is None or ca > last_contact):
            last_contact = ca
            last_contact_channel = ch.get("channel", "whatsapp")
            last_contact_direction = ch.get("direction")
    # Check comments
    for c in comments:
        ca = c.get("created_at")
        if ca and (last_contact is None or ca > last_contact):
            last_contact = ca
            last_contact_channel = "in-app"
            last_contact_direction = "inbound" if c.get("is_from_applicant") else "outbound"
    # Check conversations
    for conv in conversations:
        la = conv.get("last_activity_at")
        if la and (last_contact is None or la > last_contact):
            last_contact = la
            last_contact_channel = conv.get("channel", "web")
            last_contact_direction = "inbound"

    return {
        "total_lifetime_value": total_lifetime_value,
        "active_products": active_count,
        "total_outstanding": total_outstanding,
        "worst_dpd": worst_dpd,
        "payment_success_rate": payment_success_rate,
        "relationship_length_days": relationship_length_days,
        "last_contact": last_contact,
        "last_contact_channel": last_contact_channel,
        "last_contact_direction": last_contact_direction,
    }


# ---------------------------------------------------------------------------
# 2. Unified Timeline
# ---------------------------------------------------------------------------

async def get_customer_timeline(
    user_id: int,
    db: AsyncSession,
    *,
    categories: list[str] | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[dict]:
    """Build a unified chronological event feed for a customer."""

    # First get all loan ids for this customer
    loan_result = await db.execute(
        select(LoanApplication.id, LoanApplication.reference_number,
               LoanApplication.status, LoanApplication.created_at,
               LoanApplication.submitted_at, LoanApplication.decided_at,
               LoanApplication.disbursed_at, LoanApplication.amount_requested,
               LoanApplication.amount_approved)
        .where(LoanApplication.applicant_id == user_id)
    )
    loan_rows = loan_result.all()
    loan_ids = [r[0] for r in loan_rows]
    loan_refs = {r[0]: r[1] for r in loan_rows}

    events: list[dict] = []

    # ── Application events ──────────────────────────────────────
    for r in loan_rows:
        lid, ref, status, created, submitted, decided, disbursed, amt_req, amt_app = r
        events.append({
            "timestamp": _ser(created),
            "category": "application",
            "icon_type": "file-text",
            "title": f"Application {ref} created",
            "description": f"Amount requested: {_ser(amt_req)}",
            "actor": "customer",
            "entity_type": "loan_application",
            "entity_id": lid,
        })
        if submitted:
            events.append({
                "timestamp": _ser(submitted),
                "category": "application",
                "icon_type": "send",
                "title": f"Application {ref} submitted",
                "description": f"Amount: {_ser(amt_req)}",
                "actor": "customer",
                "entity_type": "loan_application",
                "entity_id": lid,
            })
        if decided:
            events.append({
                "timestamp": _ser(decided),
                "category": "application",
                "icon_type": "check-circle" if _ser(status) in ("approved", "disbursed", "accepted", "offer_sent") else "x-circle",
                "title": f"Application {ref} — {_ser(status).replace('_', ' ').title()}",
                "description": f"Approved amount: {_ser(amt_app)}" if amt_app else "",
                "actor": "system",
                "entity_type": "loan_application",
                "entity_id": lid,
            })
        if disbursed:
            events.append({
                "timestamp": _ser(disbursed),
                "category": "loan",
                "icon_type": "banknote",
                "title": f"Loan {ref} disbursed",
                "description": f"Amount: {_ser(amt_app or amt_req)}",
                "actor": "system",
                "entity_type": "loan_application",
                "entity_id": lid,
            })

    # ── Payments ────────────────────────────────────────────────
    if loan_ids:
        pay_result = await db.execute(
            select(Payment).where(Payment.loan_application_id.in_(loan_ids))
        )
        for p in pay_result.scalars().all():
            ref = loan_refs.get(p.loan_application_id, "")
            events.append({
                "timestamp": _ser(p.created_at),
                "category": "payment",
                "icon_type": "credit-card",
                "title": f"Payment received — {ref}",
                "description": f"Amount: {_ser(p.amount)} ({_ser(p.payment_type)})",
                "actor": "customer" if _ser(p.payment_type) == "online" else "officer",
                "entity_type": "payment",
                "entity_id": p.id,
            })

    # ── Overdue schedule entries ────────────────────────────────
    if loan_ids:
        ov_result = await db.execute(
            select(PaymentSchedule)
            .where(
                PaymentSchedule.loan_application_id.in_(loan_ids),
                PaymentSchedule.status.in_(["overdue", "partial"]),
            )
        )
        for s in ov_result.scalars().all():
            ref = loan_refs.get(s.loan_application_id, "")
            events.append({
                "timestamp": _ser(datetime.combine(s.due_date, datetime.min.time()).replace(tzinfo=timezone.utc)),
                "category": "payment",
                "icon_type": "alert-triangle",
                "title": f"Payment missed — {ref}",
                "description": f"Due: {_ser(s.amount_due)}, Paid: {_ser(s.amount_paid)}",
                "actor": "system",
                "entity_type": "payment_schedule",
                "entity_id": s.id,
            })

    # ── Collection records ──────────────────────────────────────
    if loan_ids:
        cr_result = await db.execute(
            select(CollectionRecord).where(CollectionRecord.loan_application_id.in_(loan_ids))
        )
        for cr in cr_result.scalars().all():
            ref = loan_refs.get(cr.loan_application_id, "")
            events.append({
                "timestamp": _ser(cr.created_at),
                "category": "collection",
                "icon_type": "phone-call",
                "title": f"Collection {_ser(cr.channel)} — {ref}",
                "description": f"Outcome: {_ser(cr.outcome)}. {cr.notes or ''}".strip(),
                "actor": "officer",
                "entity_type": "collection_record",
                "entity_id": cr.id,
            })

    # ── Collection chats ────────────────────────────────────────
    if loan_ids:
        cc_result = await db.execute(
            select(CollectionChat).where(CollectionChat.loan_application_id.in_(loan_ids))
        )
        for cc in cc_result.scalars().all():
            ref = loan_refs.get(cc.loan_application_id, "")
            events.append({
                "timestamp": _ser(cc.created_at),
                "category": "communication",
                "icon_type": "message-circle",
                "title": f"WhatsApp {'received' if _ser(cc.direction) == 'inbound' else 'sent'} — {ref}",
                "description": cc.message[:120] if cc.message else "",
                "actor": "customer" if _ser(cc.direction) == "inbound" else "officer",
                "entity_type": "collection_chat",
                "entity_id": cc.id,
            })

    # ── Documents ───────────────────────────────────────────────
    if loan_ids:
        doc_result = await db.execute(
            select(Document).where(Document.loan_application_id.in_(loan_ids))
        )
        for d in doc_result.scalars().all():
            ref = loan_refs.get(d.loan_application_id, "")
            events.append({
                "timestamp": _ser(d.created_at),
                "category": "document",
                "icon_type": "file-plus",
                "title": f"Document uploaded — {_ser(d.document_type)}",
                "description": f"{d.file_name} for {ref}",
                "actor": "customer",
                "entity_type": "document",
                "entity_id": d.id,
            })

    # ── Comments ────────────────────────────────────────────────
    if loan_ids:
        com_result = await db.execute(
            select(ApplicationComment).where(ApplicationComment.application_id.in_(loan_ids))
        )
        for c in com_result.scalars().all():
            events.append({
                "timestamp": _ser(c.created_at),
                "category": "communication",
                "icon_type": "message-square",
                "title": "Comment from applicant" if c.is_from_applicant else "Comment from staff",
                "description": c.content[:120] if c.content else "",
                "actor": "customer" if c.is_from_applicant else "officer",
                "entity_type": "comment",
                "entity_id": c.id,
            })

    # ── Notes ───────────────────────────────────────────────────
    if loan_ids:
        note_result = await db.execute(
            select(ApplicationNote).where(ApplicationNote.application_id.in_(loan_ids))
        )
        for n in note_result.scalars().all():
            events.append({
                "timestamp": _ser(n.created_at),
                "category": "communication",
                "icon_type": "sticky-note",
                "title": "Internal note added",
                "description": n.content[:120] if n.content else "",
                "actor": "officer",
                "entity_type": "note",
                "entity_id": n.id,
            })

    # ── Conversations (high-level) ──────────────────────────────
    conv_result = await db.execute(
        select(Conversation)
        .where(Conversation.participant_user_id == user_id)
    )
    for conv in conv_result.scalars().all():
        events.append({
            "timestamp": _ser(conv.created_at),
            "category": "communication",
            "icon_type": "bot",
            "title": f"AI Conversation started ({_ser(conv.channel)})",
            "description": f"State: {_ser(conv.current_state)}",
            "actor": "system",
            "entity_type": "conversation",
            "entity_id": conv.id,
        })

    # ── Audit logs ──────────────────────────────────────────────
    if loan_ids:
        audit_result = await db.execute(
            select(AuditLog)
            .where(
                (
                    (AuditLog.entity_type == "loan_application")
                    & AuditLog.entity_id.in_(loan_ids)
                )
                | (
                    (AuditLog.entity_type == "user")
                    & (AuditLog.entity_id == user_id)
                )
            )
            .limit(200)
        )
        for a in audit_result.scalars().all():
            events.append({
                "timestamp": _ser(a.created_at),
                "category": "system",
                "icon_type": "shield",
                "title": f"Audit: {a.action}",
                "description": a.details or f"{a.entity_type} #{a.entity_id}",
                "actor": "system",
                "entity_type": "audit_log",
                "entity_id": a.id,
            })

    # ── Filter & sort ───────────────────────────────────────────
    if categories:
        events = [e for e in events if e["category"] in categories]

    if search:
        term = search.lower()
        events = [
            e for e in events
            if term in (e.get("title") or "").lower()
            or term in (e.get("description") or "").lower()
        ]

    events.sort(key=lambda e: e["timestamp"] or "", reverse=True)

    return events[offset: offset + limit]


# ---------------------------------------------------------------------------
# 3. AI Summary
# ---------------------------------------------------------------------------

def _build_customer_context_text(data: dict) -> str:
    """Build a concise textual representation of customer data for the AI prompt."""
    lines: list[str] = []
    u = data.get("user", {})
    p = data.get("profile", {})
    qs = data.get("quick_stats", {})

    lines.append(f"Customer: {u.get('first_name', '')} {u.get('last_name', '')}")
    lines.append(f"Email: {u.get('email', '')}, Phone: {u.get('phone', '')}")
    lines.append(f"Member since: {u.get('created_at', 'unknown')}")

    if p:
        lines.append(f"Employment: {p.get('employer_name', 'N/A')}, {p.get('job_title', 'N/A')}")
        lines.append(f"Monthly income: {p.get('monthly_income', 'N/A')}, Expenses: {p.get('monthly_expenses', 'N/A')}")
        lines.append(f"Existing debt: {p.get('existing_debt', 'N/A')}")
        lines.append(f"ID verified: {p.get('id_verified', False)}, Status: {p.get('id_verification_status', 'N/A')}")

    lines.append(f"\nQuick Stats:")
    lines.append(f"  Lifetime value (interest+fees): {qs.get('total_lifetime_value', 0)}")
    lines.append(f"  Active products: {qs.get('active_products', 0)}, Outstanding: {qs.get('total_outstanding', 0)}")
    lines.append(f"  Worst DPD: {qs.get('worst_dpd', 0)}")
    lines.append(f"  Payment success rate: {qs.get('payment_success_rate', 100)}%")
    lines.append(f"  Relationship length: {qs.get('relationship_length_days', 0)} days")

    # Loans summary
    apps = data.get("applications", [])
    lines.append(f"\nApplications: {len(apps)}")
    for a in apps[:10]:
        lines.append(
            f"  - {a.get('reference_number')} | Status: {a.get('status')} | "
            f"Requested: {a.get('amount_requested')} | Approved: {a.get('amount_approved', 'N/A')} | "
            f"Term: {a.get('term_months')}m | Rate: {a.get('interest_rate', 'N/A')}%"
        )

    # Payment history summary
    payments = data.get("payments", [])
    lines.append(f"\nPayments: {len(payments)} total")
    for pay in payments[:5]:
        lines.append(
            f"  - {pay.get('payment_date')} | {pay.get('amount')} | {pay.get('payment_type')} | {pay.get('status')}"
        )

    # Schedule overview
    schedules = data.get("payment_schedules", [])
    overdue = [s for s in schedules if s.get("status") in ("overdue", "partial")]
    upcoming = [s for s in schedules if s.get("status") in ("upcoming", "due")]
    lines.append(f"\nSchedule: {len(schedules)} total installments, {len(overdue)} overdue, {len(upcoming)} upcoming")

    # Collections
    cr = data.get("collection_records", [])
    cc = data.get("collection_chats", [])
    if cr or cc:
        lines.append(f"\nCollections: {len(cr)} records, {len(cc)} chat messages")
        for r in cr[:5]:
            lines.append(
                f"  - {r.get('created_at')} | {r.get('channel')} | Outcome: {r.get('outcome')} | {r.get('notes', '')[:80]}"
            )

    # Credit reports
    creds = data.get("credit_reports", [])
    if creds:
        lines.append(f"\nCredit Reports: {len(creds)}")
        for c in creds[:3]:
            lines.append(f"  - {c.get('pulled_at')} | Score: {c.get('bureau_score', 'N/A')} | {c.get('provider')}")

    # Decisions
    decs = data.get("decisions", [])
    if decs:
        lines.append(f"\nDecisions: {len(decs)}")
        for d in decs[:5]:
            lines.append(
                f"  - App #{d.get('loan_application_id')} | Score: {d.get('credit_score', 'N/A')} | "
                f"Engine: {d.get('engine_outcome', 'N/A')} | UW action: {d.get('underwriter_action', 'N/A')}"
            )

    return "\n".join(lines)


async def generate_ai_summary(customer_data: dict) -> dict:
    """Generate an AI-powered customer account summary.

    Falls back to a rule-based summary if no OpenAI key is configured.
    """
    try:
        context = _build_customer_context_text(customer_data)
        qs = customer_data.get("quick_stats", {})

        # Try OpenAI
        if settings.openai_api_key:
            try:
                import openai
                client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

                prompt = f"""You are an expert loan officer assistant analysing a customer's complete profile for a lending company. Generate a concise intelligence brief.

CUSTOMER DATA:
{context}

Generate a JSON object with these fields:
- "summary_text": A 3-5 sentence narrative summary as described below. Write it like one colleague briefing another. Include: relationship length and product history, payment behavior pattern, the single most important thing to know NOW, any deviations from historical patterns, and 1-2 actionable recommendations.
- "sentiment": one of "positive", "neutral", "concerning", "critical" — reflects overall relationship health
- "highlights": array of 3-5 short bullet-point strings with key insights
- "risk_narrative": 1-2 sentence plain-language risk assessment
- "recommendations": array of objects with "text", "priority" ("high"/"medium"/"low"), "category" ("retention"/"collections"/"upsell"/"risk_mitigation"/"compliance")
- "confidence_score": float 0-1 representing how confident you are given data completeness

IMPORTANT: Return ONLY valid JSON, no markdown fencing."""

                resp = await client.chat.completions.create(
                    model="gpt-4.1",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1500,
                )
                raw = resp.choices[0].message.content.strip()
                # Strip markdown code fences if present
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                    if raw.endswith("```"):
                        raw = raw[:-3]
                return json.loads(raw)
            except Exception as e:
                logger.warning("OpenAI summary generation failed, falling back to rule-based: %s", e)

        # ── Rule-based fallback ─────────────────────────────────────
        return _rule_based_summary(customer_data, qs)
    except Exception as e:
        await log_error(e, db=None, module="services.customer360", function_name="generate_ai_summary")
        raise


def _rule_based_summary(data: dict, qs: dict) -> dict:
    """Simple rule-based summary when AI is unavailable."""
    u = data.get("user", {})
    apps = data.get("applications", [])
    name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
    active = qs.get("active_products", 0)
    dpd = qs.get("worst_dpd", 0)
    rate = qs.get("payment_success_rate", 100)
    days = qs.get("relationship_length_days", 0)

    # Determine sentiment
    if dpd > 60:
        sentiment = "critical"
    elif dpd > 30 or rate < 70:
        sentiment = "concerning"
    elif dpd > 0 or rate < 90:
        sentiment = "neutral"
    else:
        sentiment = "positive"

    months = days // 30
    summary_parts = [
        f"{name} has been a customer for {months} months with {len(apps)} application(s) and {active} active product(s).",
    ]
    if rate >= 90:
        summary_parts.append(f"Payment track record is strong at {rate}% on-time.")
    elif rate >= 70:
        summary_parts.append(f"Payment compliance is moderate at {rate}% on-time.")
    else:
        summary_parts.append(f"Payment compliance is concerning at only {rate}% on-time.")

    if dpd > 0:
        summary_parts.append(f"Currently {dpd} days past due on at least one account.")
    else:
        summary_parts.append("All accounts are current with no arrears.")

    highlights = []
    highlights.append(f"Relationship: {months} months, {len(apps)} applications")
    highlights.append(f"Payment success: {rate}%")
    highlights.append(f"Active products: {active}, Outstanding: {qs.get('total_outstanding', 0)}")
    if dpd > 0:
        highlights.append(f"Worst DPD: {dpd} days")

    risk = "Low risk — strong payment history." if sentiment == "positive" else \
           "Moderate risk — some payment irregularities." if sentiment == "neutral" else \
           "Elevated risk — payment issues detected, monitor closely." if sentiment == "concerning" else \
           "High risk — significant arrears, immediate attention required."

    recs = []
    if sentiment in ("concerning", "critical"):
        recs.append({"text": "Review account for collections follow-up", "priority": "high", "category": "collections"})
    if rate >= 90 and active > 0 and dpd == 0:
        recs.append({"text": "Customer qualifies for credit upgrade or upsell", "priority": "medium", "category": "upsell"})
    if days < 90:
        recs.append({"text": "New customer — monitor first 3 payments closely", "priority": "medium", "category": "risk_mitigation"})

    return {
        "summary_text": " ".join(summary_parts),
        "sentiment": sentiment,
        "highlights": highlights,
        "risk_narrative": risk,
        "recommendations": recs,
        "confidence_score": 0.6,
    }


# ---------------------------------------------------------------------------
# 4. Ask AI (Q&A)
# ---------------------------------------------------------------------------

async def ask_ai_about_customer(
    customer_data: dict,
    question: str,
    history: list[dict] | None = None,
) -> dict:
    """Answer a free-form question about the customer using AI."""
    try:
        context = _build_customer_context_text(customer_data)

        if settings.openai_api_key:
            try:
                import openai
                client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

                system_msg = f"""You are an expert lending advisor. You have access to the full customer data below. Answer the officer's question accurately, citing specific data points (loan IDs, dates, amounts). Never fabricate numbers — only use what is in the data. If data is insufficient, say so.

CUSTOMER DATA:
{context}"""

                messages = [{"role": "system", "content": system_msg}]
                if history:
                    for h in history[-6:]:  # Keep last 6 turns
                        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
                messages.append({"role": "user", "content": question})

                resp = await client.chat.completions.create(
                    model="gpt-4.1",
                    messages=messages,
                    temperature=0.2,
                    max_tokens=1000,
                )
                answer = resp.choices[0].message.content.strip()
                return {"answer": answer, "citations": []}
            except Exception as e:
                logger.warning("OpenAI ask-ai failed: %s", e)

        # Fallback
        return {
            "answer": "AI is not available. Please review the customer data manually in the tabs.",
            "citations": [],
        }
    except Exception as e:
        await log_error(e, db=None, module="services.customer360", function_name="ask_ai_about_customer")
        raise
