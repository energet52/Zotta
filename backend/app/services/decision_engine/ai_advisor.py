"""AI Intelligence Layer for Decision Strategy Management.

Provides:
  - Segmentation recommendations based on portfolio data
  - Gap detection in strategy rules
  - Threshold optimization suggestions
  - Proxy discrimination warnings
  - Decision explanation generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SegmentationRecommendation:
    attribute: str
    importance: float  # 0-1 ranking
    rationale: str
    suggested_splits: list[str]
    risk_differentiation: float  # how much default rates differ across splits
    volume_adequate: bool


@dataclass
class GapAlert:
    gap_type: str  # "unreachable", "missing_coverage", "redundant", "low_volume"
    description: str
    affected_volume_pct: float
    suggestion: str
    rule_id: str | None = None
    node_key: str | None = None


@dataclass
class ThresholdRecommendation:
    rule_id: str
    rule_name: str
    current_threshold: Any
    recommended_threshold: Any
    rationale: str
    projected_impact: dict


@dataclass
class ProxyWarning:
    attribute: str
    correlation_with: str  # protected characteristic
    correlation_strength: float  # 0-1
    recommendation: str
    alternative_attributes: list[str]


@dataclass
class AdvisorReport:
    segmentation: list[SegmentationRecommendation] = field(default_factory=list)
    gaps: list[GapAlert] = field(default_factory=list)
    threshold_suggestions: list[ThresholdRecommendation] = field(default_factory=list)
    proxy_warnings: list[ProxyWarning] = field(default_factory=list)


# ── Segmentation Analysis ──────────────────────────────────────────

def analyze_segmentation(
    decisions: list[dict],
    attributes: list[str] | None = None,
) -> list[SegmentationRecommendation]:
    """Analyze historical decisions to recommend tree segmentation.

    Examines default rates and approval rates across potential segmentation
    dimensions to identify attributes that create meaningful risk differentiation.
    """
    if not decisions:
        return []

    default_attrs = [
        "is_existing_customer", "employment_type", "income_band",
        "bureau_file_status", "channel", "merchant_tier",
    ]
    attrs_to_check = attributes or default_attrs
    recommendations: list[SegmentationRecommendation] = []

    total_count = len(decisions)
    total_defaults = sum(1 for d in decisions if d.get("defaulted", False))
    base_default_rate = total_defaults / max(total_count, 1)

    for attr in attrs_to_check:
        segments: dict[str, list[dict]] = {}
        for dec in decisions:
            val = str(dec.get(attr, "unknown"))
            segments.setdefault(val, []).append(dec)

        if len(segments) < 2:
            continue

        default_rates = {}
        for seg_name, seg_decisions in segments.items():
            seg_defaults = sum(1 for d in seg_decisions if d.get("defaulted", False))
            default_rates[seg_name] = seg_defaults / max(len(seg_decisions), 1)

        rates = list(default_rates.values())
        if not rates:
            continue
        differentiation = max(rates) - min(rates)

        min_volume = min(len(v) for v in segments.values())
        volume_ok = min_volume >= 25

        recommendations.append(SegmentationRecommendation(
            attribute=attr,
            importance=min(differentiation * 5, 1.0),
            rationale=(
                f"Default rates differ by {differentiation:.1%} across {len(segments)} segments. "
                f"Lowest: {min(rates):.1%}, Highest: {max(rates):.1%}. "
                f"{'Adequate' if volume_ok else 'Low'} volume in smallest segment ({min_volume})."
            ),
            suggested_splits=list(segments.keys()),
            risk_differentiation=differentiation,
            volume_adequate=volume_ok,
        ))

    recommendations.sort(key=lambda r: r.importance, reverse=True)
    return recommendations


# ── Gap Detection ──────────────────────────────────────────────────

def detect_gaps(
    strategy_rules: list[dict],
    tree_nodes: list[dict] | None = None,
    decisions: list[dict] | None = None,
) -> list[GapAlert]:
    """Detect coverage gaps, redundancies, and low-volume issues."""
    alerts: list[GapAlert] = []

    # Check for rules that never fire
    if decisions:
        rule_fire_counts: dict[str, int] = {}
        for dec in decisions:
            fired = dec.get("rules_fired", [])
            for rule_id in fired:
                rule_fire_counts[rule_id] = rule_fire_counts.get(rule_id, 0) + 1

        for rule in strategy_rules:
            rid = rule.get("rule_id", "")
            if rid not in rule_fire_counts:
                alerts.append(GapAlert(
                    gap_type="unreachable",
                    description=f"Rule {rid} ({rule.get('name', '')}) has never fired in the evaluation period",
                    affected_volume_pct=0,
                    suggestion="Consider whether this rule is still needed or if its threshold is too extreme",
                    rule_id=rid,
                ))

    # Check for overlapping/redundant rules
    field_groups: dict[str, list[dict]] = {}
    for rule in strategy_rules:
        f = rule.get("field", "")
        field_groups.setdefault(f, []).append(rule)

    for field_name, rules in field_groups.items():
        if len(rules) > 2:
            alerts.append(GapAlert(
                gap_type="redundant",
                description=f"{len(rules)} rules target the same field '{field_name}'",
                affected_volume_pct=0,
                suggestion=f"Review rules on '{field_name}' for potential consolidation",
            ))

    # Check tree nodes for low-volume branches
    if tree_nodes and decisions:
        total = len(decisions)
        for node in tree_nodes:
            if node.get("node_type") == "strategy":
                node_key = node.get("node_key", "")
                matched = sum(
                    1 for d in decisions
                    if any(
                        step.get("node_key") == node_key
                        for step in (d.get("routing_path", []) or [])
                    )
                )
                pct = matched / max(total, 1) * 100
                if 0 < pct < 2:
                    alerts.append(GapAlert(
                        gap_type="low_volume",
                        description=f"Strategy node '{node_key}' handles only {pct:.1f}% of applications ({matched} total)",
                        affected_volume_pct=pct,
                        suggestion="Fewer than 100 applications/quarter means the strategy cannot be reliably validated. Consider merging with an adjacent branch.",
                        node_key=node_key,
                    ))

    return alerts


# ── Threshold Optimization ─────────────────────────────────────────

def suggest_threshold_adjustments(
    rules: list[dict],
    decisions: list[dict],
) -> list[ThresholdRecommendation]:
    """Analyze rule performance to suggest threshold adjustments."""
    suggestions: list[ThresholdRecommendation] = []

    if not decisions or not rules:
        return suggestions

    for rule in rules:
        rid = rule.get("rule_id", "")
        field_name = rule.get("field", "")
        threshold = rule.get("threshold")

        if threshold is None or not isinstance(threshold, (int, float)):
            continue

        # Find applications where this rule was the decisive factor
        caught_by_rule = []
        passed_rule = []
        for dec in decisions:
            rule_results = dec.get("rule_evaluations", [])
            for rr in rule_results:
                if rr.get("rule_id") == rid:
                    if rr.get("passed"):
                        passed_rule.append(dec)
                    else:
                        caught_by_rule.append(dec)

        if not caught_by_rule:
            continue

        # If rule catches many applications and most of them would have performed well
        if len(caught_by_rule) >= 20:
            would_perform_well = sum(
                1 for d in caught_by_rule
                if not d.get("defaulted", False)
            )
            false_positive_rate = would_perform_well / len(caught_by_rule)

            if false_positive_rate > 0.7:
                suggestions.append(ThresholdRecommendation(
                    rule_id=rid,
                    rule_name=rule.get("name", rid),
                    current_threshold=threshold,
                    recommended_threshold=_suggest_relaxation(threshold, field_name),
                    rationale=(
                        f"Rule catches {len(caught_by_rule)} applications/period. "
                        f"{false_positive_rate:.0%} of caught applications would have performed well. "
                        f"Consider relaxing the threshold."
                    ),
                    projected_impact={
                        "caught_current": len(caught_by_rule),
                        "false_positive_rate": round(false_positive_rate, 3),
                        "potential_revenue_gain": len(caught_by_rule) * false_positive_rate,
                    },
                ))

    return suggestions


def _suggest_relaxation(threshold: float, field_name: str) -> float:
    """Suggest a relaxed threshold value."""
    if "dti" in field_name.lower() or "ratio" in field_name.lower():
        return round(threshold * 1.1, 2)
    elif "income" in field_name.lower():
        return round(threshold * 0.9, 2)
    elif "age" in field_name.lower():
        return threshold - 1
    elif "score" in field_name.lower():
        return threshold - 20
    return threshold


# ── Proxy Discrimination Detection ─────────────────────────────────

PROXY_RISK_ATTRIBUTES = {
    "geographic_region": {"correlates_with": "ethnicity", "alternatives": ["income_band", "employment_type"]},
    "parish": {"correlates_with": "ethnicity", "alternatives": ["income_band", "employment_type"]},
    "age_band": {"correlates_with": "age (protected)", "alternatives": ["employment_tenure", "credit_history_years"]},
    "gender": {"correlates_with": "gender (protected)", "alternatives": []},
    "marital_status": {"correlates_with": "gender (protected)", "alternatives": ["dependents", "income"]},
}


def check_proxy_discrimination(
    routing_attributes: list[str],
    decisions: list[dict] | None = None,
) -> list[ProxyWarning]:
    """Check routing attributes for proxy discrimination risk."""
    warnings: list[ProxyWarning] = []

    for attr in routing_attributes:
        attr_lower = attr.lower().replace(" ", "_")
        if attr_lower in PROXY_RISK_ATTRIBUTES:
            info = PROXY_RISK_ATTRIBUTES[attr_lower]
            warnings.append(ProxyWarning(
                attribute=attr,
                correlation_with=info["correlates_with"],
                correlation_strength=0.5,
                recommendation=(
                    f"'{attr}' may correlate with {info['correlates_with']}. "
                    f"Consider using legitimate risk-differentiating alternatives."
                ),
                alternative_attributes=info["alternatives"],
            ))

    return warnings


# ── Decision Explanation ───────────────────────────────────────────

def generate_staff_explanation(
    routing_path: list[dict],
    strategy_name: str,
    evaluation_steps: list[dict],
    final_outcome: str,
    application_id: int | None = None,
) -> str:
    """Generate a staff-facing decision explanation from audit data."""
    parts = []

    if application_id:
        parts.append(f"Application #{application_id}")

    if routing_path:
        path_desc = " -> ".join(
            f"{step.get('label', step.get('node_key', '?'))} [{step.get('branch', '?')}]"
            for step in routing_path
        )
        parts.append(f"Routing: {path_desc}")

    parts.append(f"Strategy: {strategy_name}")

    for step in evaluation_steps:
        step_name = step.get("step", step.get("step_name", ""))
        outcome = step.get("outcome", "")
        details = step.get("details", "")
        parts.append(f"  {step_name}: {outcome} — {details}")

    parts.append(f"Final Decision: {final_outcome.upper()}")

    return "\n".join(parts)


def generate_consumer_explanation(
    final_outcome: str,
    reason_codes: list[str] | None = None,
) -> str:
    """Generate a consumer-facing sanitized explanation."""
    if final_outcome == "approve":
        return (
            "Your application has been assessed based on your income, existing obligations, "
            "credit history, and the financing amount. You have been approved."
        )
    elif final_outcome == "decline":
        return (
            "Your application has been assessed based on your income, existing obligations, "
            "credit history, and the financing amount. Unfortunately, we are unable to "
            "approve your application at this time. You may reapply in the future or "
            "contact us for more information."
        )
    else:
        return (
            "Your application has been assessed and requires additional review by our "
            "team. You will be contacted with an update shortly."
        )


# ── Full Advisory Report ──────────────────────────────────────────

def generate_advisory_report(
    strategy_rules: list[dict],
    tree_nodes: list[dict] | None = None,
    decisions: list[dict] | None = None,
    routing_attributes: list[str] | None = None,
) -> AdvisorReport:
    """Generate a comprehensive advisory report."""
    report = AdvisorReport()

    if decisions:
        report.segmentation = analyze_segmentation(decisions)
    report.gaps = detect_gaps(strategy_rules, tree_nodes, decisions)
    if decisions:
        report.threshold_suggestions = suggest_threshold_adjustments(strategy_rules, decisions)
    if routing_attributes:
        report.proxy_warnings = check_proxy_discrimination(routing_attributes, decisions)

    return report
