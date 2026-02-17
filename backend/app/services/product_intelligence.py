"""AI-powered product intelligence service.

Provides: product health scoring, AI advisor, what-if simulation,
product generation from natural language, competitive analysis,
and portfolio optimization.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select, case, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.catalog import CreditProduct, ProductFee, ProductScoreRange
from app.models.loan import LoanApplication, LoanStatus
from app.models.payment import Payment

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────

def _openai_available() -> bool:
    return bool(settings.openai_api_key)


async def _chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 2000) -> str:
    """Call OpenAI chat completion."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def _strip_json(text: str) -> str:
    """Strip markdown code fences from LLM JSON output."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


# ── Product Performance Metrics ──────────────────────────────────

async def get_product_metrics(product_id: int, db: AsyncSession) -> dict:
    """Calculate comprehensive performance metrics for a product."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    ninety_days_ago = now - timedelta(days=90)

    # Total applications
    total_apps = await db.scalar(
        select(func.count(LoanApplication.id))
        .where(LoanApplication.credit_product_id == product_id)
    ) or 0

    # Applications by status
    status_counts: dict[str, int] = {}
    result = await db.execute(
        select(LoanApplication.status, func.count(LoanApplication.id))
        .where(LoanApplication.credit_product_id == product_id)
        .group_by(LoanApplication.status)
    )
    for row in result.all():
        status_val = row[0].value if hasattr(row[0], "value") else str(row[0])
        status_counts[status_val] = row[1]

    # Recent applications (30 days)
    recent_apps = await db.scalar(
        select(func.count(LoanApplication.id))
        .where(
            LoanApplication.credit_product_id == product_id,
            LoanApplication.created_at >= thirty_days_ago,
        )
    ) or 0

    # Approved & disbursed
    approved = status_counts.get("approved", 0) + status_counts.get("APPROVED", 0)
    disbursed = status_counts.get("disbursed", 0) + status_counts.get("DISBURSED", 0)
    declined = status_counts.get("declined", 0) + status_counts.get("DECLINED", 0)

    decided = approved + disbursed + declined
    approval_rate = round((approved + disbursed) / decided * 100, 1) if decided > 0 else 0

    # Average loan amount
    avg_amount = await db.scalar(
        select(func.avg(LoanApplication.amount_requested))
        .where(LoanApplication.credit_product_id == product_id)
    )

    # Total disbursed volume
    total_disbursed = await db.scalar(
        select(func.sum(LoanApplication.amount_approved))
        .where(
            LoanApplication.credit_product_id == product_id,
            LoanApplication.status.in_([LoanStatus.DISBURSED, LoanStatus.APPROVED]),
        )
    )

    # Total payments collected
    total_collected = await db.scalar(
        select(func.sum(Payment.amount))
        .join(LoanApplication, Payment.loan_application_id == LoanApplication.id)
        .where(LoanApplication.credit_product_id == product_id)
    )

    # Average term
    avg_term = await db.scalar(
        select(func.avg(LoanApplication.term_months))
        .where(LoanApplication.credit_product_id == product_id)
    )

    # Monthly trend (last 6 months)
    monthly_trend = []
    for i in range(5, -1, -1):
        month_start = (now - timedelta(days=30 * i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i > 0:
            month_end = (now - timedelta(days=30 * (i - 1))).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            month_end = now
        count = await db.scalar(
            select(func.count(LoanApplication.id))
            .where(
                LoanApplication.credit_product_id == product_id,
                LoanApplication.created_at >= month_start,
                LoanApplication.created_at < month_end,
            )
        ) or 0
        monthly_trend.append({
            "month": month_start.strftime("%b %Y"),
            "applications": count,
        })

    return {
        "total_applications": total_apps,
        "recent_applications_30d": recent_apps,
        "status_breakdown": status_counts,
        "approval_rate": approval_rate,
        "avg_loan_amount": round(float(avg_amount or 0), 2),
        "avg_term_months": round(float(avg_term or 0), 1),
        "total_disbursed_volume": round(float(total_disbursed or 0), 2),
        "total_collected": round(float(total_collected or 0), 2),
        "monthly_trend": monthly_trend,
    }


# ── Product Health Score ─────────────────────────────────────────

async def calculate_health_score(product_id: int, db: AsyncSession) -> dict:
    """AI-powered product health assessment (0-100 score with breakdown)."""
    metrics = await get_product_metrics(product_id, db)

    # Get product config
    result = await db.execute(
        select(CreditProduct).where(CreditProduct.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        return {"score": 0, "status": "unknown", "factors": []}

    factors = []
    total_score = 0
    weight_sum = 0

    # 1. Activity Score (weight: 25)
    w = 25
    if metrics["total_applications"] == 0:
        s = 0
        factors.append({"name": "Activity", "score": s, "weight": w, "detail": "No applications yet"})
    elif metrics["recent_applications_30d"] >= 10:
        s = 100
        factors.append({"name": "Activity", "score": s, "weight": w, "detail": f"{metrics['recent_applications_30d']} apps in last 30 days"})
    elif metrics["recent_applications_30d"] >= 3:
        s = 70
        factors.append({"name": "Activity", "score": s, "weight": w, "detail": f"{metrics['recent_applications_30d']} apps in last 30 days"})
    else:
        s = 30
        factors.append({"name": "Activity", "score": s, "weight": w, "detail": "Low activity"})
    total_score += s * w
    weight_sum += w

    # 2. Approval Rate (weight: 25)
    w = 25
    if metrics["total_applications"] < 5:
        s = 50
        factors.append({"name": "Approval Rate", "score": s, "weight": w, "detail": "Insufficient data"})
    elif metrics["approval_rate"] >= 70:
        s = 100
        factors.append({"name": "Approval Rate", "score": s, "weight": w, "detail": f"{metrics['approval_rate']}%"})
    elif metrics["approval_rate"] >= 40:
        s = 60
        factors.append({"name": "Approval Rate", "score": s, "weight": w, "detail": f"{metrics['approval_rate']}% — may be too restrictive"})
    else:
        s = 25
        factors.append({"name": "Approval Rate", "score": s, "weight": w, "detail": f"{metrics['approval_rate']}% — very low, review eligibility"})
    total_score += s * w
    weight_sum += w

    # 3. Configuration Completeness (weight: 20)
    w = 20
    config_items = 0
    config_total = 4
    if product.description:
        config_items += 1
    fees_result = await db.execute(
        select(func.count(ProductFee.id)).where(ProductFee.credit_product_id == product_id)
    )
    fee_count = fees_result.scalar() or 0
    if fee_count > 0:
        config_items += 1
    sr_result = await db.execute(
        select(func.count(ProductScoreRange.id)).where(ProductScoreRange.credit_product_id == product_id)
    )
    sr_count = sr_result.scalar() or 0
    if sr_count > 0:
        config_items += 1
    if product.grace_period_days > 0:
        config_items += 1
    s = round(config_items / config_total * 100)
    factors.append({"name": "Configuration", "score": s, "weight": w, "detail": f"{config_items}/{config_total} configured"})
    total_score += s * w
    weight_sum += w

    # 4. Revenue Performance (weight: 15)
    w = 15
    if metrics["total_collected"] > 0:
        s = 100
        factors.append({"name": "Revenue", "score": s, "weight": w, "detail": f"TTD {metrics['total_collected']:,.0f} collected"})
    elif metrics["total_disbursed_volume"] > 0:
        s = 60
        factors.append({"name": "Revenue", "score": s, "weight": w, "detail": "Disbursed but no payments yet"})
    else:
        s = 20
        factors.append({"name": "Revenue", "score": s, "weight": w, "detail": "No revenue yet"})
    total_score += s * w
    weight_sum += w

    # 5. Market Fit (weight: 15)
    w = 15
    amount_range = float(product.max_amount) - float(product.min_amount)
    term_range = product.max_term_months - product.min_term_months
    if amount_range > 10000 and term_range >= 6:
        s = 90
        factors.append({"name": "Market Fit", "score": s, "weight": w, "detail": "Good amount and term range"})
    elif amount_range > 5000 or term_range >= 3:
        s = 60
        factors.append({"name": "Market Fit", "score": s, "weight": w, "detail": "Moderate flexibility"})
    else:
        s = 30
        factors.append({"name": "Market Fit", "score": s, "weight": w, "detail": "Narrow product parameters"})
    total_score += s * w
    weight_sum += w

    final_score = round(total_score / weight_sum) if weight_sum > 0 else 0
    status = "excellent" if final_score >= 80 else "good" if final_score >= 60 else "needs_attention" if final_score >= 40 else "critical"

    return {
        "score": final_score,
        "status": status,
        "factors": factors,
        "metrics_summary": metrics,
    }


# ── AI Product Advisor ───────────────────────────────────────────

async def ai_advisor(
    product_id: Optional[int],
    question: str,
    db: AsyncSession,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Chat-based AI product advisor."""
    if not _openai_available():
        return {"answer": "AI advisor requires OpenAI API key configuration.", "suggestions": []}

    # Gather context
    context_parts = []

    if product_id:
        result = await db.execute(
            select(CreditProduct).where(CreditProduct.id == product_id)
        )
        product = result.scalar_one_or_none()
        if product:
            fees_r = await db.execute(select(ProductFee).where(ProductFee.credit_product_id == product_id))
            fees = fees_r.scalars().all()
            sr_r = await db.execute(select(ProductScoreRange).where(ProductScoreRange.credit_product_id == product_id))
            score_ranges = sr_r.scalars().all()
            metrics = await get_product_metrics(product_id, db)
            health = await calculate_health_score(product_id, db)

            context_parts.append(f"""Current Product: {product.name}
Description: {product.description or 'N/A'}
Terms: {product.min_term_months}-{product.max_term_months} months
Amounts: TTD {float(product.min_amount):,.0f} - TTD {float(product.max_amount):,.0f}
Repayment: {product.repayment_scheme}
Grace Period: {product.grace_period_days} days
Active: {product.is_active}
Score Ranges: {', '.join(f'{sr.min_score}-{sr.max_score}' for sr in score_ranges) or 'None'}
Fees: {', '.join(f'{f.fee_type} ({f.fee_base}): {float(f.fee_amount):.2f}' for f in fees) or 'None'}

Performance:
- Total Applications: {metrics['total_applications']}
- Recent (30d): {metrics['recent_applications_30d']}
- Approval Rate: {metrics['approval_rate']}%
- Avg Loan: TTD {metrics['avg_loan_amount']:,.0f}
- Total Disbursed: TTD {metrics['total_disbursed_volume']:,.0f}

Health Score: {health['score']}/100 ({health['status']})""")

    # Get all products for portfolio context
    all_products = await db.execute(select(CreditProduct).where(CreditProduct.is_active == True))
    products_list = all_products.scalars().all()
    context_parts.append(f"\nPortfolio: {len(products_list)} active products: {', '.join(p.name for p in products_list)}")

    system_prompt = f"""You are an expert credit product strategist and AI advisor for Zotta,
a loan management system in Trinidad & Tobago (TTD currency). You help product managers design,
optimize, and manage credit products.

Your expertise includes:
- Risk-based pricing and fee optimization
- Market positioning and competitive analysis
- Regulatory compliance (Central Bank of Trinidad & Tobago)
- Portfolio diversification and cannibalization analysis
- Customer segment targeting
- Product lifecycle management

Context:
{chr(10).join(context_parts)}

Rules:
- Be specific with numbers and TTD amounts
- Consider the Caribbean/Trinidad market
- Suggest actionable improvements
- When recommending changes, explain the business rationale
- Format responses with clear structure using markdown"""

    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history[-10:])
    messages.append({"role": "user", "content": question})

    try:
        answer = await _chat(messages, temperature=0.5, max_tokens=1500)
        return {"answer": answer, "suggestions": []}
    except Exception as e:
        logger.error(f"AI advisor error: {e}")
        return {"answer": f"AI advisor encountered an error: {str(e)}", "suggestions": []}


# ── What-If Simulator ────────────────────────────────────────────

async def simulate_changes(
    product_id: int,
    changes: dict,
    db: AsyncSession,
) -> dict:
    """Simulate the projected impact of product parameter changes."""
    if not _openai_available():
        return {"analysis": "AI simulator requires OpenAI API key.", "projections": {}}

    # Current state
    result = await db.execute(select(CreditProduct).where(CreditProduct.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        return {"analysis": "Product not found.", "projections": {}}

    metrics = await get_product_metrics(product_id, db)
    health = await calculate_health_score(product_id, db)

    current_state = {
        "name": product.name,
        "min_amount": float(product.min_amount),
        "max_amount": float(product.max_amount),
        "min_term_months": product.min_term_months,
        "max_term_months": product.max_term_months,
        "grace_period_days": product.grace_period_days,
        "is_active": product.is_active,
    }

    prompt = f"""Analyze the projected impact of these product changes:

Current Product: {json.dumps(current_state)}
Current Metrics: {json.dumps(metrics)}
Current Health Score: {health['score']}/100

Proposed Changes: {json.dumps(changes)}

Provide a JSON response with this structure:
{{
  "impact_summary": "1-2 sentence summary",
  "risk_level": "low|medium|high",
  "projected_volume_change_pct": number (-100 to +200),
  "projected_approval_rate_change_pct": number,
  "projected_revenue_impact": "positive|neutral|negative",
  "recommendations": ["list", "of", "recommendations"],
  "warnings": ["list of risks or concerns"],
  "confidence": "high|medium|low"
}}"""

    try:
        raw = await _chat([
            {"role": "system", "content": "You are a credit product analyst. Return ONLY valid JSON."},
            {"role": "user", "content": prompt},
        ], temperature=0.2, max_tokens=1000)
        analysis = json.loads(_strip_json(raw))
        return {"analysis": analysis, "current_metrics": metrics, "proposed_changes": changes}
    except Exception as e:
        logger.error(f"Simulator error: {e}")
        return {"analysis": {"impact_summary": f"Analysis error: {e}"}, "current_metrics": metrics}


# ── AI Product Generator ─────────────────────────────────────────

async def generate_product(description: str, db: AsyncSession) -> dict:
    """Generate a complete product configuration from a natural language description."""
    if not _openai_available():
        return {"error": "AI product generator requires OpenAI API key."}

    # Get existing products for context
    all_products = await db.execute(select(CreditProduct).where(CreditProduct.is_active == True))
    products = all_products.scalars().all()
    existing = [{"name": p.name, "min_amount": float(p.min_amount), "max_amount": float(p.max_amount)} for p in products]

    prompt = f"""Generate a complete credit product configuration based on this description:
"{description}"

Existing products for context (avoid duplicating): {json.dumps(existing)}

Market: Trinidad & Tobago (TTD currency)
Available fee types: admin_fee_pct, credit_fee_pct, origination_fee_pct, origination_fee_flat, late_payment_fee_flat
Available fee bases: purchase_amount, financed_amount, flat
Available repayment schemes: "Monthly Equal Installment Monthly Actual/365 (Fixed)", "Monthly Equal Installment (Fixed)", "Bi-Weekly (Fixed)"

Return ONLY valid JSON:
{{
  "name": "Product Name",
  "description": "Clear product description",
  "min_term_months": number,
  "max_term_months": number,
  "min_amount": number,
  "max_amount": number,
  "repayment_scheme": "one of the schemes above",
  "grace_period_days": number,
  "score_ranges": [{{"min_score": number, "max_score": number}}],
  "fees": [{{"fee_type": "type", "fee_base": "base", "fee_amount": number, "is_available": true}}],
  "rationale": "Why this configuration makes sense",
  "target_segment": "Who this product is for",
  "risk_assessment": "Risk profile of this product"
}}"""

    try:
        raw = await _chat([
            {"role": "system", "content": "You are a credit product designer for a Caribbean LMS. Return ONLY valid JSON."},
            {"role": "user", "content": prompt},
        ], temperature=0.4, max_tokens=1500)
        config = json.loads(_strip_json(raw))
        return {"product": config}
    except Exception as e:
        logger.error(f"Product generator error: {e}")
        return {"error": str(e)}


# ── Product Comparison ────────────────────────────────────────────

async def compare_products(product_ids: list[int], db: AsyncSession) -> dict:
    """Compare multiple products side-by-side with AI analysis."""
    products_data = []
    for pid in product_ids:
        result = await db.execute(select(CreditProduct).where(CreditProduct.id == pid))
        product = result.scalar_one_or_none()
        if not product:
            continue

        fees_r = await db.execute(select(ProductFee).where(ProductFee.credit_product_id == pid))
        fees = fees_r.scalars().all()
        sr_r = await db.execute(select(ProductScoreRange).where(ProductScoreRange.credit_product_id == pid))
        srs = sr_r.scalars().all()
        metrics = await get_product_metrics(pid, db)
        health = await calculate_health_score(pid, db)

        products_data.append({
            "id": pid,
            "name": product.name,
            "description": product.description,
            "min_amount": float(product.min_amount),
            "max_amount": float(product.max_amount),
            "min_term": product.min_term_months,
            "max_term": product.max_term_months,
            "repayment_scheme": product.repayment_scheme,
            "grace_period": product.grace_period_days,
            "is_active": product.is_active,
            "fees": [{"type": f.fee_type, "base": f.fee_base, "amount": float(f.fee_amount)} for f in fees],
            "score_ranges": [{"min": sr.min_score, "max": sr.max_score} for sr in srs],
            "metrics": metrics,
            "health_score": health["score"],
        })

    if not _openai_available() or len(products_data) < 2:
        return {"products": products_data, "analysis": None}

    try:
        raw = await _chat([
            {"role": "system", "content": "You are a credit product analyst. Compare the products and provide insights. Return JSON with: {\"summary\": \"...\", \"winner\": \"product name\", \"cannibalization_risk\": \"low|medium|high\", \"recommendations\": [...], \"differentiators\": [...]}"},
            {"role": "user", "content": f"Compare these products:\n{json.dumps(products_data, indent=2)}"},
        ], temperature=0.3, max_tokens=1000)
        analysis = json.loads(_strip_json(raw))
    except Exception:
        analysis = None

    return {"products": products_data, "analysis": analysis}


# ── Portfolio Overview ───────────────────────────────────────────

async def portfolio_overview(db: AsyncSession) -> dict:
    """Get portfolio-level product analytics for the product list page."""
    products_result = await db.execute(
        select(CreditProduct).where(CreditProduct.is_active == True)
    )
    products = products_result.scalars().all()

    summaries = []
    for p in products:
        apps_count = await db.scalar(
            select(func.count(LoanApplication.id))
            .where(LoanApplication.credit_product_id == p.id)
        ) or 0

        disbursed_vol = await db.scalar(
            select(func.sum(LoanApplication.amount_approved))
            .where(
                LoanApplication.credit_product_id == p.id,
                LoanApplication.status.in_([LoanStatus.DISBURSED, LoanStatus.APPROVED]),
            )
        ) or 0

        health = await calculate_health_score(p.id, db)

        summaries.append({
            "id": p.id,
            "name": p.name,
            "applications": apps_count,
            "disbursed_volume": round(float(disbursed_vol), 2),
            "health_score": health["score"],
            "health_status": health["status"],
        })

    # Sort by health score
    summaries.sort(key=lambda x: x["health_score"], reverse=True)

    total_volume = sum(s["disbursed_volume"] for s in summaries)
    total_apps = sum(s["applications"] for s in summaries)

    return {
        "total_products": len(products),
        "total_applications": total_apps,
        "total_disbursed_volume": total_volume,
        "products": summaries,
    }
