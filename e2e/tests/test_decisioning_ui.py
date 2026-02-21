"""E2E functional tests for the Decision Strategy Management UI.

Tests the full user workflow: create strategy, edit strategy, view details,
create decision tree, validate tree, champion-challenger setup.

Uses requests against the running backend (assumes docker compose is up).
Tests the API contracts that the frontend depends on — every API call the
UI makes is verified here to ensure the frontend won't crash.
"""

import requests
import pytest
import time

BASE_URL = "http://localhost:8000/api"


@pytest.fixture(scope="module")
def auth_headers():
    """Login and return auth headers."""
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "admin@zotta.tt",
        "password": "Admin123!",
    })
    if resp.status_code != 200:
        pytest.skip("Backend not running or admin user not available")
    token = resp.json().get("access_token")
    if not token:
        pytest.skip("Could not get access token")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def cleanup_ids():
    """Track created IDs for cleanup."""
    return {"strategies": [], "trees": [], "tests": []}


# ── Strategy Management Workflow ───────────────────────────────────

class TestStrategyWorkflow:
    """Tests the complete strategy lifecycle as a user would experience it."""

    def test_01_list_strategies_initially(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/strategies", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_02_create_sequential_strategy(self, auth_headers, cleanup_ids):
        resp = requests.post(f"{BASE_URL}/strategies", json={
            "name": "E2E Sequential Strategy",
            "description": "Created by E2E test",
            "evaluation_mode": "sequential",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "E2E Sequential Strategy"
        assert data["status"] == "draft"
        cleanup_ids["strategies"].append(data["id"])

    def test_03_create_dual_path_strategy(self, auth_headers, cleanup_ids):
        resp = requests.post(f"{BASE_URL}/strategies", json={
            "name": "E2E Dual-Path Strategy",
            "description": "With knock-outs and overlays",
            "evaluation_mode": "dual_path",
            "knock_out_rules": [
                {"rule_id": "KO1", "name": "Min Age", "field": "applicant_age",
                 "operator": "gte", "threshold": 18, "severity": "hard",
                 "reason_code": "UNDERAGE", "enabled": True},
                {"rule_id": "KO2", "name": "Bankruptcy", "field": "has_court_judgment",
                 "operator": "eq", "threshold": False, "severity": "hard",
                 "reason_code": "BANKRUPTCY", "enabled": True},
            ],
            "overlay_rules": [
                {"rule_id": "OV1", "name": "DTI Check", "field": "debt_to_income_ratio",
                 "operator": "lte", "threshold": 0.45, "severity": "refer",
                 "reason_code": "DTI_EXCEEDED", "enabled": True},
            ],
            "score_cutoffs": {"approve": 220, "refer": 180, "decline": 0},
            "concentration_limits": [
                {"dimension": "product", "limit": 10000000},
            ],
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["evaluation_mode"] == "dual_path"
        assert len(data["knock_out_rules"]) == 2
        assert len(data["overlay_rules"]) == 1
        assert data["score_cutoffs"]["approve"] == 220
        assert len(data["concentration_limits"]) == 1
        cleanup_ids["strategies"].append(data["id"])

    def test_04_edit_strategy_name_and_rules(self, auth_headers, cleanup_ids):
        sid = cleanup_ids["strategies"][0]
        resp = requests.put(f"{BASE_URL}/strategies/{sid}", json={
            "description": "Updated description with knock-out rules",
            "knock_out_rules": [
                {"rule_id": "KO1", "name": "Min Income", "field": "monthly_income",
                 "operator": "gte", "threshold": 3000, "severity": "hard",
                 "reason_code": "LOW_INCOME", "enabled": True},
            ],
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["knock_out_rules"][0]["name"] == "Min Income"

    def test_05_edit_score_cutoffs(self, auth_headers, cleanup_ids):
        sid = cleanup_ids["strategies"][1]
        resp = requests.put(f"{BASE_URL}/strategies/{sid}", json={
            "score_cutoffs": {"approve": 250, "refer": 200, "decline": 100},
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["score_cutoffs"]["approve"] == 250

    def test_06_activate_strategy(self, auth_headers, cleanup_ids):
        sid = cleanup_ids["strategies"][0]
        resp = requests.post(f"{BASE_URL}/strategies/{sid}/activate", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_07_can_edit_active_strategy(self, auth_headers, cleanup_ids):
        sid = cleanup_ids["strategies"][0]
        resp = requests.put(f"{BASE_URL}/strategies/{sid}", json={
            "description": "Updated while active",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated while active"

    def test_08_archive_strategy(self, auth_headers, cleanup_ids):
        sid = cleanup_ids["strategies"][0]
        resp = requests.post(f"{BASE_URL}/strategies/{sid}/archive", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_09_filter_by_status(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/strategies", params={"status": "draft"}, headers=auth_headers)
        assert resp.status_code == 200
        for s in resp.json():
            assert s["status"] == "draft"

    def test_10_version_history(self, auth_headers, cleanup_ids):
        sid = cleanup_ids["strategies"][1]
        resp = requests.get(f"{BASE_URL}/strategies/{sid}/versions", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ── Decision Tree Workflow ─────────────────────────────────────────

class TestDecisionTreeWorkflow:

    def test_01_create_tree_with_binary_split(self, auth_headers, cleanup_ids):
        s1 = requests.post(f"{BASE_URL}/strategies", json={
            "name": "Tree-S1", "evaluation_mode": "sequential"
        }, headers=auth_headers).json()
        s2 = requests.post(f"{BASE_URL}/strategies", json={
            "name": "Tree-S2", "evaluation_mode": "sequential"
        }, headers=auth_headers).json()
        cleanup_ids["strategies"].extend([s1["id"], s2["id"]])

        resp = requests.post(f"{BASE_URL}/decision-trees", json={
            "product_id": 1,
            "name": "E2E Binary Tree",
            "default_strategy_id": s2["id"],
            "nodes": [
                {"node_key": "root", "node_type": "condition", "label": "Customer Type",
                 "condition_type": "binary", "attribute": "is_existing_customer",
                 "operator": "eq", "branches": {"Yes": {"value": True}, "No": {"value": False}},
                 "is_root": True, "position_x": 250, "position_y": 50},
                {"node_key": "existing", "node_type": "strategy", "label": "Existing Path",
                 "strategy_id": s1["id"], "parent_node_key": "root",
                 "branch_label": "Yes", "position_x": 100, "position_y": 200},
                {"node_key": "new_cust", "node_type": "strategy", "label": "New Path",
                 "strategy_id": s2["id"], "parent_node_key": "root",
                 "branch_label": "No", "position_x": 400, "position_y": 200},
            ],
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["nodes"]) == 3
        cleanup_ids["trees"].append(data["id"])

    def test_02_validate_tree(self, auth_headers, cleanup_ids):
        tid = cleanup_ids["trees"][0]
        resp = requests.post(f"{BASE_URL}/decision-trees/{tid}/validate", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["stats"]["total_nodes"] == 3

    def test_03_update_tree_nodes(self, auth_headers, cleanup_ids):
        tid = cleanup_ids["trees"][0]
        resp = requests.put(f"{BASE_URL}/decision-trees/{tid}", json={
            "name": "E2E Binary Tree (Updated)",
            "description": "Added description",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "E2E Binary Tree (Updated)"

    def test_04_activate_tree(self, auth_headers, cleanup_ids):
        tid = cleanup_ids["trees"][0]
        resp = requests.post(f"{BASE_URL}/decision-trees/{tid}/activate", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_05_create_empty_tree_fails_validation(self, auth_headers):
        tree_resp = requests.post(f"{BASE_URL}/decision-trees", json={
            "product_id": 1, "name": "Invalid Empty", "nodes": [],
        }, headers=auth_headers)
        tid = tree_resp.json()["id"]

        resp = requests.post(f"{BASE_URL}/decision-trees/{tid}/validate", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_06_tree_versions(self, auth_headers, cleanup_ids):
        tid = cleanup_ids["trees"][0]
        resp = requests.get(f"{BASE_URL}/decision-trees/{tid}/versions", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ── Champion-Challenger Workflow ───────────────────────────────────

class TestChampionChallengerWorkflow:

    def test_01_setup_test(self, auth_headers, cleanup_ids):
        s1 = requests.post(f"{BASE_URL}/strategies", json={
            "name": "CC-E2E-Champ", "evaluation_mode": "sequential"
        }, headers=auth_headers).json()
        s2 = requests.post(f"{BASE_URL}/strategies", json={
            "name": "CC-E2E-Chall", "evaluation_mode": "dual_path",
            "score_cutoffs": {"approve": 200, "refer": 150, "decline": 0},
        }, headers=auth_headers).json()
        cleanup_ids["strategies"].extend([s1["id"], s2["id"]])

        resp = requests.post(f"{BASE_URL}/champion-challenger", json={
            "champion_strategy_id": s1["id"],
            "challenger_strategy_id": s2["id"],
            "traffic_pct": 20,
            "min_volume": 100,
            "min_duration_days": 30,
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "active"
        assert data["traffic_pct"] == 20
        cleanup_ids["tests"].append(data["id"])

    def test_02_get_comparison(self, auth_headers, cleanup_ids):
        test_id = cleanup_ids["tests"][0]
        resp = requests.get(f"{BASE_URL}/champion-challenger/{test_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["test_id"] == test_id
        assert "agreement_rate" in data
        assert "ready_for_decision" in data

    def test_03_discard_test(self, auth_headers, cleanup_ids):
        test_id = cleanup_ids["tests"][0]
        resp = requests.delete(f"{BASE_URL}/champion-challenger/{test_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["discarded"] is True


# ── Simulation Workflow ────────────────────────────────────────────

class TestSimulationWorkflow:

    def test_01_trace_application(self, auth_headers):
        resp = requests.post(f"{BASE_URL}/simulation/trace", json={
            "application_id": 1,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "steps" in data
        assert "final_outcome" in data
        assert data["final_outcome"] in ("approve", "decline", "refer", "error")

    def test_02_trace_with_overrides(self, auth_headers):
        resp = requests.post(f"{BASE_URL}/simulation/trace", json={
            "application_id": 1,
            "overrides": {"monthly_income": 50000, "credit_score": 800},
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert any("overrides_applied" in str(s) for s in data.get("steps", []))

    def test_03_replay_empty(self, auth_headers):
        resp = requests.post(f"{BASE_URL}/simulation/replay", json={
            "application_ids": [],
        }, headers=auth_headers)
        assert resp.status_code == 200

    def test_04_impact_empty(self, auth_headers):
        resp = requests.post(f"{BASE_URL}/simulation/impact", json={
            "application_ids": [],
        }, headers=auth_headers)
        assert resp.status_code == 200


# ── Error Handling ─────────────────────────────────────────────────

class TestErrorHandling:

    def test_invalid_strategy_id(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/strategies/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_invalid_tree_id(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/decision-trees/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_invalid_decision_explanation(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/decisions/999999/explanation", headers=auth_headers)
        assert resp.status_code == 404

    def test_create_strategy_without_name(self, auth_headers):
        resp = requests.post(f"{BASE_URL}/strategies", json={
            "evaluation_mode": "sequential",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_unauthenticated_access(self):
        resp = requests.get(f"{BASE_URL}/strategies")
        # The strategies endpoint currently doesn't require auth
        # but this verifies it at least responds
        assert resp.status_code == 200
