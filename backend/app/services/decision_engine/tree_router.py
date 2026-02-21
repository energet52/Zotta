"""Decision Tree Router — traverses a decision tree to route an application
to the correct strategy based on its characteristics.

Pure traversal logic with no database calls during routing.  The tree structure
and application context are passed in, making the router fully testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from app.models.strategy import (
    DecisionTree,
    DecisionTreeNode,
    NodeType,
    ConditionType,
)


# ── Result types ───────────────────────────────────────────────────

@dataclass
class RoutingStep:
    node_key: str
    node_label: str | None
    attribute: str | None
    actual_value: Any
    branch_taken: str
    node_type: str


@dataclass
class RoutingResult:
    strategy_id: int | None
    strategy_params: dict | None
    assessment_id: int | None = None
    path: list[RoutingStep] = field(default_factory=list)
    used_default: bool = False


# ── Routing context builder ────────────────────────────────────────

@dataclass
class RoutingContext:
    """All attributes available for tree routing decisions."""

    # Customer relationship
    is_existing_customer: bool = False
    relationship_status: str = ""  # new, existing_active, existing_dormant, previous, staff
    relationship_tenure_months: int = 0
    internal_risk_grade: str = ""
    prior_loan_count: int = 0
    worst_ever_dpd: int = 0
    has_cross_default: bool = False

    # Application characteristics
    product_family: str = ""
    product_type: str = ""
    loan_amount: float = 0
    loan_tenure_months: int = 0
    loan_purpose: str = ""
    down_payment_pct: float = 0
    channel: str = ""  # branch, online, mobile, agent, api, pos
    is_pre_approved: bool = False
    is_topup_refinance: bool = False

    # Borrower profile
    employment_type: str = ""
    employment_tenure_months: int = 0
    income_band: str = ""
    monthly_income: float = 0
    is_income_verified: bool = False
    age: int = 0
    geographic_region: str = ""
    employer_category: str = ""

    # Bureau profile
    bureau_file_status: str = ""  # thick, standard, thin, none
    worst_delinquency_12m: int = 0
    worst_delinquency_24m: int = 0
    active_credit_facilities: int = 0
    total_outstanding_debt: float = 0
    has_adverse_records: bool = False
    recent_inquiries: int = 0

    # Scorecard outputs
    application_score: float | None = None
    behavioral_score: float | None = None
    fraud_score: float | None = None

    # Derived
    dti_ratio: float = 0
    ltv_ratio: float = 0
    net_disposable_income: float = 0
    total_exposure: float = 0

    # Merchant
    merchant_name: str = ""
    merchant_tier: str = ""
    is_approved_merchant: bool = False


def build_routing_context(
    application,
    profile,
    bureau_data: dict,
    extra: dict | None = None,
) -> RoutingContext:
    """Build a RoutingContext from application data available at decision time."""
    ctx = RoutingContext()

    # Application characteristics
    if application:
        ctx.loan_amount = float(getattr(application, "amount_requested", 0) or 0)
        ctx.loan_tenure_months = getattr(application, "term_months", 0) or 0
        cp = getattr(application, "credit_product", None)
        if cp:
            ctx.product_family = getattr(cp, "name", "") or ""
            ctx.product_type = getattr(cp, "name", "") or ""

    # Borrower profile
    if profile:
        ctx.employment_type = (getattr(profile, "employment_type", "") or "").lower()
        ctx.monthly_income = float(getattr(profile, "monthly_income", 0) or 0)
        ctx.age = _calculate_age(getattr(profile, "date_of_birth", None))
        years_emp = getattr(profile, "years_employed", 0) or 0
        ctx.employment_tenure_months = int(years_emp * 12)

        income = ctx.monthly_income
        if income > 0:
            if income < 5000:
                ctx.income_band = "below_5000"
            elif income < 15000:
                ctx.income_band = "5000_15000"
            elif income < 30000:
                ctx.income_band = "15000_30000"
            else:
                ctx.income_band = "above_30000"

        expenses = float(getattr(profile, "monthly_expenses", 0) or 0)
        existing_debt = float(getattr(profile, "existing_debt", 0) or 0)
        if income > 0:
            ctx.dti_ratio = (expenses + existing_debt) / income
        ctx.net_disposable_income = income - expenses - existing_debt

    # Bureau data
    if bureau_data:
        score = bureau_data.get("score")
        if score is not None:
            ctx.application_score = float(score)

        tradelines = bureau_data.get("tradelines", [])
        ctx.active_credit_facilities = len(tradelines) if tradelines else 0

        public_records = bureau_data.get("public_records", [])
        ctx.has_adverse_records = any(
            r.get("type") in ("Judgment", "Bankruptcy", "WriteOff") and r.get("status") == "active"
            for r in public_records
        ) if public_records else False

        ctx.recent_inquiries = bureau_data.get("num_inquiries", 0)
        ctx.total_outstanding_debt = float(bureau_data.get("total_outstanding_debt", 0))

        # Determine bureau file status
        history_years = bureau_data.get("credit_history_years", 0)
        if ctx.active_credit_facilities == 0 and history_years == 0:
            ctx.bureau_file_status = "none"
        elif history_years < 2 or ctx.active_credit_facilities < 2:
            ctx.bureau_file_status = "thin"
        elif history_years >= 5 and ctx.active_credit_facilities >= 3:
            ctx.bureau_file_status = "thick"
        else:
            ctx.bureau_file_status = "standard"

    # Merchant data
    if application:
        merchant = getattr(application, "merchant", None)
        if merchant:
            ctx.merchant_name = getattr(merchant, "name", "") or ""
            ctx.is_approved_merchant = bool(getattr(merchant, "is_active", False))

    # Overrides from extra context
    if extra:
        for key, value in extra.items():
            if hasattr(ctx, key):
                setattr(ctx, key, value)

    return ctx


def _calculate_age(dob) -> int:
    if not dob:
        return 30
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ── Tree traversal ─────────────────────────────────────────────────

def route_application(
    context: RoutingContext,
    nodes: list[DecisionTreeNode],
    default_strategy_id: int | None = None,
) -> RoutingResult:
    """Traverse the decision tree and return the assigned strategy.

    This is a pure function — no database calls, no side effects.
    The tree nodes and context are passed in directly.
    """
    if not nodes:
        if default_strategy_id:
            return RoutingResult(
                strategy_id=default_strategy_id,
                strategy_params=None,
                used_default=True,
            )
        raise ValueError("Empty tree and no default strategy configured")

    node_map: dict[str, DecisionTreeNode] = {n.node_key: n for n in nodes}

    root = next((n for n in nodes if n.is_root), None)
    if root is None:
        root = next((n for n in nodes if n.parent_node_id is None), None)
    if root is None:
        raise ValueError("Decision tree has no root node")

    path: list[RoutingStep] = []
    current = root
    visited: set[str] = set()

    while current is not None:
        if current.node_key in visited:
            raise ValueError(f"Cycle detected at node {current.node_key}")
        visited.add(current.node_key)

        # Terminal: strategy or assessment assignment
        if current.node_type in (NodeType.STRATEGY, NodeType.ASSESSMENT):
            path.append(RoutingStep(
                node_key=current.node_key,
                node_label=current.label,
                attribute=None,
                actual_value=None,
                branch_taken="terminal",
                node_type=current.node_type.value if hasattr(current.node_type, 'value') else str(current.node_type),
            ))
            return RoutingResult(
                strategy_id=current.strategy_id,
                strategy_params=current.strategy_params,
                assessment_id=getattr(current, 'assessment_id', None),
                path=path,
            )

        # Annotation nodes — skip to child
        if current.node_type == NodeType.ANNOTATION:
            children = [n for n in nodes if n.parent_node_id == current.id]
            current = children[0] if children else None
            continue

        # Condition or scorecard gate — evaluate and branch
        branch_taken, actual_value = _evaluate_node(current, context)

        path.append(RoutingStep(
            node_key=current.node_key,
            node_label=current.label,
            attribute=current.attribute,
            actual_value=actual_value,
            branch_taken=branch_taken,
            node_type=current.node_type.value if current.node_type else "condition",
        ))

        next_node = _find_child(nodes, current, branch_taken, node_map)

        if next_node is None:
            # Fall through to default strategy
            if default_strategy_id:
                return RoutingResult(
                    strategy_id=default_strategy_id,
                    strategy_params=None,
                    path=path,
                    used_default=True,
                )
            raise ValueError(
                f"No child node for branch '{branch_taken}' at node '{current.node_key}' "
                f"and no default strategy"
            )

        current = next_node

    # Should not reach here, but safety net
    if default_strategy_id:
        return RoutingResult(
            strategy_id=default_strategy_id,
            strategy_params=None,
            path=path,
            used_default=True,
        )
    raise ValueError("Tree traversal ended without reaching a strategy node")


def _evaluate_node(
    node: DecisionTreeNode,
    context: RoutingContext,
) -> tuple[str, Any]:
    """Evaluate a condition/scorecard_gate node and return (branch_name, actual_value)."""

    if node.node_type == NodeType.SCORECARD_GATE:
        return _evaluate_scorecard_gate(node, context)

    if node.condition_type == ConditionType.COMPOUND:
        return _evaluate_compound(node, context)

    attribute = node.attribute or ""
    actual_value = _get_context_value(context, attribute)

    # Null handling
    if actual_value is None or actual_value == "":
        if node.null_branch:
            return node.null_branch, None
        branches = node.branches or {}
        if "Other" in branches:
            return "Other", None
        if "other" in branches:
            return "other", None
        return next(iter(branches.keys()), "Other"), None

    if node.condition_type == ConditionType.BINARY:
        return _evaluate_binary(node, actual_value)
    elif node.condition_type == ConditionType.CATEGORICAL:
        return _evaluate_categorical(node, actual_value)
    elif node.condition_type == ConditionType.NUMERIC_RANGE:
        return _evaluate_numeric_range(node, actual_value)

    # Fallback for untyped conditions — treat as categorical
    return _evaluate_categorical(node, actual_value)


def _evaluate_binary(node: DecisionTreeNode, value: Any) -> tuple[str, Any]:
    """Binary split: evaluate to one of two branches."""
    branches = node.branches or {}
    operator = (node.operator or "eq").lower()

    branch_keys = list(branches.keys())
    if len(branch_keys) < 2:
        return branch_keys[0] if branch_keys else "Other", value

    true_branch = branch_keys[0]
    false_branch = branch_keys[1]

    threshold = branches.get(true_branch, {}).get("value")

    result = _compare_value(value, operator, threshold)
    return (true_branch if result else false_branch), value


def _evaluate_categorical(node: DecisionTreeNode, value: Any) -> tuple[str, Any]:
    """Categorical split: match value to a named branch."""
    branches = node.branches or {}
    str_value = str(value).lower().strip()

    for branch_name, branch_config in branches.items():
        if branch_name.lower() in ("other", "all_others", "catch_all"):
            continue
        branch_values = branch_config.get("values", []) if isinstance(branch_config, dict) else []
        if str_value in [str(v).lower().strip() for v in branch_values]:
            return branch_name, value
        if str_value == branch_name.lower().strip():
            return branch_name, value

    # No match — fall to Other/catch-all
    for branch_name in branches:
        if branch_name.lower() in ("other", "all_others", "catch_all"):
            return branch_name, value

    return "Other", value


def _evaluate_numeric_range(node: DecisionTreeNode, value: Any) -> tuple[str, Any]:
    """Numeric range split: find the band the value falls into."""
    branches = node.branches or {}
    try:
        num_value = float(value)
    except (TypeError, ValueError):
        for branch_name in branches:
            if branch_name.lower() in ("other", "all_others", "catch_all"):
                return branch_name, value
        return "Other", value

    for branch_name, branch_config in branches.items():
        if branch_name.lower() in ("other", "all_others", "catch_all"):
            continue
        if not isinstance(branch_config, dict):
            continue
        low = branch_config.get("min")
        high = branch_config.get("max")

        in_range = True
        if low is not None and num_value < float(low):
            in_range = False
        if high is not None and num_value >= float(high):
            in_range = False
        if in_range:
            return branch_name, value

    for branch_name in branches:
        if branch_name.lower() in ("other", "all_others", "catch_all"):
            return branch_name, value

    return "Other", value


def _evaluate_scorecard_gate(
    node: DecisionTreeNode,
    context: RoutingContext,
) -> tuple[str, Any]:
    """Scorecard gate: route based on score bands defined in branches."""
    score = context.application_score
    if score is None:
        if node.null_branch:
            return node.null_branch, None
        return "Other", None

    return _evaluate_numeric_range(node, score)


def _evaluate_compound(
    node: DecisionTreeNode,
    context: RoutingContext,
) -> tuple[str, Any]:
    """Compound condition: multiple conditions combined with AND/OR."""
    conditions = node.compound_conditions or []
    logic = (node.compound_logic or "AND").upper()
    branches = node.branches or {}

    branch_keys = list(branches.keys())
    if len(branch_keys) < 2:
        return branch_keys[0] if branch_keys else "Other", None

    true_branch = branch_keys[0]
    false_branch = branch_keys[1]

    results = []
    values_seen = {}
    for cond in conditions:
        attr = cond.get("attribute", "")
        op = cond.get("operator", "eq")
        threshold = cond.get("value")
        val = _get_context_value(context, attr)
        values_seen[attr] = val
        if val is None:
            results.append(False)
        else:
            results.append(_compare_value(val, op, threshold))

    if logic == "AND":
        matched = all(results)
    else:
        matched = any(results)

    return (true_branch if matched else false_branch), values_seen


def _find_child(
    nodes: list[DecisionTreeNode],
    parent: DecisionTreeNode,
    branch_label: str,
    node_map: dict[str, DecisionTreeNode],
) -> DecisionTreeNode | None:
    """Find the child node for a given branch label."""
    for n in nodes:
        if n.parent_node_id == parent.id and n.branch_label == branch_label:
            return n
    # Fallback: case-insensitive match
    branch_lower = branch_label.lower()
    for n in nodes:
        if n.parent_node_id == parent.id and (n.branch_label or "").lower() == branch_lower:
            return n
    return None


def _get_context_value(context: RoutingContext, attribute: str) -> Any:
    """Retrieve an attribute value from the routing context."""
    if not attribute:
        return None
    attr_clean = attribute.strip().lower().replace(" ", "_").replace("-", "_")
    # Direct attribute lookup
    if hasattr(context, attr_clean):
        return getattr(context, attr_clean)
    # Try without underscores
    for field_name in context.__dataclass_fields__:
        if field_name.lower() == attr_clean:
            return getattr(context, field_name)
    return None


def _compare_value(value: Any, operator: str, threshold: Any) -> bool:
    """Generic comparison."""
    if value is None or threshold is None:
        return False

    op = operator.lower()

    try:
        if op in ("gte", ">="):
            return float(value) >= float(threshold)
        elif op in ("lte", "<="):
            return float(value) <= float(threshold)
        elif op in ("gt", ">"):
            return float(value) > float(threshold)
        elif op in ("lt", "<"):
            return float(value) < float(threshold)
    except (TypeError, ValueError):
        pass

    if op in ("eq", "==", "equals"):
        return str(value).lower().strip() == str(threshold).lower().strip()
    elif op in ("neq", "!=", "not_equals"):
        return str(value).lower().strip() != str(threshold).lower().strip()
    elif op == "in":
        if isinstance(threshold, list):
            return str(value).lower().strip() in [str(v).lower().strip() for v in threshold]
        return str(value).lower().strip() in str(threshold).lower().strip()
    elif op == "not_in":
        if isinstance(threshold, list):
            return str(value).lower().strip() not in [str(v).lower().strip() for v in threshold]
        return str(value).lower().strip() not in str(threshold).lower().strip()
    elif op == "between":
        if isinstance(threshold, (list, tuple)) and len(threshold) >= 2:
            try:
                return float(threshold[0]) <= float(value) <= float(threshold[1])
            except (TypeError, ValueError):
                return False
    elif op in ("true", "is_true"):
        return bool(value) is True
    elif op in ("false", "is_false"):
        return bool(value) is False

    return str(value).lower().strip() == str(threshold).lower().strip()
