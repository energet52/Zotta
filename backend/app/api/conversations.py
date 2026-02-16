"""Conversation API for Customer Support chat."""

import random
import string
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationChannel,
    ConversationEntryPoint,
    ConversationState,
    MessageRole,
)
from app.models.user import User, UserRole
from app.auth_utils import get_optional_user, get_current_user, require_roles
from app.models.loan import LoanApplication, LoanStatus, LoanPurpose
from app.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationMessageResponse,
    SendMessageRequest,
    StartApplicationRequest,
    LoanApplicationResponse,
)
from app.services.error_logger import log_error
import logging

router = APIRouter()


def _can_access(current_user: User | None, conv: Conversation) -> bool:
    """Check if user can access this conversation (participant or agent)."""
    if current_user is None:
        return conv.participant_user_id is None  # Anonymous conversation
    if conv.participant_user_id == current_user.id:
        return True
    if conv.assigned_agent_id == current_user.id:
        return True
    if current_user.role in (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER, UserRole.JUNIOR_UNDERWRITER):
        return True
    return False


@router.post("/", response_model=ConversationDetailResponse, status_code=201)
async def create_conversation(
    data: ConversationCreate | None = None,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation or resume an existing one for the user."""
    try:
        data = data or ConversationCreate()

        # Resume: if user is logged in, look for active non-escalated conversation
        if current_user:
            result = await db.execute(
                select(Conversation)
                .where(
                    Conversation.participant_user_id == current_user.id,
                    Conversation.channel == ConversationChannel.WEB,
                    Conversation.assigned_agent_id.is_(None),
                    Conversation.current_state.not_in([
                        ConversationState.WITHDRAWN,
                        ConversationState.EXPIRED,
                        ConversationState.DECLINED,
                    ]),
                )
                .order_by(Conversation.last_activity_at.desc())
                .options(selectinload(Conversation.messages), selectinload(Conversation.loan_application))
            )
            existing = result.scalars().first()
            if existing:
                return _to_detail(existing)
        else:
            # Anonymous: always create new
            pass

        channel = ConversationChannel(data.channel or "web")
        entry_point = None
        if data.entry_point:
            try:
                entry_point = ConversationEntryPoint(data.entry_point)
            except ValueError:
                pass

        conv = Conversation(
            channel=channel,
            participant_user_id=current_user.id if current_user else None,
            current_state=ConversationState.INITIATED,
            entry_point=entry_point,
            entry_context=data.entry_context,
        )
        db.add(conv)
        await db.flush()

        # Re-fetch with eager loading to avoid lazy-load in async context
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conv.id)
            .options(selectinload(Conversation.messages), selectinload(Conversation.loan_application))
        )
        conv = result.scalar_one()
        return _to_detail(conv)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.conversations", function_name="create_conversation")
        raise


@router.get("/", response_model=list[ConversationResponse])
async def list_conversations(
    status_filter: str | None = Query(None, description="Filter by state: active, escalated, all"),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER, UserRole.JUNIOR_UNDERWRITER)),
    db: AsyncSession = Depends(get_db),
):
    """List conversations (lender agent queue)."""
    try:
        q = select(Conversation).order_by(Conversation.last_activity_at.desc())
        if status_filter == "escalated":
            q = q.where(Conversation.assigned_agent_id.isnot(None))
        elif status_filter == "active":
            q = q.where(
                Conversation.current_state.not_in([
                    ConversationState.WITHDRAWN,
                    ConversationState.EXPIRED,
                    ConversationState.DECLINED,
                    ConversationState.DISBURSED,
                ])
            )
        result = await db.execute(q)
        convs = result.scalars().all()
        return [ConversationResponse.model_validate(c) for c in convs[:50]]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.conversations", function_name="list_conversations")
        raise


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: int,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a conversation with full message history."""
    try:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(
                selectinload(Conversation.messages),
                selectinload(Conversation.loan_application),
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # For list endpoint, agents can view any. For get, we check access.
        if current_user:
            if current_user.role not in (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER, UserRole.JUNIOR_UNDERWRITER):
                if not _can_access(current_user, conv):
                    raise HTTPException(status_code=403, detail="Not authorized to view this conversation")
        else:
            if conv.participant_user_id is not None:
                raise HTTPException(status_code=401, detail="Authentication required")

        return _to_detail(conv)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.conversations", function_name="get_conversation")
        raise


@router.post("/{conversation_id}/messages", response_model=ConversationMessageResponse)
async def send_message(
    conversation_id: int,
    data: SendMessageRequest,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and receive AI response."""
    try:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(
                selectinload(Conversation.messages),
                selectinload(Conversation.loan_application),
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if not _can_access(current_user, conv):
            raise HTTPException(status_code=403, detail="Not authorized for this conversation")

        # Don't allow new messages if escalated to human (unless agent)
        if conv.assigned_agent_id and (
            current_user is None or current_user.role == UserRole.APPLICANT
        ):
            raise HTTPException(
                status_code=400,
                detail="This conversation has been escalated. A team member will respond shortly.",
            )

        # Save user message
        user_msg = ConversationMessage(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=data.content.strip(),
        )
        db.add(user_msg)
        await db.flush()

        # Process with AI
        from app.services.conversation_processor import process_conversation_message
        reply_text, metadata = await process_conversation_message(conv, data.content.strip(), db)

        # Save assistant response
        assistant_msg = ConversationMessage(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=reply_text,
            metadata_=metadata,
        )
        db.add(assistant_msg)
        await db.flush()
        await db.refresh(conv)

        return ConversationMessageResponse(
            id=assistant_msg.id,
            conversation_id=conversation_id,
            role=assistant_msg.role.value,
            content=assistant_msg.content,
            metadata=assistant_msg.metadata_,
            created_at=assistant_msg.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.conversations", function_name="send_message")
        raise


def _generate_reference() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=8))
    return f"ZOT-{datetime.now().year}-{suffix}"


@router.post("/{conversation_id}/start-application", response_model=LoanApplicationResponse, status_code=201)
async def start_application_from_conversation(
    conversation_id: int,
    data: StartApplicationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a draft loan application from conversation and link it. Requires authenticated user."""
    try:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.loan_application))
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conv.participant_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your conversation")
        if conv.loan_application_id:
            raise HTTPException(status_code=400, detail="Application already started for this conversation")

        purpose = LoanPurpose(data.purpose) if data.purpose in [p.value for p in LoanPurpose] else LoanPurpose.PERSONAL
        app = LoanApplication(
            reference_number=_generate_reference(),
            applicant_id=current_user.id,
            amount_requested=data.amount_requested,
            term_months=data.term_months,
            purpose=purpose,
            purpose_description=None,
            status=LoanStatus.DRAFT,
            conversation_id=conversation_id,
        )
        db.add(app)
        await db.flush()
        conv.loan_application_id = app.id
        conv.current_state = ConversationState.APPLICATION_IN_PROGRESS
        await db.refresh(app)
        return LoanApplicationResponse.model_validate(app)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.conversations", function_name="start_application_from_conversation")
        raise


def _to_detail(conv: Conversation) -> ConversationDetailResponse:
    """Build ConversationDetailResponse from Conversation."""
    app_summary = None
    if conv.loan_application_id and conv.loan_application:
        app = conv.loan_application
        app_summary = {
            "id": app.id,
            "reference_number": app.reference_number,
            "status": app.status.value,
            "amount_requested": float(app.amount_requested),
            "term_months": app.term_months,
        }
    return ConversationDetailResponse(
        id=conv.id,
        channel=conv.channel.value,
        current_state=conv.current_state.value,
        loan_application_id=conv.loan_application_id,
        entry_point=conv.entry_point.value if conv.entry_point else None,
        assigned_agent_id=conv.assigned_agent_id,
        escalated_at=conv.escalated_at,
        escalation_reason=conv.escalation_reason,
        created_at=conv.created_at,
        last_activity_at=conv.last_activity_at,
        messages=[
            ConversationMessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role.value,
                content=m.content,
                metadata=m.metadata_,
                created_at=m.created_at,
            )
            for m in (conv.messages or [])
        ],
        application_summary=app_summary,
    )
