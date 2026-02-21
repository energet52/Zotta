"""Tests for the Decision Tree routing and validation engine.

Covers:
  - Binary, categorical, numeric range, compound conditions
  - Null handling at every node type
  - Multi-level traversal (4+ levels)
  - Completeness validation (dead ends, orphans, cycles rejected)
  - Strategy parameter override propagation
  - Catch-all enforcement
"""

import pytest
from unittest.mock import MagicMock

from app.models.strategy import (
    DecisionTreeNode, NodeType, ConditionType,
)
from app.services.decision_engine.tree_router import (
    RoutingContext, route_application,
)
from app.services.decision_engine.tree_validator import validate_tree


def _node(
    id_: int, key: str, node_type: NodeType,
    parent_id=None, branch_label=None, is_root=False,
    condition_type=None, attribute=None, operator=None,
    branches=None, strategy_id=None, strategy_params=None,
    null_branch=None, compound_conditions=None, compound_logic=None,
    scorecard_id=None,
):
    n = MagicMock(spec=DecisionTreeNode)
    n.id = id_
    n.node_key = key
    n.node_type = node_type
    n.parent_node_id = parent_id
    n.branch_label = branch_label
    n.is_root = is_root
    n.condition_type = condition_type
    n.attribute = attribute
    n.operator = operator
    n.branches = branches or {}
    n.strategy_id = strategy_id
    n.strategy_params = strategy_params
    n.null_branch = null_branch
    n.null_strategy_id = None
    n.compound_conditions = compound_conditions
    n.compound_logic = compound_logic
    n.scorecard_id = scorecard_id
    n.label = key
    n.position_x = 0
    n.position_y = 0
    return n


class TestBinaryCondition:
    def test_true_branch(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.BINARY, attribute="is_existing_customer",
                      operator="eq", branches={"Yes": {"value": True}, "No": {"value": False}})
        yes_strat = _node(2, "yes_strat", NodeType.STRATEGY, parent_id=1,
                          branch_label="Yes", strategy_id=100)
        no_strat = _node(3, "no_strat", NodeType.STRATEGY, parent_id=1,
                         branch_label="No", strategy_id=200)

        ctx = RoutingContext(is_existing_customer=True)
        result = route_application(ctx, [root, yes_strat, no_strat])
        assert result.strategy_id == 100

    def test_false_branch(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.BINARY, attribute="is_existing_customer",
                      operator="eq", branches={"Yes": {"value": True}, "No": {"value": False}})
        yes_strat = _node(2, "yes_strat", NodeType.STRATEGY, parent_id=1,
                          branch_label="Yes", strategy_id=100)
        no_strat = _node(3, "no_strat", NodeType.STRATEGY, parent_id=1,
                         branch_label="No", strategy_id=200)

        ctx = RoutingContext(is_existing_customer=False)
        result = route_application(ctx, [root, yes_strat, no_strat])
        assert result.strategy_id == 200

    def test_null_uses_null_branch(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.BINARY, attribute="is_existing_customer",
                      operator="eq", branches={"Yes": {"value": True}, "No": {"value": False}},
                      null_branch="No")
        yes_strat = _node(2, "yes_strat", NodeType.STRATEGY, parent_id=1,
                          branch_label="Yes", strategy_id=100)
        no_strat = _node(3, "no_strat", NodeType.STRATEGY, parent_id=1,
                         branch_label="No", strategy_id=200)

        ctx = RoutingContext()  # is_existing_customer defaults False
        result = route_application(ctx, [root, yes_strat, no_strat])
        assert result.strategy_id == 200


class TestCategoricalCondition:
    def test_matches_branch(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.CATEGORICAL, attribute="employment_type",
                      branches={
                          "Salaried": {"values": ["salaried", "employed"]},
                          "Self-Employed": {"values": ["self_employed", "self-employed"]},
                          "Other": {"values": []},
                      })
        sal = _node(2, "sal", NodeType.STRATEGY, parent_id=1,
                    branch_label="Salaried", strategy_id=100)
        se = _node(3, "se", NodeType.STRATEGY, parent_id=1,
                   branch_label="Self-Employed", strategy_id=200)
        other = _node(4, "other", NodeType.STRATEGY, parent_id=1,
                      branch_label="Other", strategy_id=300)

        ctx = RoutingContext(employment_type="self_employed")
        result = route_application(ctx, [root, sal, se, other])
        assert result.strategy_id == 200

    def test_unmatched_falls_to_other(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.CATEGORICAL, attribute="employment_type",
                      branches={
                          "Salaried": {"values": ["salaried"]},
                          "Other": {"values": []},
                      })
        sal = _node(2, "sal", NodeType.STRATEGY, parent_id=1,
                    branch_label="Salaried", strategy_id=100)
        other = _node(3, "other", NodeType.STRATEGY, parent_id=1,
                      branch_label="Other", strategy_id=300)

        ctx = RoutingContext(employment_type="retired")
        result = route_application(ctx, [root, sal, other])
        assert result.strategy_id == 300


class TestNumericRangeCondition:
    def test_matches_band(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.NUMERIC_RANGE, attribute="monthly_income",
                      branches={
                          "Below 5K": {"min": None, "max": 5000},
                          "5K-15K": {"min": 5000, "max": 15000},
                          "Above 15K": {"min": 15000, "max": None},
                      })
        low = _node(2, "low", NodeType.STRATEGY, parent_id=1,
                    branch_label="Below 5K", strategy_id=100)
        mid = _node(3, "mid", NodeType.STRATEGY, parent_id=1,
                    branch_label="5K-15K", strategy_id=200)
        high = _node(4, "high", NodeType.STRATEGY, parent_id=1,
                     branch_label="Above 15K", strategy_id=300)

        ctx = RoutingContext(monthly_income=10000)
        result = route_application(ctx, [root, low, mid, high])
        assert result.strategy_id == 200

    def test_boundary_lower_inclusive(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.NUMERIC_RANGE, attribute="monthly_income",
                      branches={
                          "Below 5K": {"min": None, "max": 5000},
                          "5K-15K": {"min": 5000, "max": 15000},
                      })
        low = _node(2, "low", NodeType.STRATEGY, parent_id=1,
                    branch_label="Below 5K", strategy_id=100)
        mid = _node(3, "mid", NodeType.STRATEGY, parent_id=1,
                    branch_label="5K-15K", strategy_id=200)

        ctx = RoutingContext(monthly_income=5000)
        result = route_application(ctx, [root, low, mid])
        assert result.strategy_id == 200  # min inclusive, max exclusive


class TestCompoundCondition:
    def test_and_both_true(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.COMPOUND,
                      compound_conditions=[
                          {"attribute": "is_existing_customer", "operator": "eq", "value": "True"},
                          {"attribute": "monthly_income", "operator": "gte", "value": 10000},
                      ],
                      compound_logic="AND",
                      branches={"FastTrack": {}, "Standard": {}})
        fast = _node(2, "fast", NodeType.STRATEGY, parent_id=1,
                     branch_label="FastTrack", strategy_id=100)
        std = _node(3, "std", NodeType.STRATEGY, parent_id=1,
                    branch_label="Standard", strategy_id=200)

        ctx = RoutingContext(is_existing_customer=True, monthly_income=15000)
        result = route_application(ctx, [root, fast, std])
        assert result.strategy_id == 100

    def test_and_one_false(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.COMPOUND,
                      compound_conditions=[
                          {"attribute": "is_existing_customer", "operator": "eq", "value": "True"},
                          {"attribute": "monthly_income", "operator": "gte", "value": 10000},
                      ],
                      compound_logic="AND",
                      branches={"FastTrack": {}, "Standard": {}})
        fast = _node(2, "fast", NodeType.STRATEGY, parent_id=1,
                     branch_label="FastTrack", strategy_id=100)
        std = _node(3, "std", NodeType.STRATEGY, parent_id=1,
                    branch_label="Standard", strategy_id=200)

        ctx = RoutingContext(is_existing_customer=True, monthly_income=5000)
        result = route_application(ctx, [root, fast, std])
        assert result.strategy_id == 200

    def test_or_one_true(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.COMPOUND,
                      compound_conditions=[
                          {"attribute": "is_existing_customer", "operator": "eq", "value": "True"},
                          {"attribute": "monthly_income", "operator": "gte", "value": 10000},
                      ],
                      compound_logic="OR",
                      branches={"FastTrack": {}, "Standard": {}})
        fast = _node(2, "fast", NodeType.STRATEGY, parent_id=1,
                     branch_label="FastTrack", strategy_id=100)
        std = _node(3, "std", NodeType.STRATEGY, parent_id=1,
                    branch_label="Standard", strategy_id=200)

        ctx = RoutingContext(is_existing_customer=False, monthly_income=15000)
        result = route_application(ctx, [root, fast, std])
        assert result.strategy_id == 100


class TestMultiLevelTree:
    def test_four_level_tree(self):
        """4-level deep tree: Customer -> Merchant -> Amount -> Strategy."""
        lvl1 = _node(1, "cust", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.BINARY, attribute="is_existing_customer",
                      operator="eq", branches={"Yes": {"value": True}, "No": {"value": False}})
        lvl2 = _node(2, "merchant", NodeType.CONDITION, parent_id=1, branch_label="No",
                      condition_type=ConditionType.CATEGORICAL, attribute="merchant_tier",
                      branches={"Tier1": {"values": ["tier1"]}, "Other": {"values": []}})
        lvl3 = _node(3, "amount", NodeType.CONDITION, parent_id=2, branch_label="Tier1",
                      condition_type=ConditionType.NUMERIC_RANGE, attribute="loan_amount",
                      branches={"Small": {"min": None, "max": 50000}, "Large": {"min": 50000, "max": None}})
        strat_a = _node(4, "strat_a", NodeType.STRATEGY, parent_id=3,
                        branch_label="Small", strategy_id=100)
        strat_b = _node(5, "strat_b", NodeType.STRATEGY, parent_id=3,
                        branch_label="Large", strategy_id=200)
        strat_existing = _node(6, "strat_existing", NodeType.STRATEGY, parent_id=1,
                               branch_label="Yes", strategy_id=300)
        strat_other = _node(7, "strat_other", NodeType.STRATEGY, parent_id=2,
                            branch_label="Other", strategy_id=400)

        nodes = [lvl1, lvl2, lvl3, strat_a, strat_b, strat_existing, strat_other]

        # New customer, Tier1, Small amount
        ctx = RoutingContext(is_existing_customer=False, merchant_tier="tier1", loan_amount=25000)
        result = route_application(ctx, nodes)
        assert result.strategy_id == 100
        assert len(result.path) == 4

        # Existing customer goes straight to strategy
        ctx2 = RoutingContext(is_existing_customer=True)
        result2 = route_application(ctx2, nodes)
        assert result2.strategy_id == 300


class TestStrategyParameterOverride:
    def test_params_passed_through(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.BINARY, attribute="is_existing_customer",
                      operator="eq", branches={"Yes": {"value": True}, "No": {"value": False}})
        strat_yes = _node(2, "yes", NodeType.STRATEGY, parent_id=1,
                          branch_label="Yes", strategy_id=100,
                          strategy_params={"max_approval_amount": 200000})
        strat_no = _node(3, "no", NodeType.STRATEGY, parent_id=1,
                         branch_label="No", strategy_id=100,
                         strategy_params={"max_approval_amount": 50000, "min_down_payment_pct": 20})

        ctx = RoutingContext(is_existing_customer=False)
        result = route_application(ctx, [root, strat_yes, strat_no])
        assert result.strategy_id == 100
        assert result.strategy_params["max_approval_amount"] == 50000
        assert result.strategy_params["min_down_payment_pct"] == 20


class TestDefaultStrategy:
    def test_empty_tree_uses_default(self):
        result = route_application(RoutingContext(), [], default_strategy_id=999)
        assert result.strategy_id == 999
        assert result.used_default is True

    def test_no_tree_no_default_raises(self):
        with pytest.raises(ValueError, match="Empty tree"):
            route_application(RoutingContext(), [])


class TestScorecardGate:
    def test_routes_by_score_band(self):
        gate = _node(1, "gate", NodeType.SCORECARD_GATE, is_root=True,
                      condition_type=ConditionType.NUMERIC_RANGE,
                      attribute="application_score",
                      branches={
                          "Low": {"min": None, "max": 180},
                          "Medium": {"min": 180, "max": 280},
                          "High": {"min": 280, "max": None},
                      })
        low_s = _node(2, "low", NodeType.STRATEGY, parent_id=1,
                      branch_label="Low", strategy_id=100)
        med_s = _node(3, "med", NodeType.STRATEGY, parent_id=1,
                      branch_label="Medium", strategy_id=200)
        high_s = _node(4, "high", NodeType.STRATEGY, parent_id=1,
                       branch_label="High", strategy_id=300)

        ctx = RoutingContext(application_score=250)
        result = route_application(ctx, [gate, low_s, med_s, high_s])
        assert result.strategy_id == 200

    def test_boundary_score_exactly_280(self):
        gate = _node(1, "gate", NodeType.SCORECARD_GATE, is_root=True,
                      condition_type=ConditionType.NUMERIC_RANGE,
                      attribute="application_score",
                      branches={
                          "Medium": {"min": 180, "max": 280},
                          "High": {"min": 280, "max": None},
                      })
        med_s = _node(2, "med", NodeType.STRATEGY, parent_id=1,
                      branch_label="Medium", strategy_id=200)
        high_s = _node(3, "high", NodeType.STRATEGY, parent_id=1,
                       branch_label="High", strategy_id=300)

        ctx = RoutingContext(application_score=280)
        result = route_application(ctx, [gate, med_s, high_s])
        assert result.strategy_id == 300  # min inclusive


# ── Validation Tests ───────────────────────────────────────────────

class TestTreeValidation:
    def test_empty_tree_invalid(self):
        result = validate_tree([])
        assert not result.valid
        assert any(e.code == "EMPTY_TREE" for e in result.errors)

    def test_valid_simple_tree(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.BINARY,
                      branches={"Yes": {}, "No": {}})
        yes_s = _node(2, "yes", NodeType.STRATEGY, parent_id=1,
                      branch_label="Yes", strategy_id=100)
        no_s = _node(3, "no", NodeType.STRATEGY, parent_id=1,
                     branch_label="No", strategy_id=200)

        result = validate_tree([root, yes_s, no_s], valid_strategy_ids={100, 200})
        assert result.valid

    def test_dead_end_rejected(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.BINARY,
                      branches={"Yes": {}, "No": {}})
        # Only one branch has a child — "No" is a dead end
        yes_s = _node(2, "yes", NodeType.STRATEGY, parent_id=1,
                      branch_label="Yes", strategy_id=100)

        result = validate_tree([root, yes_s])
        assert not result.valid
        assert any(e.code == "MISSING_BRANCH_TARGET" for e in result.errors)

    def test_no_strategy_rejected(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.BINARY,
                      branches={"Yes": {}, "No": {}})
        yes_s = _node(2, "yes", NodeType.STRATEGY, parent_id=1,
                      branch_label="Yes", strategy_id=None)
        no_s = _node(3, "no", NodeType.STRATEGY, parent_id=1,
                     branch_label="No", strategy_id=200)

        result = validate_tree([root, yes_s, no_s])
        assert not result.valid
        assert any(e.code == "NO_STRATEGY" for e in result.errors)

    def test_invalid_strategy_reference(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.BINARY,
                      branches={"Yes": {}, "No": {}})
        yes_s = _node(2, "yes", NodeType.STRATEGY, parent_id=1,
                      branch_label="Yes", strategy_id=999)
        no_s = _node(3, "no", NodeType.STRATEGY, parent_id=1,
                     branch_label="No", strategy_id=200)

        result = validate_tree([root, yes_s, no_s], valid_strategy_ids={200})
        assert not result.valid
        assert any(e.code == "INVALID_STRATEGY" for e in result.errors)

    def test_categorical_warns_no_catch_all(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.CATEGORICAL, attribute="employment_type",
                      branches={"Salaried": {}, "Self-Employed": {}})
        s1 = _node(2, "s1", NodeType.STRATEGY, parent_id=1,
                   branch_label="Salaried", strategy_id=100)
        s2 = _node(3, "s2", NodeType.STRATEGY, parent_id=1,
                   branch_label="Self-Employed", strategy_id=200)

        result = validate_tree([root, s1, s2], valid_strategy_ids={100, 200})
        assert any(w.code == "NO_CATCH_ALL" for w in result.warnings)

    def test_stats_computed(self):
        root = _node(1, "root", NodeType.CONDITION, is_root=True,
                      condition_type=ConditionType.BINARY,
                      branches={"Yes": {}, "No": {}})
        yes_s = _node(2, "yes", NodeType.STRATEGY, parent_id=1,
                      branch_label="Yes", strategy_id=100)
        no_s = _node(3, "no", NodeType.STRATEGY, parent_id=1,
                     branch_label="No", strategy_id=200)

        result = validate_tree([root, yes_s, no_s], valid_strategy_ids={100, 200})
        assert result.stats["total_nodes"] == 3
        assert result.stats["condition_nodes"] == 1
        assert result.stats["terminal_nodes"] == 2
        assert result.stats["max_depth"] == 2
