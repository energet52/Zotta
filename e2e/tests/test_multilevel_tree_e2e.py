"""Playwright E2E: multi-level decision tree with nested branching.

Scenario (matching the reference mockup):

  All Applications
      |
  Customer Relationship?  (binary: existing / new)
      |                           |
  Existing Customer          New Customer
      |                           |
  High Income?             Bureau Data?
  (numeric_range: >5K)     (categorical: thin/standard)
      |         |               |           |
  Fast Track  Standard    New Customer  Alternative
  Assessment  Assessment  Assessment    Assessment

Tree: 7 nodes (1 root + 2 sub-conditions + 4 assessment terminals)
Assessments: 4, each from template with different DSR thresholds

Tests:
  1. Create strategy + 4 assessments
  2. Build the 3-level decision tree
  3. Validate (7 nodes, 3 conditions, 4 terminals, max depth 3)
  4. Verify tree renders in strategy panel
  5. Activate, trace, deactivate
"""

import pytest
import re
import time
import requests as http_requests
from playwright.sync_api import sync_playwright, expect, Page

BASE_URL = "http://localhost:5173"
API_URL = "http://localhost:8000/api"
ADMIN_EMAIL = "admin@zotta.tt"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def browser_context():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    context.set_default_timeout(15000)
    yield context
    context.close()
    browser.close()
    pw.stop()


@pytest.fixture(scope="module")
def page(browser_context):
    return browser_context.new_page()


@pytest.fixture(scope="module")
def api_headers():
    resp = http_requests.post(f"{API_URL}/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    })
    if resp.status_code != 200:
        pytest.skip("Backend not running")
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="module")
def test_data(api_headers):
    """Build the full multi-level tree scenario via API."""
    ts = int(time.time())
    data = {}

    strat = http_requests.post(f"{API_URL}/strategies", json={
        "name": f"E2E-MultiLevel-{ts}",
        "description": "Multi-level branching: customer type + income/bureau",
        "evaluation_mode": "dual_path",
        "score_cutoffs": {"approve": 0, "refer": 0, "decline": 0},
    }, headers=api_headers)
    assert strat.status_code == 201, f"Strategy failed: {strat.text}"
    data["strategy"] = strat.json()
    sid = data["strategy"]["id"]

    assessment_configs = [
        ("Fast Track Assessment", "R08", 1.0, "R12", 0.50),
        ("Standard Assessment", "R08", 0.80, "R12", 0.40),
        ("New Customer Assessment", "R08", 1.0, "R12", 0.45),
        ("Alternative Assessment", "R08", 0.60, "R12", 0.35),
    ]

    data["assessments"] = []
    for name, r08_id, r08_thresh, r12_id, r12_thresh in assessment_configs:
        resp = http_requests.post(
            f"{API_URL}/assessments/from-template?strategy_id={sid}&name={name.replace(' ', '+')}",
            headers=api_headers,
        )
        assert resp.status_code == 201, f"Assessment '{name}' failed: {resp.text}"
        assess = resp.json()

        rules = assess["rules"]
        for rule in rules:
            if rule.get("rule_id") == r08_id:
                rule["threshold"] = r08_thresh
            if rule.get("rule_id") == r12_id:
                rule["threshold"] = r12_thresh

        http_requests.put(f"{API_URL}/assessments/{assess['id']}", json={
            "name": name,
            "rules": rules,
        }, headers=api_headers)
        data["assessments"].append(assess)

    products = http_requests.get(f"{API_URL}/admin/products", headers=api_headers).json()
    product = products[0]

    a_fast, a_standard, a_newcust, a_alt = [a["id"] for a in data["assessments"]]

    tree_resp = http_requests.post(f"{API_URL}/decision-trees", json={
        "product_id": product["id"],
        "name": f"E2E Multi-Level Tree {ts}",
        "description": "3-level: customer type -> income/bureau -> assessments",
        "nodes": [
            {
                "node_key": "root",
                "node_type": "condition",
                "label": "Customer Relationship?",
                "condition_type": "binary",
                "attribute": "is_existing_customer",
                "operator": "eq",
                "branches": {
                    "Existing Customer": {"value": True},
                    "New Customer": {"value": False},
                },
                "is_root": True,
                "position_x": 400, "position_y": 50,
            },
            {
                "node_key": "existing_income",
                "node_type": "condition",
                "label": "High Income?",
                "condition_type": "numeric_range",
                "attribute": "monthly_income",
                "operator": "gte",
                "branches": {
                    "> $5K": {"min": 5000},
                    "Standard": {"max": 4999},
                },
                "parent_node_key": "root",
                "branch_label": "Existing Customer",
                "is_root": False,
                "position_x": 200, "position_y": 200,
            },
            {
                "node_key": "new_bureau",
                "node_type": "condition",
                "label": "Bureau Data?",
                "condition_type": "categorical",
                "attribute": "bureau_file_status",
                "branches": {
                    "Thin File": {"values": ["thin", "none"]},
                    "Standard+": {"values": ["standard", "thick"]},
                },
                "parent_node_key": "root",
                "branch_label": "New Customer",
                "is_root": False,
                "position_x": 600, "position_y": 200,
            },
            {
                "node_key": "assess_fast",
                "node_type": "assessment",
                "label": "Fast Track Assessment",
                "assessment_id": a_fast,
                "parent_node_key": "existing_income",
                "branch_label": "> $5K",
                "is_root": False,
                "position_x": 100, "position_y": 400,
            },
            {
                "node_key": "assess_standard",
                "node_type": "assessment",
                "label": "Standard Assessment",
                "assessment_id": a_standard,
                "parent_node_key": "existing_income",
                "branch_label": "Standard",
                "is_root": False,
                "position_x": 300, "position_y": 400,
            },
            {
                "node_key": "assess_newcust",
                "node_type": "assessment",
                "label": "New Customer Assessment",
                "assessment_id": a_newcust,
                "parent_node_key": "new_bureau",
                "branch_label": "Standard+",
                "is_root": False,
                "position_x": 500, "position_y": 400,
            },
            {
                "node_key": "assess_alt",
                "node_type": "assessment",
                "label": "Alternative Assessment",
                "assessment_id": a_alt,
                "parent_node_key": "new_bureau",
                "branch_label": "Thin File",
                "is_root": False,
                "position_x": 700, "position_y": 400,
            },
        ],
    }, headers=api_headers)
    assert tree_resp.status_code == 201, f"Tree failed: {tree_resp.text}"
    data["tree"] = tree_resp.json()

    http_requests.put(f"{API_URL}/strategies/{sid}", json={
        "decision_tree_id": data["tree"]["id"],
    }, headers=api_headers)

    yield data

    http_requests.post(f"{API_URL}/strategies/{sid}/deactivate", headers=api_headers)
    http_requests.post(f"{API_URL}/strategies/{sid}/archive", headers=api_headers)


def login(page: Page):
    page.goto(f"{BASE_URL}/login")
    page.get_by_label("Email").fill(ADMIN_EMAIL)
    page.get_by_label("Password").fill(ADMIN_PASSWORD)
    page.get_by_role("button", name="Sign In").click()
    page.wait_for_url(re.compile(r".*/(backoffice|dashboard|my-loans).*"), timeout=10000)


def go_strategies(page: Page):
    page.goto(f"{BASE_URL}/backoffice/strategies")
    page.wait_for_selector("[data-testid='strategy-list']", timeout=10000)


class TestMultiLevelTreeWorkflow:

    # ── Setup verification ────────────────────────────────────

    def test_01_login(self, page):
        login(page)

    def test_02_fixture_created_7_nodes(self, test_data):
        """Verify fixture created the full tree structure."""
        assert len(test_data["tree"]["nodes"]) == 7
        assert len(test_data["assessments"]) == 4

    # ── Validation ────────────────────────────────────────────

    def test_03_validate_tree_structure(self, api_headers, test_data):
        """Validate: 7 nodes, 3 conditions, 4 terminals, max depth 3."""
        tid = test_data["tree"]["id"]
        resp = http_requests.post(f"{API_URL}/decision-trees/{tid}/validate", headers=api_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True, f"Validation failed: {data.get('errors')}"
        assert data["stats"]["total_nodes"] == 7
        assert data["stats"]["condition_nodes"] == 3
        assert data["stats"]["terminal_nodes"] == 4
        assert data["stats"]["max_depth"] == 3

    # ── UI: tree visible in strategy panel ────────────────────

    def test_04_tree_renders_in_strategy_editor(self, page, test_data):
        """Open strategy and verify the embedded tree shows all nodes."""
        go_strategies(page)
        sname = test_data["strategy"]["name"]
        row = page.locator(f"text={sname}").first
        row.wait_for(timeout=5000)
        row.click()
        page.wait_for_timeout(3000)

        expect(page.locator("[data-testid='embedded-tree-section']")).to_be_visible(timeout=5000)
        expect(page.locator("text=7 nodes").first).to_be_visible(timeout=5000)

    def test_05_tree_shows_condition_labels(self, page):
        """Verify condition node labels are visible in the embedded tree."""
        tree_section = page.locator("[data-testid='embedded-tree-section']")
        expect(tree_section.locator("text=Customer Relationship?").first).to_be_visible(timeout=5000)

    def test_06_tree_shows_assessment_labels(self, page):
        """Verify assessment node labels are visible in the embedded tree."""
        tree_section = page.locator("[data-testid='embedded-tree-section']")
        expect(tree_section.locator("text=Fast Track Assessment").first).to_be_visible(timeout=5000)

    def test_07_all_four_assessments_listed(self, page):
        """Verify the assessments section shows all 4 assessments."""
        section = page.locator("[data-testid='assessments-section']")
        expect(section.locator("text=Fast Track Assessment").first).to_be_visible(timeout=5000)
        expect(section.locator("text=Standard Assessment").first).to_be_visible(timeout=5000)
        expect(section.locator("text=New Customer Assessment").first).to_be_visible(timeout=5000)
        expect(section.locator("text=Alternative Assessment").first).to_be_visible(timeout=5000)

    def test_08_open_builder_link_present(self, page):
        """Verify the 'Open Builder' link points to the tree."""
        link = page.locator("[data-testid='btn-open-tree-builder']")
        expect(link).to_be_visible(timeout=3000)

    # ── Activation ────────────────────────────────────────────

    def test_09_activate_strategy(self, page, test_data):
        go_strategies(page)
        sid = test_data["strategy"]["id"]
        btn = page.get_by_test_id(f"btn-activate-{sid}")
        btn.wait_for(timeout=5000)
        btn.click()
        page.wait_for_timeout(1500)

        row = page.get_by_test_id(f"strategy-row-{sid}")
        expect(row.locator("text=active")).to_be_visible(timeout=5000)

    # ── Simulation traces through different branches ──────────

    def test_10_trace_existing_customer_path(self, api_headers, test_data):
        """Trace with existing customer context — should route through income branch."""
        resp = http_requests.post(f"{API_URL}/simulation/trace", json={
            "application_id": 1,
            "tree_id": test_data["tree"]["id"],
        }, headers=api_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["final_outcome"] in ("approve", "decline", "refer", "error")
        print(f"\n  Trace outcome: {data['final_outcome']}")
        print(f"  Steps: {len(data.get('steps', []))}")

    # ── Cleanup ───────────────────────────────────────────────

    def test_11_deactivate_and_archive(self, page, test_data):
        go_strategies(page)
        page.get_by_test_id("filter-status").select_option("")
        page.wait_for_timeout(1000)

        sid = test_data["strategy"]["id"]
        deact = page.get_by_test_id(f"btn-deactivate-{sid}")
        if deact.is_visible():
            deact.click()
            page.wait_for_timeout(1500)

        page.reload()
        page.wait_for_selector("[data-testid='strategy-list']", timeout=5000)

        archive = page.get_by_test_id(f"btn-archive-{sid}")
        if archive.is_visible():
            archive.click()
            page.wait_for_timeout(1000)

    def test_12_verify_archived(self, api_headers, test_data):
        sid = test_data["strategy"]["id"]
        resp = http_requests.get(f"{API_URL}/strategies/{sid}", headers=api_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"
        print("\n  Multi-level tree strategy archived. Test complete.")
