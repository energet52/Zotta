"""AI-powered user management features: admin NLP queries, role recommendation."""

import json
import logging
from typing import Optional

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User, UserStatus
from app.models.rbac import Role, Permission, RolePermission, UserRoleAssignment
from app.models.session import LoginAttempt, UserSession

logger = logging.getLogger(__name__)


# ── Role Recommendation ──────────────────────────────────────


ROLE_RECOMMENDATION_RULES: dict[str, list[str]] = {
    "underwriting": ["Junior Underwriter", "Senior Underwriter"],
    "loan officer": ["Loan Officer"],
    "credit": ["Credit Risk Manager"],
    "scoring": ["Credit Risk Manager"],
    "risk": ["Credit Risk Manager"],
    "collections": ["Collections Agent", "Collections Manager"],
    "recovery": ["Collections Agent"],
    "finance": ["Finance Manager"],
    "accounting": ["Finance Manager"],
    "gl": ["Finance Manager"],
    "compliance": ["Compliance Officer"],
    "audit": ["Compliance Officer"],
    "admin": ["System Administrator"],
    "system": ["System Administrator"],
    "it": ["System Administrator"],
    "customer": ["Loan Officer"],
    "support": ["Loan Officer"],
}


async def recommend_roles(
    db: AsyncSession,
    department: Optional[str] = None,
    job_title: Optional[str] = None,
) -> list[dict]:
    """Recommend roles based on department and job title using rule-based heuristics.

    Falls back to OpenAI for ambiguous cases if API key is configured.
    """
    recommendations: list[dict] = []
    matched_role_names: set[str] = set()

    # Rule-based matching (word boundary aware)
    import re
    search_text = f"{department or ''} {job_title or ''}".lower()
    for keyword, role_names in ROLE_RECOMMENDATION_RULES.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', search_text):
            for rn in role_names:
                if rn not in matched_role_names:
                    matched_role_names.add(rn)
                    recommendations.append({
                        "role_name": rn,
                        "confidence": 0.85,
                        "reason": f"Matched keyword '{keyword}' in department/title",
                        "source": "rule_based",
                    })

    # If rule-based found results, return them
    if recommendations:
        # Resolve role IDs
        for rec in recommendations:
            role_result = await db.execute(
                select(Role).where(Role.name == rec["role_name"])
            )
            role = role_result.scalar_one_or_none()
            if role:
                rec["role_id"] = role.id
        return [r for r in recommendations if "role_id" in r]

    # Fallback: Try OpenAI if configured
    if settings.openai_api_key:
        try:
            return await _ai_recommend_roles(db, department, job_title)
        except Exception as e:
            logger.warning("AI role recommendation failed: %s", e)

    # Ultimate fallback: recommend Applicant
    role_result = await db.execute(select(Role).where(Role.name == "Applicant"))
    role = role_result.scalar_one_or_none()
    return [{
        "role_name": "Applicant",
        "role_id": role.id if role else None,
        "confidence": 0.5,
        "reason": "Default role — no specific match found",
        "source": "fallback",
    }]


async def _ai_recommend_roles(
    db: AsyncSession,
    department: Optional[str],
    job_title: Optional[str],
) -> list[dict]:
    """Use OpenAI to recommend roles for ambiguous cases."""
    import openai

    # Get all available roles
    roles_result = await db.execute(select(Role).where(Role.is_active.is_(True)))
    roles = roles_result.scalars().all()
    role_descriptions = "\n".join(
        f"- {r.name}: {r.description or 'No description'}" for r in roles
    )

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an RBAC advisor for a lending platform. "
                    "Given a user's department and job title, recommend the most appropriate roles. "
                    "Respond with a JSON array of objects: [{\"role_name\": \"...\", \"confidence\": 0.0-1.0, \"reason\": \"...\"}]"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Department: {department or 'Unknown'}\n"
                    f"Job Title: {job_title or 'Unknown'}\n\n"
                    f"Available roles:\n{role_descriptions}\n\n"
                    "Recommend 1-3 roles."
                ),
            },
        ],
        temperature=0.3,
        max_tokens=300,
    )

    content = response.choices[0].message.content or "[]"
    # Extract JSON from response
    try:
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        recs = json.loads(content.strip())
    except json.JSONDecodeError:
        return []

    # Resolve role IDs
    result = []
    for rec in recs:
        role_result = await db.execute(
            select(Role).where(Role.name == rec.get("role_name", ""))
        )
        role = role_result.scalar_one_or_none()
        if role:
            result.append({
                "role_name": role.name,
                "role_id": role.id,
                "confidence": rec.get("confidence", 0.7),
                "reason": rec.get("reason", "AI recommendation"),
                "source": "ai",
            })
    return result


# ── Admin NLP Query ──────────────────────────────────────────


async def admin_nlp_query(db: AsyncSession, query: str) -> dict:
    """Process a natural language admin query about users.

    Supports queries like:
    - "How many active users are there?"
    - "List all locked accounts"
    - "Who logged in today?"
    - "Show users without MFA"
    """
    q = query.lower().strip()

    # Pattern matching for common queries
    if any(w in q for w in ["how many", "count", "total"]):
        return await _handle_count_query(db, q)
    elif any(w in q for w in ["list", "show", "who", "find"]):
        return await _handle_list_query(db, q)
    elif any(w in q for w in ["locked", "suspended", "deactivated"]):
        return await _handle_status_query(db, q)

    # Fallback to OpenAI if available
    if settings.openai_api_key:
        try:
            return await _ai_admin_query(db, query)
        except Exception as e:
            logger.warning("AI admin query failed: %s", e)

    return {
        "answer": "I couldn't understand that query. Try asking about user counts, status, or login activity.",
        "data": None,
        "source": "fallback",
    }


async def _handle_count_query(db: AsyncSession, q: str) -> dict:
    """Handle count/total queries."""
    if "active" in q:
        count = (await db.execute(
            select(func.count(User.id)).where(User.status == "active")
        )).scalar() or 0
        return {"answer": f"There are {count} active users.", "data": {"count": count, "status": "active"}, "source": "rule_based"}

    if "locked" in q:
        count = (await db.execute(
            select(func.count(User.id)).where(User.status == "locked")
        )).scalar() or 0
        return {"answer": f"There are {count} locked accounts.", "data": {"count": count, "status": "locked"}, "source": "rule_based"}

    if "suspended" in q:
        count = (await db.execute(
            select(func.count(User.id)).where(User.status == "suspended")
        )).scalar() or 0
        return {"answer": f"There are {count} suspended accounts.", "data": {"count": count, "status": "suspended"}, "source": "rule_based"}

    if "mfa" in q or "two-factor" in q or "2fa" in q:
        enabled = (await db.execute(
            select(func.count(User.id)).where(User.mfa_enabled.is_(True))
        )).scalar() or 0
        total = (await db.execute(select(func.count(User.id)))).scalar() or 0
        return {
            "answer": f"{enabled} out of {total} users have MFA enabled ({round(enabled/total*100,1) if total else 0}%).",
            "data": {"mfa_enabled": enabled, "total": total},
            "source": "rule_based",
        }

    total = (await db.execute(select(func.count(User.id)))).scalar() or 0
    return {"answer": f"There are {total} total users.", "data": {"count": total}, "source": "rule_based"}


async def _handle_list_query(db: AsyncSession, q: str) -> dict:
    """Handle list/show queries."""
    if "without mfa" in q or "no mfa" in q:
        result = await db.execute(
            select(User.id, User.email, User.first_name, User.last_name, User.role).where(
                User.mfa_enabled.is_(False),
                User.status == "active",
            ).limit(20)
        )
        users = [{"id": r[0], "email": r[1], "name": f"{r[2]} {r[3]}", "role": r[4].value if hasattr(r[4], 'value') else r[4]} for r in result.all()]
        return {
            "answer": f"Found {len(users)} active users without MFA.",
            "data": {"users": users},
            "source": "rule_based",
        }

    if "logged in today" in q:
        from datetime import date
        today = date.today()
        result = await db.execute(
            select(User.id, User.email, User.first_name, User.last_name).where(
                User.last_login_at >= datetime.combine(today, datetime.min.time()),
            ).limit(20)
        )
        users = [{"id": r[0], "email": r[1], "name": f"{r[2]} {r[3]}"} for r in result.all()]
        return {
            "answer": f"{len(users)} users logged in today.",
            "data": {"users": users},
            "source": "rule_based",
        }

    return {"answer": "Please be more specific. Try 'show users without MFA' or 'who logged in today'.", "data": None, "source": "rule_based"}


async def _handle_status_query(db: AsyncSession, q: str) -> dict:
    """Handle status-specific queries."""
    status = None
    if "locked" in q:
        status = "locked"
    elif "suspended" in q:
        status = "suspended"
    elif "deactivated" in q:
        status = "deactivated"

    if status:
        result = await db.execute(
            select(User.id, User.email, User.first_name, User.last_name).where(
                User.status == status,
            ).limit(20)
        )
        users = [{"id": r[0], "email": r[1], "name": f"{r[2]} {r[3]}"} for r in result.all()]
        return {
            "answer": f"Found {len(users)} {status} accounts.",
            "data": {"users": users, "status": status},
            "source": "rule_based",
        }

    return {"answer": "Could not determine which status to query.", "data": None, "source": "rule_based"}


async def _ai_admin_query(db: AsyncSession, query: str) -> dict:
    """Use OpenAI to interpret and answer admin queries about users."""
    import openai

    # Gather context
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    status_counts = {}
    for s in UserStatus:
        c = (await db.execute(select(func.count(User.id)).where(User.status == s.value))).scalar() or 0
        status_counts[s.value] = c
    mfa_count = (await db.execute(select(func.count(User.id)).where(User.mfa_enabled.is_(True)))).scalar() or 0

    context = (
        f"User Management Database Summary:\n"
        f"- Total users: {total_users}\n"
        f"- By status: {json.dumps(status_counts)}\n"
        f"- MFA enabled: {mfa_count}\n"
    )

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an admin assistant for a lending platform's user management module. "
                    "Answer questions concisely based on the provided data. "
                    "If the question requires user-specific data you don't have, suggest how to find it."
                ),
            },
            {"role": "user", "content": f"{context}\n\nQuestion: {query}"},
        ],
        temperature=0.3,
        max_tokens=300,
    )

    answer = response.choices[0].message.content or "I couldn't process that query."
    return {"answer": answer, "data": status_counts, "source": "ai"}
