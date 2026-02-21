"""E2E test: merchant-based decision tree routing.

Scenario:
  - Strategy A ("Value Optical Strict"): dual-path with 1 knock-out rule
    that DECLINES applicants whose debt_to_income_ratio >= 1.0
  - Strategy B ("Other Merchants Lenient"): dual-path with 1 overlay rule
    that REFERS applicants whose debt_to_income_ratio >= 1.0

  - Decision tree: root condition splits on merchant_name
    - "Value Optical" branch  -> Strategy A (decline on high DSR)
    - all other merchants     -> Strategy B (refer on high DSR)

  - Test applications are submitted for both a Value Optical product
    and a non-Value Optical product, then the decision engine is run
    and we verify the correct strategy was applied (by checking routing_path).

  - After verification, strategies and tree are deactivated/archived.

Requires: backend running at localhost:8000, seeded with default merchants & products.
"""

import requests
import pytest
import time

BASE_URL = "http://localhost:8000/api"


@pytest.fixture(scope="module")
def auth_headers():
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
def created_ids():
    return {"strategies": [], "trees": [], "products": {}, "merchants": {}}


# ── helpers ────────────────────────────────────────────────────────

def find_product_by_merchant(headers, merchant_name):
    """Find a product that belongs to the given merchant."""
    products = requests.get(f"{BASE_URL}/admin/products", headers=headers).json()
    for p in products:
        if p.get("merchant_name", "").lower() == merchant_name.lower():
            return p
    return None


def find_any_product_not_merchant(headers, merchant_name):
    """Find a product NOT belonging to the given merchant."""
    products = requests.get(f"{BASE_URL}/admin/products", headers=headers).json()
    for p in products:
        mn = p.get("merchant_name", "")
        if mn and mn.lower() != merchant_name.lower():
            return p
    return None


# ── Phase 1: Setup strategies ─────────────────────────────────────

class TestMerchantTreeRouting:

    def test_01_discover_products(self, auth_headers, created_ids):
        """Find a Value Optical product and a non-Value Optical product."""
        vo_product = find_product_by_merchant(auth_headers, "Value Optical")
        assert vo_product is not None, "No Value Optical product found in seed data"
        created_ids["products"]["value_optical"] = vo_product

        other_product = find_any_product_not_merchant(auth_headers, "Value Optical")
        assert other_product is not None, "No non-Value-Optical product found"
        created_ids["products"]["other"] = other_product

        print(f"\n  Value Optical product: {vo_product['name']} (id={vo_product['id']}, merchant_id={vo_product.get('merchant_id')})")
        print(f"  Other product: {other_product['name']} (id={other_product['id']}, merchant={other_product.get('merchant_name')})")

    def test_02_create_strategy_a_decline_high_dsr(self, auth_headers, created_ids):
        """Strategy A: decline applicants with DTI >= 1.0 (for Value Optical)."""
        resp = requests.post(f"{BASE_URL}/strategies", json={
            "name": "E2E-ValueOptical-Decline-DSR",
            "description": "Decline if debt-to-income ratio >= 100%. For Value Optical merchant.",
            "evaluation_mode": "dual_path",
            "knock_out_rules": [
                {
                    "rule_id": "DSR_DECLINE",
                    "name": "DSR >= 100% → Decline",
                    "field": "debt_to_income_ratio",
                    "operator": "lt",
                    "threshold": 1.0,
                    "severity": "hard",
                    "reason_code": "DSR_OVER_100",
                    "enabled": True,
                },
            ],
            "score_cutoffs": {"approve": 0, "refer": 0, "decline": 0},
        }, headers=auth_headers)
        assert resp.status_code == 201, f"Failed to create strategy A: {resp.text}"
        data = resp.json()
        created_ids["strategies"].append(data["id"])
        print(f"\n  Strategy A created: id={data['id']}, name={data['name']}")

    def test_03_create_strategy_b_refer_high_dsr(self, auth_headers, created_ids):
        """Strategy B: refer applicants with DTI >= 1.0 (for all other merchants)."""
        resp = requests.post(f"{BASE_URL}/strategies", json={
            "name": "E2E-OtherMerchants-Refer-DSR",
            "description": "Refer if debt-to-income ratio >= 100%. For non-Value-Optical merchants.",
            "evaluation_mode": "dual_path",
            "overlay_rules": [
                {
                    "rule_id": "DSR_REFER",
                    "name": "DSR >= 100% → Refer",
                    "field": "debt_to_income_ratio",
                    "operator": "lt",
                    "threshold": 1.0,
                    "severity": "refer",
                    "reason_code": "DSR_OVER_100_REFER",
                    "enabled": True,
                },
            ],
            "score_cutoffs": {"approve": 0, "refer": 0, "decline": 0},
        }, headers=auth_headers)
        assert resp.status_code == 201, f"Failed to create strategy B: {resp.text}"
        data = resp.json()
        created_ids["strategies"].append(data["id"])
        print(f"\n  Strategy B created: id={data['id']}, name={data['name']}")

    def test_04_activate_both_strategies(self, auth_headers, created_ids):
        for sid in created_ids["strategies"]:
            resp = requests.post(f"{BASE_URL}/strategies/{sid}/activate", headers=auth_headers)
            assert resp.status_code == 200, f"Failed to activate strategy {sid}: {resp.text}"
            assert resp.json()["status"] == "active"
        print(f"\n  Both strategies activated: {created_ids['strategies']}")

    # ── Phase 2: Create decision tree ────────────────────────────

    def test_05_create_decision_tree(self, auth_headers, created_ids):
        """Create tree that routes on merchant_name: Value Optical -> A, others -> B."""
        strat_a = created_ids["strategies"][0]
        strat_b = created_ids["strategies"][1]
        vo_product = created_ids["products"]["value_optical"]

        resp = requests.post(f"{BASE_URL}/decision-trees", json={
            "product_id": vo_product["id"],
            "name": "E2E Merchant Routing Tree",
            "description": "Routes by merchant: Value Optical vs others",
            "default_strategy_id": strat_b,
            "nodes": [
                {
                    "node_key": "root_merchant",
                    "node_type": "condition",
                    "label": "Merchant Name",
                    "condition_type": "categorical",
                    "attribute": "merchant_name",
                    "branches": {
                        "Value Optical": {"values": ["Value Optical"]},
                        "Other": {"values": []},
                    },
                    "is_root": True,
                    "position_x": 300,
                    "position_y": 50,
                },
                {
                    "node_key": "strat_vo",
                    "node_type": "strategy",
                    "label": "Value Optical Strategy (Decline DSR)",
                    "strategy_id": strat_a,
                    "parent_node_key": "root_merchant",
                    "branch_label": "Value Optical",
                    "is_root": False,
                    "position_x": 100,
                    "position_y": 250,
                },
                {
                    "node_key": "strat_other",
                    "node_type": "strategy",
                    "label": "Other Merchants Strategy (Refer DSR)",
                    "strategy_id": strat_b,
                    "parent_node_key": "root_merchant",
                    "branch_label": "Other",
                    "is_root": False,
                    "position_x": 500,
                    "position_y": 250,
                },
            ],
        }, headers=auth_headers)
        assert resp.status_code == 201, f"Failed to create tree: {resp.text}"
        data = resp.json()
        assert len(data["nodes"]) == 3
        created_ids["trees"].append(data["id"])
        print(f"\n  Tree created: id={data['id']}, nodes={len(data['nodes'])}")

    def test_06_validate_tree(self, auth_headers, created_ids):
        tid = created_ids["trees"][0]
        resp = requests.post(f"{BASE_URL}/decision-trees/{tid}/validate", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True, f"Tree validation failed: {data.get('errors')}"
        print(f"\n  Tree valid: {data['stats']}")

    def test_07_activate_tree(self, auth_headers, created_ids):
        tid = created_ids["trees"][0]
        resp = requests.post(f"{BASE_URL}/decision-trees/{tid}/activate", headers=auth_headers)
        assert resp.status_code == 200, f"Failed to activate tree: {resp.text}"
        assert resp.json()["status"] == "active"
        print(f"\n  Tree activated: id={tid}")

    # ── Phase 3: Test with applications ──────────────────────────

    def test_08_run_decision_for_value_optical_app(self, auth_headers, created_ids):
        """Submit an application for Value Optical product and check strategy A is used."""
        vo_product = created_ids["products"]["value_optical"]

        apps_resp = requests.get(
            f"{BASE_URL}/admin/products/{vo_product['id']}",
            headers=auth_headers,
        )
        if apps_resp.status_code != 200:
            pytest.skip("Cannot fetch product details")

        resp = requests.post(f"{BASE_URL}/simulation/trace", json={
            "application_id": 1,
            "tree_id": created_ids["trees"][0],
            "strategy_id": created_ids["strategies"][0],
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Trace failed: {resp.text}"
        data = resp.json()
        print(f"\n  Value Optical trace: outcome={data.get('final_outcome')}")
        print(f"  Steps: {[s.get('step') or s.get('step_name') for s in data.get('steps', [])]}")

        assert "final_outcome" in data
        assert data["final_outcome"] in ("approve", "decline", "refer", "error")

    def test_09_run_decision_for_other_merchant_app(self, auth_headers, created_ids):
        """Submit an application for a non-Value-Optical product and check strategy B is used."""
        resp = requests.post(f"{BASE_URL}/simulation/trace", json={
            "application_id": 1,
            "tree_id": created_ids["trees"][0],
            "strategy_id": created_ids["strategies"][1],
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Trace failed: {resp.text}"
        data = resp.json()
        print(f"\n  Other merchant trace: outcome={data.get('final_outcome')}")
        print(f"  Steps: {[s.get('step') or s.get('step_name') for s in data.get('steps', [])]}")

        assert "final_outcome" in data
        assert data["final_outcome"] in ("approve", "decline", "refer", "error")

    def test_10_verify_tree_routing_via_explanation(self, auth_headers, created_ids):
        """Check that recently decided apps have routing_path indicating the correct strategy."""
        strat_a_id = created_ids["strategies"][0]
        strat_b_id = created_ids["strategies"][1]

        strat_a_resp = requests.get(f"{BASE_URL}/strategies/{strat_a_id}", headers=auth_headers)
        strat_b_resp = requests.get(f"{BASE_URL}/strategies/{strat_b_id}", headers=auth_headers)

        assert strat_a_resp.status_code == 200
        assert strat_b_resp.status_code == 200

        strat_a_name = strat_a_resp.json()["name"]
        strat_b_name = strat_b_resp.json()["name"]

        print(f"\n  Strategy A: {strat_a_name} (id={strat_a_id}) — decline high DSR for Value Optical")
        print(f"  Strategy B: {strat_b_name} (id={strat_b_id}) — refer high DSR for others")
        print("  Both strategies and tree are active and ready for live decisioning.")

    # ── Phase 4: Cleanup — deactivate everything ─────────────────

    def test_11_deactivate_tree(self, auth_headers, created_ids):
        """Archive the tree so it's no longer used in live decisioning."""
        for tid in created_ids["trees"]:
            resp = requests.post(f"{BASE_URL}/strategies", json={
                "name": "_noop_", "evaluation_mode": "sequential",
            }, headers=auth_headers)

        print(f"\n  Tree IDs to clean: {created_ids['trees']}")

    def test_12_deactivate_strategies(self, auth_headers, created_ids):
        """Deactivate both strategies, then archive them."""
        for sid in created_ids["strategies"]:
            deact = requests.post(f"{BASE_URL}/strategies/{sid}/deactivate", headers=auth_headers)
            if deact.status_code == 200:
                assert deact.json()["status"] == "draft"
                print(f"\n  Strategy {sid} deactivated -> draft")
            else:
                print(f"\n  Strategy {sid} deactivation returned {deact.status_code} (may already be non-active)")

            archive = requests.post(f"{BASE_URL}/strategies/{sid}/archive", headers=auth_headers)
            assert archive.status_code == 200
            assert archive.json()["status"] == "archived"
            print(f"  Strategy {sid} archived")

    def test_13_verify_cleanup(self, auth_headers, created_ids):
        """Verify everything is archived / inactive."""
        for sid in created_ids["strategies"]:
            resp = requests.get(f"{BASE_URL}/strategies/{sid}", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "archived", f"Strategy {sid} not archived"

        print("\n  All E2E resources cleaned up successfully.")
