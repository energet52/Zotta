"""Credit Scoring Module API — Scorecard CRUD, scoring, champion-challenger,
performance monitoring, batch scoring, and back-testing.
"""

from __future__ import annotations

import io
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth_utils import require_roles
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, ApplicantProfile
from app.models.scorecard import (
    Scorecard, ScorecardStatus, ScorecardCharacteristic, ScorecardBin,
    BinType, ScoreResult, ScorecardChangeLog, ScorecardChangeStatus,
    ScorecardPerformanceSnapshot, ScorecardAlert,
)
from app.services.scorecard_engine import (
    score_application, extract_applicant_data, generate_scoring_script,
    parse_scoring_script, parse_scorecard_csv, build_scorecard_from_parsed,
    get_active_scorecards, score_all_models, select_decisioning_model,
    simulate_impact, what_if_analysis, batch_score_csv,
)
from app.services.scorecard_performance import (
    generate_performance_snapshot, champion_challenger_comparison,
    get_score_band_analysis, check_scorecard_health,
    get_vintage_analysis, get_performance_history,
)

try:
    from app.services.error_logging import log_error
except ImportError:
    async def log_error(*a, **kw):
        pass

router = APIRouter()

STAFF_ROLES = (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER, UserRole.JUNIOR_UNDERWRITER)
SENIOR_ROLES = (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER)


# ══════════════════════════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════════════════════════

class BinSchema(BaseModel):
    bin_type: str  # range, category, default
    label: str
    points: float
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    category_value: Optional[str] = None
    notes: Optional[str] = None
    sort_order: int = 0


class CharacteristicSchema(BaseModel):
    code: str
    name: str
    data_field: str
    is_active: bool = True
    weight_multiplier: float = 1.0
    sort_order: int = 0
    bins: list[BinSchema] = []


class ScorecardCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    base_score: float = 0
    min_score: float = 100
    max_score: float = 850
    auto_approve_threshold: Optional[float] = None
    manual_review_threshold: Optional[float] = None
    auto_decline_threshold: Optional[float] = None
    target_products: Optional[list[str]] = None
    target_markets: Optional[list[str]] = None
    characteristics: list[CharacteristicSchema] = []


class ScorecardUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_score: Optional[float] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    auto_approve_threshold: Optional[float] = None
    manual_review_threshold: Optional[float] = None
    auto_decline_threshold: Optional[float] = None
    target_products: Optional[list[str]] = None


class EditPointsRequest(BaseModel):
    bin_id: int
    new_points: float
    justification: str = Field(min_length=5)


class EditBinRequest(BaseModel):
    characteristic_id: int
    bins: list[BinSchema]
    justification: str = Field(min_length=5)


class WeightScaleRequest(BaseModel):
    characteristic_id: int
    multiplier: float
    justification: str = Field(min_length=5)


class EditCutoffRequest(BaseModel):
    auto_approve_threshold: Optional[float] = None
    manual_review_threshold: Optional[float] = None
    auto_decline_threshold: Optional[float] = None
    justification: str = Field(min_length=5)


class TrafficAllocationRequest(BaseModel):
    scorecard_id: int
    traffic_pct: float = Field(ge=0, le=100)


class PromoteDemoteRequest(BaseModel):
    justification: str = Field(min_length=5)


class ScoreApplicationRequest(BaseModel):
    application_id: int


class WhatIfRequest(BaseModel):
    application_id: int
    modifications: dict


class ApproveChangeRequest(BaseModel):
    change_id: int


class BatchScoreRequest(BaseModel):
    scorecard_id: int


class SaveScriptRequest(BaseModel):
    script: str = Field(min_length=10)
    justification: str = Field(default="Script edited via UI", min_length=5)


# ══════════════════════════════════════════════════════════════════
# 1. Scorecard CRUD
# ══════════════════════════════════════════════════════════════════

@router.get("/")
async def list_scorecards(
    status: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List all scorecards with optional status filter."""
    q = select(Scorecard).order_by(Scorecard.created_at.desc())
    if status:
        q = q.where(Scorecard.status == ScorecardStatus(status))
    result = await db.execute(q)
    scorecards = result.scalars().all()
    return [_scorecard_summary(sc) for sc in scorecards]


@router.get("/{scorecard_id}")
async def get_scorecard(
    scorecard_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get full scorecard with characteristics and bins."""
    q = (
        select(Scorecard)
        .where(Scorecard.id == scorecard_id)
        .options(
            selectinload(Scorecard.characteristics)
            .selectinload(ScorecardCharacteristic.bins)
        )
    )
    sc = (await db.execute(q)).scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    return _scorecard_detail(sc)


@router.post("/")
async def create_scorecard(
    data: ScorecardCreateRequest,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new scorecard."""
    # Check name uniqueness
    existing = await db.execute(
        select(func.count()).where(Scorecard.name == data.name)
    )
    count = existing.scalar()
    version = (count or 0) + 1

    sc = Scorecard(
        name=data.name, version=version, description=data.description,
        base_score=data.base_score, min_score=data.min_score, max_score=data.max_score,
        auto_approve_threshold=data.auto_approve_threshold,
        manual_review_threshold=data.manual_review_threshold,
        auto_decline_threshold=data.auto_decline_threshold,
        target_products=data.target_products, target_markets=data.target_markets,
        status=ScorecardStatus.DRAFT, created_by=current_user.id,
    )

    for char_data in data.characteristics:
        char = ScorecardCharacteristic(
            code=char_data.code, name=char_data.name, data_field=char_data.data_field,
            is_active=char_data.is_active, weight_multiplier=char_data.weight_multiplier,
            sort_order=char_data.sort_order,
        )
        for bin_data in char_data.bins:
            b = ScorecardBin(
                bin_type=BinType(bin_data.bin_type), label=bin_data.label, points=bin_data.points,
                min_value=bin_data.min_value, max_value=bin_data.max_value,
                category_value=bin_data.category_value, notes=bin_data.notes,
                sort_order=bin_data.sort_order,
            )
            char.bins.append(b)
        sc.characteristics.append(char)

    db.add(sc)
    await db.flush()
    await db.refresh(sc, attribute_names=["characteristics"])
    return _scorecard_detail(sc)


@router.put("/{scorecard_id}")
async def update_scorecard(
    scorecard_id: int,
    data: ScorecardUpdateRequest,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Update scorecard metadata."""
    sc = await _get_scorecard(scorecard_id, db)
    if sc.status not in (ScorecardStatus.DRAFT, ScorecardStatus.VALIDATED):
        raise HTTPException(status_code=400, detail="Can only edit draft or validated scorecards")

    for field in ["name", "description", "base_score", "min_score", "max_score",
                   "auto_approve_threshold", "manual_review_threshold", "auto_decline_threshold",
                   "target_products"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(sc, field, val)

    await db.flush()
    return _scorecard_summary(sc)


@router.post("/{scorecard_id}/clone")
async def clone_scorecard(
    scorecard_id: int,
    name: str = Query(None),
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Clone a scorecard as starting point for a new version."""
    original = await _get_scorecard_with_bins(scorecard_id, db)
    clone_name = name or f"{original.name}"

    # Get next version
    count_q = select(func.count()).where(Scorecard.name == clone_name)
    count = (await db.execute(count_q)).scalar() or 0

    clone = Scorecard(
        name=clone_name, version=count + 1,
        description=f"Cloned from {original.name} v{original.version}",
        base_score=original.base_score, min_score=original.min_score, max_score=original.max_score,
        auto_approve_threshold=original.auto_approve_threshold,
        manual_review_threshold=original.manual_review_threshold,
        auto_decline_threshold=original.auto_decline_threshold,
        target_products=original.target_products, target_markets=original.target_markets,
        status=ScorecardStatus.DRAFT, cloned_from_id=original.id, created_by=current_user.id,
    )

    for char in original.characteristics:
        new_char = ScorecardCharacteristic(
            code=char.code, name=char.name, data_field=char.data_field,
            is_active=char.is_active, weight_multiplier=char.weight_multiplier,
            sort_order=char.sort_order,
        )
        for b in char.bins:
            new_bin = ScorecardBin(
                bin_type=b.bin_type, label=b.label, points=b.points,
                min_value=b.min_value, max_value=b.max_value,
                category_value=b.category_value, notes=b.notes, sort_order=b.sort_order,
            )
            new_char.bins.append(new_bin)
        clone.characteristics.append(new_char)

    db.add(clone)
    await db.flush()
    return {"id": clone.id, "name": clone.name, "version": clone.version, "status": clone.status.value}


@router.post("/import-csv")
async def import_scorecard_csv(
    file: UploadFile = File(...),
    name: str = Query(..., description="Scorecard name"),
    auto_approve: Optional[float] = Query(None),
    manual_review: Optional[float] = Query(None),
    auto_decline: Optional[float] = Query(None),
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Import a scorecard from CSV file."""
    content = (await file.read()).decode("utf-8-sig")
    parsed = parse_scorecard_csv(content)

    if parsed["errors"]:
        raise HTTPException(status_code=400, detail={"errors": parsed["errors"]})

    sc = build_scorecard_from_parsed(
        parsed, name=name, description=f"Imported from {file.filename}",
        auto_approve=auto_approve, manual_review=manual_review, auto_decline=auto_decline,
    )
    sc.created_by = current_user.id

    # Version check
    count_q = select(func.count()).where(Scorecard.name == name)
    count = (await db.execute(count_q)).scalar() or 0
    sc.version = count + 1

    db.add(sc)
    await db.flush()
    await db.refresh(sc, attribute_names=["characteristics"])
    return _scorecard_detail(sc)


# ══════════════════════════════════════════════════════════════════
# 2. Points / Weights / Cutoffs Editing
# ══════════════════════════════════════════════════════════════════

@router.patch("/{scorecard_id}/edit-points")
async def edit_points(
    scorecard_id: int,
    data: EditPointsRequest,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Edit points for a specific bin."""
    sc = await _get_scorecard(scorecard_id, db)
    bin_q = select(ScorecardBin).where(ScorecardBin.id == data.bin_id)
    b = (await db.execute(bin_q)).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Bin not found")

    old_points = b.points
    # Log change
    log = ScorecardChangeLog(
        scorecard_id=scorecard_id, change_type="edit_points",
        field_path=f"bin_{data.bin_id}", old_value=str(old_points),
        new_value=str(data.new_points), justification=data.justification,
        proposed_by=current_user.id, status=ScorecardChangeStatus.APPLIED,
    )
    db.add(log)
    b.points = data.new_points
    await db.flush()
    return {"status": "ok", "old_points": old_points, "new_points": data.new_points}


@router.patch("/{scorecard_id}/edit-bins")
async def edit_bins(
    scorecard_id: int,
    data: EditBinRequest,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Replace all bins for a characteristic."""
    await _get_scorecard(scorecard_id, db)
    char_q = select(ScorecardCharacteristic).where(ScorecardCharacteristic.id == data.characteristic_id)
    char = (await db.execute(char_q)).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Characteristic not found")

    # Log
    log = ScorecardChangeLog(
        scorecard_id=scorecard_id, change_type="edit_bins",
        field_path=f"char_{char.code}", old_value=str(len(char.bins)),
        new_value=str(len(data.bins)), justification=data.justification,
        proposed_by=current_user.id, status=ScorecardChangeStatus.APPLIED,
    )
    db.add(log)

    # Delete old bins
    for old_bin in list(char.bins):
        await db.delete(old_bin)

    # Add new bins
    for i, bin_data in enumerate(data.bins):
        new_bin = ScorecardBin(
            characteristic_id=char.id,
            bin_type=BinType(bin_data.bin_type), label=bin_data.label, points=bin_data.points,
            min_value=bin_data.min_value, max_value=bin_data.max_value,
            category_value=bin_data.category_value, notes=bin_data.notes, sort_order=i,
        )
        db.add(new_bin)

    await db.flush()
    return {"status": "ok", "bins_count": len(data.bins)}


@router.patch("/{scorecard_id}/weight-scale")
async def weight_scale(
    scorecard_id: int,
    data: WeightScaleRequest,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Apply weight multiplier to a characteristic."""
    await _get_scorecard(scorecard_id, db)
    char_q = select(ScorecardCharacteristic).where(ScorecardCharacteristic.id == data.characteristic_id)
    char = (await db.execute(char_q)).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Characteristic not found")

    old_mult = char.weight_multiplier
    log = ScorecardChangeLog(
        scorecard_id=scorecard_id, change_type="weight_scale",
        field_path=f"char_{char.code}.weight_multiplier",
        old_value=str(old_mult), new_value=str(data.multiplier),
        justification=data.justification,
        proposed_by=current_user.id, status=ScorecardChangeStatus.APPLIED,
    )
    db.add(log)
    char.weight_multiplier = data.multiplier
    await db.flush()
    return {"status": "ok", "old_multiplier": old_mult, "new_multiplier": data.multiplier}


@router.patch("/{scorecard_id}/edit-cutoffs")
async def edit_cutoffs(
    scorecard_id: int,
    data: EditCutoffRequest,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Edit scoring cutoff thresholds."""
    sc = await _get_scorecard(scorecard_id, db)
    changes = {}
    if data.auto_approve_threshold is not None:
        changes["auto_approve"] = (sc.auto_approve_threshold, data.auto_approve_threshold)
        sc.auto_approve_threshold = data.auto_approve_threshold
    if data.manual_review_threshold is not None:
        changes["manual_review"] = (sc.manual_review_threshold, data.manual_review_threshold)
        sc.manual_review_threshold = data.manual_review_threshold
    if data.auto_decline_threshold is not None:
        changes["auto_decline"] = (sc.auto_decline_threshold, data.auto_decline_threshold)
        sc.auto_decline_threshold = data.auto_decline_threshold

    log = ScorecardChangeLog(
        scorecard_id=scorecard_id, change_type="edit_cutoffs",
        field_path="cutoffs", old_value=str({k: v[0] for k, v in changes.items()}),
        new_value=str({k: v[1] for k, v in changes.items()}),
        justification=data.justification,
        proposed_by=current_user.id, status=ScorecardChangeStatus.APPLIED,
    )
    db.add(log)
    await db.flush()
    return {"status": "ok", "changes": {k: {"old": v[0], "new": v[1]} for k, v in changes.items()}}


# ══════════════════════════════════════════════════════════════════
# 3. Raw Scoring Script
# ══════════════════════════════════════════════════════════════════

@router.get("/{scorecard_id}/script")
async def get_scoring_script(
    scorecard_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get the raw scoring script for a scorecard."""
    sc = await _get_scorecard_with_bins(scorecard_id, db)
    script = generate_scoring_script(sc)
    return {"scorecard_id": sc.id, "name": sc.name, "version": sc.version, "script": script}


@router.put("/{scorecard_id}/script")
async def save_scoring_script(
    scorecard_id: int,
    data: SaveScriptRequest,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Save an edited scoring script and sync characteristics/bins.

    Parses the script text back into structured characteristics/bins,
    replaces all existing characteristics+bins on the scorecard, and
    logs the change in the audit trail.
    """
    sc = await _get_scorecard_with_bins(scorecard_id, db)

    # Parse the script
    parsed = parse_scoring_script(data.script)
    if parsed.get("errors"):
        raise HTTPException(status_code=422, detail=f"Script parse errors: {'; '.join(parsed['errors'])}")

    # Capture old state for audit
    old_script = generate_scoring_script(sc)

    # Update base score / score range if changed in script
    sc.base_score = parsed["base_score"]
    sc.min_score = parsed["min_score"]
    sc.max_score = parsed["max_score"]

    # Delete existing characteristics + bins (cascade)
    for char in list(sc.characteristics):
        for b in list(char.bins):
            await db.delete(b)
        await db.delete(char)
    await db.flush()

    # Rebuild from parsed script
    for i, char_data in enumerate(parsed["characteristics"]):
        char = ScorecardCharacteristic(
            scorecard_id=sc.id,
            code=char_data["code"],
            name=char_data["name"],
            data_field=char_data["data_field"],
            weight_multiplier=char_data.get("weight_multiplier", 1.0),
            sort_order=i,
            is_active=True,
        )
        db.add(char)
        await db.flush()  # get char.id

        for j, bin_data in enumerate(char_data["bins"]):
            b = ScorecardBin(
                characteristic_id=char.id,
                bin_type=BinType(bin_data["bin_type"]),
                label=bin_data["label"],
                points=bin_data["points"],
                sort_order=j,
                min_value=bin_data.get("min_value"),
                max_value=bin_data.get("max_value"),
                category_value=bin_data.get("category_value"),
            )
            db.add(b)

    await db.flush()

    # Audit log
    log = ScorecardChangeLog(
        scorecard_id=scorecard_id,
        change_type="script_edit",
        field_path="script",
        old_value=old_script[:2000] if old_script else "",
        new_value=data.script[:2000],
        justification=data.justification,
        proposed_by=current_user.id,
        status=ScorecardChangeStatus.APPLIED,
    )
    db.add(log)
    await db.flush()

    # Reload and return the full detail
    updated_sc = await _get_scorecard_with_bins(scorecard_id, db)
    return _scorecard_detail(updated_sc)


@router.post("/{scorecard_id}/live-calculate")
async def live_calculate(
    scorecard_id: int,
    applicant_data: dict,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Execute scorecard against provided data with step-by-step trace."""
    sc = await _get_scorecard_with_bins(scorecard_id, db)
    result = score_application(sc, applicant_data)
    return result


# ══════════════════════════════════════════════════════════════════
# 4. Champion-Challenger Management
# ══════════════════════════════════════════════════════════════════

@router.get("/champion-challenger/status")
async def get_champion_challenger_status(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get current champion-challenger configuration."""
    scorecards = await get_active_scorecards(db)
    result = []
    for sc in scorecards:
        result.append({
            "id": sc.id, "name": sc.name, "version": sc.version,
            "status": sc.status.value, "traffic_pct": sc.traffic_pct,
            "is_decisioning": sc.is_decisioning,
            "shadow_start_date": sc.shadow_start_date.isoformat() if sc.shadow_start_date else None,
            "challenger_start_date": sc.challenger_start_date.isoformat() if sc.challenger_start_date else None,
            "champion_start_date": sc.champion_start_date.isoformat() if sc.champion_start_date else None,
        })
    return result


@router.post("/{scorecard_id}/activate-shadow")
async def activate_shadow(
    scorecard_id: int,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Move scorecard to shadow mode."""
    sc = await _get_scorecard(scorecard_id, db)
    if sc.status not in (ScorecardStatus.DRAFT, ScorecardStatus.VALIDATED):
        raise HTTPException(status_code=400, detail=f"Cannot move from {sc.status.value} to shadow")
    sc.status = ScorecardStatus.SHADOW
    sc.traffic_pct = 0
    sc.is_decisioning = False
    sc.shadow_start_date = datetime.now(timezone.utc)
    await db.flush()
    return {"status": "ok", "scorecard_status": sc.status.value}


@router.post("/{scorecard_id}/activate-challenger")
async def activate_challenger(
    scorecard_id: int,
    traffic_pct: float = Query(5, ge=1, le=50),
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Activate scorecard as challenger with traffic allocation."""
    sc = await _get_scorecard(scorecard_id, db)
    if sc.status not in (ScorecardStatus.SHADOW, ScorecardStatus.VALIDATED):
        raise HTTPException(status_code=400, detail=f"Cannot activate as challenger from {sc.status.value}")

    # Check total challenger traffic doesn't exceed 50%
    existing_q = select(func.coalesce(func.sum(Scorecard.traffic_pct), 0)).where(
        Scorecard.status == ScorecardStatus.CHALLENGER, Scorecard.id != scorecard_id,
    )
    existing_traffic = (await db.execute(existing_q)).scalar() or 0
    if existing_traffic + traffic_pct > 50:
        raise HTTPException(status_code=400, detail=f"Total challenger traffic would be {existing_traffic + traffic_pct}%, max is 50%")

    sc.status = ScorecardStatus.CHALLENGER
    sc.traffic_pct = traffic_pct
    sc.is_decisioning = True
    sc.challenger_start_date = datetime.now(timezone.utc)
    await db.flush()
    return {"status": "ok", "scorecard_status": sc.status.value, "traffic_pct": sc.traffic_pct}


@router.post("/{scorecard_id}/promote-to-champion")
async def promote_to_champion(
    scorecard_id: int,
    data: PromoteDemoteRequest,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Promote a challenger to champion. Demotes current champion."""
    sc = await _get_scorecard(scorecard_id, db)
    if sc.status not in (ScorecardStatus.CHALLENGER, ScorecardStatus.SHADOW):
        raise HTTPException(status_code=400, detail=f"Can only promote challenger/shadow to champion")

    # Demote current champion(s)
    current_champions = (await db.execute(
        select(Scorecard).where(Scorecard.status == ScorecardStatus.CHAMPION)
    )).scalars().all()
    for old_champ in current_champions:
        old_champ.status = ScorecardStatus.RETIRED
        old_champ.retired_at = datetime.now(timezone.utc)
        old_champ.traffic_pct = 0
        old_champ.is_decisioning = False

    # Promote
    sc.status = ScorecardStatus.CHAMPION
    sc.traffic_pct = 100 - sum(
        s.traffic_pct for s in (await db.execute(
            select(Scorecard).where(
                Scorecard.status == ScorecardStatus.CHALLENGER, Scorecard.id != scorecard_id,
            )
        )).scalars().all()
    )
    sc.is_decisioning = True
    sc.champion_start_date = datetime.now(timezone.utc)
    sc.approved_by = current_user.id

    # Log
    log = ScorecardChangeLog(
        scorecard_id=scorecard_id, change_type="promote_to_champion",
        old_value="challenger", new_value="champion",
        justification=data.justification,
        proposed_by=current_user.id, status=ScorecardChangeStatus.APPLIED,
    )
    db.add(log)
    await db.flush()
    return {"status": "ok", "scorecard_status": sc.status.value}


@router.post("/{scorecard_id}/kill-switch")
async def kill_switch(
    scorecard_id: int,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Emergency: move model to shadow mode instantly."""
    sc = await _get_scorecard(scorecard_id, db)
    if sc.status == ScorecardStatus.CHAMPION:
        raise HTTPException(status_code=400, detail="Cannot kill-switch champion. Promote another first.")

    sc.status = ScorecardStatus.SHADOW
    sc.traffic_pct = 0
    sc.is_decisioning = False

    log = ScorecardChangeLog(
        scorecard_id=scorecard_id, change_type="kill_switch",
        old_value=sc.status.value, new_value="shadow",
        justification="Emergency kill switch activated",
        proposed_by=current_user.id, status=ScorecardChangeStatus.APPLIED,
    )
    db.add(log)
    await db.flush()
    return {"status": "ok", "scorecard_status": "shadow"}


@router.post("/{scorecard_id}/retire")
async def retire_scorecard(
    scorecard_id: int,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Retire a scorecard."""
    sc = await _get_scorecard(scorecard_id, db)
    if sc.status == ScorecardStatus.CHAMPION:
        raise HTTPException(status_code=400, detail="Cannot retire active champion")
    sc.status = ScorecardStatus.RETIRED
    sc.retired_at = datetime.now(timezone.utc)
    sc.traffic_pct = 0
    sc.is_decisioning = False
    await db.flush()
    return {"status": "ok"}


@router.patch("/traffic-allocation")
async def update_traffic_allocation(
    allocations: list[TrafficAllocationRequest],
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Update traffic allocations for multiple scorecards."""
    total = sum(a.traffic_pct for a in allocations)
    if total > 100:
        raise HTTPException(status_code=400, detail=f"Total traffic allocation is {total}%, must be ≤100%")

    for alloc in allocations:
        sc_q = select(Scorecard).where(Scorecard.id == alloc.scorecard_id)
        sc = (await db.execute(sc_q)).scalar_one_or_none()
        if not sc:
            continue
        sc.traffic_pct = alloc.traffic_pct

    await db.flush()
    return {"status": "ok", "total_allocated": total}


# ══════════════════════════════════════════════════════════════════
# 5. Scoring
# ══════════════════════════════════════════════════════════════════

@router.post("/score-application")
async def score_single_application(
    data: ScoreApplicationRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Score an application against all active scorecards."""
    app_q = select(LoanApplication).where(LoanApplication.id == data.application_id)
    app = (await db.execute(app_q)).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    profile_q = select(ApplicantProfile).where(ApplicantProfile.user_id == app.applicant_id)
    profile = (await db.execute(profile_q)).scalar_one_or_none()

    applicant_data = extract_applicant_data(profile, app)
    results = await score_all_models(data.application_id, applicant_data, db)

    return [{
        "scorecard_id": r.scorecard_id,
        "scorecard_name": r.scorecard_name,
        "scorecard_version": r.scorecard_version,
        "total_score": r.total_score,
        "decision": r.decision,
        "is_decisioning": r.is_decisioning,
        "model_role": r.model_role,
        "characteristic_scores": r.characteristic_scores,
        "reason_codes": r.reason_codes,
        "top_positive_factors": r.top_positive_factors,
        "top_negative_factors": r.top_negative_factors,
    } for r in results]


@router.get("/score-results/{application_id}")
async def get_score_results(
    application_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get all score results for an application."""
    q = (
        select(ScoreResult)
        .where(ScoreResult.loan_application_id == application_id)
        .order_by(ScoreResult.scored_at.desc())
    )
    results = (await db.execute(q)).scalars().all()
    return [{
        "id": r.id,
        "scorecard_id": r.scorecard_id,
        "scorecard_name": r.scorecard_name,
        "scorecard_version": r.scorecard_version,
        "total_score": r.total_score,
        "base_score_used": r.base_score_used,
        "decision": r.decision,
        "is_decisioning": r.is_decisioning,
        "model_role": r.model_role,
        "characteristic_scores": r.characteristic_scores,
        "reason_codes": r.reason_codes,
        "top_positive_factors": r.top_positive_factors,
        "top_negative_factors": r.top_negative_factors,
        "score_percentile": r.score_percentile,
        "scored_at": r.scored_at.isoformat() if r.scored_at else None,
    } for r in results]


@router.post("/{scorecard_id}/what-if")
async def run_what_if(
    scorecard_id: int,
    data: WhatIfRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Run what-if analysis on an application."""
    sc = await _get_scorecard_with_bins(scorecard_id, db)
    app_q = select(LoanApplication).where(LoanApplication.id == data.application_id)
    app = (await db.execute(app_q)).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    profile_q = select(ApplicantProfile).where(ApplicantProfile.user_id == app.applicant_id)
    profile = (await db.execute(profile_q)).scalar_one_or_none()

    base_data = extract_applicant_data(profile, app)
    result = what_if_analysis(sc, base_data, data.modifications)
    return result


@router.post("/{scorecard_id}/batch-score")
async def batch_score(
    scorecard_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Batch score a CSV file against a scorecard."""
    sc = await _get_scorecard_with_bins(scorecard_id, db)
    content = (await file.read()).decode("utf-8-sig")
    results = batch_score_csv(sc, content)
    return {
        "scorecard": {"id": sc.id, "name": sc.name, "version": sc.version},
        "total_scored": len(results),
        "results": results[:1000],  # Limit response size
        "summary": {
            "avg_score": round(sum(r["total_score"] for r in results) / max(len(results), 1), 1),
            "approval_rate": round(sum(1 for r in results if r["decision"] == "AUTO_APPROVE") / max(len(results), 1) * 100, 1),
            "decline_rate": round(sum(1 for r in results if r["decision"] == "AUTO_DECLINE") / max(len(results), 1) * 100, 1),
            "review_rate": round(sum(1 for r in results if r["decision"] == "MANUAL_REVIEW") / max(len(results), 1) * 100, 1),
        },
    }


@router.post("/{scorecard_id}/simulate-impact")
async def run_simulate_impact(
    scorecard_id: int,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Simulate scorecard impact on recent applications."""
    sc = await _get_scorecard_with_bins(scorecard_id, db)
    result = await simulate_impact(sc, db)
    return result


# ══════════════════════════════════════════════════════════════════
# 6. Performance Monitoring
# ══════════════════════════════════════════════════════════════════

@router.get("/{scorecard_id}/performance")
async def get_performance(
    scorecard_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get performance dashboard for a scorecard."""
    snap = await generate_performance_snapshot(scorecard_id, db)
    history = await get_performance_history(scorecard_id, db)

    return {
        "snapshot": {
            "date": snap.snapshot_date.isoformat(),
            "total_scored": snap.total_scored,
            "total_approved": snap.total_approved,
            "total_declined": snap.total_declined,
            "total_review": snap.total_review,
            "approval_rate": snap.approval_rate,
            "default_rate": snap.default_rate,
            "gini": snap.gini_coefficient,
            "ks": snap.ks_statistic,
            "auc_roc": snap.auc_roc,
            "psi": snap.psi,
            "avg_score": snap.avg_score,
            "avg_score_defaulters": snap.avg_score_defaulters,
            "avg_score_non_defaulters": snap.avg_score_non_defaulters,
            "score_distribution": snap.score_distribution,
            "score_band_analysis": snap.score_band_analysis,
        },
        "history": history,
    }


@router.get("/comparison/champion-challenger")
async def get_comparison(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Champion vs challenger comparison."""
    return await champion_challenger_comparison(db)


@router.get("/{scorecard_id}/vintage-analysis")
async def vintage_analysis(
    scorecard_id: int,
    months: int = Query(12, ge=3, le=36),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Vintage analysis for a scorecard."""
    return await get_vintage_analysis(scorecard_id, db, months)


@router.get("/{scorecard_id}/score-bands")
async def score_bands(
    scorecard_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Score band analysis."""
    return await get_score_band_analysis(scorecard_id, db)


@router.get("/{scorecard_id}/alerts")
async def get_alerts(
    scorecard_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get alerts for a scorecard."""
    q = (
        select(ScorecardAlert)
        .where(ScorecardAlert.scorecard_id == scorecard_id)
        .order_by(ScorecardAlert.created_at.desc())
        .limit(50)
    )
    alerts = (await db.execute(q)).scalars().all()
    return [{
        "id": a.id, "type": a.alert_type, "severity": a.severity,
        "title": a.title, "message": a.message,
        "recommendation": a.recommendation,
        "is_acknowledged": a.is_acknowledged,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in alerts]


@router.post("/{scorecard_id}/run-health-check")
async def run_health_check(
    scorecard_id: int,
    current_user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Run health checks and generate alerts."""
    alerts = await check_scorecard_health(scorecard_id, db)
    return {"alerts_generated": len(alerts), "alerts": alerts}


@router.patch("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge an alert."""
    q = select(ScorecardAlert).where(ScorecardAlert.id == alert_id)
    alert = (await db.execute(q)).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_acknowledged = True
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    await db.flush()
    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════
# 7. Change Log & Audit
# ══════════════════════════════════════════════════════════════════

@router.get("/{scorecard_id}/change-log")
async def get_change_log(
    scorecard_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get change history for a scorecard."""
    q = (
        select(ScorecardChangeLog)
        .where(ScorecardChangeLog.scorecard_id == scorecard_id)
        .order_by(ScorecardChangeLog.created_at.desc())
        .limit(100)
    )
    logs = (await db.execute(q)).scalars().all()

    result = []
    for l in logs:
        proposed_name = None
        if l.proposed_by:
            u_q = select(User.first_name, User.last_name).where(User.id == l.proposed_by)
            u = (await db.execute(u_q)).one_or_none()
            if u:
                proposed_name = f"{u[0]} {u[1]}"

        result.append({
            "id": l.id, "change_type": l.change_type, "field_path": l.field_path,
            "old_value": l.old_value, "new_value": l.new_value,
            "justification": l.justification, "status": l.status.value,
            "proposed_by": l.proposed_by, "proposed_by_name": proposed_name,
            "approved_by": l.approved_by,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        })
    return result


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════

async def _get_scorecard(scorecard_id: int, db: AsyncSession) -> Scorecard:
    sc = (await db.execute(select(Scorecard).where(Scorecard.id == scorecard_id))).scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    return sc


async def _get_scorecard_with_bins(scorecard_id: int, db: AsyncSession) -> Scorecard:
    q = (
        select(Scorecard)
        .where(Scorecard.id == scorecard_id)
        .options(
            selectinload(Scorecard.characteristics)
            .selectinload(ScorecardCharacteristic.bins)
        )
    )
    sc = (await db.execute(q)).scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    return sc


def _scorecard_summary(sc: Scorecard) -> dict:
    return {
        "id": sc.id, "name": sc.name, "version": sc.version,
        "description": sc.description, "status": sc.status.value,
        "base_score": sc.base_score, "min_score": sc.min_score, "max_score": sc.max_score,
        "auto_approve_threshold": sc.auto_approve_threshold,
        "manual_review_threshold": sc.manual_review_threshold,
        "auto_decline_threshold": sc.auto_decline_threshold,
        "traffic_pct": sc.traffic_pct,
        "target_products": sc.target_products,
        "created_at": sc.created_at.isoformat() if sc.created_at else None,
    }


def _scorecard_detail(sc: Scorecard) -> dict:
    d = _scorecard_summary(sc)
    d["characteristics"] = []
    for char in (sc.characteristics or []):
        cd = {
            "id": char.id, "code": char.code, "name": char.name,
            "data_field": char.data_field, "is_active": char.is_active,
            "weight_multiplier": char.weight_multiplier, "sort_order": char.sort_order,
            "bins": [{
                "id": b.id, "bin_type": b.bin_type.value, "label": b.label,
                "points": b.points, "min_value": b.min_value, "max_value": b.max_value,
                "category_value": b.category_value, "notes": b.notes, "sort_order": b.sort_order,
            } for b in (char.bins or [])],
        }
        d["characteristics"].append(cd)
    # Auto-generate script
    d["script"] = generate_scoring_script(sc) if sc.characteristics else ""
    return d
