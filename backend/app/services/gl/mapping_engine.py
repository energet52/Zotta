"""GL Mapping Engine.

Converts loan lifecycle events into journal entries automatically.

Mapping templates define which accounts to debit/credit for each event type.
Templates can be global or product-specific, with optional conditions
(e.g., ``{"days_past_due": {">": 90}}``) for conditional mappings.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.gl import (
    GLMappingTemplate,
    GLMappingTemplateLine,
    JournalSourceType,
    MappingAmountSource,
    MappingLineType,
    GLAccount,
)
from app.services.gl.journal_engine import create_journal_entry, JournalEngineError

logger = logging.getLogger(__name__)


class MappingError(Exception):
    """GL mapping error."""


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------

def _evaluate_conditions(conditions: dict | None, context: dict) -> bool:
    """Check if context matches the template conditions.

    Conditions format: ``{"field_name": {"operator": value}}``
    Supported operators: >, <, >=, <=, ==, !=, in, not_in
    """
    if not conditions:
        return True

    for field, rule in conditions.items():
        actual = context.get(field)
        if actual is None:
            return False

        for op, expected in rule.items():
            if op == ">" and not (actual > expected):
                return False
            elif op == "<" and not (actual < expected):
                return False
            elif op == ">=" and not (actual >= expected):
                return False
            elif op == "<=" and not (actual <= expected):
                return False
            elif op == "==" and not (actual == expected):
                return False
            elif op == "!=" and not (actual != expected):
                return False
            elif op == "in" and actual not in expected:
                return False
            elif op == "not_in" and actual in expected:
                return False

    return True


# ---------------------------------------------------------------------------
# Amount resolution
# ---------------------------------------------------------------------------

def _resolve_amount(
    source: MappingAmountSource,
    amount_breakdown: dict[str, Decimal],
) -> Decimal:
    """Extract the correct amount based on the mapping template's amount_source.

    *amount_breakdown* is expected to have keys like:
    ``principal``, ``interest``, ``fee``, ``full_amount``
    """
    mapping = {
        MappingAmountSource.PRINCIPAL: "principal",
        MappingAmountSource.INTEREST: "interest",
        MappingAmountSource.FEE: "fee",
        MappingAmountSource.FULL_AMOUNT: "full_amount",
    }
    key = mapping.get(source)
    if key:
        return Decimal(str(amount_breakdown.get(key, 0)))
    # CUSTOM — caller provides the amount directly
    return Decimal(str(amount_breakdown.get("custom", 0)))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_mapping_for_event(
    db: AsyncSession,
    event_type: JournalSourceType,
    product_id: int | None = None,
    context: dict | None = None,
) -> GLMappingTemplate | None:
    """Find the best matching template for an event.

    Priority: product-specific > global, active only.
    Conditional templates are checked against *context*.
    """
    ctx = context or {}

    # First try product-specific
    if product_id:
        result = await db.execute(
            select(GLMappingTemplate)
            .where(
                GLMappingTemplate.event_type == event_type,
                GLMappingTemplate.credit_product_id == product_id,
                GLMappingTemplate.is_active == True,
            )
            .options(selectinload(GLMappingTemplate.lines))
        )
        for tpl in result.scalars().all():
            if _evaluate_conditions(tpl.conditions, ctx):
                return tpl

    # Fall back to global
    result = await db.execute(
        select(GLMappingTemplate)
        .where(
            GLMappingTemplate.event_type == event_type,
            GLMappingTemplate.credit_product_id.is_(None),
            GLMappingTemplate.is_active == True,
        )
        .options(selectinload(GLMappingTemplate.lines))
    )
    for tpl in result.scalars().all():
        if _evaluate_conditions(tpl.conditions, ctx):
            return tpl

    return None


async def generate_journal_entry(
    db: AsyncSession,
    *,
    event_type: JournalSourceType,
    source_reference: str,
    amount_breakdown: dict[str, Decimal | float | int],
    product_id: int | None = None,
    context: dict | None = None,
    description: str | None = None,
    effective_date: date | None = None,
    currency_code: str = "JMD",
    exchange_rate: Decimal = Decimal("1.000000"),
    created_by: int | None = None,
    loan_reference: str | None = None,
    auto_post: bool = True,
    dry_run: bool = False,
) -> "dict | Any":
    """Generate a journal entry from a mapping template.

    If *dry_run* is True, returns a dict preview without persisting.
    """
    template = await get_mapping_for_event(
        db, event_type, product_id=product_id, context=context
    )
    if not template:
        logger.warning(
            "No mapping template found for event=%s product=%s",
            event_type.value, product_id,
        )
        if dry_run:
            return {"error": "No matching template found"}
        raise MappingError(
            f"No mapping template found for event type {event_type.value}"
        )

    # Normalise amounts to Decimal
    amounts = {k: Decimal(str(v)) for k, v in amount_breakdown.items()}

    # Build journal lines
    lines = []
    for tpl_line in template.lines:
        amount = _resolve_amount(tpl_line.amount_source, amounts)
        if amount <= 0:
            continue  # Skip zero-amount lines

        desc = tpl_line.description_template or template.name
        # Simple template substitution
        desc = desc.replace("{source_reference}", source_reference or "")
        desc = desc.replace("{amount}", f"{amount:,.2f}")

        line = {
            "gl_account_id": tpl_line.gl_account_id,
            "debit_amount": float(amount) if tpl_line.line_type == MappingLineType.DEBIT else 0.0,
            "credit_amount": float(amount) if tpl_line.line_type == MappingLineType.CREDIT else 0.0,
            "description": desc,
            "loan_reference": loan_reference,
        }
        lines.append(line)

    if not lines or len(lines) < 2:
        msg = "Template produced fewer than 2 lines — check amount breakdown"
        if dry_run:
            return {"error": msg, "template": template.name}
        raise MappingError(msg)

    entry_desc = description or f"{template.name} — {source_reference}"

    if dry_run:
        return {
            "template_name": template.name,
            "event_type": event_type.value,
            "description": entry_desc,
            "lines": lines,
            "total_debit": sum(ln["debit_amount"] for ln in lines),
            "total_credit": sum(ln["credit_amount"] for ln in lines),
            "is_balanced": (
                sum(ln["debit_amount"] for ln in lines) ==
                sum(ln["credit_amount"] for ln in lines)
            ),
        }

    entry = await create_journal_entry(
        db,
        lines=lines,
        source_type=event_type,
        source_reference=source_reference,
        description=entry_desc,
        effective_date=effective_date,
        currency_code=currency_code,
        exchange_rate=exchange_rate,
        created_by=created_by,
        auto_post=auto_post,
    )
    logger.info(
        "Generated JE %s from template '%s' for event %s (source: %s)",
        entry.entry_number, template.name, event_type.value, source_reference,
    )
    return entry


async def dry_run(
    db: AsyncSession,
    *,
    event_type: JournalSourceType,
    source_reference: str,
    amount_breakdown: dict[str, Decimal | float | int],
    product_id: int | None = None,
    context: dict | None = None,
) -> dict:
    """Preview what JE would be created without persisting."""
    return await generate_journal_entry(
        db,
        event_type=event_type,
        source_reference=source_reference,
        amount_breakdown=amount_breakdown,
        product_id=product_id,
        context=context,
        dry_run=True,
    )


async def validate_product_mappings(
    db: AsyncSession, product_id: int
) -> dict:
    """Check that a product has mappings for all critical event types.

    Returns a dict of event_type → bool (True = mapped).
    """
    critical_events = [
        JournalSourceType.LOAN_DISBURSEMENT,
        JournalSourceType.REPAYMENT,
        JournalSourceType.INTEREST_ACCRUAL,
        JournalSourceType.FEE,
        JournalSourceType.PROVISION,
        JournalSourceType.WRITE_OFF,
    ]
    results = {}
    for event in critical_events:
        template = await get_mapping_for_event(db, event, product_id=product_id)
        results[event.value] = template is not None

    all_mapped = all(results.values())
    return {"product_id": product_id, "mappings": results, "is_complete": all_mapped}


async def list_templates(
    db: AsyncSession,
    event_type: JournalSourceType | None = None,
) -> list[GLMappingTemplate]:
    """List all mapping templates, optionally filtered by event type."""
    q = select(GLMappingTemplate).options(selectinload(GLMappingTemplate.lines))
    if event_type:
        q = q.where(GLMappingTemplate.event_type == event_type)
    q = q.order_by(GLMappingTemplate.event_type, GLMappingTemplate.name)
    result = await db.execute(q)
    return list(result.scalars().all())


async def create_template(
    db: AsyncSession,
    *,
    name: str,
    event_type: JournalSourceType,
    lines: list[dict],
    credit_product_id: int | None = None,
    conditions: dict | None = None,
    description: str | None = None,
) -> GLMappingTemplate:
    """Create a new mapping template with lines."""
    template = GLMappingTemplate(
        name=name,
        event_type=event_type,
        credit_product_id=credit_product_id,
        conditions=conditions,
        description=description,
        is_active=True,
    )
    db.add(template)
    await db.flush()

    for ln in lines:
        tpl_line = GLMappingTemplateLine(
            template_id=template.id,
            line_type=MappingLineType(ln["line_type"]),
            gl_account_id=ln["gl_account_id"],
            amount_source=MappingAmountSource(ln["amount_source"]),
            description_template=ln.get("description_template"),
        )
        db.add(tpl_line)

    await db.flush()
    await db.refresh(template, ["lines"])
    logger.info("Created mapping template '%s' for event %s", name, event_type.value)
    return template
