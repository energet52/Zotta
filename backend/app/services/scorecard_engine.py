"""Scorecard Scoring Engine — score calculation, script generation, batch scoring,
CSV import, champion-challenger assignment.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import random
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.scorecard import (
    Scorecard, ScorecardStatus, ScorecardCharacteristic, ScorecardBin,
    BinType, ScoreResult,
)
from app.models.loan import LoanApplication, ApplicantProfile

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
# 1. Score an Application Against a Scorecard
# ────────────────────────────────────────────────────────────────────

def score_application(
    scorecard: Scorecard,
    applicant_data: dict[str, Any],
) -> dict[str, Any]:
    """Score an applicant against a scorecard. Pure function (no DB).

    Args:
        scorecard: Scorecard with characteristics and bins loaded
        applicant_data: dict of field_name -> value

    Returns:
        dict with total_score, characteristic_scores, decision, reason_codes,
        top_positive_factors, top_negative_factors
    """
    score = scorecard.base_score
    characteristic_scores: list[dict] = []
    all_contributions: list[dict] = []

    for char in scorecard.characteristics:
        if not char.is_active:
            continue

        raw_value = applicant_data.get(char.data_field)
        matched_bin = _match_bin(char, raw_value)

        points = 0.0
        bin_label = "Missing/Default"
        if matched_bin:
            points = matched_bin.points * char.weight_multiplier
            bin_label = matched_bin.label

        score += points

        entry = {
            "code": char.code,
            "name": char.name,
            "data_field": char.data_field,
            "value": str(raw_value) if raw_value is not None else None,
            "bin_label": bin_label,
            "raw_points": matched_bin.points if matched_bin else 0,
            "weight_multiplier": char.weight_multiplier,
            "weighted_points": round(points, 2),
        }
        characteristic_scores.append(entry)
        all_contributions.append(entry)

    # Clamp score
    total_score = max(scorecard.min_score, min(score, scorecard.max_score))

    # Decision
    decision = _determine_decision(total_score, scorecard)

    # Reason codes
    reason_codes = _generate_reason_codes(all_contributions, decision)

    # Top factors
    sorted_by_points = sorted(all_contributions, key=lambda x: x["weighted_points"])
    top_negative = [
        {"code": c["code"], "name": c["name"], "points": c["weighted_points"], "bin": c["bin_label"]}
        for c in sorted_by_points[:3] if c["weighted_points"] < 0
    ]
    top_positive = [
        {"code": c["code"], "name": c["name"], "points": c["weighted_points"], "bin": c["bin_label"]}
        for c in reversed(sorted_by_points) if c["weighted_points"] > 0
    ][:3]

    return {
        "total_score": round(total_score, 2),
        "base_score_used": scorecard.base_score,
        "characteristic_scores": characteristic_scores,
        "decision": decision,
        "reason_codes": reason_codes,
        "top_positive_factors": top_positive,
        "top_negative_factors": top_negative,
    }


def _match_bin(char: ScorecardCharacteristic, value: Any) -> ScorecardBin | None:
    """Find the matching bin for a value within a characteristic."""
    default_bin = None

    for b in char.bins:
        if b.bin_type == BinType.DEFAULT:
            default_bin = b
            continue

        if b.bin_type == BinType.RANGE:
            if value is None:
                continue
            try:
                num_val = float(value) if not isinstance(value, (int, float, Decimal)) else float(value)
            except (ValueError, TypeError):
                continue
            min_v = b.min_value if b.min_value is not None else float("-inf")
            max_v = b.max_value if b.max_value is not None else float("inf")
            if min_v <= num_val < max_v:
                return b

        elif b.bin_type == BinType.CATEGORY:
            if value is None:
                continue
            str_val = str(value).strip().lower()
            cat_val = (b.category_value or "").strip().lower()
            if str_val == cat_val:
                return b

    return default_bin


def _determine_decision(score: float, scorecard: Scorecard) -> str:
    """Map score to decision based on cutoffs."""
    if scorecard.auto_approve_threshold and score >= scorecard.auto_approve_threshold:
        return "AUTO_APPROVE"
    if scorecard.auto_decline_threshold and score < scorecard.auto_decline_threshold:
        return "AUTO_DECLINE"
    if scorecard.manual_review_threshold is not None:
        if score >= scorecard.manual_review_threshold:
            return "MANUAL_REVIEW"
    return "MANUAL_REVIEW"


def _generate_reason_codes(contributions: list[dict], decision: str) -> list[str]:
    """Generate reason codes for decline/review."""
    if decision == "AUTO_APPROVE":
        return []
    codes = []
    sorted_neg = sorted(contributions, key=lambda x: x["weighted_points"])
    for i, c in enumerate(sorted_neg[:5]):
        if c["weighted_points"] <= 0:
            codes.append(f"RC{i+1:02d}_{c['code']}")
    return codes


# ────────────────────────────────────────────────────────────────────
# 2. Extract Applicant Data from Profile
# ────────────────────────────────────────────────────────────────────

def extract_applicant_data(
    profile: ApplicantProfile | None,
    application: LoanApplication | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    """Build applicant data dict from profile for scorecard scoring."""
    data: dict[str, Any] = {}

    if profile:
        # Age
        if profile.date_of_birth:
            today = date.today()
            age = today.year - profile.date_of_birth.year - (
                (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)
            )
            data["age"] = age
        data["occupation"] = profile.job_title
        data["employment_type"] = profile.employment_type
        data["employer_sector"] = profile.employer_sector
        data["employer_name"] = profile.employer_name
        data["years_employed"] = profile.years_employed
        data["monthly_income"] = float(profile.monthly_income or 0)
        data["monthly_expenses"] = float(profile.monthly_expenses or 0)
        data["existing_debt"] = float(profile.existing_debt or 0)
        data["dependents"] = profile.dependents
        data["marital_status"] = profile.marital_status
        data["gender"] = profile.gender
        data["residential_status"] = getattr(profile, "residential_status", None)
        data["residence_tenure"] = getattr(profile, "residence_tenure_years", None)
        data["geographic_location"] = profile.city or profile.parish
        data["payment_channel"] = getattr(profile, "payment_channel", None)
        data["payment_frequency"] = getattr(profile, "payment_frequency", None)
        # Aliases for scorecard field mapping
        data["employment_tenure_months"] = (profile.years_employed or 0) * 12

    if application:
        data["loan_amount_requested"] = float(application.amount_requested)
        data["term_months"] = application.term_months
        data["purpose"] = application.purpose.value if hasattr(application.purpose, "value") else str(application.purpose)
        if data.get("monthly_income"):
            data["dti_ratio"] = round(
                (data.get("monthly_expenses", 0) + data.get("existing_debt", 0))
                / max(data["monthly_income"], 1) * 100, 2
            )
            data["lti_ratio"] = round(
                float(application.amount_requested) / max(data["monthly_income"], 1), 2
            )

    if extra:
        data.update(extra)

    return data


# ────────────────────────────────────────────────────────────────────
# 3. Generate Raw Scoring Script
# ────────────────────────────────────────────────────────────────────

def generate_scoring_script(scorecard: Scorecard) -> str:
    """Generate a human-readable Python scoring script from scorecard definition."""
    lines: list[str] = []
    lines.append(f"# Scorecard: {scorecard.name} v{scorecard.version} ({scorecard.status.value})")
    lines.append(f"# Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"# Base Score: {scorecard.base_score}")
    lines.append(f"# Score Range: {scorecard.min_score} - {scorecard.max_score}")
    lines.append("")
    lines.append(f"score = {scorecard.base_score}  # base score")
    lines.append("")

    for char in scorecard.characteristics:
        if not char.is_active:
            continue

        lines.append(f"# Characteristic: {char.code} - {char.name} (field: {char.data_field})")
        if char.weight_multiplier != 1.0:
            lines.append(f"# Weight multiplier: {char.weight_multiplier}x")

        # Sort bins: ranges first (by min_value), then categories, then default
        range_bins = sorted(
            [b for b in char.bins if b.bin_type == BinType.RANGE],
            key=lambda b: b.min_value if b.min_value is not None else float("-inf"),
        )
        cat_bins = [b for b in char.bins if b.bin_type == BinType.CATEGORY]
        default_bins = [b for b in char.bins if b.bin_type == BinType.DEFAULT]

        first = True
        var_name = char.data_field

        for b in range_bins:
            prefix = "if" if first else "elif"
            min_v = b.min_value
            max_v = b.max_value
            pts = round(b.points * char.weight_multiplier, 2)

            if min_v is not None and max_v is not None:
                lines.append(f"{prefix} {var_name} >= {min_v} and {var_name} < {max_v}: score += {pts}  # {b.label}")
            elif min_v is not None:
                lines.append(f"{prefix} {var_name} >= {min_v}: score += {pts}  # {b.label}")
            elif max_v is not None:
                lines.append(f"{prefix} {var_name} < {max_v}: score += {pts}  # {b.label}")
            first = False

        for b in cat_bins:
            prefix = "if" if first else "elif"
            pts = round(b.points * char.weight_multiplier, 2)
            lines.append(f'{prefix} {var_name} == "{b.category_value}": score += {pts}  # {b.label}')
            first = False

        for b in default_bins:
            pts = round(b.points * char.weight_multiplier, 2)
            if first:
                lines.append(f"score += {pts}  # {b.label} (default/missing)")
            else:
                lines.append(f"else: score += {pts}  # {b.label} (default/missing)")
            first = False

        lines.append("")

    # Final score clamping
    lines.append("# Final Score")
    lines.append(f"final_score = max(min(score, {scorecard.max_score}), {scorecard.min_score})  # clamp to range")
    lines.append("")

    # Decision thresholds
    lines.append("# Decision")
    if scorecard.auto_approve_threshold:
        lines.append(f'if final_score >= {scorecard.auto_approve_threshold}: decision = "AUTO_APPROVE"')
    if scorecard.manual_review_threshold and scorecard.auto_approve_threshold:
        lines.append(f'elif final_score >= {scorecard.manual_review_threshold}: decision = "MANUAL_REVIEW"')
    elif scorecard.manual_review_threshold:
        lines.append(f'if final_score >= {scorecard.manual_review_threshold}: decision = "MANUAL_REVIEW"')
    lines.append(f'else: decision = "AUTO_DECLINE"')

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────
# 3b. Parse Scoring Script Back Into Characteristics/Bins
# ────────────────────────────────────────────────────────────────────

def parse_scoring_script(script_text: str) -> dict[str, Any]:
    """Parse a human-readable scoring script back into structured scorecard data.

    This is the inverse of generate_scoring_script().  It extracts
    base_score, min_score, max_score, and the full list of
    characteristics with their bins.

    Returns:
        {
            "base_score": float,
            "min_score": float,
            "max_score": float,
            "characteristics": [{
                "code": str, "name": str, "data_field": str,
                "weight_multiplier": float,
                "bins": [{"bin_type": str, "label": str, "points": float,
                          "min_value": float|None, "max_value": float|None,
                          "category_value": str|None}]
            }],
            "errors": [str],
        }
    """
    import re

    result: dict[str, Any] = {
        "base_score": 0,
        "min_score": 100,
        "max_score": 850,
        "characteristics": [],
        "errors": [],
    }

    current_char: dict | None = None
    char_order = 0

    for line_no, raw_line in enumerate(script_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        # ── Header comments ──
        # # Base Score: 536
        m = re.match(r"^#\s*Base Score:\s*([\d.\-]+)", line)
        if m:
            result["base_score"] = float(m.group(1))
            continue

        # # Score Range: 100 - 850
        m = re.match(r"^#\s*Score Range:\s*([\d.\-]+)\s*-\s*([\d.\-]+)", line)
        if m:
            result["min_score"] = float(m.group(1))
            result["max_score"] = float(m.group(2))
            continue

        # ── Base score assignment ──
        # score = 536  # base score
        m = re.match(r"^score\s*=\s*([\d.\-]+)", line)
        if m:
            result["base_score"] = float(m.group(1))
            continue

        # ── Characteristic header ──
        # # Characteristic: C01 - Age (field: age)
        m = re.match(
            r"^#\s*Characteristic:\s*(\S+)\s*-\s*(.+?)\s*\(field:\s*(\S+)\)",
            line,
        )
        if m:
            # Flush previous characteristic
            current_char = {
                "code": m.group(1),
                "name": m.group(2).strip(),
                "data_field": m.group(3).strip(),
                "weight_multiplier": 1.0,
                "sort_order": char_order,
                "bins": [],
            }
            result["characteristics"].append(current_char)
            char_order += 1
            continue

        # ── Weight multiplier ──
        # # Weight multiplier: 1.2x
        m = re.match(r"^#\s*Weight multiplier:\s*([\d.]+)x", line)
        if m and current_char:
            current_char["weight_multiplier"] = float(m.group(1))
            continue

        # ── Final score clamping ──
        # final_score = max(min(score, 850), 100)
        m = re.match(
            r"^final_score\s*=\s*max\(min\(score,\s*([\d.\-]+)\),\s*([\d.\-]+)\)",
            line,
        )
        if m:
            result["max_score"] = float(m.group(1))
            result["min_score"] = float(m.group(2))
            continue

        # Skip pure comment lines & decision lines
        if line.startswith("#") or "decision" in line:
            continue

        if not current_char:
            continue

        wm = current_char["weight_multiplier"]

        # ── Range bin:  (if|elif) var >= min and var < max: score += pts  # label ──
        m = re.match(
            r"^(?:el)?if\s+\S+\s*>=\s*([\d.\-]+)\s+and\s+\S+\s*<\s*([\d.\-]+):\s*score\s*\+=\s*([\d.\-]+)\s*#\s*(.+)",
            line,
        )
        if m:
            pts = float(m.group(3))
            raw_pts = round(pts / wm, 4) if wm != 0 else pts
            current_char["bins"].append({
                "bin_type": "range",
                "label": m.group(4).strip(),
                "points": raw_pts,
                "min_value": float(m.group(1)),
                "max_value": float(m.group(2)),
                "category_value": None,
            })
            continue

        # ── Range bin (open lower): (if|elif) var < max: score += pts  # label ──
        m = re.match(
            r"^(?:el)?if\s+\S+\s*<\s*([\d.\-]+):\s*score\s*\+=\s*([\d.\-]+)\s*#\s*(.+)",
            line,
        )
        if m:
            pts = float(m.group(2))
            raw_pts = round(pts / wm, 4) if wm != 0 else pts
            current_char["bins"].append({
                "bin_type": "range",
                "label": m.group(3).strip(),
                "points": raw_pts,
                "min_value": None,
                "max_value": float(m.group(1)),
                "category_value": None,
            })
            continue

        # ── Range bin (open upper): (if|elif) var >= min: score += pts  # label ──
        m = re.match(
            r"^(?:el)?if\s+\S+\s*>=\s*([\d.\-]+):\s*score\s*\+=\s*([\d.\-]+)\s*#\s*(.+)",
            line,
        )
        if m:
            pts = float(m.group(2))
            raw_pts = round(pts / wm, 4) if wm != 0 else pts
            current_char["bins"].append({
                "bin_type": "range",
                "label": m.group(3).strip(),
                "points": raw_pts,
                "min_value": float(m.group(1)),
                "max_value": None,
                "category_value": None,
            })
            continue

        # ── Category bin: (if|elif) var == "value": score += pts  # label ──
        m = re.match(
            r'^(?:el)?if\s+\S+\s*==\s*"([^"]+)":\s*score\s*\+=\s*([\d.\-]+)\s*#\s*(.+)',
            line,
        )
        if m:
            pts = float(m.group(2))
            raw_pts = round(pts / wm, 4) if wm != 0 else pts
            current_char["bins"].append({
                "bin_type": "category",
                "label": m.group(3).strip(),
                "points": raw_pts,
                "min_value": None,
                "max_value": None,
                "category_value": m.group(1),
            })
            continue

        # ── Default bin: else: score += pts  # label ──
        m = re.match(
            r"^else:\s*score\s*\+=\s*([\d.\-]+)\s*#\s*(.+)",
            line,
        )
        if m:
            pts = float(m.group(1))
            raw_pts = round(pts / wm, 4) if wm != 0 else pts
            current_char["bins"].append({
                "bin_type": "default",
                "label": m.group(2).strip().rstrip(" (default/missing)"),
                "points": raw_pts,
                "min_value": None,
                "max_value": None,
                "category_value": m.group(2).strip().rstrip(" (default/missing)"),
            })
            continue

        # ── Standalone default: score += pts  # label (default/missing) ──
        m = re.match(
            r"^score\s*\+=\s*([\d.\-]+)\s*#\s*(.+)",
            line,
        )
        if m:
            pts = float(m.group(1))
            raw_pts = round(pts / wm, 4) if wm != 0 else pts
            lbl = m.group(2).strip().rstrip(" (default/missing)")
            current_char["bins"].append({
                "bin_type": "default",
                "label": lbl,
                "points": raw_pts,
                "min_value": None,
                "max_value": None,
                "category_value": lbl,
            })
            continue

    return result


# ────────────────────────────────────────────────────────────────────
# 4. CSV Import
# ────────────────────────────────────────────────────────────────────

def parse_scorecard_csv(csv_content: str) -> dict[str, Any]:
    """Parse a scorecard CSV and return structured data.

    Expected CSV format:
        Characteristic,Attribute,Points,Notes
        BASE SCORE,Starting Score,536,Base score
        ,,,
        C01: Age,18-34 years,-16,Note
        ,35-44 years,-8,
        ...

    Returns:
        {"base_score": float, "characteristics": [{code, name, bins: [{label, points, notes, ...}]}], "errors": []}
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    result: dict[str, Any] = {
        "base_score": 0,
        "characteristics": [],
        "errors": [],
    }

    current_char: dict | None = None
    char_order = 0

    for row_num, row in enumerate(reader, start=2):
        char_col = (row.get("Characteristic") or "").strip()
        attr_col = (row.get("Attribute") or "").strip()
        points_col = (row.get("Points") or "").strip()
        notes_col = (row.get("Notes") or "").strip()

        # Skip empty rows
        if not char_col and not attr_col:
            continue

        # Base score
        if char_col.upper() == "BASE SCORE":
            try:
                result["base_score"] = float(points_col)
            except ValueError:
                result["errors"].append(f"Row {row_num}: Invalid base score '{points_col}'")
            continue

        # New characteristic
        if char_col:
            # Parse code and name from "C01: Age"
            if ":" in char_col:
                code, name = char_col.split(":", 1)
                code = code.strip()
                name = name.strip()
            else:
                code = f"C{char_order + 1:02d}"
                name = char_col
            current_char = {
                "code": code,
                "name": name,
                "sort_order": char_order,
                "bins": [],
            }
            result["characteristics"].append(current_char)
            char_order += 1

        # Add bin to current characteristic
        if current_char and attr_col:
            try:
                points = float(points_col)
            except ValueError:
                result["errors"].append(f"Row {row_num}: Invalid points '{points_col}' for '{attr_col}'")
                continue

            bin_info = _parse_bin_from_label(attr_col, points, notes_col)
            current_char["bins"].append(bin_info)

    return result


def _parse_bin_from_label(label: str, points: float, notes: str = "") -> dict:
    """Infer bin type and boundaries from label text."""
    label_lower = label.lower().strip()

    # Check for range patterns
    if "missing" in label_lower or "other" in label_lower or "default" in label_lower:
        return {
            "bin_type": "default",
            "label": label,
            "points": points,
            "notes": notes,
            "category_value": label,
        }

    # Try numeric range: "18-34 years", "< 3 years", "60+ months", etc.
    import re
    range_match = re.match(r"(\d+)\s*[-–]\s*(\d+)", label)
    if range_match:
        min_v = float(range_match.group(1))
        max_v = float(range_match.group(2)) + 1  # make upper bound exclusive
        return {
            "bin_type": "range",
            "label": label,
            "points": points,
            "notes": notes,
            "min_value": min_v,
            "max_value": max_v,
        }

    lt_match = re.match(r"<\s*(\d+)", label)
    if lt_match:
        return {
            "bin_type": "range",
            "label": label,
            "points": points,
            "notes": notes,
            "min_value": None,
            "max_value": float(lt_match.group(1)),
        }

    gte_match = re.match(r"(\d+)\+", label)
    if gte_match:
        return {
            "bin_type": "range",
            "label": label,
            "points": points,
            "notes": notes,
            "min_value": float(gte_match.group(1)),
            "max_value": None,
        }

    # Otherwise treat as category
    return {
        "bin_type": "category",
        "label": label,
        "points": points,
        "notes": notes,
        "category_value": label,
    }


# ────────────────────────────────────────────────────────────────────
# 5. Champion-Challenger Assignment
# ────────────────────────────────────────────────────────────────────

async def get_active_scorecards(db: AsyncSession) -> list[Scorecard]:
    """Get all scorecards that should score applications (champion + challengers + shadow)."""
    q = (
        select(Scorecard)
        .where(Scorecard.status.in_([
            ScorecardStatus.CHAMPION,
            ScorecardStatus.CHALLENGER,
            ScorecardStatus.SHADOW,
        ]))
        .options(
            selectinload(Scorecard.characteristics)
            .selectinload(ScorecardCharacteristic.bins)
        )
    )
    result = await db.execute(q)
    return list(result.scalars().all())


def select_decisioning_model(scorecards: list[Scorecard]) -> Scorecard | None:
    """Randomly select which scorecard makes the actual decision based on traffic allocation.

    Champion gets remaining traffic after challengers.
    Shadow models never decision.
    """
    if not scorecards:
        return None

    champion = None
    challengers: list[Scorecard] = []

    for sc in scorecards:
        if sc.status == ScorecardStatus.CHAMPION:
            champion = sc
        elif sc.status == ScorecardStatus.CHALLENGER and sc.traffic_pct > 0:
            challengers.append(sc)

    if not champion:
        return None

    # Random selection based on traffic percentages
    roll = random.random() * 100
    cumulative = 0.0

    for ch in challengers:
        cumulative += ch.traffic_pct
        if roll < cumulative:
            return ch

    return champion


# ────────────────────────────────────────────────────────────────────
# 6. Score All Models (Parallel Scoring)
# ────────────────────────────────────────────────────────────────────

async def score_all_models(
    application_id: int,
    applicant_data: dict[str, Any],
    db: AsyncSession,
) -> list[ScoreResult]:
    """Score an application against ALL active scorecards.

    Returns list of ScoreResult objects (already added to db session).
    """
    scorecards = await get_active_scorecards(db)
    if not scorecards:
        return []

    # Select decisioning model
    decisioning_model = select_decisioning_model(scorecards)

    results: list[ScoreResult] = []

    for sc in scorecards:
        score_data = score_application(sc, applicant_data)
        is_decisioning = (sc.id == decisioning_model.id) if decisioning_model else False

        sr = ScoreResult(
            loan_application_id=application_id,
            scorecard_id=sc.id,
            scorecard_name=sc.name,
            scorecard_version=sc.version,
            total_score=score_data["total_score"],
            base_score_used=score_data["base_score_used"],
            characteristic_scores=score_data["characteristic_scores"],
            decision=score_data["decision"],
            reason_codes=score_data["reason_codes"],
            is_decisioning=is_decisioning,
            model_role=sc.status.value,
            top_positive_factors=score_data["top_positive_factors"],
            top_negative_factors=score_data["top_negative_factors"],
        )
        db.add(sr)
        results.append(sr)

    await db.flush()
    return results


# ────────────────────────────────────────────────────────────────────
# 7. Impact Simulation
# ────────────────────────────────────────────────────────────────────

async def simulate_impact(
    scorecard: Scorecard,
    db: AsyncSession,
    sample_limit: int = 500,
) -> dict[str, Any]:
    """Simulate the impact of a scorecard on recent applications.

    Returns score distribution, approval/decline/review rates, etc.
    """
    from app.models.loan import LoanStatus

    # Get recent scored applications with profile data
    apps_q = (
        select(LoanApplication.id, LoanApplication.applicant_id)
        .where(LoanApplication.status.in_([
            LoanStatus.APPROVED, LoanStatus.DECLINED,
            LoanStatus.DECISION_PENDING, LoanStatus.DISBURSED,
        ]))
        .order_by(LoanApplication.created_at.desc())
        .limit(sample_limit)
    )
    apps = (await db.execute(apps_q)).all()

    scores: list[float] = []
    decisions = {"AUTO_APPROVE": 0, "MANUAL_REVIEW": 0, "AUTO_DECLINE": 0}

    for app_id, applicant_id in apps:
        profile_q = select(ApplicantProfile).where(ApplicantProfile.user_id == applicant_id)
        profile = (await db.execute(profile_q)).scalar_one_or_none()
        if not profile:
            continue

        app_q = select(LoanApplication).where(LoanApplication.id == app_id)
        app_obj = (await db.execute(app_q)).scalar_one_or_none()
        if not app_obj:
            continue

        applicant_data = extract_applicant_data(profile, app_obj)
        result = score_application(scorecard, applicant_data)
        scores.append(result["total_score"])
        dec = result["decision"]
        if dec in decisions:
            decisions[dec] += 1

    total = len(scores)
    if total == 0:
        return {"total_scored": 0, "distribution": [], "rates": {}, "summary": {}}

    # Build histogram (10 bands)
    band_size = (scorecard.max_score - scorecard.min_score) / 10
    distribution = []
    for i in range(10):
        lower = scorecard.min_score + i * band_size
        upper = lower + band_size
        count = sum(1 for s in scores if lower <= s < upper)
        distribution.append({
            "band": f"{int(lower)}-{int(upper)}",
            "count": count,
            "pct": round(count / total * 100, 1),
        })

    return {
        "total_scored": total,
        "distribution": distribution,
        "rates": {
            "approval_rate": round(decisions["AUTO_APPROVE"] / total * 100, 1),
            "review_rate": round(decisions["MANUAL_REVIEW"] / total * 100, 1),
            "decline_rate": round(decisions["AUTO_DECLINE"] / total * 100, 1),
        },
        "summary": {
            "avg_score": round(sum(scores) / total, 1),
            "min_score": round(min(scores), 1),
            "max_score": round(max(scores), 1),
            "median_score": round(sorted(scores)[total // 2], 1),
        },
    }


# ────────────────────────────────────────────────────────────────────
# 8. What-If Analysis
# ────────────────────────────────────────────────────────────────────

def what_if_analysis(
    scorecard: Scorecard,
    base_data: dict[str, Any],
    modifications: dict[str, Any],
) -> dict[str, Any]:
    """Run what-if analysis: score with base data, then with modifications."""
    base_result = score_application(scorecard, base_data)

    modified_data = {**base_data, **modifications}
    modified_result = score_application(scorecard, modified_data)

    # Find changed characteristics
    changes = []
    for base_cs, mod_cs in zip(base_result["characteristic_scores"], modified_result["characteristic_scores"]):
        if base_cs["weighted_points"] != mod_cs["weighted_points"]:
            changes.append({
                "code": base_cs["code"],
                "name": base_cs["name"],
                "original_value": base_cs["value"],
                "modified_value": mod_cs["value"],
                "original_points": base_cs["weighted_points"],
                "modified_points": mod_cs["weighted_points"],
                "point_change": round(mod_cs["weighted_points"] - base_cs["weighted_points"], 2),
            })

    return {
        "base_score": base_result["total_score"],
        "base_decision": base_result["decision"],
        "modified_score": modified_result["total_score"],
        "modified_decision": modified_result["decision"],
        "score_change": round(modified_result["total_score"] - base_result["total_score"], 2),
        "changes": changes,
    }


# ────────────────────────────────────────────────────────────────────
# 9. Batch Scoring
# ────────────────────────────────────────────────────────────────────

def batch_score_csv(
    scorecard: Scorecard,
    csv_content: str,
) -> list[dict[str, Any]]:
    """Score a batch of applicants from CSV content."""
    reader = csv.DictReader(io.StringIO(csv_content))
    results = []

    for row_num, row in enumerate(reader, start=2):
        # Convert numeric fields
        applicant_data = {}
        for key, val in row.items():
            if val is None or val.strip() == "":
                applicant_data[key] = None
            else:
                try:
                    applicant_data[key] = float(val)
                except ValueError:
                    applicant_data[key] = val.strip()

        score_result = score_application(scorecard, applicant_data)
        score_result["row_number"] = row_num
        score_result["input_data"] = {k: v for k, v in row.items() if v}
        results.append(score_result)

    return results


# ────────────────────────────────────────────────────────────────────
# 10. Build Scorecard from Parsed CSV Data
# ────────────────────────────────────────────────────────────────────

def build_scorecard_from_parsed(
    parsed: dict[str, Any],
    name: str,
    description: str = "",
    auto_approve: float | None = None,
    manual_review: float | None = None,
    auto_decline: float | None = None,
) -> Scorecard:
    """Build a Scorecard ORM object from parsed CSV data."""
    sc = Scorecard(
        name=name,
        version=1,
        description=description,
        base_score=parsed["base_score"],
        min_score=100,
        max_score=850,
        auto_approve_threshold=auto_approve,
        manual_review_threshold=manual_review,
        auto_decline_threshold=auto_decline,
        status=ScorecardStatus.DRAFT,
    )

    # Infer data_field from characteristic name
    field_map = {
        "age": "age",
        "occupation": "occupation",
        "payment channel": "payment_channel",
        "payment frequency": "payment_frequency",
        "residence tenure": "residence_tenure",
        "employment tenure": "employment_tenure_months",
        "residential status": "residential_status",
        "geographic location": "geographic_location",
        "monthly income": "monthly_income",
        "employment type": "employment_type",
        "years employed": "years_employed",
        "employer sector": "employer_sector",
        "debt-to-income": "dti_ratio",
        "loan-to-value": "lti_ratio",
        "existing loans": "existing_debt",
        "dependents": "dependents",
    }

    for i, char_data in enumerate(parsed["characteristics"]):
        char_name_lower = char_data["name"].lower()
        data_field = field_map.get(char_name_lower, char_name_lower.replace(" ", "_"))

        char = ScorecardCharacteristic(
            code=char_data["code"],
            name=char_data["name"],
            data_field=data_field,
            sort_order=i,
            is_active=True,
            weight_multiplier=1.0,
        )

        for j, bin_data in enumerate(char_data["bins"]):
            b = ScorecardBin(
                bin_type=BinType(bin_data["bin_type"]),
                label=bin_data["label"],
                points=bin_data["points"],
                sort_order=j,
                notes=bin_data.get("notes", ""),
                min_value=bin_data.get("min_value"),
                max_value=bin_data.get("max_value"),
                category_value=bin_data.get("category_value"),
            )
            char.bins.append(b)

        sc.characteristics.append(char)

    return sc
