"""Collections AI service — enhanced NBA, propensity scoring, behavioral analysis,
risk signals, daily briefing, AI message drafting, and similar-borrower outcomes.

Uses OpenAI with rule-based fallbacks throughout.
"""

from __future__ import annotations

import json
import logging
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.loan import LoanApplication, LoanStatus, ApplicantProfile
from app.models.payment import Payment, PaymentSchedule, ScheduleStatus, PaymentStatus
from app.models.collection import CollectionRecord, CollectionChat
from app.models.collections_ext import (
    CollectionCase, CaseStatus, DelinquencyStage,
    PromiseToPay, PTPStatus,
    SettlementOffer, ComplianceRule,
    CollectionsDashboardSnapshot,
)
from app.models.user import User
from app.services.collections_engine import compute_next_best_action, calculate_settlement

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _ser(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if hasattr(val, "value"):
        return val.value
    return val


async def _get_sector_risk(employer_sector: str | None, db: AsyncSession) -> dict:
    """Get sector risk rating from SectorPolicy if available."""
    if not employer_sector:
        return {"sector": None, "risk_rating": None}
    try:
        from app.models.sector_analysis import SectorPolicy
        q = select(SectorPolicy).where(
            func.lower(SectorPolicy.sector_name) == employer_sector.lower(),
            SectorPolicy.is_active == True,
        )
        policy = (await db.execute(q)).scalars().first()
        if policy:
            return {
                "sector": policy.sector_name,
                "risk_rating": policy.risk_rating.value if hasattr(policy.risk_rating, "value") else str(policy.risk_rating),
            }
    except Exception:
        pass
    return {"sector": employer_sector, "risk_rating": None}


# ────────────────────────────────────────────────────────────────────
# 1. Enhanced NBA with AI reasoning
# ────────────────────────────────────────────────────────────────────

async def generate_enhanced_nba(
    case: CollectionCase,
    borrower_context: dict,
    db: AsyncSession,
) -> dict[str, Any]:
    """Enhanced NBA with OpenAI reasoning, timing, channel, and offer suggestion.

    Falls back to rule-based compute_next_best_action().
    """
    # Start with rule-based NBA
    base_nba = await compute_next_best_action(case, db)

    # Gather context for enhancement
    profile = borrower_context.get("profile", {})
    interactions = borrower_context.get("interactions", [])
    payments = borrower_context.get("payments", [])
    ptps = borrower_context.get("ptps", [])

    # Determine best channel from interaction history
    channel_success = {"phone": 0, "whatsapp": 0, "sms": 0, "email": 0}
    channel_attempts = {"phone": 0, "whatsapp": 0, "sms": 0, "email": 0}
    for rec in interactions:
        ch = (rec.get("channel") or "phone").lower()
        if ch in channel_attempts:
            channel_attempts[ch] += 1
            if rec.get("outcome") in ("promise_to_pay", "payment_arranged"):
                channel_success[ch] += 1

    best_channel = "phone"
    best_rate = 0
    for ch, attempts in channel_attempts.items():
        if attempts > 0:
            rate = channel_success[ch] / attempts
            if rate > best_rate:
                best_rate = rate
                best_channel = ch

    # Determine best contact number
    phone = borrower_context.get("phone")
    whatsapp = profile.get("whatsapp_number")
    mobile = profile.get("mobile_phone")
    best_number = whatsapp or mobile or phone

    # Timing: detect salary cycle from payment dates
    timing = "Today 9:00–12:00"
    pay_days = [p.get("payment_date") for p in payments if p.get("payment_date")]
    if pay_days:
        days_of_month = []
        for pd in pay_days[-6:]:
            if isinstance(pd, str):
                try:
                    pd = datetime.fromisoformat(pd).date()
                except Exception:
                    continue
            if hasattr(pd, "day"):
                days_of_month.append(pd.day)
        if days_of_month:
            avg_day = sum(days_of_month) // len(days_of_month)
            today = date.today()
            if avg_day - 3 <= today.day <= avg_day + 5:
                timing = f"Today (near salary day ~{avg_day}th) — high priority"

    # Calculate suggested offer
    suggested_offer = None
    if case.total_overdue and float(case.total_overdue) > 0:
        options = calculate_settlement(case.total_overdue, case.dpd)
        if options:
            # Pick the most appropriate: short plan for low DPD, partial settlement for high
            if case.dpd > 60 and len(options) > 1:
                suggested_offer = options[1]  # partial settlement
            else:
                # Find 3-month plan
                for opt in options:
                    if opt.get("plan_months") == 3:
                        suggested_offer = opt
                        break
                if not suggested_offer:
                    suggested_offer = options[0]

    # Count broken promises for context
    broken = len([p for p in ptps if p.get("status") == "broken"])
    total_ptps = len(ptps)
    kept = len([p for p in ptps if p.get("status") == "kept"])

    # Build enhanced result (rule-based)
    result = {
        "action": base_nba["action"],
        "confidence": base_nba["confidence"],
        "reasoning": base_nba["reasoning"],
        "timing": timing,
        "best_channel": best_channel,
        "best_number": best_number,
        "suggested_offer": suggested_offer,
        "confidence_label": "High" if base_nba["confidence"] >= 0.85 else "Medium" if base_nba["confidence"] >= 0.7 else "Low",
    }

    # Try OpenAI for richer reasoning
    if settings.openai_api_key:
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

            borrower_name = borrower_context.get("name", "Borrower")
            employer = profile.get("employer_name", "Unknown")
            sector_info = borrower_context.get("sector_risk", {})
            income = profile.get("monthly_income", "Unknown")

            prompt = f"""You are a senior collections strategist for a lending company. Analyze this case and provide a recommendation.

CASE DATA:
- Borrower: {borrower_name}
- DPD: {case.dpd} days past due
- Total Overdue: ${float(case.total_overdue or 0):,.2f}
- Employer: {employer} (Sector: {sector_info.get('sector', 'N/A')}, Risk: {sector_info.get('risk_rating', 'N/A')})
- Monthly Income: {income}
- Interaction History: {len(interactions)} records, best channel: {best_channel} ({channel_attempts})
- PTP History: {total_ptps} promises, {kept} kept, {broken} broken
- Flags: dispute={case.dispute_active}, vulnerability={case.vulnerability_flag}, hardship={case.hardship_flag}
- Rule-based recommendation: {base_nba['action']}

Generate a JSON response:
{{"reasoning": "2-4 sentences explaining WHY this action NOW, referencing specific data points",
"timing_detail": "specific best time window with explanation",
"tone_guidance": "brief guidance on conversation tone"}}

IMPORTANT: Return ONLY valid JSON."""

            resp = await client.chat.completions.create(
                model="gpt-4.1",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
            ai_data = json.loads(raw)
            result["reasoning"] = ai_data.get("reasoning", result["reasoning"])
            result["timing"] = ai_data.get("timing_detail", result["timing"])
            result["tone_guidance"] = ai_data.get("tone_guidance", "")
        except Exception as e:
            logger.warning("OpenAI enhanced NBA failed, using rule-based: %s", e)

    return result


# ────────────────────────────────────────────────────────────────────
# 2. Propensity-to-Pay Score
# ────────────────────────────────────────────────────────────────────

async def compute_propensity_score(
    case: CollectionCase,
    payment_history: list[dict],
    ptps: list[dict],
    profile: dict,
    sector_risk: dict | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Rule-based propensity-to-pay score (0-100) with factors."""
    score = 50  # Start at neutral
    factors_positive: list[str] = []
    factors_negative: list[str] = []

    # 1. Payment history consistency (last 12 payments)
    recent_payments = payment_history[-12:] if payment_history else []
    if recent_payments:
        on_time = sum(1 for p in recent_payments if p.get("status") == "paid")
        ratio = on_time / len(recent_payments)
        if ratio >= 0.8:
            score += 20
            factors_positive.append(f"Strong payment history ({on_time}/{len(recent_payments)} on time)")
        elif ratio >= 0.5:
            score += 10
            factors_positive.append(f"Moderate payment history ({on_time}/{len(recent_payments)} on time)")
        else:
            score -= 15
            factors_negative.append(f"Poor payment history ({on_time}/{len(recent_payments)} on time)")
    else:
        score -= 5
        factors_negative.append("No payment history available")

    # 2. DPD trajectory
    if case.dpd <= 15:
        score += 15
        factors_positive.append("Early delinquency — higher cure probability")
    elif case.dpd <= 30:
        score += 5
    elif case.dpd <= 60:
        score -= 5
    elif case.dpd <= 90:
        score -= 15
        factors_negative.append(f"Extended delinquency ({case.dpd} DPD)")
    else:
        score -= 25
        factors_negative.append(f"Severe delinquency ({case.dpd} DPD)")

    # 3. Promise reliability
    if ptps:
        kept = sum(1 for p in ptps if p.get("status") == "kept")
        broken = sum(1 for p in ptps if p.get("status") == "broken")
        total = kept + broken
        if total > 0:
            keep_rate = kept / total
            if keep_rate >= 0.7:
                score += 15
                factors_positive.append(f"Good promise history ({kept}/{total} kept)")
            elif keep_rate >= 0.4:
                score += 5
            else:
                score -= 15
                factors_negative.append(f"Poor promise history ({broken}/{total} broken)")

    # 4. Employment stability (sector risk)
    if sector_risk and sector_risk.get("risk_rating"):
        risk = sector_risk["risk_rating"]
        if risk in ("low",):
            score += 10
            factors_positive.append(f"Stable employment sector ({sector_risk.get('sector', '')})")
        elif risk in ("medium",):
            score += 5
        elif risk in ("high", "very_high"):
            score -= 10
            factors_negative.append(f"High-risk sector ({sector_risk.get('sector', '')})")
        elif risk == "critical":
            score -= 20
            factors_negative.append(f"Critical-risk sector ({sector_risk.get('sector', '')})")

    # 5. Income-to-debt ratio
    monthly_income = float(profile.get("monthly_income") or 0)
    monthly_expenses = float(profile.get("monthly_expenses") or 0)
    if monthly_income > 0:
        disposable = monthly_income - monthly_expenses
        overdue = float(case.total_overdue or 0)
        if disposable > 0 and overdue > 0:
            months_to_clear = overdue / disposable
            if months_to_clear <= 2:
                score += 10
                factors_positive.append("Overdue is manageable relative to income")
            elif months_to_clear <= 6:
                score += 5
            else:
                score -= 10
                factors_negative.append("High overdue relative to disposable income")

    # 6. Recent contact responsiveness
    if case.last_contact_at:
        days_since = (datetime.now(timezone.utc) - case.last_contact_at).days if case.last_contact_at.tzinfo else (datetime.now() - case.last_contact_at).days
        if days_since <= 3:
            score += 5
            factors_positive.append("Recent contact engagement")
    elif case.first_contact_at is None:
        factors_negative.append("No contact established yet")

    # Clamp
    score = max(0, min(100, score))

    # Trend (compare to a simple heuristic)
    trend = "stable"
    if case.dpd <= 30 and len([p for p in ptps if p.get("status") == "kept"]) > 0:
        trend = "improving"
    elif case.dpd > 60 and len([p for p in ptps if p.get("status") == "broken"]) > 1:
        trend = "declining"

    return {
        "score": score,
        "trend": trend,
        "factors_positive": factors_positive[:3],
        "factors_negative": factors_negative[:3],
    }


# ────────────────────────────────────────────────────────────────────
# 3. Behavioral Pattern Analysis
# ────────────────────────────────────────────────────────────────────

async def analyze_behavioral_patterns(
    case: CollectionCase,
    interactions: list[dict],
    payments: list[dict],
    ptps: list[dict],
    db: AsyncSession,
) -> list[dict[str, str]]:
    """Analyze interaction/payment data to extract behavioral patterns."""
    patterns: list[dict[str, str]] = []

    # Preferred channel
    channel_counts: dict[str, int] = {}
    successful_channels: dict[str, int] = {}
    for rec in interactions:
        ch = (rec.get("channel") or "phone").lower()
        channel_counts[ch] = channel_counts.get(ch, 0) + 1
        if rec.get("outcome") in ("promise_to_pay", "payment_arranged"):
            successful_channels[ch] = successful_channels.get(ch, 0) + 1
    if channel_counts:
        best_ch = max(channel_counts, key=channel_counts.get)
        patterns.append({
            "category": "channel",
            "insight": f"Most contacted via {best_ch} ({channel_counts[best_ch]} times).",
        })
    if successful_channels:
        best_success = max(successful_channels, key=successful_channels.get)
        patterns.append({
            "category": "channel",
            "insight": f"Best outcomes via {best_success} ({successful_channels[best_success]} positive responses).",
        })

    # Contact attempt pattern
    no_answer = sum(1 for r in interactions if r.get("outcome") == "no_answer")
    total_contacts = len(interactions)
    if total_contacts > 0:
        rpc_rate = (total_contacts - no_answer) / total_contacts * 100
        if rpc_rate < 30:
            patterns.append({
                "category": "responsiveness",
                "insight": f"Low contact rate — only {rpc_rate:.0f}% of {total_contacts} attempts reached the borrower.",
            })
        elif rpc_rate > 70:
            patterns.append({
                "category": "responsiveness",
                "insight": f"Good contact rate — {rpc_rate:.0f}% of attempts reached the borrower.",
            })

    # Salary cycle detection from payment dates
    pay_days: list[int] = []
    for p in payments:
        pd = p.get("payment_date")
        if pd:
            if isinstance(pd, str):
                try:
                    pd = datetime.fromisoformat(pd).date()
                except Exception:
                    continue
            if hasattr(pd, "day"):
                pay_days.append(pd.day)
    if len(pay_days) >= 3:
        avg_day = sum(pay_days) // len(pay_days)
        spread = max(pay_days) - min(pay_days)
        if spread <= 10:
            patterns.append({
                "category": "payment_cycle",
                "insight": f"Salary cycle detected: payments typically around the {avg_day}th of the month.",
            })

    # Promise reliability
    if ptps:
        kept = sum(1 for p in ptps if p.get("status") == "kept")
        broken = sum(1 for p in ptps if p.get("status") == "broken")
        total = kept + broken
        if total >= 2:
            keep_pct = kept / total * 100
            patterns.append({
                "category": "promise",
                "insight": f"Promise reliability: {keep_pct:.0f}% kept ({kept} of {total}). {'Reliable borrower.' if keep_pct >= 70 else 'Frequent broken promises — consider smaller, more realistic amounts.'}",
            })

    # Average days late on broken promises
    broken_ptps = [p for p in ptps if p.get("status") == "broken" and p.get("broken_at") and p.get("promise_date")]
    if broken_ptps:
        delays = []
        for p in broken_ptps:
            try:
                pdate = p["promise_date"]
                bdate = p["broken_at"]
                if isinstance(pdate, str):
                    pdate = datetime.fromisoformat(pdate).date()
                if isinstance(bdate, str):
                    bdate = datetime.fromisoformat(bdate).date()
                if hasattr(pdate, "toordinal") and hasattr(bdate, "toordinal"):
                    delays.append((bdate - pdate).days if hasattr(bdate, "__sub__") else 0)
            except Exception:
                continue
        if delays:
            avg_delay = sum(delays) // len(delays)
            patterns.append({
                "category": "promise",
                "insight": f"Average delay on broken promises: {avg_delay} days past promise date.",
            })

    # Try AI summary if OpenAI available
    if settings.openai_api_key and patterns:
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            bullet_points = "\n".join(f"- {p['insight']}" for p in patterns)
            resp = await client.chat.completions.create(
                model="gpt-4.1",
                messages=[{
                    "role": "user",
                    "content": f"Summarize these borrower behavioral patterns into ONE concise sentence a collections agent can act on:\n{bullet_points}\n\nReturn just the sentence, no JSON.",
                }],
                temperature=0.3,
                max_tokens=150,
            )
            summary = resp.choices[0].message.content.strip()
            patterns.insert(0, {"category": "ai_summary", "insight": summary})
        except Exception as e:
            logger.warning("OpenAI behavioral summary failed: %s", e)

    return patterns


# ────────────────────────────────────────────────────────────────────
# 4. Risk Signals
# ────────────────────────────────────────────────────────────────────

async def get_risk_signals(
    case: CollectionCase,
    profile: dict,
    sector_risk: dict,
    interactions: list[dict],
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Aggregate risk signals for the case."""
    signals: list[dict[str, Any]] = []

    # Sector risk
    if sector_risk.get("risk_rating") in ("high", "very_high", "critical"):
        signals.append({
            "severity": "high" if sector_risk["risk_rating"] == "critical" else "medium",
            "category": "sector",
            "signal": f"Borrower's sector ({sector_risk.get('sector', 'Unknown')}) rated {sector_risk['risk_rating'].upper()} risk.",
        })

    # Contact failure trend
    recent = interactions[-10:] if interactions else []
    if len(recent) >= 3:
        recent_failures = sum(1 for r in recent[-5:] if r.get("outcome") == "no_answer")
        if recent_failures >= 4:
            signals.append({
                "severity": "high",
                "category": "contact",
                "signal": f"Contact failure trend: {recent_failures} of last 5 attempts unanswered. Possible skip trace needed.",
            })
        elif recent_failures >= 3:
            signals.append({
                "severity": "medium",
                "category": "contact",
                "signal": f"Declining reachability: {recent_failures} of last 5 attempts unanswered.",
            })

    # DPD acceleration
    if case.dpd > 60:
        signals.append({
            "severity": "high" if case.dpd > 90 else "medium",
            "category": "delinquency",
            "signal": f"Severe delinquency at {case.dpd} DPD. {'Legal escalation territory.' if case.dpd > 90 else 'Approaching legal threshold.'}",
        })

    # High overdue relative to income
    monthly_income = float(profile.get("monthly_income") or 0)
    overdue = float(case.total_overdue or 0)
    if monthly_income > 0 and overdue > monthly_income * 3:
        signals.append({
            "severity": "medium",
            "category": "affordability",
            "signal": f"Overdue amount (${overdue:,.0f}) exceeds 3x monthly income (${monthly_income:,.0f}).",
        })

    # Multiple broken promises
    broken_q = select(func.count()).where(
        PromiseToPay.collection_case_id == case.id,
        PromiseToPay.status == PTPStatus.BROKEN,
    )
    broken_count = (await db.execute(broken_q)).scalar() or 0
    if broken_count >= 3:
        signals.append({
            "severity": "high",
            "category": "behavior",
            "signal": f"{broken_count} broken promises. Conventional approach ineffective.",
        })

    # Shared phone number check (fraud signal)
    phone = profile.get("mobile_phone") or profile.get("whatsapp_number")
    if phone:
        shared_q = select(func.count()).where(
            ApplicantProfile.mobile_phone == phone,
        )
        shared = (await db.execute(shared_q)).scalar() or 0
        if shared > 2:
            signals.append({
                "severity": "medium",
                "category": "fraud",
                "signal": f"Phone number shared with {shared - 1} other borrower(s).",
            })

    return signals


# ────────────────────────────────────────────────────────────────────
# 5. Similar Borrower Outcomes
# ────────────────────────────────────────────────────────────────────

async def get_similar_borrower_outcomes(
    case: CollectionCase,
    profile: dict,
    db: AsyncSession,
) -> dict[str, Any]:
    """Find cure rates for borrowers with similar profile."""
    # Define similarity: same DPD band, similar employment type
    dpd = case.dpd
    if dpd <= 30:
        dpd_band = "1-30"
        dpd_filter = and_(CollectionCase.dpd >= 1, CollectionCase.dpd <= 30)
    elif dpd <= 60:
        dpd_band = "31-60"
        dpd_filter = and_(CollectionCase.dpd >= 31, CollectionCase.dpd <= 60)
    elif dpd <= 90:
        dpd_band = "61-90"
        dpd_filter = and_(CollectionCase.dpd >= 61, CollectionCase.dpd <= 90)
    else:
        dpd_band = "90+"
        dpd_filter = CollectionCase.dpd > 90

    # Count total and cured in same DPD band
    total_q = select(func.count()).where(dpd_filter)
    total = (await db.execute(total_q)).scalar() or 0

    cured_q = select(func.count()).where(
        dpd_filter,
        CollectionCase.status.in_([CaseStatus.CLOSED, CaseStatus.SETTLED]),
    )
    cured = (await db.execute(cured_q)).scalar() or 0

    cure_rate = round(cured / max(total, 1) * 100, 1)

    # Average days to resolve for cured cases in same band
    avg_days_q = select(
        func.avg(
            func.extract("epoch", CollectionCase.updated_at - CollectionCase.created_at) / 86400
        )
    ).where(
        dpd_filter,
        CollectionCase.status.in_([CaseStatus.CLOSED, CaseStatus.SETTLED]),
    )
    avg_days = (await db.execute(avg_days_q)).scalar()

    return {
        "dpd_band": dpd_band,
        "total_similar": total,
        "cured": cured,
        "cure_rate": cure_rate,
        "avg_resolution_days": round(float(avg_days), 1) if avg_days else None,
        "description": (
            f"Borrowers in the {dpd_band} DPD band have a {cure_rate}% cure rate"
            f"{f' (avg {round(float(avg_days))} days to resolve)' if avg_days else ''}."
            f" Based on {total} similar cases."
        ),
    }


# ────────────────────────────────────────────────────────────────────
# 6. Daily Briefing
# ────────────────────────────────────────────────────────────────────

async def generate_daily_briefing(
    agent_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    """Generate AI-powered daily briefing for a collections agent."""
    today = date.today()
    now = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)

    # Broken promises needing follow-up
    broken_q = (
        select(PromiseToPay)
        .join(CollectionCase, PromiseToPay.collection_case_id == CollectionCase.id)
        .where(
            CollectionCase.assigned_agent_id == agent_id,
            PromiseToPay.status == PTPStatus.BROKEN,
            PromiseToPay.broken_at >= datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc),
        )
    )
    broken_ptps = (await db.execute(broken_q)).scalars().all()

    # Cases hitting DPD thresholds today (30, 60, 90)
    threshold_cases = []
    for threshold in [30, 60, 90]:
        q = (
            select(func.count())
            .where(
                CollectionCase.assigned_agent_id == agent_id,
                CollectionCase.dpd == threshold,
                CollectionCase.status.in_([CaseStatus.OPEN, CaseStatus.IN_PROGRESS]),
            )
        )
        count = (await db.execute(q)).scalar() or 0
        if count > 0:
            threshold_cases.append({"threshold": threshold, "count": count})

    # High-propensity settlement candidates (high balance + mid DPD)
    high_balance_q = (
        select(func.count())
        .where(
            CollectionCase.assigned_agent_id == agent_id,
            CollectionCase.total_overdue > 100000,
            CollectionCase.dpd.between(30, 90),
            CollectionCase.status.in_([CaseStatus.OPEN, CaseStatus.IN_PROGRESS]),
        )
    )
    settlement_candidates = (await db.execute(high_balance_q)).scalar() or 0

    # New payments received overnight
    payments_q = (
        select(func.count(), func.coalesce(func.sum(Payment.amount), 0))
        .where(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.created_at >= datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc),
        )
    )
    pay_result = (await db.execute(payments_q)).one()
    new_payments_count = pay_result[0] or 0
    new_payments_amount = float(pay_result[1] or 0)

    # New cases assigned
    new_cases_q = (
        select(func.count())
        .where(
            CollectionCase.assigned_agent_id == agent_id,
            CollectionCase.created_at >= datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc),
        )
    )
    new_assignments = (await db.execute(new_cases_q)).scalar() or 0

    # Total portfolio
    portfolio_q = (
        select(func.count(), func.coalesce(func.sum(CollectionCase.total_overdue), 0))
        .where(
            CollectionCase.assigned_agent_id == agent_id,
            CollectionCase.status.in_([CaseStatus.OPEN, CaseStatus.IN_PROGRESS]),
        )
    )
    port_result = (await db.execute(portfolio_q)).one()
    total_cases = port_result[0] or 0
    total_overdue = float(port_result[1] or 0)

    # SLA breaches approaching (within 4 hours)
    sla_q = (
        select(func.count())
        .where(
            CollectionCase.assigned_agent_id == agent_id,
            CollectionCase.sla_next_contact_deadline.isnot(None),
            CollectionCase.sla_next_contact_deadline <= now + timedelta(hours=4),
            CollectionCase.status.in_([CaseStatus.OPEN, CaseStatus.IN_PROGRESS]),
        )
    )
    sla_approaching = (await db.execute(sla_q)).scalar() or 0

    # Build priority items
    priorities: list[str] = []
    if broken_ptps:
        priorities.append(f"{len(broken_ptps)} broken promise(s) from yesterday need immediate follow-up")
    for tc in threshold_cases:
        priorities.append(f"{tc['count']} account(s) hitting {tc['threshold']} DPD today — critical window for cure")
    if settlement_candidates > 0:
        priorities.append(f"{settlement_candidates} high-balance account(s) are good candidates for settlement")
    if sla_approaching > 0:
        priorities.append(f"{sla_approaching} case(s) approaching SLA breach — needs attention within 4 hours")

    # Build portfolio changes
    changes: list[str] = []
    if new_payments_count > 0:
        changes.append(f"{new_payments_count} new payment(s) received (${new_payments_amount:,.0f} total)")
    if new_assignments > 0:
        changes.append(f"{new_assignments} new case(s) assigned to you")

    # Strategy tip (rule-based)
    strategy_tip = (
        "Focus on broken promises first — quick follow-up within 24 hours has 40% higher recovery rate."
        if broken_ptps
        else "Start with high-DPD cases approaching thresholds — early intervention before stage escalation is key."
    )

    briefing = {
        "date": today.isoformat(),
        "portfolio_summary": {
            "total_cases": total_cases,
            "total_overdue": total_overdue,
        },
        "priorities": priorities,
        "changes": changes,
        "strategy_tip": strategy_tip,
    }

    # Try AI for a richer briefing narrative
    if settings.openai_api_key and priorities:
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            context = f"""Generate a concise daily briefing for a collections agent.
Portfolio: {total_cases} cases, ${total_overdue:,.0f} total overdue.
Priority items: {'; '.join(priorities)}
Changes: {'; '.join(changes) if changes else 'No significant changes'}

Write 2-3 sentences of strategy advice personalized to this agent's current situation. Be specific and actionable. Return just the text."""

            resp = await client.chat.completions.create(
                model="gpt-4.1",
                messages=[{"role": "user", "content": context}],
                temperature=0.4,
                max_tokens=200,
            )
            briefing["strategy_tip"] = resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("OpenAI daily briefing failed: %s", e)

    return briefing


# ────────────────────────────────────────────────────────────────────
# 7. AI Message Drafting
# ────────────────────────────────────────────────────────────────────

_TEMPLATES = {
    "reminder": "Hi {name}, this is a friendly reminder that your payment of ${amount} on loan {ref} is overdue by {dpd} days. Please make a payment at your earliest convenience or contact us to discuss options.",
    "demand": "Dear {name}, despite previous notices, your account {ref} remains ${amount} past due ({dpd} days). Immediate payment is required to avoid further action. Please contact us urgently.",
    "follow_up": "Hi {name}, following up on our recent conversation about your account {ref}. As discussed, your next payment of ${amount} is expected soon. Let us know if you need assistance.",
    "promise_reminder": "Hi {name}, this is a reminder that your promised payment of ${promise_amount} for account {ref} is due on {promise_date}. Thank you for your commitment.",
    "broken_promise": "Hi {name}, we noticed the payment of ${promise_amount} promised for {promise_date} on account {ref} was not received. Please contact us to make arrangements.",
    "payment_link": "Hi {name}, here is your secure payment link for account {ref}: [Payment Link]. Amount due: ${amount}. You can pay online anytime.",
    "settlement_offer": "Hi {name}, we'd like to offer you a resolution for account {ref}. We can settle your balance of ${amount} with a {offer_type}. Contact us to discuss.",
}


async def draft_collection_message(
    case: CollectionCase,
    channel: str,
    template_type: str,
    borrower_context: dict,
    db: AsyncSession,
) -> dict[str, str]:
    """Draft a collection message using AI or templates."""
    name = borrower_context.get("name", "Customer")
    ref = borrower_context.get("reference_number", "N/A")
    amount = f"{float(case.total_overdue or 0):,.2f}"
    dpd = str(case.dpd)

    # Get active PTP info
    active_ptp = borrower_context.get("active_ptp", {})
    promise_amount = f"{float(active_ptp.get('amount_promised', 0)):,.2f}" if active_ptp else "0"
    promise_date = active_ptp.get("promise_date", "N/A") if active_ptp else "N/A"

    # Template fallback
    template = _TEMPLATES.get(template_type, _TEMPLATES["reminder"])
    fallback_message = template.format(
        name=name, amount=amount, ref=ref, dpd=dpd,
        promise_amount=promise_amount, promise_date=promise_date,
        offer_type="payment plan",
    )

    # Try AI
    if settings.openai_api_key:
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

            prompt = f"""Draft a {channel} message for debt collection. Be professional, empathetic, and compliant.

Borrower: {name}
Account: {ref}
Amount overdue: ${amount}
Days past due: {dpd}
Message type: {template_type}
Channel: {channel}
{'Promise: $' + promise_amount + ' due ' + str(promise_date) if active_ptp else ''}

Requirements:
- {"Keep under 160 chars for SMS" if channel == "sms" else "Keep concise but warm for WhatsApp" if channel == "whatsapp" else "Professional email tone"}
- Never threaten or use aggressive language
- Include a clear call to action
- Do not include any placeholders or brackets

Return just the message text."""

            resp = await client.chat.completions.create(
                model="gpt-4.1",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=300,
            )
            return {
                "message": resp.choices[0].message.content.strip(),
                "source": "ai",
                "template_type": template_type,
            }
        except Exception as e:
            logger.warning("AI message drafting failed: %s", e)

    return {
        "message": fallback_message,
        "source": "template",
        "template_type": template_type,
    }
