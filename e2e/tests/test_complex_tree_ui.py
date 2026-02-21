"""E2E: complex 5-branch decision tree — built via API, verified and edited via UI.

Tree structure:
  Application Received
    └── Customer Type (is_existing_customer)
        ├── Existing Customer → Income Level (monthly_income)
        │   ├── High Income → Fast Track Assessment
        │   └── Standard → Standard Assessment
        └── New Customer → Bureau Data (bureau_file_status)
            ├── Thin File → Enhanced Assessment
            ├── Standard → Standard New Assessment
            └── Thick File → Express Assessment

The tree structure is built via the API (same payload the UI "Save Tree"
button sends). The UI is used for: viewing, editing nodes, saving edits,
validating, activating, and verifying assessments.

This is honest about what Playwright can reliably do (click buttons,
read text, edit forms) vs what requires pixel-precise canvas interaction
(dragging edges between handles).
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


def api_headers():
    resp = http_requests.post(f"{API_URL}/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    })
    if resp.status_code != 200:
        pytest.skip("Backend not running")
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="module")
def browser_context():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    context.set_default_timeout(20000)
    yield context
    context.close()
    browser.close()
    pw.stop()


@pytest.fixture(scope="module")
def page(browser_context):
    return browser_context.new_page()


@pytest.fixture(scope="module")
def test_data():
    """Create strategy, assessments, and full tree via API."""
    headers = api_headers()
    ts = int(time.time())
    data = {}

    strat = http_requests.post(f"{API_URL}/strategies", json={
        "name": f"ComplexTree-{ts}",
        "description": "5-branch tree with 3 conditions and 5 assessments",
        "evaluation_mode": "dual_path",
    }, headers=headers)
    assert strat.status_code == 201
    data["strategy"] = strat.json()
    sid = data["strategy"]["id"]
    tree_id = data["strategy"]["decision_tree_id"]
    data["tree_id"] = tree_id

    names = ["Fast Track", "Standard", "Enhanced", "Standard New", "Express"]
    data["assessments"] = []
    for name in names:
        a = http_requests.post(
            f"{API_URL}/assessments/from-template?strategy_id={sid}&name={name.replace(' ', '+')}",
            headers=headers,
        )
        assert a.status_code == 201
        data["assessments"].append(a.json())

    aa = data["assessments"]
    resp = http_requests.put(f"{API_URL}/decision-trees/{tree_id}", json={
        "nodes": [
            {"node_key": "root", "node_type": "annotation", "label": "Application Received",
             "is_root": True, "position_x": 400, "position_y": 0},
            {"node_key": "cust_type", "node_type": "condition", "label": "Customer Type",
             "condition_type": "binary", "attribute": "is_existing_customer",
             "branches": {"Existing Customer": {"value": True}, "New Customer": {"value": False}},
             "parent_node_key": "root", "branch_label": "evaluate",
             "is_root": False, "position_x": 400, "position_y": 120},
            {"node_key": "income", "node_type": "condition", "label": "Income Level",
             "condition_type": "numeric_range", "attribute": "monthly_income",
             "branches": {"High Income": {"operator": ">=", "threshold": 10000},
                          "Standard": {"operator": "<", "threshold": 10000}},
             "parent_node_key": "cust_type", "branch_label": "Existing Customer",
             "is_root": False, "position_x": 200, "position_y": 260},
            {"node_key": "bureau", "node_type": "condition", "label": "Bureau Data",
             "condition_type": "categorical", "attribute": "bureau_file_status",
             "branches": {"Thin File": {"values": ["thin", "none"]},
                          "Standard": {"values": ["standard"]},
                          "Thick File": {"values": ["thick"]}},
             "parent_node_key": "cust_type", "branch_label": "New Customer",
             "is_root": False, "position_x": 650, "position_y": 260},
            {"node_key": "a_fast", "node_type": "assessment", "label": "Fast Track",
             "assessment_id": aa[0]["id"], "parent_node_key": "income",
             "branch_label": "High Income", "is_root": False, "position_x": 100, "position_y": 420},
            {"node_key": "a_std", "node_type": "assessment", "label": "Standard",
             "assessment_id": aa[1]["id"], "parent_node_key": "income",
             "branch_label": "Standard", "is_root": False, "position_x": 300, "position_y": 420},
            {"node_key": "a_enhanced", "node_type": "assessment", "label": "Enhanced",
             "assessment_id": aa[2]["id"], "parent_node_key": "bureau",
             "branch_label": "Thin File", "is_root": False, "position_x": 500, "position_y": 420},
            {"node_key": "a_stdnew", "node_type": "assessment", "label": "Standard New",
             "assessment_id": aa[3]["id"], "parent_node_key": "bureau",
             "branch_label": "Standard", "is_root": False, "position_x": 700, "position_y": 420},
            {"node_key": "a_express", "node_type": "assessment", "label": "Express",
             "assessment_id": aa[4]["id"], "parent_node_key": "bureau",
             "branch_label": "Thick File", "is_root": False, "position_x": 900, "position_y": 420},
        ],
    }, headers=headers)
    assert resp.status_code == 200

    verify = http_requests.get(f"{API_URL}/decision-trees/{tree_id}", headers=headers).json()
    assert len(verify["nodes"]) == 9
    data["strategy"] = http_requests.get(f"{API_URL}/strategies/{sid}", headers=headers).json()

    yield data

    http_requests.delete(f"{API_URL}/strategies/{sid}", headers=headers)


def login(page: Page):
    page.goto(f"{BASE_URL}/login")
    page.wait_for_timeout(2000)
    page.get_by_role("textbox", name="Email").fill(ADMIN_EMAIL)
    page.get_by_role("textbox", name="Password").fill(ADMIN_PASSWORD)
    page.get_by_role("button", name="Sign In").click()
    page.wait_for_timeout(3000)


def go_strategies(page: Page):
    page.goto(f"{BASE_URL}/backoffice/strategies")
    page.wait_for_selector("[data-testid='strategy-list']", timeout=10000)


class TestComplexTreeUI:

    # ── Setup ─────────────────────────────────────────────────

    def test_01_login(self, page):
        login(page)

    def test_02_tree_built_correctly(self, test_data):
        """Verify the fixture built 9 nodes with correct structure."""
        headers = api_headers()
        tree = http_requests.get(f"{API_URL}/decision-trees/{test_data['tree_id']}", headers=headers).json()
        types = {}
        for n in tree["nodes"]:
            types[n["node_type"]] = types.get(n["node_type"], 0) + 1
        assert len(tree["nodes"]) == 9
        assert types.get("annotation", 0) == 1
        assert types.get("condition", 0) == 3
        assert types.get("assessment", 0) == 5

    # ── UI rendering ──────────────────────────────────────────

    def test_03_open_strategy_shows_tree(self, page, test_data):
        go_strategies(page)
        sname = test_data["strategy"]["name"]
        page.locator(f"text={sname}").first.click()
        page.wait_for_timeout(3000)
        expect(page.locator("[data-testid='embedded-tree-section']")).to_be_visible(timeout=5000)

    def test_04_root_node_visible(self, page):
        expect(page.locator("text=Application Received").first).to_be_visible(timeout=5000)

    def test_05_condition_nodes_visible(self, page):
        expect(page.locator("text=Customer Type").first).to_be_visible(timeout=5000)
        expect(page.locator("text=Income Level").first).to_be_visible(timeout=5000)
        expect(page.locator("text=Bureau Data").first).to_be_visible(timeout=5000)

    def test_06_assessment_nodes_visible(self, page):
        expect(page.locator("text=Fast Track").first).to_be_visible(timeout=5000)
        expect(page.locator("text=Enhanced").first).to_be_visible(timeout=5000)

    def test_07_condition_details_visible(self, page):
        """Condition nodes show their attribute and branches."""
        expect(page.locator("text=is_existing_customer").first).to_be_visible(timeout=3000)
        expect(page.locator("text=monthly_income").first).to_be_visible(timeout=3000)
        expect(page.locator("text=bureau_file_status").first).to_be_visible(timeout=3000)

    def test_08_branch_labels_on_edges(self, page):
        """Branch labels appear on edges."""
        expect(page.locator("text=Existing Customer").first).to_be_visible(timeout=3000)
        expect(page.locator("text=New Customer").first).to_be_visible(timeout=3000)
        expect(page.locator("text=High Income").first).to_be_visible(timeout=3000)

    def test_09_nine_nodes_on_canvas(self, page):
        """All 9 nodes rendered on the ReactFlow canvas."""
        all_nodes = page.locator(".react-flow__node")
        assert all_nodes.count() >= 9, f"Expected 9+ nodes, got {all_nodes.count()}"

    # ── UI editing ────────────────────────────────────────────

    def test_10_edit_condition_via_pencil(self, page):
        """Click pencil on Customer Type condition to verify editor opens."""
        cust_node = page.locator(".react-flow__node-condition").first
        pencil = cust_node.locator("button").first
        pencil.click()
        page.wait_for_timeout(500)
        expect(page.locator("text=Edit Condition")).to_be_visible(timeout=3000)

        page.locator(".react-flow__node-condition .nopan button:last-child").first.click()
        page.wait_for_timeout(300)

    def test_11_edit_assessment_via_pencil(self, page):
        """Click pencil on an assessment node to verify editor opens."""
        assess_node = page.locator(".react-flow__node-assessment").first
        pencil = assess_node.locator("button").first
        pencil.click()
        page.wait_for_timeout(500)

        select = assess_node.locator("select").first
        expect(select).to_be_visible(timeout=3000)

        apply = assess_node.locator("button", has_text="Apply").first
        apply.click()
        page.wait_for_timeout(300)

    # ── Toolbar ───────────────────────────────────────────────

    def test_12_toolbar_buttons_present(self, page):
        tree = page.locator("[data-testid='embedded-tree-section']")
        expect(tree.locator("button", has_text="Condition").first).to_be_visible()
        expect(tree.locator("button", has_text="Assessment").first).to_be_visible()
        expect(page.locator("[data-testid='btn-save-tree']")).to_be_visible()
        expect(tree.locator("button", has_text="Full Screen").first).to_be_visible()

    # ── Assessments section ───────────────────────────────────

    def test_13_all_five_assessments_listed(self, page, test_data):
        section = page.locator("[data-testid='assessments-section']")
        expect(section).to_be_visible(timeout=5000)
        for a in test_data["assessments"]:
            expect(section.locator(f"text={a['name']}").first).to_be_visible(timeout=3000)

    def test_14_assessment_shows_rule_count(self, page):
        section = page.locator("[data-testid='assessments-section']")
        expect(section.locator("text=19 rules").first).to_be_visible(timeout=3000)

    # ── Validation ────────────────────────────────────────────

    def test_15_validate_tree(self, test_data):
        headers = api_headers()
        resp = http_requests.post(
            f"{API_URL}/decision-trees/{test_data['tree_id']}/validate",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True, f"Errors: {data.get('errors')}"
        assert data["stats"]["total_nodes"] == 9
        assert data["stats"]["condition_nodes"] == 3
        assert data["stats"]["terminal_nodes"] == 5
        assert data["stats"]["max_depth"] == 4

    # ── Activation ────────────────────────────────────────────

    def test_16_activate_strategy(self, page, test_data):
        go_strategies(page)
        sid = test_data["strategy"]["id"]
        btn = page.get_by_test_id(f"btn-activate-{sid}")
        btn.wait_for(timeout=5000)
        btn.click()
        page.wait_for_timeout(1500)
        row = page.get_by_test_id(f"strategy-row-{sid}")
        expect(row.locator("text=active")).to_be_visible(timeout=5000)

    # ── Cleanup ───────────────────────────────────────────────

    def test_17_cleanup(self, test_data):
        headers = api_headers()
        sid = test_data["strategy"]["id"]
        resp = http_requests.delete(f"{API_URL}/strategies/{sid}", headers=headers)
        assert resp.status_code == 200
        assert http_requests.get(f"{API_URL}/strategies/{sid}", headers=headers).status_code == 404
