"""AI-powered collection sequence intelligence.

Provides: sequence generation, template generation, sequence optimization,
and effectiveness analytics.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select, case as sa_case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.collection_sequence import (
    CollectionSequence, SequenceStep, MessageTemplate,
    SequenceEnrollment, StepExecution,
)
from app.models.collections_ext import CollectionCase

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────

def _openai_available() -> bool:
    return bool(settings.openai_api_key)


async def _chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 2000) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def _strip_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


AVAILABLE_VARIABLES = [
    "{{name}}", "{{first_name}}", "{{amount_due}}", "{{total_overdue}}",
    "{{due_date}}", "{{dpd}}", "{{ref}}", "{{payment_link}}",
    "{{promise_amount}}", "{{promise_date}}",
]


# ── 1. Generate Sequence ─────────────────────────────────────

async def generate_sequence(
    description: str,
    delinquency_stage: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """Generate a multi-step collection sequence from natural language."""

    stage_context = {
        "early_1_30": "Early stage (1-30 days past due). Borrowers are typically just forgetful or experiencing minor cash flow issues. Tone should be friendly and helpful.",
        "mid_31_60": "Mid stage (31-60 days past due). Borrowers may be experiencing financial difficulty. Tone escalates to firm but empathetic. Offer payment plans.",
        "late_61_90": "Late stage (61-90 days past due). Serious delinquency. Urgent tone with clear consequences. Push settlement offers.",
        "severe_90_plus": "Severe stage (90+ days past due). Pre-legal. Final notices. Maximum urgency with legal action warnings.",
    }

    context = stage_context.get(delinquency_stage, "General collection stage.")

    if _openai_available():
        try:
            prompt = f"""Design an optimal collection notification sequence for a lending company.

Description: {description}
Delinquency stage: {delinquency_stage}
Context: {context}

Available channels: whatsapp, sms, email, phone
Available action types: send_message, create_task, escalate, create_ptp_request, settlement_offer
Available template variables: {', '.join(AVAILABLE_VARIABLES)}

Return ONLY valid JSON with this structure:
{{
  "name": "sequence name",
  "description": "brief description",
  "steps": [
    {{
      "step_number": 1,
      "day_offset": 1,
      "channel": "whatsapp",
      "action_type": "send_message",
      "message": "template message text with {{{{variables}}}}",
      "tone": "friendly|firm|urgent|final",
      "send_time": "09:00",
      "wait_for_response_hours": 24,
      "condition": null
    }}
  ],
  "summary": "strategy explanation"
}}"""

            raw = await _chat([
                {"role": "system", "content": "You are a collections strategy expert designing optimal notification sequences for a Caribbean lending company. Focus on compliance, empathy, and effectiveness."},
                {"role": "user", "content": prompt},
            ], temperature=0.4, max_tokens=3000)
            result = json.loads(_strip_json(raw))
            result["ai_generated"] = True
            return result
        except Exception as e:
            logger.warning("AI sequence generation failed: %s", e)

    # Fallback: generate deterministic sequence based on stage
    return _fallback_sequence(delinquency_stage, description)


def _fallback_sequence(stage: str, description: str) -> dict:
    """Deterministic fallback when OpenAI is unavailable."""
    templates = {
        "early_1_30": [
            {"step_number": 1, "day_offset": 1, "channel": "whatsapp", "action_type": "send_message", "message": "Hi {{name}}, this is a friendly reminder that your payment of TTD {{amount_due}} for loan {{ref}} was due on {{due_date}}. Please make your payment at your earliest convenience.", "tone": "friendly", "send_time": "09:00", "wait_for_response_hours": 48},
            {"step_number": 2, "day_offset": 5, "channel": "whatsapp", "action_type": "send_message", "message": "Hi {{name}}, your payment of TTD {{amount_due}} for loan {{ref}} is now {{dpd}} days overdue. Please arrange payment or contact us to discuss options.", "tone": "friendly", "send_time": "10:00", "wait_for_response_hours": 24},
            {"step_number": 3, "day_offset": 10, "channel": "sms", "action_type": "send_message", "message": "Zotta: Payment of TTD {{amount_due}} for {{ref}} is {{dpd}} days overdue. Please pay or contact us.", "tone": "firm", "send_time": "09:00", "wait_for_response_hours": 24},
            {"step_number": 4, "day_offset": 15, "channel": "whatsapp", "action_type": "send_message", "message": "Hi {{name}}, your account {{ref}} is now {{dpd}} days overdue (TTD {{total_overdue}}). We'd like to help you get back on track. Reply to discuss a payment plan.", "tone": "firm", "send_time": "10:00", "wait_for_response_hours": 48},
            {"step_number": 5, "day_offset": 21, "channel": "phone", "action_type": "create_task", "message": "Call borrower to discuss payment arrangements for {{ref}}", "tone": "firm", "send_time": "10:00", "wait_for_response_hours": 0},
            {"step_number": 6, "day_offset": 28, "channel": "whatsapp", "action_type": "create_ptp_request", "message": "Hi {{name}}, your payment for loan {{ref}} is significantly overdue. Please contact us today to make a promise to pay arrangement.", "tone": "urgent", "send_time": "09:00", "wait_for_response_hours": 24},
        ],
        "mid_31_60": [
            {"step_number": 1, "day_offset": 31, "channel": "whatsapp", "action_type": "send_message", "message": "Hi {{name}}, your account {{ref}} is now {{dpd}} days past due (TTD {{total_overdue}}). Immediate attention is required. Please contact us to arrange payment.", "tone": "firm", "send_time": "09:00", "wait_for_response_hours": 24},
            {"step_number": 2, "day_offset": 35, "channel": "phone", "action_type": "create_task", "message": "Priority call: Account {{ref}} is {{dpd}} DPD. Discuss payment plan options.", "tone": "firm", "send_time": "10:00", "wait_for_response_hours": 0},
            {"step_number": 3, "day_offset": 40, "channel": "whatsapp", "action_type": "settlement_offer", "message": "Hi {{name}}, we want to help resolve your account {{ref}} (TTD {{total_overdue}} overdue). We can offer a flexible payment plan. Reply to discuss.", "tone": "firm", "send_time": "09:00", "wait_for_response_hours": 48},
            {"step_number": 4, "day_offset": 50, "channel": "sms", "action_type": "send_message", "message": "URGENT: Zotta account {{ref}} is {{dpd}} days overdue. Contact us immediately to avoid further action.", "tone": "urgent", "send_time": "09:00", "wait_for_response_hours": 24},
            {"step_number": 5, "day_offset": 55, "channel": "phone", "action_type": "escalate", "message": "Escalation: Account {{ref}} approaching 60 DPD. Senior agent review required.", "tone": "urgent", "send_time": "10:00", "wait_for_response_hours": 0},
        ],
        "late_61_90": [
            {"step_number": 1, "day_offset": 61, "channel": "whatsapp", "action_type": "send_message", "message": "IMPORTANT: {{name}}, your account {{ref}} is now {{dpd}} days past due with TTD {{total_overdue}} outstanding. Immediate action is required to avoid legal proceedings.", "tone": "urgent", "send_time": "09:00", "wait_for_response_hours": 24},
            {"step_number": 2, "day_offset": 65, "channel": "phone", "action_type": "create_task", "message": "Urgent call: {{ref}} at {{dpd}} DPD. Final settlement discussion before legal referral.", "tone": "urgent", "send_time": "09:00", "wait_for_response_hours": 0},
            {"step_number": 3, "day_offset": 70, "channel": "whatsapp", "action_type": "settlement_offer", "message": "{{name}}, this is a final opportunity to resolve account {{ref}} (TTD {{total_overdue}}). We can offer a settlement arrangement. This must be addressed within 7 days.", "tone": "final", "send_time": "09:00", "wait_for_response_hours": 48},
            {"step_number": 4, "day_offset": 80, "channel": "whatsapp", "action_type": "escalate", "message": "FINAL NOTICE: {{name}}, account {{ref}} will be referred for legal action if not resolved within 10 days. Contact us immediately.", "tone": "final", "send_time": "09:00", "wait_for_response_hours": 24},
        ],
        "severe_90_plus": [
            {"step_number": 1, "day_offset": 91, "channel": "whatsapp", "action_type": "send_message", "message": "FINAL NOTICE: {{name}}, your account {{ref}} (TTD {{total_overdue}}) is being prepared for legal proceedings. Contact us within 48 hours for a last resolution opportunity.", "tone": "final", "send_time": "09:00", "wait_for_response_hours": 48},
            {"step_number": 2, "day_offset": 95, "channel": "phone", "action_type": "escalate", "message": "Legal referral review: Account {{ref}} at {{dpd}} DPD. Final attempt before legal handover.", "tone": "final", "send_time": "09:00", "wait_for_response_hours": 0},
            {"step_number": 3, "day_offset": 100, "channel": "whatsapp", "action_type": "settlement_offer", "message": "{{name}}, before proceeding with legal action on {{ref}}, we are offering a final settlement option for TTD {{total_overdue}}. Please respond within 5 days.", "tone": "final", "send_time": "09:00", "wait_for_response_hours": 120},
        ],
    }

    steps = templates.get(stage, templates["early_1_30"])
    name_map = {
        "early_1_30": "Early Stage Recovery",
        "mid_31_60": "Mid Stage Recovery",
        "late_61_90": "Late Stage Recovery",
        "severe_90_plus": "Severe Delinquency Recovery",
    }

    return {
        "name": name_map.get(stage, "Collection Sequence"),
        "description": description or f"Auto-generated sequence for {stage}",
        "steps": steps,
        "summary": f"Deterministic {len(steps)}-step sequence for {stage} stage. OpenAI unavailable.",
        "ai_generated": False,
    }


# ── 2. Optimize Sequence ─────────────────────────────────────

async def optimize_sequence(
    sequence_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    """Analyze execution history and recommend optimizations."""

    result = await db.execute(
        select(CollectionSequence)
        .options(selectinload(CollectionSequence.steps))
        .where(CollectionSequence.id == sequence_id)
    )
    seq = result.scalar_one_or_none()
    if not seq:
        return {"error": "Sequence not found"}

    # Gather step-level analytics
    analytics = await compute_sequence_analytics(sequence_id, db)

    if _openai_available() and analytics.get("step_stats"):
        try:
            prompt = f"""Analyze this collection notification sequence and suggest optimizations.

Sequence: {seq.name}
Stage: {seq.delinquency_stage}
Description: {seq.description}

Steps and their performance:
{json.dumps(analytics.get('step_stats', []), indent=2, default=str)}

Overall metrics:
- Total enrollments: {analytics.get('total_enrollments', 0)}
- Completion rate: {analytics.get('completion_rate', 0):.1f}%
- Average response rate: {analytics.get('avg_response_rate', 0):.1f}%
- Average payment rate: {analytics.get('avg_payment_rate', 0):.1f}%

Provide specific, actionable recommendations. Return ONLY valid JSON:
{{
  "summary": "overall analysis",
  "score": 75,
  "recommendations": [
    {{
      "step_number": 1,
      "type": "timing|channel|message|add_step|remove_step",
      "current": "current configuration",
      "suggested": "suggested change",
      "rationale": "why this change",
      "projected_impact": "+X% response rate",
      "risk": "low|medium|high"
    }}
  ],
  "ai_powered": true
}}"""

            raw = await _chat([
                {"role": "system", "content": "You are a collections optimization expert. Analyze notification sequence performance and suggest data-driven improvements."},
                {"role": "user", "content": prompt},
            ], temperature=0.3, max_tokens=2000)
            result = json.loads(_strip_json(raw))
            result["ai_powered"] = True
            return result
        except Exception as e:
            logger.warning("AI optimization failed: %s", e)

    # Deterministic fallback
    recs = []
    for ss in analytics.get("step_stats", []):
        if ss.get("response_rate", 0) < 10 and ss.get("total_executions", 0) > 5:
            recs.append({
                "step_number": ss["step_number"],
                "type": "message",
                "current": f"Step {ss['step_number']} via {ss.get('channel', '?')}",
                "suggested": "Revise message content or change channel",
                "rationale": f"Response rate is only {ss.get('response_rate', 0):.1f}%",
                "projected_impact": "Potential +5-10% response rate",
                "risk": "low",
            })

    return {
        "summary": f"Analysis of {seq.name}: {len(recs)} optimization opportunities found.",
        "score": max(0, 100 - len(recs) * 15),
        "recommendations": recs,
        "ai_powered": False,
    }


# ── 3. Generate Template ─────────────────────────────────────

async def generate_template(
    channel: str,
    tone: str,
    category: str,
    context: str | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Generate a message template using AI."""

    if _openai_available():
        try:
            channel_rules = {
                "sms": "Keep under 160 characters. Be concise.",
                "whatsapp": "Keep concise but warm. Can be up to 1000 characters.",
                "email": "Professional tone. Include subject line.",
            }

            prompt = f"""Create a collection message template for a Caribbean lending company.

Channel: {channel}
Tone: {tone}
Category: {category}
{f'Additional context: {context}' if context else ''}
Channel rules: {channel_rules.get(channel, 'Professional tone.')}

Available variables: {', '.join(AVAILABLE_VARIABLES)}

Return ONLY valid JSON:
{{
  "name": "template name",
  "body": "message template text with {{{{variables}}}}",
  "subject": "email subject if applicable, else null",
  "variables": ["list", "of", "used", "variables"],
  "explanation": "why this template is effective"
}}"""

            raw = await _chat([
                {"role": "system", "content": "You are a collections communication expert. Create compliant, empathetic, and effective collection message templates."},
                {"role": "user", "content": prompt},
            ], temperature=0.5, max_tokens=1000)
            result = json.loads(_strip_json(raw))
            result["ai_generated"] = True
            return result
        except Exception as e:
            logger.warning("AI template generation failed: %s", e)

    # Fallback templates
    fallbacks = {
        "reminder": {
            "name": f"{tone.title()} {channel.title()} Reminder",
            "body": "Hi {{name}}, your payment of TTD {{amount_due}} for loan {{ref}} is {{dpd}} days overdue. Please make a payment at your earliest convenience.",
            "subject": "Payment Reminder - Account {{ref}}" if channel == "email" else None,
            "variables": ["name", "amount_due", "ref", "dpd"],
        },
        "demand": {
            "name": f"{tone.title()} {channel.title()} Demand",
            "body": "Dear {{name}}, your account {{ref}} has TTD {{total_overdue}} outstanding ({{dpd}} days overdue). Immediate payment is required.",
            "subject": "Urgent: Payment Required - {{ref}}" if channel == "email" else None,
            "variables": ["name", "ref", "total_overdue", "dpd"],
        },
    }
    tmpl = fallbacks.get(category, fallbacks["reminder"])
    tmpl["ai_generated"] = False
    tmpl["explanation"] = "Fallback template generated without AI."
    return tmpl


# ── 4. Sequence Analytics ────────────────────────────────────

async def compute_sequence_analytics(
    sequence_id: int | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Compute per-step and aggregate analytics for a sequence or all sequences."""

    if sequence_id:
        return await _single_sequence_analytics(sequence_id, db)
    return await _portfolio_analytics(db)


async def _single_sequence_analytics(sequence_id: int, db: AsyncSession) -> dict:
    # Total enrollments
    enroll_q = select(func.count()).select_from(SequenceEnrollment).where(
        SequenceEnrollment.sequence_id == sequence_id,
    )
    total_enrollments = (await db.execute(enroll_q)).scalar() or 0

    completed_q = select(func.count()).select_from(SequenceEnrollment).where(
        SequenceEnrollment.sequence_id == sequence_id,
        SequenceEnrollment.status == "completed",
    )
    completed = (await db.execute(completed_q)).scalar() or 0

    # Per-step stats
    steps_q = select(SequenceStep).where(
        SequenceStep.sequence_id == sequence_id,
    ).order_by(SequenceStep.step_number)
    steps = (await db.execute(steps_q)).scalars().all()

    step_stats = []
    total_response_rate = 0
    total_payment_rate = 0
    step_count = 0

    for step in steps:
        exec_q = select(
            func.count().label("total"),
            func.sum(sa_case((StepExecution.borrower_responded == True, 1), else_=0)).label("responded"),
            func.sum(sa_case((StepExecution.payment_after == True, 1), else_=0)).label("paid"),
            func.sum(sa_case((StepExecution.delivery_status == "delivered", 1), else_=0)).label("delivered"),
            func.sum(sa_case((StepExecution.delivery_status == "failed", 1), else_=0)).label("failed"),
        ).where(StepExecution.step_id == step.id)
        row = (await db.execute(exec_q)).one()

        total = row.total or 0
        responded = row.responded or 0
        paid = row.paid or 0
        delivered = row.delivered or 0
        failed = row.failed or 0

        resp_rate = (responded / total * 100) if total > 0 else 0
        pay_rate = (paid / total * 100) if total > 0 else 0

        step_stats.append({
            "step_number": step.step_number,
            "day_offset": step.day_offset,
            "channel": step.channel,
            "action_type": step.action_type,
            "total_executions": total,
            "delivered": delivered,
            "failed": failed,
            "response_rate": round(resp_rate, 1),
            "payment_rate": round(pay_rate, 1),
            "effectiveness_score": step.ai_effectiveness_score,
        })

        if total > 0:
            total_response_rate += resp_rate
            total_payment_rate += pay_rate
            step_count += 1

    return {
        "sequence_id": sequence_id,
        "total_enrollments": total_enrollments,
        "completed_enrollments": completed,
        "completion_rate": round((completed / total_enrollments * 100) if total_enrollments > 0 else 0, 1),
        "avg_response_rate": round((total_response_rate / step_count) if step_count > 0 else 0, 1),
        "avg_payment_rate": round((total_payment_rate / step_count) if step_count > 0 else 0, 1),
        "step_stats": step_stats,
    }


async def _portfolio_analytics(db: AsyncSession) -> dict:
    # Overall counts
    seq_count = (await db.execute(
        select(func.count()).select_from(CollectionSequence).where(CollectionSequence.is_active == True)
    )).scalar() or 0

    active_enrollments = (await db.execute(
        select(func.count()).select_from(SequenceEnrollment).where(SequenceEnrollment.status == "active")
    )).scalar() or 0

    # Messages sent in last 7 days
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    msgs_7d = (await db.execute(
        select(func.count()).select_from(StepExecution).where(StepExecution.executed_at >= week_ago)
    )).scalar() or 0

    # Response rate and payment rate (last 30 days)
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    stats_q = select(
        func.count().label("total"),
        func.sum(sa_case((StepExecution.borrower_responded == True, 1), else_=0)).label("responded"),
        func.sum(sa_case((StepExecution.payment_after == True, 1), else_=0)).label("paid"),
    ).where(StepExecution.executed_at >= month_ago)
    stats_row = (await db.execute(stats_q)).one()

    total = stats_row.total or 0
    responded = stats_row.responded or 0
    paid = stats_row.paid or 0

    # Per-channel breakdown
    channel_q = select(
        StepExecution.channel,
        func.count().label("total"),
        func.sum(sa_case((StepExecution.borrower_responded == True, 1), else_=0)).label("responded"),
        func.sum(sa_case((StepExecution.payment_after == True, 1), else_=0)).label("paid"),
    ).where(StepExecution.executed_at >= month_ago).group_by(StepExecution.channel)
    channel_rows = (await db.execute(channel_q)).all()

    channel_stats = []
    for cr in channel_rows:
        ct = cr.total or 0
        channel_stats.append({
            "channel": cr.channel,
            "total": ct,
            "response_rate": round((cr.responded or 0) / ct * 100, 1) if ct > 0 else 0,
            "payment_rate": round((cr.paid or 0) / ct * 100, 1) if ct > 0 else 0,
        })

    # Per-sequence summary
    seq_q = (
        select(
            CollectionSequence.id,
            CollectionSequence.name,
            CollectionSequence.delinquency_stage,
            func.count(SequenceEnrollment.id).label("enrollments"),
        )
        .outerjoin(SequenceEnrollment, SequenceEnrollment.sequence_id == CollectionSequence.id)
        .where(CollectionSequence.is_active == True)
        .group_by(CollectionSequence.id, CollectionSequence.name, CollectionSequence.delinquency_stage)
    )
    seq_rows = (await db.execute(seq_q)).all()
    sequence_summary = [
        {"id": r.id, "name": r.name, "stage": r.delinquency_stage, "enrollments": r.enrollments or 0}
        for r in seq_rows
    ]

    return {
        "total_sequences": seq_count,
        "active_enrollments": active_enrollments,
        "messages_sent_7d": msgs_7d,
        "response_rate": round((responded / total * 100) if total > 0 else 0, 1),
        "payment_rate": round((paid / total * 100) if total > 0 else 0, 1),
        "channel_stats": channel_stats,
        "sequence_summary": sequence_summary,
    }


# ── 5. Preview Message ──────────────────────────────────────

def render_template(body: str, context: dict | None = None) -> str:
    """Render a template body with sample or real data."""
    sample = {
        "name": "Marcus Mohammed",
        "first_name": "Marcus",
        "amount_due": "2,500.00",
        "total_overdue": "5,000.00",
        "due_date": "Jan 15, 2026",
        "dpd": "14",
        "ref": "ZL-2026-0042",
        "payment_link": "https://pay.zotta.tt/abc123",
        "promise_amount": "1,250.00",
        "promise_date": "Feb 01, 2026",
    }
    data = {**sample, **(context or {})}
    result = body
    for key, val in data.items():
        result = result.replace("{{" + key + "}}", str(val))
    return result
