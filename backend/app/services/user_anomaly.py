"""Login anomaly detection — rule-based heuristics with simple statistical analysis."""

import logging
from datetime import datetime, timedelta, timezone
from collections import Counter

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import LoginAttempt

logger = logging.getLogger(__name__)


async def detect_login_anomalies(
    db: AsyncSession,
    user_id: int,
    current_ip: str,
    current_ua: str,
) -> dict:
    """Analyze recent login behavior and flag anomalies.

    Returns:
        {
            "risk_score": 0-100,
            "flags": [{"type": str, "detail": str, "severity": str}],
            "recommendation": str | None,
        }
    """
    now = datetime.now(timezone.utc)
    flags: list[dict] = []
    risk_score = 0

    # Fetch recent login history (last 90 days)
    result = await db.execute(
        select(LoginAttempt).where(
            LoginAttempt.user_id == user_id,
            LoginAttempt.created_at >= now - timedelta(days=90),
        ).order_by(LoginAttempt.created_at.desc()).limit(200)
    )
    attempts = result.scalars().all()

    if len(attempts) < 2:
        return {"risk_score": 0, "flags": [], "recommendation": None}

    successful = [a for a in attempts if a.success]
    failed = [a for a in attempts if not a.success]

    # ── 1. New IP address check ─────────────────────────────
    known_ips = {a.ip_address for a in successful if a.ip_address}
    if current_ip and current_ip not in known_ips and len(known_ips) >= 2:
        flags.append({
            "type": "new_ip",
            "detail": f"Login from new IP {current_ip}. Known IPs: {len(known_ips)}",
            "severity": "medium",
        })
        risk_score += 20

    # ── 2. New user agent check ─────────────────────────────
    known_uas = {a.user_agent for a in successful if a.user_agent}
    if current_ua and current_ua not in known_uas and len(known_uas) >= 2:
        flags.append({
            "type": "new_device",
            "detail": "Login from a new device/browser",
            "severity": "low",
        })
        risk_score += 10

    # ── 3. Brute force detection (many failures recently) ───
    recent_failures = [
        a for a in failed
        if a.created_at and a.created_at >= now - timedelta(hours=1)
    ]
    if len(recent_failures) >= 3:
        flags.append({
            "type": "brute_force",
            "detail": f"{len(recent_failures)} failed attempts in the last hour",
            "severity": "high",
        })
        risk_score += 30

    # ── 4. Unusual time login ───────────────────────────────
    if successful:
        login_hours = [a.created_at.hour for a in successful if a.created_at]
        if login_hours:
            hour_counts = Counter(login_hours)
            current_hour = now.hour
            most_common_hours = {h for h, _ in hour_counts.most_common(6)}
            if current_hour not in most_common_hours and len(login_hours) >= 10:
                flags.append({
                    "type": "unusual_time",
                    "detail": f"Login at {current_hour}:00 is unusual for this user",
                    "severity": "low",
                })
                risk_score += 10

    # ── 5. Rapid IP switching ───────────────────────────────
    recent_logins = [
        a for a in successful
        if a.created_at and a.created_at >= now - timedelta(hours=24)
    ]
    recent_unique_ips = {a.ip_address for a in recent_logins if a.ip_address}
    if len(recent_unique_ips) >= 4:
        flags.append({
            "type": "ip_hopping",
            "detail": f"{len(recent_unique_ips)} different IPs in 24 hours",
            "severity": "medium",
        })
        risk_score += 15

    # ── 6. Impossible travel (basic heuristic) ──────────────
    # (Would need GeoIP in production — here we just flag rapid IP changes)
    if len(recent_logins) >= 2:
        last = recent_logins[0]
        if (
            last.ip_address
            and current_ip
            and last.ip_address != current_ip
            and last.created_at
            and (now - last.created_at).total_seconds() < 300  # < 5 minutes
        ):
            flags.append({
                "type": "impossible_travel",
                "detail": f"IP changed from {last.ip_address} to {current_ip} within 5 minutes",
                "severity": "high",
            })
            risk_score += 25

    # Cap risk score at 100
    risk_score = min(risk_score, 100)

    recommendation = None
    if risk_score >= 60:
        recommendation = "High risk — consider requiring MFA verification"
    elif risk_score >= 30:
        recommendation = "Moderate risk — monitor closely"

    return {
        "risk_score": risk_score,
        "flags": flags,
        "recommendation": recommendation,
    }


async def get_login_analytics(db: AsyncSession, days: int = 30) -> dict:
    """Aggregate login analytics across all users for the admin dashboard."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # Total attempts
    total = (await db.execute(
        select(func.count(LoginAttempt.id)).where(LoginAttempt.created_at >= cutoff)
    )).scalar() or 0

    success_count = (await db.execute(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.created_at >= cutoff,
            LoginAttempt.success.is_(True),
        )
    )).scalar() or 0

    failure_count = total - success_count

    # Top failure reasons
    reason_result = await db.execute(
        select(
            LoginAttempt.failure_reason,
            func.count(LoginAttempt.id).label("cnt"),
        ).where(
            LoginAttempt.created_at >= cutoff,
            LoginAttempt.success.is_(False),
        ).group_by(LoginAttempt.failure_reason).order_by(func.count(LoginAttempt.id).desc()).limit(5)
    )
    top_failure_reasons = [
        {"reason": row[0] or "unknown", "count": row[1]}
        for row in reason_result.all()
    ]

    # Unique users who logged in
    unique_users = (await db.execute(
        select(func.count(func.distinct(LoginAttempt.user_id))).where(
            LoginAttempt.created_at >= cutoff,
            LoginAttempt.success.is_(True),
            LoginAttempt.user_id.isnot(None),
        )
    )).scalar() or 0

    return {
        "period_days": days,
        "total_attempts": total,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_count / total * 100, 1) if total > 0 else 0,
        "unique_active_users": unique_users,
        "top_failure_reasons": top_failure_reasons,
    }
