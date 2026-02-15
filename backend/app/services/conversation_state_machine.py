"""Conversation state machine for Customer Support flow.

Enforces valid state transitions per the spec. Any state can transition to
ESCALATED_TO_HUMAN or WITHDRAWN. EXPIRED can reactivate to APPLICATION_IN_PROGRESS.
"""

from typing import Callable

from app.models.conversation import ConversationState

# Valid transitions: from_state -> set of allowed to_states
TRANSITIONS: dict[ConversationState, set[ConversationState]] = {
    ConversationState.INITIATED: {
        ConversationState.DISCOVERY,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
        ConversationState.EXPIRED,
    },
    ConversationState.DISCOVERY: {
        ConversationState.APPLICATION_IN_PROGRESS,
        ConversationState.SERVICING,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
        ConversationState.EXPIRED,
    },
    ConversationState.APPLICATION_IN_PROGRESS: {
        ConversationState.DOCUMENTS_PENDING,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
        ConversationState.EXPIRED,
    },
    ConversationState.DOCUMENTS_PENDING: {
        ConversationState.VERIFICATION_IN_PROGRESS,
        ConversationState.APPLICATION_IN_PROGRESS,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
        ConversationState.EXPIRED,
    },
    ConversationState.VERIFICATION_IN_PROGRESS: {
        ConversationState.CREDIT_CHECK_CONSENT,
        ConversationState.DOCUMENTS_PENDING,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
        ConversationState.EXPIRED,
    },
    ConversationState.CREDIT_CHECK_CONSENT: {
        ConversationState.CREDIT_CHECK_IN_PROGRESS,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
        ConversationState.EXPIRED,
    },
    ConversationState.CREDIT_CHECK_IN_PROGRESS: {
        ConversationState.DECISION_RENDERED,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
        ConversationState.EXPIRED,
    },
    ConversationState.DECISION_RENDERED: {
        ConversationState.OFFER_PRESENTED,
        ConversationState.DECLINED,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
        ConversationState.EXPIRED,
    },
    ConversationState.OFFER_PRESENTED: {
        ConversationState.OFFER_ACCEPTED,
        ConversationState.WITHDRAWN,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.EXPIRED,
    },
    ConversationState.OFFER_ACCEPTED: {
        ConversationState.DISBURSEMENT_PROCESSING,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
        ConversationState.EXPIRED,
    },
    ConversationState.DISBURSEMENT_PROCESSING: {
        ConversationState.DISBURSED,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
        ConversationState.EXPIRED,
    },
    ConversationState.DISBURSED: {
        ConversationState.SERVICING,
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
    },
    ConversationState.DECLINED: {
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
    },
    ConversationState.WITHDRAWN: set(),
    ConversationState.EXPIRED: {
        ConversationState.APPLICATION_IN_PROGRESS,
        ConversationState.DISCOVERY,
    },
    ConversationState.ESCALATED_TO_HUMAN: {
        ConversationState.APPLICATION_IN_PROGRESS,
        ConversationState.DOCUMENTS_PENDING,
        ConversationState.VERIFICATION_IN_PROGRESS,
        ConversationState.CREDIT_CHECK_CONSENT,
        ConversationState.DECISION_RENDERED,
        ConversationState.OFFER_PRESENTED,
        ConversationState.DISBURSEMENT_PROCESSING,
        ConversationState.SERVICING,
    },
    ConversationState.SERVICING: {
        ConversationState.ESCALATED_TO_HUMAN,
        ConversationState.WITHDRAWN,
    },
}


def can_transition(
    from_state: ConversationState,
    to_state: ConversationState,
) -> bool:
    """Check if a transition from from_state to to_state is valid."""
    allowed = TRANSITIONS.get(from_state, set())
    return to_state in allowed


def get_allowed_transitions(from_state: ConversationState) -> set[ConversationState]:
    """Return the set of states that from_state can transition to."""
    return TRANSITIONS.get(from_state, set())


def is_terminal_state(state: ConversationState) -> bool:
    """Return True if the state is terminal (no further transitions typically)."""
    return state in (
        ConversationState.WITHDRAWN,
        ConversationState.DECLINED,
        ConversationState.DISBURSED,
    )
