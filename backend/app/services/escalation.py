"""Escalation logic for AI-to-human handoff.

Mandatory triggers always require human takeover.
Soft triggers flag for review but don't immediately transfer.
"""

from datetime import datetime, timezone

# Configurable thresholds
MANDATORY_TRIGGERS = [
    "policy_exception",
    "identity_verification_failure",
    "fraud_indicators",
    "complex_credit",
    "complaint",
    "regulatory_requirement",
    "high_value",
    "restructuring_hardship",
    "legal_litigation",
]

SOFT_TRIGGERS = [
    "sentiment_deterioration",
    "conversation_looping",
    "unusual_request",
    "borderline_decision",
    "high_value_prospect",
    "co_browsing_needed",
]


def should_escalate_mandatory(reason: str) -> bool:
    """Check if reason is a mandatory escalation trigger."""
    return reason in MANDATORY_TRIGGERS or reason == "borrower_requested_human"


def should_escalate_soft(reason: str) -> bool:
    """Check if reason is a soft escalation trigger."""
    return reason in SOFT_TRIGGERS


def create_escalation_brief(
    borrower_name: str | None,
    request_type: str,
    summary: str,
    stage: str,
    outstanding_items: list[str],
    escalation_reason: str,
    recommended_steps: list[str],
) -> dict:
    """Build structured handoff brief for human agent."""
    return {
        "borrower_name": borrower_name or "Unknown",
        "request_type": request_type,
        "summary": summary,
        "stage": stage,
        "outstanding_items": outstanding_items,
        "escalation_reason": escalation_reason,
        "recommended_steps": recommended_steps,
        "handoff_at": datetime.now(timezone.utc).isoformat(),
    }
