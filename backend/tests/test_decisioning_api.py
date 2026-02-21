"""Comprehensive API functional tests for the Decision Strategy Management module.

Tests all endpoints against the live backend (localhost:8000).
Run with: pytest tests/test_decisioning_api.py -v

Covers: strategies CRUD + lifecycle, decision trees CRUD + validate + activate,
champion-challenger, simulation, and decision explanation.
"""

import pytest
import requests

BASE_URL = "http://localhost:8000/api"


def _is_backend_running():
    try:
        return requests.get(f"{BASE_URL}/health", timeout=2).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _is_backend_running(),
    reason="Backend not running at localhost:8000",
)


# ── Strategy CRUD ──────────────────────────────────────────────────

class TestStrategyCRUD:

    def test_list_strategies(self):
        resp = requests.get(f"{BASE_URL}/strategies")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_sequential_strategy(self):
        resp = requests.post(f"{BASE_URL}/strategies", json={
            "name": "API Test Sequential",
            "description": "Sequential test",
            "evaluation_mode": "sequential",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Test Sequential"
        assert data["evaluation_mode"] == "sequential"
        assert data["status"] == "draft"
        assert data["version"] >= 1
        assert data["id"] > 0

    def test_create_dual_path_strategy(self):
        resp = requests.post(f"{BASE_URL}/strategies", json={
            "name": "API Test Dual-Path",
            "evaluation_mode": "dual_path",
            "knock_out_rules": [
                {"rule_id": "KO1", "name": "Min Age", "field": "applicant_age",
                 "operator": "gte", "threshold": 18, "severity": "hard", "enabled": True},
            ],
            "overlay_rules": [
                {"rule_id": "OV1", "name": "DTI", "field": "debt_to_income_ratio",
                 "operator": "lte", "threshold": 0.45, "severity": "refer", "enabled": True},
            ],
            "score_cutoffs": {"approve": 220, "refer": 180, "decline": 0},
            "concentration_limits": [{"dimension": "product", "limit": 10000000}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["evaluation_mode"] == "dual_path"
        assert len(data["knock_out_rules"]) == 1
        assert len(data["overlay_rules"]) == 1
        assert data["score_cutoffs"]["approve"] == 220
        assert len(data["concentration_limits"]) == 1

    def test_create_scoring_strategy(self):
        resp = requests.post(f"{BASE_URL}/strategies", json={
            "name": "API Test Scoring",
            "evaluation_mode": "scoring",
        })
        assert resp.status_code == 201
        assert resp.json()["evaluation_mode"] == "scoring"

    def test_create_hybrid_strategy(self):
        resp = requests.post(f"{BASE_URL}/strategies", json={
            "name": "API Test Hybrid",
            "evaluation_mode": "hybrid",
        })
        assert resp.status_code == 201
        assert resp.json()["evaluation_mode"] == "hybrid"

    def test_get_strategy(self):
        create = requests.post(f"{BASE_URL}/strategies", json={
            "name": "API Get Test", "evaluation_mode": "sequential",
        })
        sid = create.json()["id"]
        resp = requests.get(f"{BASE_URL}/strategies/{sid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "API Get Test"

    def test_get_nonexistent_strategy(self):
        resp = requests.get(f"{BASE_URL}/strategies/999999")
        assert resp.status_code == 404

    def test_update_draft_strategy(self):
        import time
        unique = str(int(time.time() * 1000))
        create = requests.post(f"{BASE_URL}/strategies", json={
            "name": f"API Update Test {unique}", "evaluation_mode": "sequential",
        })
        sid = create.json()["id"]
        resp = requests.put(f"{BASE_URL}/strategies/{sid}", json={
            "description": "Now updated",
            "evaluation_mode": "dual_path",
            "knock_out_rules": [
                {"rule_id": "KO1", "name": "Test Rule", "field": "applicant_age",
                 "operator": "gte", "threshold": 18, "severity": "hard",
                 "reason_code": "UNDERAGE", "enabled": True},
            ],
            "score_cutoffs": {"approve": 250, "refer": 200, "decline": 0},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["evaluation_mode"] == "dual_path"
        assert len(data["knock_out_rules"]) == 1
        assert data["score_cutoffs"]["approve"] == 250

    def test_cannot_edit_active_strategy(self):
        create = requests.post(f"{BASE_URL}/strategies", json={
            "name": "API Active Edit Test", "evaluation_mode": "sequential",
        })
        sid = create.json()["id"]
        requests.post(f"{BASE_URL}/strategies/{sid}/activate")
        resp = requests.put(f"{BASE_URL}/strategies/{sid}", json={"name": "Fail"})
        assert resp.status_code == 400

    def test_activate_strategy(self):
        create = requests.post(f"{BASE_URL}/strategies", json={
            "name": "API Activate Test", "evaluation_mode": "sequential",
        })
        sid = create.json()["id"]
        resp = requests.post(f"{BASE_URL}/strategies/{sid}/activate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
        assert resp.json()["activated_at"] is not None

    def test_archive_strategy(self):
        create = requests.post(f"{BASE_URL}/strategies", json={
            "name": "API Archive Test", "evaluation_mode": "sequential",
        })
        sid = create.json()["id"]
        resp = requests.post(f"{BASE_URL}/strategies/{sid}/archive")
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_strategy_versions(self):
        create = requests.post(f"{BASE_URL}/strategies", json={
            "name": "API Version Test", "evaluation_mode": "sequential",
        })
        sid = create.json()["id"]
        resp = requests.get(f"{BASE_URL}/strategies/{sid}/versions")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_filter_by_status(self):
        resp = requests.get(f"{BASE_URL}/strategies", params={"status": "draft"})
        assert resp.status_code == 200
        for s in resp.json():
            assert s["status"] == "draft"

    def test_create_without_name_fails(self):
        resp = requests.post(f"{BASE_URL}/strategies", json={
            "evaluation_mode": "sequential",
        })
        assert resp.status_code == 422


# ── Decision Tree CRUD ─────────────────────────────────────────────

class TestDecisionTreeCRUD:

    def test_list_trees(self):
        resp = requests.get(f"{BASE_URL}/decision-trees")
        assert resp.status_code == 200

    def test_create_tree_with_nodes(self):
        s1 = requests.post(f"{BASE_URL}/strategies", json={"name": "TreeS1", "evaluation_mode": "sequential"}).json()
        s2 = requests.post(f"{BASE_URL}/strategies", json={"name": "TreeS2", "evaluation_mode": "sequential"}).json()

        resp = requests.post(f"{BASE_URL}/decision-trees", json={
            "product_id": 1,
            "name": "API Test Tree",
            "default_strategy_id": s2["id"],
            "nodes": [
                {"node_key": "root", "node_type": "condition", "label": "Customer Type",
                 "condition_type": "binary", "attribute": "is_existing_customer",
                 "branches": {"Yes": {"value": True}, "No": {"value": False}},
                 "is_root": True, "position_x": 250, "position_y": 50},
                {"node_key": "yes_strat", "node_type": "strategy", "label": "Existing",
                 "strategy_id": s1["id"], "parent_node_key": "root",
                 "branch_label": "Yes", "position_x": 100, "position_y": 200},
                {"node_key": "no_strat", "node_type": "strategy", "label": "New",
                 "strategy_id": s2["id"], "parent_node_key": "root",
                 "branch_label": "No", "position_x": 400, "position_y": 200},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["nodes"]) == 3
        assert data["status"] == "draft"

    def test_validate_valid_tree(self):
        s1 = requests.post(f"{BASE_URL}/strategies", json={"name": "ValTreeS1", "evaluation_mode": "sequential"}).json()
        s2 = requests.post(f"{BASE_URL}/strategies", json={"name": "ValTreeS2", "evaluation_mode": "sequential"}).json()

        tree = requests.post(f"{BASE_URL}/decision-trees", json={
            "product_id": 1, "name": "API Valid Tree",
            "nodes": [
                {"node_key": "root", "node_type": "condition", "condition_type": "binary",
                 "attribute": "x", "branches": {"Yes": {}, "No": {}},
                 "is_root": True, "position_x": 0, "position_y": 0},
                {"node_key": "y", "node_type": "strategy", "strategy_id": s1["id"],
                 "parent_node_key": "root", "branch_label": "Yes", "position_x": 0, "position_y": 100},
                {"node_key": "n", "node_type": "strategy", "strategy_id": s2["id"],
                 "parent_node_key": "root", "branch_label": "No", "position_x": 200, "position_y": 100},
            ],
        }).json()
        tid = tree["id"]

        resp = requests.post(f"{BASE_URL}/decision-trees/{tid}/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["stats"]["total_nodes"] == 3
        assert data["stats"]["terminal_nodes"] == 2

    def test_validate_empty_tree_fails(self):
        tree = requests.post(f"{BASE_URL}/decision-trees", json={
            "product_id": 1, "name": "API Empty Tree", "nodes": [],
        }).json()
        resp = requests.post(f"{BASE_URL}/decision-trees/{tree['id']}/validate")
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_activate_tree(self):
        s1 = requests.post(f"{BASE_URL}/strategies", json={"name": "ActTreeS1", "evaluation_mode": "sequential"}).json()
        s2 = requests.post(f"{BASE_URL}/strategies", json={"name": "ActTreeS2", "evaluation_mode": "sequential"}).json()

        tree = requests.post(f"{BASE_URL}/decision-trees", json={
            "product_id": 1, "name": "API Activate Tree",
            "nodes": [
                {"node_key": "root", "node_type": "condition", "condition_type": "binary",
                 "attribute": "x", "branches": {"Yes": {}, "No": {}},
                 "is_root": True, "position_x": 0, "position_y": 0},
                {"node_key": "y", "node_type": "strategy", "strategy_id": s1["id"],
                 "parent_node_key": "root", "branch_label": "Yes", "position_x": 0, "position_y": 100},
                {"node_key": "n", "node_type": "strategy", "strategy_id": s2["id"],
                 "parent_node_key": "root", "branch_label": "No", "position_x": 200, "position_y": 100},
            ],
        }).json()

        resp = requests.post(f"{BASE_URL}/decision-trees/{tree['id']}/activate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_get_nonexistent_tree(self):
        resp = requests.get(f"{BASE_URL}/decision-trees/999999")
        assert resp.status_code == 404

    def test_update_tree(self):
        tree = requests.post(f"{BASE_URL}/decision-trees", json={
            "product_id": 1, "name": "API Update Tree", "nodes": [],
        }).json()
        resp = requests.put(f"{BASE_URL}/decision-trees/{tree['id']}", json={
            "name": "API Update Tree (Edited)",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "API Update Tree (Edited)"


# ── Champion-Challenger ────────────────────────────────────────────

class TestChampionChallengerAPI:

    def test_create_and_discard(self):
        s1 = requests.post(f"{BASE_URL}/strategies", json={"name": "CC-API-C", "evaluation_mode": "sequential"}).json()
        s2 = requests.post(f"{BASE_URL}/strategies", json={"name": "CC-API-Ch", "evaluation_mode": "sequential"}).json()

        resp = requests.post(f"{BASE_URL}/champion-challenger", json={
            "champion_strategy_id": s1["id"],
            "challenger_strategy_id": s2["id"],
            "traffic_pct": 15,
            "min_volume": 100,
            "min_duration_days": 30,
        })
        assert resp.status_code == 201
        test_id = resp.json()["id"]

        # Get comparison
        comp = requests.get(f"{BASE_URL}/champion-challenger/{test_id}")
        assert comp.status_code == 200
        assert comp.json()["test_id"] == test_id

        # Discard
        discard = requests.delete(f"{BASE_URL}/champion-challenger/{test_id}")
        assert discard.status_code == 200
        assert discard.json()["discarded"] is True

    def test_nonexistent_test(self):
        resp = requests.get(f"{BASE_URL}/champion-challenger/999999")
        assert resp.status_code == 200
        assert resp.json().get("error") == "Test not found"


# ── Simulation ─────────────────────────────────────────────────────

class TestSimulationAPI:

    def test_trace(self):
        resp = requests.post(f"{BASE_URL}/simulation/trace", json={
            "application_id": 1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "steps" in data
        assert "final_outcome" in data

    def test_trace_with_overrides(self):
        resp = requests.post(f"{BASE_URL}/simulation/trace", json={
            "application_id": 1,
            "overrides": {"monthly_income": 50000},
        })
        assert resp.status_code == 200

    def test_replay_empty(self):
        resp = requests.post(f"{BASE_URL}/simulation/replay", json={
            "application_ids": [],
        })
        assert resp.status_code == 200

    def test_impact_empty(self):
        resp = requests.post(f"{BASE_URL}/simulation/impact", json={
            "application_ids": [],
        })
        assert resp.status_code == 200


# ── Decision Explanation ───────────────────────────────────────────

class TestDecisionExplanationAPI:

    def test_nonexistent_decision(self):
        resp = requests.get(f"{BASE_URL}/decisions/999999/explanation")
        assert resp.status_code == 404
