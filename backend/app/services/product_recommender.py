"""Product recommendation based on borrower needs description."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import CreditProduct


async def get_recommended_products(
    need_description: str,
    amount_hint: float | None,
    db: AsyncSession,
) -> list[dict]:
    """Return products that match the borrower's described need.

    Args:
        need_description: Free-text description (e.g. "fix my roof", "buy a fridge").
        amount_hint: Optional amount in TTD if mentioned.
        db: Database session.

    Returns:
        List of dicts with id, name, description, min_amount, max_amount, term_range, plain_reason.
    """
    result = await db.execute(
        select(CreditProduct)
        .where(CreditProduct.is_active == True)
        .options(selectinload(CreditProduct.merchant))
        .order_by(CreditProduct.name)
    )
    products = result.scalars().all()
    if not products:
        return []

    # Filter by amount if we have a hint
    if amount_hint and amount_hint > 0:
        filtered = [p for p in products if float(p.min_amount) <= amount_hint <= float(p.max_amount)]
        if filtered:
            products = filtered

    # Build plain-language summaries for LLM
    out = []
    for p in products[:5]:
        out.append({
            "id": p.id,
            "name": p.name,
            "description": p.description or "",
            "min_amount": float(p.min_amount),
            "max_amount": float(p.max_amount),
            "term_range": f"{p.min_term_months}-{p.max_term_months} months",
            "plain_reason": _match_reason(need_description, p),
        })
    return out


def _match_reason(need: str, product: CreditProduct) -> str:
    """Simple heuristic for why a product matches a need."""
    need_lower = need.lower()
    name_lower = (product.name or "").lower()
    desc = (product.description or "").lower()

    if "home" in need_lower or "roof" in need_lower or "renovation" in need_lower:
        if "home" in name_lower or "home" in desc or "personal" in name_lower:
            return "Good for home improvement or repairs"
    if "car" in need_lower or "vehicle" in need_lower:
        if "vehicle" in name_lower or "auto" in name_lower or "car" in name_lower:
            return "Designed for vehicle purchases"
    if "medical" in need_lower or "hospital" in need_lower:
        if "medical" in name_lower or "personal" in name_lower:
            return "Can be used for medical expenses"
    if "fridge" in need_lower or "appliance" in need_lower or "electronics" in need_lower:
        if "hire" in name_lower or "personal" in name_lower:
            return "Suitable for appliance and electronics purchase"

    return f"Flexible personal loan for various needs"
