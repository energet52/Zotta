"""Decision Tree Validator — enforces structural integrity of decision trees.

Validates DAG properties, completeness of conditions, catch-all branches,
and strategy reference validity.  Returns structured errors for the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.strategy import DecisionTreeNode, NodeType, ConditionType


@dataclass
class ValidationError:
    severity: str  # "error" | "warning"
    node_key: str | None
    code: str
    message: str


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add_error(self, node_key: str | None, code: str, message: str):
        self.errors.append(ValidationError("error", node_key, code, message))
        self.valid = False

    def add_warning(self, node_key: str | None, code: str, message: str):
        self.warnings.append(ValidationError("warning", node_key, code, message))


def validate_tree(
    nodes: list[DecisionTreeNode],
    valid_strategy_ids: set[int] | None = None,
) -> ValidationResult:
    """Run all validation checks on a decision tree.

    Args:
        nodes: List of tree nodes to validate.
        valid_strategy_ids: Optional set of valid strategy IDs.  If provided,
            terminal nodes referencing strategies not in this set will fail.
    """
    result = ValidationResult(valid=True)

    if not nodes:
        result.add_error(None, "EMPTY_TREE", "Decision tree has no nodes")
        return result

    node_map = {n.node_key: n for n in nodes}
    id_map = {n.id: n for n in nodes}

    _validate_root(nodes, result)
    _validate_no_cycles(nodes, id_map, result)
    _validate_no_orphans(nodes, id_map, result)
    _validate_no_dead_ends(nodes, id_map, result)
    _validate_completeness(nodes, result)
    _validate_catch_all(nodes, result)
    _validate_strategy_references(nodes, valid_strategy_ids, result)
    _validate_null_handling(nodes, result)

    # Stats
    condition_count = sum(1 for n in nodes if n.node_type in (NodeType.CONDITION, NodeType.SCORECARD_GATE))
    terminal_count = sum(1 for n in nodes if n.node_type in (NodeType.STRATEGY, NodeType.ASSESSMENT))
    max_depth = _calculate_max_depth(nodes, id_map)

    result.stats = {
        "total_nodes": len(nodes),
        "condition_nodes": condition_count,
        "terminal_nodes": terminal_count,
        "max_depth": max_depth,
    }

    return result


def _validate_root(nodes: list[DecisionTreeNode], result: ValidationResult):
    """Verify exactly one root node exists."""
    roots = [n for n in nodes if n.is_root]
    if not roots:
        parentless = [n for n in nodes if n.parent_node_id is None]
        if len(parentless) == 0:
            result.add_error(None, "NO_ROOT", "No root node found")
        elif len(parentless) > 1:
            result.add_error(
                None, "MULTIPLE_ROOTS",
                f"Multiple root candidates found: {[n.node_key for n in parentless]}",
            )
    elif len(roots) > 1:
        result.add_error(
            None, "MULTIPLE_ROOTS",
            f"Multiple root nodes marked: {[n.node_key for n in roots]}",
        )


def _validate_no_cycles(
    nodes: list[DecisionTreeNode],
    id_map: dict[int, DecisionTreeNode],
    result: ValidationResult,
):
    """Verify the tree is a DAG with no cycles."""
    visited: set[str] = set()
    in_stack: set[str] = set()

    def _dfs(node: DecisionTreeNode) -> bool:
        if node.node_key in in_stack:
            result.add_error(
                node.node_key, "CYCLE_DETECTED",
                f"Cycle detected involving node '{node.node_key}'",
            )
            return True
        if node.node_key in visited:
            return False
        visited.add(node.node_key)
        in_stack.add(node.node_key)

        children = [n for n in nodes if n.parent_node_id == node.id]
        for child in children:
            if _dfs(child):
                return True

        in_stack.discard(node.node_key)
        return False

    for node in nodes:
        if node.node_key not in visited:
            _dfs(node)


def _validate_no_orphans(
    nodes: list[DecisionTreeNode],
    id_map: dict[int, DecisionTreeNode],
    result: ValidationResult,
):
    """Verify every node is reachable from the root."""
    roots = [n for n in nodes if n.is_root or n.parent_node_id is None]
    if not roots:
        return

    reachable: set[str] = set()

    def _walk(node: DecisionTreeNode):
        reachable.add(node.node_key)
        children = [n for n in nodes if n.parent_node_id == node.id]
        for child in children:
            if child.node_key not in reachable:
                _walk(child)

    for root in roots:
        _walk(root)

    for node in nodes:
        if node.node_key not in reachable:
            result.add_error(
                node.node_key, "ORPHAN_NODE",
                f"Node '{node.node_key}' is not reachable from the root",
            )


def _validate_no_dead_ends(
    nodes: list[DecisionTreeNode],
    id_map: dict[int, DecisionTreeNode],
    result: ValidationResult,
):
    """Verify every path terminates at a strategy node (no dead ends)."""
    for node in nodes:
        if node.node_type in (NodeType.CONDITION, NodeType.SCORECARD_GATE):
            children = [n for n in nodes if n.parent_node_id == node.id]
            if not children:
                result.add_error(
                    node.node_key, "DEAD_END",
                    f"Condition node '{node.node_key}' has no child nodes (dead end)",
                )


def _validate_completeness(
    nodes: list[DecisionTreeNode],
    result: ValidationResult,
):
    """Verify condition nodes handle all possible values."""
    for node in nodes:
        if node.node_type not in (NodeType.CONDITION, NodeType.SCORECARD_GATE):
            continue

        branches = node.branches or {}
        children = [n for n in nodes if n.parent_node_id == node.id]
        child_branches = {n.branch_label for n in children if n.branch_label}

        for branch_name in branches:
            if branch_name not in child_branches:
                result.add_error(
                    node.node_key, "MISSING_BRANCH_TARGET",
                    f"Branch '{branch_name}' on node '{node.node_key}' has no target node",
                )


def _validate_catch_all(
    nodes: list[DecisionTreeNode],
    result: ValidationResult,
):
    """Verify categorical/range conditions have a catch-all branch."""
    for node in nodes:
        if node.node_type != NodeType.CONDITION:
            continue
        if node.condition_type not in (ConditionType.CATEGORICAL, ConditionType.NUMERIC_RANGE):
            continue

        branches = node.branches or {}
        has_catch_all = any(
            k.lower() in ("other", "all_others", "catch_all", "default")
            for k in branches
        )
        if not has_catch_all:
            result.add_warning(
                node.node_key, "NO_CATCH_ALL",
                f"Node '{node.node_key}' has no 'Other' catch-all branch. "
                f"Applications that match no explicit branch will fail routing.",
            )


def _validate_strategy_references(
    nodes: list[DecisionTreeNode],
    valid_ids: set[int] | None,
    result: ValidationResult,
):
    """Verify all terminal nodes reference valid strategies or assessments."""
    for node in nodes:
        if node.node_type == NodeType.STRATEGY:
            if node.strategy_id is None:
                result.add_error(
                    node.node_key, "NO_STRATEGY",
                    f"Strategy node '{node.node_key}' has no strategy assigned",
                )
            elif valid_ids is not None and node.strategy_id not in valid_ids:
                result.add_error(
                    node.node_key, "INVALID_STRATEGY",
                    f"Strategy node '{node.node_key}' references strategy {node.strategy_id} "
                    f"which does not exist or is archived",
                )
        elif node.node_type == NodeType.ASSESSMENT:
            assessment_id = getattr(node, 'assessment_id', None)
            if assessment_id is None:
                result.add_error(
                    node.node_key, "NO_ASSESSMENT",
                    f"Assessment node '{node.node_key}' has no assessment assigned",
                )


def _validate_null_handling(
    nodes: list[DecisionTreeNode],
    result: ValidationResult,
):
    """Verify condition nodes define null handling."""
    for node in nodes:
        if node.node_type not in (NodeType.CONDITION, NodeType.SCORECARD_GATE):
            continue
        if node.null_branch is None and node.null_strategy_id is None:
            branches = node.branches or {}
            has_catch_all = any(
                k.lower() in ("other", "all_others", "catch_all", "default")
                for k in branches
            )
            if not has_catch_all:
                result.add_warning(
                    node.node_key, "NO_NULL_HANDLING",
                    f"Node '{node.node_key}' does not define null handling. "
                    f"Applications with missing '{node.attribute}' may fail routing.",
                )


def _calculate_max_depth(
    nodes: list[DecisionTreeNode],
    id_map: dict[int, DecisionTreeNode],
) -> int:
    """Calculate the maximum depth of the tree."""
    if not nodes:
        return 0

    depth_cache: dict[str, int] = {}

    def _depth(node: DecisionTreeNode) -> int:
        if node.node_key in depth_cache:
            return depth_cache[node.node_key]

        children = [n for n in nodes if n.parent_node_id == node.id]
        if not children:
            depth_cache[node.node_key] = 1
            return 1

        max_child = max(_depth(c) for c in children)
        depth_cache[node.node_key] = 1 + max_child
        return 1 + max_child

    roots = [n for n in nodes if n.is_root or n.parent_node_id is None]
    if not roots:
        return 0
    return max(_depth(r) for r in roots)
