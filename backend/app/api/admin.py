"""Administration endpoints for hire-purchase catalog management and rules."""

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth_utils import require_roles
from app.database import get_db
from app.models.user import User, UserRole
from app.models.audit import AuditLog
from app.models.decision import Decision, DecisionRulesConfig
from app.models.catalog import (
    Merchant,
    Branch,
    ProductCategory,
    CreditProduct,
    ProductScoreRange,
    ProductFee,
    ProductRateTier,
)
from app.schemas import (
    MerchantCreate,
    MerchantUpdate,
    MerchantResponse,
    BranchCreate,
    BranchUpdate,
    BranchResponse,
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductCategoryResponse,
    CreditProductCreate,
    CreditProductUpdate,
    CreditProductResponse,
    ProductScoreRangeCreate,
    ProductScoreRangeUpdate,
    ProductScoreRangeResponse,
    ProductFeeCreate,
    ProductFeeUpdate,
    ProductFeeResponse,
    ProductRateTierCreate,
    ProductRateTierUpdate,
    ProductRateTierResponse,
    ProductAdvisorRequest,
    ProductAdvisorResponse,
    ProductSimulateRequest,
    ProductGenerateRequest,
    ProductCompareRequest,
)
from app.services.decision_engine.rules import RULES_REGISTRY, DEFAULT_RULES
from app.services.rule_generator import generate_rule, ALLOWED_FIELDS
from app.services.error_logger import log_error

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Pydantic schemas for rules endpoints ─────────────────────────────────

class RuleEntry(BaseModel):
    rule_id: str
    name: str
    description: str
    field: str
    operator: str
    threshold: Any = None
    outcome: str
    severity: str
    type: str = "threshold"
    is_custom: bool = False
    enabled: bool = True


class RulesConfigResponse(BaseModel):
    version: int
    name: str
    rules: list[RuleEntry]
    allowed_fields: dict[str, Any]


class RulesUpdateRequest(BaseModel):
    rules: list[RuleEntry]


class RuleGenerateRequest(BaseModel):
    prompt: str = Field(min_length=5)
    conversation_history: Optional[list[dict]] = None


class RuleGenerateResponse(BaseModel):
    status: str
    questions: Optional[list[str]] = None
    refusal_reason: Optional[str] = None
    rule: Optional[dict] = None
    explanation: Optional[str] = None


# ── Rules management endpoints (admin-only) ──────────────────────────────

@router.get("/rules", response_model=RulesConfigResponse)
async def get_rules(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Return the current active rules config."""
    try:
        # Load latest active config from DB
        result = await db.execute(
            select(DecisionRulesConfig)
            .where(DecisionRulesConfig.is_active == True)
            .order_by(desc(DecisionRulesConfig.version))
            .limit(1)
        )
        db_config = result.scalar_one_or_none()

        # Start from defaults
        registry = {k: dict(v) for k, v in RULES_REGISTRY.items()}

        # Overlay DB overrides
        if db_config and db_config.rules:
            saved_registry = db_config.rules.get("rules_registry")
            if saved_registry and isinstance(saved_registry, dict):
                for rid, overrides in saved_registry.items():
                    # Skip rules marked as deleted
                    if overrides.get("_deleted"):
                        registry.pop(rid, None)
                        continue
                    if rid in registry:
                        registry[rid].update(overrides)
                    else:
                        registry[rid] = overrides

        version = db_config.version if db_config else DEFAULT_RULES["version"]
        name = db_config.name if db_config else DEFAULT_RULES["name"]

        rules_list = []
        for rule_id in sorted(registry.keys()):
            r = registry[rule_id]
            rules_list.append(RuleEntry(
                rule_id=rule_id,
                name=r.get("name", rule_id),
                description=r.get("description", ""),
                field=r.get("field", ""),
                operator=r.get("operator", ""),
                threshold=r.get("threshold"),
                outcome=r.get("outcome", "decline"),
                severity=r.get("severity", "hard"),
                type=r.get("type", "threshold"),
                is_custom=r.get("is_custom", False),
                enabled=r.get("enabled", True),
            ))

        return RulesConfigResponse(
            version=version,
            name=name,
            rules=rules_list,
            allowed_fields=ALLOWED_FIELDS,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="get_rules")
        raise


def _diff_rules(old_registry: dict, new_registry: dict) -> list[dict]:
    """Compare two rules registries and return a list of change objects."""
    changes = []
    all_ids = set(old_registry.keys()) | set(new_registry.keys())
    for rid in sorted(all_ids):
        old_r = old_registry.get(rid)
        new_r = new_registry.get(rid)
        # Skip _deleted markers
        if old_r and old_r.get("_deleted"):
            old_r = None
        if new_r and new_r.get("_deleted"):
            new_r = None
        if old_r is None and new_r is not None:
            changes.append({"rule_id": rid, "change_type": "added", "name": new_r.get("name", rid)})
        elif old_r is not None and new_r is None:
            changes.append({"rule_id": rid, "change_type": "removed", "name": old_r.get("name", rid)})
        elif old_r is not None and new_r is not None:
            diffs = {}
            for key in ("threshold", "outcome", "enabled", "severity", "name", "description", "field", "operator"):
                ov = old_r.get(key)
                nv = new_r.get(key)
                if str(ov) != str(nv):
                    diffs[key] = {"old": ov, "new": nv}
            if diffs:
                changes.append({"rule_id": rid, "change_type": "modified", "name": new_r.get("name", rid), "fields": diffs})
    return changes


@router.put("/rules")
async def update_rules(
    body: RulesUpdateRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Save updated rules config. Creates a new version."""
    try:
        # Get current latest version
        result = await db.execute(
            select(DecisionRulesConfig)
            .where(DecisionRulesConfig.is_active == True)
            .order_by(desc(DecisionRulesConfig.version))
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        old_version = existing.version if existing else DEFAULT_RULES["version"]
        new_version = old_version + 1

        # Build old registry for diffing
        old_registry: dict[str, dict] = {}
        if existing and existing.rules:
            saved = existing.rules.get("rules_registry")
            if saved and isinstance(saved, dict):
                old_registry = {k: v for k, v in saved.items() if isinstance(v, dict) and not v.get("_deleted")}

        # Build registry dict from the rules list
        registry: dict[str, dict] = {}
        for rule in body.rules:
            registry[rule.rule_id] = {
                "name": rule.name,
                "description": rule.description,
                "field": rule.field,
                "operator": rule.operator,
                "threshold": rule.threshold,
                "outcome": rule.outcome,
                "severity": rule.severity,
                "type": rule.type,
                "is_custom": rule.is_custom,
                "enabled": rule.enabled,
            }

        # Preserve _deleted markers from previous config so built-in
        # rules that were deleted don't reappear on next load
        if existing and existing.rules:
            prev_registry = existing.rules.get("rules_registry", {})
            for rid, val in prev_registry.items():
                if isinstance(val, dict) and val.get("_deleted") and rid not in registry:
                    registry[rid] = {"_deleted": True}

        # Build full config (keep legacy structure + new registry)
        full_config = dict(DEFAULT_RULES)
        full_config["rules_registry"] = registry

        # Mark old configs as inactive
        if existing:
            existing.is_active = False

        # Create new version
        new_config = DecisionRulesConfig(
            version=new_version,
            name=f"Rules v{new_version}",
            rules=full_config,
            is_active=True,
            created_by=current_user.id,
        )
        db.add(new_config)

        # Audit logging: diff old vs new
        changes = _diff_rules(old_registry, {k: v for k, v in registry.items() if isinstance(v, dict) and not v.get("_deleted")})
        if changes:
            summary_parts = []
            for c in changes[:5]:
                if c["change_type"] == "added":
                    summary_parts.append(f"added {c['rule_id']} ({c['name']})")
                elif c["change_type"] == "removed":
                    summary_parts.append(f"removed {c['rule_id']} ({c['name']})")
                elif c["change_type"] == "modified":
                    fields_changed = list(c.get("fields", {}).keys())
                    summary_parts.append(f"{c['rule_id']}: changed {', '.join(fields_changed)}")
            if len(changes) > 5:
                summary_parts.append(f"and {len(changes) - 5} more")
            details = f"v{old_version}→v{new_version}: {'; '.join(summary_parts)}"
        else:
            details = f"v{old_version}→v{new_version}: no effective changes"

        db.add(AuditLog(
            entity_type="rules",
            entity_id=new_version,
            action="rules_updated",
            user_id=current_user.id,
            old_values={"version": old_version, "changes": changes},
            new_values={"version": new_version},
            details=details,
        ))

        await db.flush()

        return {"message": "Rules saved", "version": new_version}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="update_rules")
        raise


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Delete any rule from the config (admin only)."""
    try:
        # Load current config
        result = await db.execute(
            select(DecisionRulesConfig)
            .where(DecisionRulesConfig.is_active == True)
            .order_by(desc(DecisionRulesConfig.version))
            .limit(1)
        )
        existing = result.scalar_one_or_none()

        if not existing or not existing.rules:
            raise HTTPException(status_code=404, detail="No active rules config found")

        saved_registry = existing.rules.get("rules_registry", {})

        is_builtin = rule_id in RULES_REGISTRY
        found_in_saved = rule_id in saved_registry

        if not is_builtin and not found_in_saved:
            raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

        # Remove from saved registry if present
        if found_in_saved:
            del saved_registry[rule_id]

        # For built-in rules, mark as deleted so they don't reappear from RULES_REGISTRY
        if is_builtin:
            saved_registry[rule_id] = {"_deleted": True}

        # Create new version
        new_version = existing.version + 1
        full_config = dict(existing.rules)
        full_config["rules_registry"] = saved_registry

        existing.is_active = False

        new_config = DecisionRulesConfig(
            version=new_version,
            name=f"Rules v{new_version}",
            rules=full_config,
            is_active=True,
            created_by=current_user.id,
        )
        db.add(new_config)

        db.add(AuditLog(
            entity_type="rules", entity_id=0, action="rule_deleted",
            user_id=current_user.id,
            old_values={"rule_id": rule_id, "is_builtin": is_builtin},
            details=f"Rule '{rule_id}' deleted by {current_user.email}",
        ))

        await db.flush()

        return {"message": f"Rule {rule_id} deleted", "version": new_version}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="delete_rule")
        raise


@router.post("/rules/generate", response_model=RuleGenerateResponse)
async def generate_rule_endpoint(
    body: RuleGenerateRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Use AI to generate a rule from a natural-language prompt."""
    try:
        result = generate_rule(
            prompt=body.prompt,
            conversation_history=body.conversation_history,
        )
        return RuleGenerateResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=None, module="api.admin", function_name="generate_rule_endpoint")
        raise


# ── Rules history / stats / AI endpoints ──────────────────────────────


@router.get("/rules/history")
async def get_rules_history(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Return audit trail entries for rules changes."""
    try:
        # Total count
        count_q = select(func.count()).select_from(AuditLog).where(AuditLog.entity_type == "rules")
        total = (await db.execute(count_q)).scalar() or 0

        # Paginated entries with user name
        q = (
            select(AuditLog, User.first_name, User.last_name)
            .outerjoin(User, AuditLog.user_id == User.id)
            .where(AuditLog.entity_type == "rules")
            .order_by(desc(AuditLog.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = (await db.execute(q)).all()

        entries = []
        for audit, first_name, last_name in rows:
            user_name = f"{first_name or ''} {last_name or ''}".strip() or None
            old_vals = audit.old_values or {}
            entries.append({
                "id": audit.id,
                "action": audit.action,
                "version": old_vals.get("version") or audit.entity_id,
                "new_version": (audit.new_values or {}).get("version", audit.entity_id),
                "user_name": user_name or "System",
                "created_at": audit.created_at.isoformat() if audit.created_at else None,
                "changes": old_vals.get("changes", []),
                "details": audit.details,
            })

        return {"entries": entries, "total": total}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="get_rules_history")
        raise


@router.get("/rules/stats")
async def get_rules_stats(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Return per-rule pass/fail statistics aggregated from decision rules_results."""
    try:
        # Use jsonb_array_elements to unnest the rules_results.rules array
        # Cast to jsonb since column may be JSON not JSONB
        raw_sql = text("""
            SELECT
                elem->>'id' AS rule_id,
                COUNT(*) AS total,
                SUM(CASE WHEN (elem->>'passed')::boolean THEN 1 ELSE 0 END) AS passed,
                SUM(CASE WHEN NOT (elem->>'passed')::boolean THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN NOT (elem->>'passed')::boolean AND elem->>'severity' = 'hard' THEN 1 ELSE 0 END) AS decline,
                SUM(CASE WHEN NOT (elem->>'passed')::boolean AND elem->>'severity' IN ('soft', 'refer') THEN 1 ELSE 0 END) AS refer
            FROM decisions,
                 jsonb_array_elements((rules_results::jsonb)->'rules') AS elem
            WHERE rules_results IS NOT NULL
            GROUP BY elem->>'id'
        """)
        result = await db.execute(raw_sql)
        stats: dict[str, dict] = {}
        for row in result:
            stats[row.rule_id] = {
                "total": int(row.total),
                "passed": int(row.passed),
                "failed": int(row.failed),
                "decline": int(row.decline),
                "refer": int(row.refer),
            }
        return stats
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="get_rules_stats")
        raise


@router.post("/rules/ai/analyze")
async def analyze_rules(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """AI-powered analysis and optimization recommendations for current rules."""
    try:
        from app.config import settings as cfg

        # Gather current rules
        result = await db.execute(
            select(DecisionRulesConfig)
            .where(DecisionRulesConfig.is_active == True)
            .order_by(desc(DecisionRulesConfig.version))
            .limit(1)
        )
        db_config = result.scalar_one_or_none()
        if not db_config:
            raise HTTPException(status_code=404, detail="No active rules configuration found")

        registry = db_config.rules.get("rules_registry", {})
        # Filter out deleted
        active_rules = {k: v for k, v in registry.items() if isinstance(v, dict) and not v.get("_deleted")}

        # Gather stats (reuse the same SQL)
        raw_sql = text("""
            SELECT
                elem->>'id' AS rule_id,
                COUNT(*) AS total,
                SUM(CASE WHEN (elem->>'passed')::boolean THEN 1 ELSE 0 END) AS passed,
                SUM(CASE WHEN NOT (elem->>'passed')::boolean THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN NOT (elem->>'passed')::boolean AND elem->>'severity' = 'hard' THEN 1 ELSE 0 END) AS decline,
                SUM(CASE WHEN NOT (elem->>'passed')::boolean AND elem->>'severity' IN ('soft', 'refer') THEN 1 ELSE 0 END) AS refer
            FROM decisions,
                 jsonb_array_elements((rules_results::jsonb)->'rules') AS elem
            WHERE rules_results IS NOT NULL
            GROUP BY elem->>'id'
        """)
        stats_result = await db.execute(raw_sql)
        stats: dict[str, dict] = {}
        for row in stats_result:
            stats[row.rule_id] = {
                "total": int(row.total),
                "passed": int(row.passed),
                "failed": int(row.failed),
                "decline": int(row.decline),
                "refer": int(row.refer),
            }

        # Overall counts
        total_apps_q = select(func.count()).select_from(Decision)
        total_apps = (await db.execute(total_apps_q)).scalar() or 0

        if not cfg.openai_api_key:
            # Provide deterministic fallback analysis
            top_decliners = sorted(
                [(rid, s) for rid, s in stats.items() if s["decline"] > 0],
                key=lambda x: -x[1]["decline"],
            )
            recs = []
            for rid, s in top_decliners[:5]:
                rule_def = active_rules.get(rid, {})
                recs.append({
                    "rule_id": rid,
                    "rule_name": rule_def.get("name", rid),
                    "current_declines": s["decline"],
                    "total_evaluated": s["total"],
                    "decline_rate": round(s["decline"] / s["total"] * 100, 1) if s["total"] else 0,
                    "recommendation": "Review threshold for potential optimization",
                    "risk": "medium",
                })
            return {
                "total_applications": total_apps,
                "rules_evaluated": len(stats),
                "top_decliners": recs,
                "recommendations": recs,
                "ai_powered": False,
                "summary": f"Deterministic analysis of {len(stats)} rules across {total_apps} decisions. OpenAI unavailable.",
            }

        # Build AI prompt
        rules_info = []
        for rid, rdef in active_rules.items():
            s = stats.get(rid, {"total": 0, "passed": 0, "failed": 0, "decline": 0, "refer": 0})
            rules_info.append({
                "id": rid,
                "name": rdef.get("name", rid),
                "field": rdef.get("field"),
                "operator": rdef.get("operator"),
                "threshold": rdef.get("threshold"),
                "severity": rdef.get("severity"),
                "enabled": rdef.get("enabled", True),
                **s,
            })

        prompt = f"""Analyze these lending rules and their impact statistics. Total applications: {total_apps}.

Rules and their stats:
{json.dumps(rules_info, indent=2, default=str)}

Provide:
1. A summary of the current acceptance vs decline profile
2. Top rules causing declines (sorted by impact)
3. Specific threshold or configuration recommendations to improve acceptance without materially increasing default risk
4. A risk assessment for each recommendation

Return ONLY valid JSON with this structure:
{{
  "summary": "overall analysis text",
  "total_applications": {total_apps},
  "rules_evaluated": {len(rules_info)},
  "top_decliners": [
    {{"rule_id": "R01", "rule_name": "...", "current_declines": 50, "total_evaluated": 100, "decline_rate": 50.0, "recommendation": "...", "risk": "low|medium|high"}}
  ],
  "recommendations": [
    {{"rule_id": "R01", "rule_name": "...", "change": "Reduce threshold from X to Y", "projected_impact": "+N% acceptance", "risk": "low|medium|high", "rationale": "..."}}
  ],
  "ai_powered": true
}}"""

        import json as json_mod
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=cfg.openai_api_key)
        resp = await client.chat.completions.create(
            model=cfg.openai_model,
            messages=[
                {"role": "system", "content": "You are a lending risk analytics expert. Analyze rules and provide optimization recommendations."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        raw = resp.choices[0].message.content or "{}"
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
        analysis = json_mod.loads(raw)
        analysis["ai_powered"] = True
        return analysis

    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="analyze_rules")
        raise


def _product_to_response(product: CreditProduct) -> CreditProductResponse:
    rate_tiers = getattr(product, "rate_tiers", None) or []
    return CreditProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        merchant_id=product.merchant_id,
        merchant_name=product.merchant.name if product.merchant else None,
        min_term_months=product.min_term_months,
        max_term_months=product.max_term_months,
        min_amount=float(product.min_amount),
        max_amount=float(product.max_amount),
        repayment_scheme=product.repayment_scheme,
        grace_period_days=product.grace_period_days,
        is_active=product.is_active,
        interest_rate=float(product.interest_rate) if product.interest_rate else None,
        eligibility_criteria=product.eligibility_criteria,
        lifecycle_status=getattr(product, "lifecycle_status", "active") or "active",
        version=getattr(product, "version", 1) or 1,
        channels=product.channels,
        target_segments=product.target_segments,
        internal_notes=product.internal_notes,
        regulatory_code=product.regulatory_code,
        ai_summary=product.ai_summary,
        decision_tree_id=product.decision_tree_id,
        default_strategy_id=product.default_strategy_id,
        score_ranges=[ProductScoreRangeResponse.model_validate(sr) for sr in product.score_ranges],
        fees=[ProductFeeResponse.model_validate(fee) for fee in product.fees],
        rate_tiers=[ProductRateTierResponse.model_validate(rt) for rt in rate_tiers],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("/merchants", response_model=list[MerchantResponse])
async def list_merchants(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Merchant).order_by(Merchant.name).limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.post("/merchants", response_model=MerchantResponse, status_code=status.HTTP_201_CREATED)
async def create_merchant(
    data: MerchantCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        exists = await db.execute(select(Merchant).where(func.lower(Merchant.name) == data.name.lower()))
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Merchant with this name already exists")

        merchant = Merchant(name=data.name.strip(), is_active=data.is_active)
        db.add(merchant)
        await db.flush()

        # Every merchant gets an Online branch by default
        online = Branch(
            merchant_id=merchant.id,
            name="Online",
            address="Online",
            is_online=True,
            is_active=True,
        )
        db.add(online)
        await db.flush()
        await db.refresh(merchant)
        return merchant
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="create_merchant")
        raise


@router.put("/merchants/{merchant_id}", response_model=MerchantResponse)
async def update_merchant(
    merchant_id: int,
    data: MerchantUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
        merchant = result.scalar_one_or_none()
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found")

        if data.name is not None:
            merchant.name = data.name.strip()
        if data.is_active is not None:
            merchant.is_active = data.is_active

        await db.flush()
        await db.refresh(merchant)
        return merchant
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="update_merchant")
        raise


@router.delete("/merchants/{merchant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_merchant(
    merchant_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
        merchant = result.scalar_one_or_none()
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found")
        await db.delete(merchant)
        await db.flush()
        return None
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="delete_merchant")
        raise


@router.get("/merchants/{merchant_id}/branches", response_model=list[BranchResponse])
async def list_branches(
    merchant_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(Branch).where(Branch.merchant_id == merchant_id).order_by(Branch.is_online.desc(), Branch.name)
        )
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="list_branches")
        raise


@router.post("/merchants/{merchant_id}/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
async def create_branch(
    merchant_id: int,
    data: BranchCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        m = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
        if not m.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Merchant not found")

        branch = Branch(
            merchant_id=merchant_id,
            name=data.name.strip(),
            address=data.address,
            is_online=data.is_online,
            is_active=data.is_active,
        )
        db.add(branch)
        await db.flush()
        await db.refresh(branch)
        return branch
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="create_branch")
        raise


@router.put("/branches/{branch_id}", response_model=BranchResponse)
async def update_branch(
    branch_id: int,
    data: BranchUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(Branch).where(Branch.id == branch_id))
        branch = result.scalar_one_or_none()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")

        _BRANCH_EDITABLE = ("name", "address", "is_online", "is_active")
        for field in _BRANCH_EDITABLE:
            value = getattr(data, field, None)
            if value is not None:
                setattr(branch, field, value)

        await db.flush()
        await db.refresh(branch)
        return branch
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="update_branch")
        raise


@router.delete("/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(
    branch_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(Branch).where(Branch.id == branch_id))
        branch = result.scalar_one_or_none()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        await db.delete(branch)
        await db.flush()
        return None
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="delete_branch")
        raise


@router.get("/merchants/{merchant_id}/categories", response_model=list[ProductCategoryResponse])
async def list_categories(
    merchant_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        m = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
        if not m.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Merchant not found")
        result = await db.execute(
            select(ProductCategory).where(ProductCategory.merchant_id == merchant_id).order_by(ProductCategory.name)
        )
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="list_categories")
        raise


@router.post("/merchants/{merchant_id}/categories", response_model=ProductCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    merchant_id: int,
    data: ProductCategoryCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        m = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
        if not m.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Merchant not found")
        exists = await db.execute(
            select(ProductCategory).where(
                ProductCategory.merchant_id == merchant_id,
                func.lower(ProductCategory.name) == data.name.strip().lower(),
            )
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Category with this name already exists for merchant")
        category = ProductCategory(merchant_id=merchant_id, name=data.name.strip())
        db.add(category)
        await db.flush()
        await db.refresh(category)
        return category
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="create_category")
        raise


@router.put("/categories/{category_id}", response_model=ProductCategoryResponse)
async def update_category(
    category_id: int,
    data: ProductCategoryUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(ProductCategory).where(ProductCategory.id == category_id))
        category = result.scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        category.name = data.name.strip()
        await db.flush()
        await db.refresh(category)
        return category
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="update_category")
        raise


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(ProductCategory).where(ProductCategory.id == category_id))
        category = result.scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        await db.delete(category)
        await db.flush()
        return None
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="delete_category")
        raise


@router.get("/products", response_model=list[CreditProductResponse])
async def list_products(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(CreditProduct)
            .options(
                selectinload(CreditProduct.score_ranges),
                selectinload(CreditProduct.fees),
                selectinload(CreditProduct.rate_tiers),
                selectinload(CreditProduct.merchant),
            )
            .order_by(CreditProduct.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_product_to_response(p) for p in result.scalars().unique().all()]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="list_products")
        raise


@router.get("/products/{product_id}", response_model=CreditProductResponse)
async def get_product(
    product_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(CreditProduct)
            .where(CreditProduct.id == product_id)
            .options(
                selectinload(CreditProduct.score_ranges),
                selectinload(CreditProduct.fees),
                selectinload(CreditProduct.rate_tiers),
                selectinload(CreditProduct.merchant),
            )
        )
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return _product_to_response(product)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="get_product")
        raise


@router.post("/products", response_model=CreditProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: CreditProductCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        product = CreditProduct(
            name=data.name.strip(),
            description=data.description,
            merchant_id=data.merchant_id,
            min_term_months=data.min_term_months,
            max_term_months=data.max_term_months,
            min_amount=data.min_amount,
            max_amount=data.max_amount,
            repayment_scheme=data.repayment_scheme,
            grace_period_days=data.grace_period_days,
            is_active=data.is_active,
            interest_rate=data.interest_rate,
            eligibility_criteria=data.eligibility_criteria,
            lifecycle_status=data.lifecycle_status,
            channels=data.channels,
            target_segments=data.target_segments,
            internal_notes=data.internal_notes,
            regulatory_code=data.regulatory_code,
            default_strategy_id=data.default_strategy_id,
            decision_tree_id=data.decision_tree_id,
        )
        db.add(product)
        await db.flush()

        for sr in data.score_ranges:
            db.add(ProductScoreRange(credit_product_id=product.id, min_score=sr.min_score, max_score=sr.max_score))
        for fee in data.fees:
            db.add(
                ProductFee(
                    credit_product_id=product.id,
                    fee_type=fee.fee_type,
                    fee_base=fee.fee_base,
                    fee_amount=fee.fee_amount,
                    is_available=fee.is_available,
                )
            )
        for rt in data.rate_tiers:
            db.add(
                ProductRateTier(
                    credit_product_id=product.id,
                    tier_name=rt.tier_name,
                    min_score=rt.min_score,
                    max_score=rt.max_score,
                    interest_rate=rt.interest_rate,
                    max_ltv_pct=rt.max_ltv_pct,
                    max_dti_pct=rt.max_dti_pct,
                    is_active=rt.is_active,
                )
            )
        await db.flush()
        return await get_product(product.id, current_user, db)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="create_product")
        raise


@router.put("/products/{product_id}", response_model=CreditProductResponse)
async def update_product(
    product_id: int,
    data: CreditProductUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(CreditProduct).where(CreditProduct.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        _PRODUCT_EDITABLE = (
            "name", "description", "merchant_id",
            "min_term_months", "max_term_months", "min_amount", "max_amount",
            "repayment_scheme", "grace_period_days", "is_active",
            "interest_rate", "eligibility_criteria", "lifecycle_status",
            "channels", "target_segments", "internal_notes", "regulatory_code",
            "default_strategy_id", "decision_tree_id",
        )
        update_data = data.model_dump(exclude_unset=True)
        for field in _PRODUCT_EDITABLE:
            if field in update_data:
                setattr(product, field, update_data[field])
        await db.flush()
        return await get_product(product_id, current_user, db)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="update_product")
        raise


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(CreditProduct).where(CreditProduct.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        await db.delete(product)
        await db.flush()
        return None
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="delete_product")
        raise


@router.post("/products/{product_id}/score-ranges", response_model=ProductScoreRangeResponse, status_code=status.HTTP_201_CREATED)
async def create_score_range(
    product_id: int,
    data: ProductScoreRangeCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        item = ProductScoreRange(credit_product_id=product_id, min_score=data.min_score, max_score=data.max_score)
        db.add(item)
        await db.flush()
        await db.refresh(item)
        return item
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="create_score_range")
        raise


@router.put("/score-ranges/{score_range_id}", response_model=ProductScoreRangeResponse)
async def update_score_range(
    score_range_id: int,
    data: ProductScoreRangeUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(ProductScoreRange).where(ProductScoreRange.id == score_range_id))
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Score range not found")
        _SCORE_EDITABLE = ("min_score", "max_score")
        for field in _SCORE_EDITABLE:
            value = getattr(data, field, None)
            if value is not None:
                setattr(item, field, value)
        await db.flush()
        await db.refresh(item)
        return item
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="update_score_range")
        raise


@router.delete("/score-ranges/{score_range_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_score_range(
    score_range_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(ProductScoreRange).where(ProductScoreRange.id == score_range_id))
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Score range not found")
        await db.delete(item)
        await db.flush()
        return None
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="delete_score_range")
        raise


@router.post("/products/{product_id}/fees", response_model=ProductFeeResponse, status_code=status.HTTP_201_CREATED)
async def create_fee(
    product_id: int,
    data: ProductFeeCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        fee = ProductFee(
            credit_product_id=product_id,
            fee_type=data.fee_type,
            fee_base=data.fee_base,
            fee_amount=data.fee_amount,
            is_available=data.is_available,
        )
        db.add(fee)
        await db.flush()
        await db.refresh(fee)
        return fee
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="create_fee")
        raise


@router.put("/fees/{fee_id}", response_model=ProductFeeResponse)
async def update_fee(
    fee_id: int,
    data: ProductFeeUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(ProductFee).where(ProductFee.id == fee_id))
        fee = result.scalar_one_or_none()
        if not fee:
            raise HTTPException(status_code=404, detail="Fee not found")
        _FEE_EDITABLE = ("fee_type", "fee_base", "fee_amount", "is_available")
        for field in _FEE_EDITABLE:
            value = getattr(data, field, None)
            if value is not None:
                setattr(fee, field, value)
        await db.flush()
        await db.refresh(fee)
        return fee
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="update_fee")
        raise


@router.delete("/fees/{fee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fee(
    fee_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(ProductFee).where(ProductFee.id == fee_id))
        fee = result.scalar_one_or_none()
        if not fee:
            raise HTTPException(status_code=404, detail="Fee not found")
        await db.delete(fee)
        await db.flush()
        return None
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="delete_fee")
        raise


# ═══════════════════════════════════════════════════════════════
# RATE TIERS (Risk-Based Pricing)
# ═══════════════════════════════════════════════════════════════


@router.post("/products/{product_id}/rate-tiers", response_model=ProductRateTierResponse, status_code=status.HTTP_201_CREATED)
async def create_rate_tier(
    product_id: int,
    data: ProductRateTierCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        tier = ProductRateTier(
            credit_product_id=product_id,
            tier_name=data.tier_name,
            min_score=data.min_score,
            max_score=data.max_score,
            interest_rate=data.interest_rate,
            max_ltv_pct=data.max_ltv_pct,
            max_dti_pct=data.max_dti_pct,
            is_active=data.is_active,
        )
        db.add(tier)
        await db.flush()
        await db.refresh(tier)
        return tier
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="create_rate_tier")
        raise


@router.put("/rate-tiers/{tier_id}", response_model=ProductRateTierResponse)
async def update_rate_tier(
    tier_id: int,
    data: ProductRateTierUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(ProductRateTier).where(ProductRateTier.id == tier_id))
        tier = result.scalar_one_or_none()
        if not tier:
            raise HTTPException(status_code=404, detail="Rate tier not found")
        for field in ("tier_name", "min_score", "max_score", "interest_rate", "max_ltv_pct", "max_dti_pct", "is_active"):
            value = getattr(data, field, None)
            if value is not None:
                setattr(tier, field, value)
        await db.flush()
        await db.refresh(tier)
        return tier
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="update_rate_tier")
        raise


@router.delete("/rate-tiers/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rate_tier(
    tier_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(ProductRateTier).where(ProductRateTier.id == tier_id))
        tier = result.scalar_one_or_none()
        if not tier:
            raise HTTPException(status_code=404, detail="Rate tier not found")
        await db.delete(tier)
        await db.flush()
        return None
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="delete_rate_tier")
        raise


# ═══════════════════════════════════════════════════════════════
# PRODUCT CLONING
# ═══════════════════════════════════════════════════════════════


@router.post("/products/{product_id}/clone", response_model=CreditProductResponse, status_code=status.HTTP_201_CREATED)
async def clone_product(
    product_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Deep-clone a product with all fees, score ranges, and rate tiers."""
    try:
        result = await db.execute(
            select(CreditProduct)
            .where(CreditProduct.id == product_id)
            .options(
                selectinload(CreditProduct.score_ranges),
                selectinload(CreditProduct.fees),
                selectinload(CreditProduct.rate_tiers),
            )
        )
        source = result.scalar_one_or_none()
        if not source:
            raise HTTPException(status_code=404, detail="Product not found")

        clone = CreditProduct(
            name=f"{source.name} (Copy)",
            description=source.description,
            merchant_id=source.merchant_id,
            min_term_months=source.min_term_months,
            max_term_months=source.max_term_months,
            min_amount=source.min_amount,
            max_amount=source.max_amount,
            repayment_scheme=source.repayment_scheme,
            grace_period_days=source.grace_period_days,
            is_active=False,
            interest_rate=source.interest_rate,
            eligibility_criteria=source.eligibility_criteria,
            lifecycle_status="draft",
            channels=source.channels,
            target_segments=source.target_segments,
            internal_notes=f"Cloned from product #{source.id} ({source.name})",
            regulatory_code=source.regulatory_code,
        )
        db.add(clone)
        await db.flush()

        for sr in source.score_ranges:
            db.add(ProductScoreRange(credit_product_id=clone.id, min_score=sr.min_score, max_score=sr.max_score))
        for fee in source.fees:
            db.add(ProductFee(
                credit_product_id=clone.id, fee_type=fee.fee_type,
                fee_base=fee.fee_base, fee_amount=fee.fee_amount, is_available=fee.is_available,
            ))
        for rt in source.rate_tiers:
            db.add(ProductRateTier(
                credit_product_id=clone.id, tier_name=rt.tier_name,
                min_score=rt.min_score, max_score=rt.max_score,
                interest_rate=rt.interest_rate, max_ltv_pct=rt.max_ltv_pct,
                max_dti_pct=rt.max_dti_pct, is_active=rt.is_active,
            ))
        await db.flush()

        db.add(AuditLog(
            entity_type="product", entity_id=clone.id,
            action="clone", user_id=current_user.id,
            details=f"Cloned from product #{source.id}",
        ))
        await db.flush()

        return await get_product(clone.id, current_user, db)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="clone_product")
        raise


# ═══════════════════════════════════════════════════════════════
# AI-POWERED PRODUCT INTELLIGENCE
# ═══════════════════════════════════════════════════════════════


@router.get("/products/portfolio/overview")
async def product_portfolio_overview(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Portfolio-level product analytics."""
    from app.services.product_intelligence import portfolio_overview
    try:
        return await portfolio_overview(db)
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="portfolio_overview")
        raise


@router.get("/products/{product_id}/analytics")
async def product_analytics(
    product_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Comprehensive product performance analytics."""
    from app.services.product_intelligence import get_product_metrics, calculate_health_score
    try:
        metrics = await get_product_metrics(product_id, db)
        health = await calculate_health_score(product_id, db)
        return {"metrics": metrics, "health": health}
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="product_analytics")
        raise


@router.post("/products/ai/advisor")
async def product_ai_advisor(
    data: ProductAdvisorRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """AI product advisor — ask questions about product design, optimization, etc."""
    from app.services.product_intelligence import ai_advisor
    try:
        return await ai_advisor(data.product_id, data.question, db, data.conversation_history)
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="product_ai_advisor")
        raise


@router.post("/products/ai/simulate")
async def product_simulate(
    data: ProductSimulateRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Simulate impact of product parameter changes."""
    from app.services.product_intelligence import simulate_changes
    try:
        return await simulate_changes(data.product_id, data.changes, db)
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="product_simulate")
        raise


@router.post("/products/ai/generate")
async def product_ai_generate(
    data: ProductGenerateRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """AI-generate a complete product configuration from natural language."""
    from app.services.product_intelligence import generate_product
    try:
        return await generate_product(data.description, db)
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="product_ai_generate")
        raise


@router.post("/products/ai/compare")
async def product_compare(
    data: ProductCompareRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Compare multiple products side-by-side with AI analysis."""
    from app.services.product_intelligence import compare_products
    try:
        return await compare_products(data.product_ids, db)
    except Exception as e:
        await log_error(e, db=db, module="api.admin", function_name="product_compare")
        raise


# ═══════════════════════════════════════════════════════════════
# AUDIT TRAIL
# ═══════════════════════════════════════════════════════════════


class AuditLogEntry(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    action: str
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


@router.get("/audit-trail")
async def get_audit_trail(
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER)),
    db: AsyncSession = Depends(get_db),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    action: Optional[str] = Query(None, description="Filter by action"),
    user_id: Optional[int] = Query(None, description="Filter by user who performed the action"),
    search: Optional[str] = Query(None, description="Search in details text"),
    date_from: Optional[str] = Query(None, description="Start date (ISO format)"),
    date_to: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Global audit trail with filtering."""
    from datetime import datetime as dt

    query = (
        select(AuditLog, User.first_name, User.last_name)
        .outerjoin(User, AuditLog.user_id == User.id)
    )

    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if action:
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if search:
        query = query.where(AuditLog.details.ilike(f"%{search}%"))
    if date_from:
        try:
            query = query.where(AuditLog.created_at >= dt.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.where(AuditLog.created_at <= dt.fromisoformat(date_to))
        except ValueError:
            pass

    # Count
    from sqlalchemy import func as sqla_func
    count_q = select(sqla_func.count()).select_from(AuditLog)
    if entity_type:
        count_q = count_q.where(AuditLog.entity_type == entity_type)
    if action:
        count_q = count_q.where(AuditLog.action == action)
    if user_id:
        count_q = count_q.where(AuditLog.user_id == user_id)
    if search:
        count_q = count_q.where(AuditLog.details.ilike(f"%{search}%"))
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
    result = await db.execute(query)

    entries = []
    for row in result.all():
        log = row[0]
        first = row[1] or ""
        last = row[2] or ""
        entries.append(AuditLogEntry(
            id=log.id,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            user_id=log.user_id,
            user_name=f"{first} {last}".strip() or None,
            old_values=log.old_values,
            new_values=log.new_values,
            details=log.details,
            ip_address=log.ip_address,
            created_at=log.created_at.isoformat() if log.created_at else "",
        ))

    # Distinct entity types and actions for filter dropdowns
    types_q = await db.execute(select(AuditLog.entity_type).distinct())
    actions_q = await db.execute(select(AuditLog.action).distinct())
    entity_types = sorted([r[0] for r in types_q.all() if r[0]])
    actions_list = sorted([r[0] for r in actions_q.all() if r[0]])

    return {
        "entries": entries,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "entity_types": entity_types,
            "actions": actions_list,
        },
    }
