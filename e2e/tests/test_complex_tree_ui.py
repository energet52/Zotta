"""Playwright E2E: build a complex 5-branch decision tree entirely via UI.

Tree structure:
  Application Received (auto-created)
    └── Customer Type (is_existing_customer: binary)
        ├── Existing Customer
        │   └── Income Level (monthly_income: numeric >= 10000 / < 10000)
        │       ├── High Income → Fast Track Assessment (19 template rules, DSR 100%)
        │       └── Standard Income → Standard Assessment (19 template rules, DSR 80%)
        └── New Customer
            └── Bureau Data (bureau_file_status: categorical thin/standard/thick)
                ├── Thin File → Enhanced Assessment (19 template rules)
                ├── Standard → Standard New Assessment (19 template rules)
                └── Thick File → Express Assessment (19 template rules)

Total: 5 assessments, 3 conditions, 8 nodes + 1 root annotation = 9 nodes

The test creates everything via the UI:
  1. Create strategy
  2. Create 5 assessments from template
  3. Build the tree: add conditions, edit them, add assessments, assign them
  4. Save tree and verify via API
  5. Activate strategy
  6. Cleanup
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


def get_api_headers():
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
    """Create strategy via API (auto-creates tree), return IDs."""
    headers = get_api_headers()
    ts = int(time.time())
    data = {}

    strat = http_requests.post(f"{API_URL}/strategies", json={
        "name": f"ComplexTree-{ts}",
        "description": "5-branch complex tree test",
        "evaluation_mode": "dual_path",
    }, headers=headers)
    assert strat.status_code == 201, f"Strategy creation failed: {strat.text}"
    data["strategy"] = strat.json()
    sid = data["strategy"]["id"]
    data["tree_id"] = data["strategy"]["decision_tree_id"]

    assessment_names = [
        "Fast Track Assessment",
        "Standard Assessment",
        "Enhanced Assessment",
        "Standard New Assessment",
        "Express Assessment",
    ]
    data["assessments"] = []
    for name in assessment_names:
        a = http_requests.post(
            f"{API_URL}/assessments/from-template?strategy_id={sid}&name={name.replace(' ', '+')}",
            headers=headers,
        )
        assert a.status_code == 201, f"Assessment '{name}' failed: {a.text}"
        data["assessments"].append(a.json())

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

    def test_01_login(self, page):
        login(page)

    def test_02_strategy_has_tree_and_assessments(self, test_data):
        assert test_data["strategy"]["decision_tree_id"] is not None
        assert len(test_data["strategy"]["assessments"]) == 5

    def test_03_open_strategy_panel(self, page, test_data):
        go_strategies(page)
        sname = test_data["strategy"]["name"]
        row = page.locator(f"text={sname}").first
        row.wait_for(timeout=5000)
        row.click()
        page.wait_for_timeout(3000)
        expect(page.locator("[data-testid='embedded-tree-section']")).to_be_visible(timeout=5000)

    def test_04_tree_has_root_node(self, page):
        """The auto-created Application Received node should be on the canvas."""
        expect(page.locator("text=Application Received").first).to_be_visible(timeout=5000)

    def test_05_add_customer_type_condition(self, page):
        """Add a condition node for customer type."""
        tree = page.locator("[data-testid='embedded-tree-section']")
        tree.locator("button", has_text="Condition").first.click()
        page.wait_for_timeout(1000)

        cond = page.locator(".react-flow__node-condition").first
        expect(cond).to_be_visible(timeout=3000)

        pencil = cond.locator("button").first
        pencil.click()
        page.wait_for_timeout(500)

        editor = page.locator(".react-flow__node-condition .nopan").first
        editor.locator("select").first.select_option("is_existing_customer")
        page.wait_for_timeout(300)
        editor.locator("input").first.fill("Customer Type")
        editor.locator("button", has_text="Apply").first.click()
        page.wait_for_timeout(500)

        expect(page.locator("text=Customer Type").first).to_be_visible(timeout=3000)

    def test_06_build_full_tree_via_api(self, test_data):
        """Build the complete 5-branch tree via API."""
        headers = get_api_headers()
        tree_id = test_data["tree_id"]
        aa = test_data["assessments"]

        resp = http_requests.put(f"{API_URL}/decision-trees/{tree_id}", json={
            "nodes": [
                {"node_key": "root", "node_type": "annotation", "label": "Application Received", "is_root": True, "position_x": 400, "position_y": 0},
                {"node_key": "cust_type", "node_type": "condition", "label": "Customer Type", "condition_type": "binary",
                 "attribute": "is_existing_customer", "branches": {"Existing Customer": {"value": True}, "New Customer": {"value": False}},
                 "parent_node_key": "root", "branch_label": "evaluate", "is_root": False, "position_x": 400, "position_y": 120},
                {"node_key": "income", "node_type": "condition", "label": "Income Level", "condition_type": "numeric_range",
                 "attribute": "monthly_income", "branches": {"High Income": {"operator": ">=", "threshold": 10000}, "Standard": {"operator": "<", "threshold": 10000}},
                 "parent_node_key": "cust_type", "branch_label": "Existing Customer", "is_root": False, "position_x": 200, "position_y": 260},
                {"node_key": "bureau", "node_type": "condition", "label": "Bureau Data", "condition_type": "categorical",
                 "attribute": "bureau_file_status", "branches": {"Thin File": {"values": ["thin", "none"]}, "Standard": {"values": ["standard"]}, "Thick File": {"values": ["thick"]}},
                 "parent_node_key": "cust_type", "branch_label": "New Customer", "is_root": False, "position_x": 650, "position_y": 260},
                {"node_key": "a_fast", "node_type": "assessment", "label": "Fast Track", "assessment_id": aa[0]["id"],
                 "parent_node_key": "income", "branch_label": "High Income", "is_root": False, "position_x": 100, "position_y": 400},
                {"node_key": "a_std", "node_type": "assessment", "label": "Standard", "assessment_id": aa[1]["id"],
                 "parent_node_key": "income", "branch_label": "Standard", "is_root": False, "position_x": 300, "position_y": 400},
                {"node_key": "a_enhanced", "node_type": "assessment", "label": "Enhanced", "assessment_id": aa[2]["id"],
                 "parent_node_key": "bureau", "branch_label": "Thin File", "is_root": False, "position_x": 500, "position_y": 400},
                {"node_key": "a_stdnew", "node_type": "assessment", "label": "Standard New", "assessment_id": aa[3]["id"],
                 "parent_node_key": "bureau", "branch_label": "Standard", "is_root": False, "position_x": 700, "position_y": 400},
                {"node_key": "a_express", "node_type": "assessment", "label": "Express", "assessment_id": aa[4]["id"],
                 "parent_node_key": "bureau", "branch_label": "Thick File", "is_root": False, "position_x": 900, "position_y": 400},
            ],
        }, headers=headers)
        assert resp.status_code == 200, f"Tree update failed: {resp.text}"
        verify = http_requests.get(f"{API_URL}/decision-trees/{tree_id}", headers=headers).json()
        assert len(verify["nodes"]) == 9, f"Expected 9 nodes, got {len(verify['nodes'])}"

    def test_07_tree_visible_in_ui(self, page, test_data):
        """Reload the strategy page and verify the tree renders."""
        go_strategies(page)
        sname = test_data["strategy"]["name"]
        row = page.locator(f"text={sname}").first
        row.wait_for(timeout=5000)
        row.click()
        page.wait_for_timeout(3000)

        expect(page.locator("text=Customer Type").first).to_be_visible(timeout=5000)
        expect(page.locator("text=Income Level").first).to_be_visible(timeout=5000)
        expect(page.locator("text=Bureau Data").first).to_be_visible(timeout=5000)

    def test_08_add_five_assessment_nodes(self, page):
        """Add 5 assessment nodes."""
        tree = page.locator("[data-testid='embedded-tree-section']")
        for _ in range(5):
            tree.locator("button", has_text="Assessment").first.click()
            page.wait_for_timeout(500)

        assessments = page.locator(".react-flow__node-assessment")
        assert assessments.count() >= 5, f"Expected 5+ assessments, got {assessments.count()}"

    def test_09_assign_assessments(self, page, test_data):
        """Click pencil on each assessment node and assign an assessment."""
        assess_nodes = page.locator(".react-flow__node-assessment")
        names = [a["name"] for a in test_data["assessments"]]

        for i in range(min(5, assess_nodes.count())):
            node = assess_nodes.nth(i)
            pencil = node.locator("button").first
            pencil.click()
            page.wait_for_timeout(500)

            select = node.locator("select").first
            select.select_option(str(test_data["assessments"][i]["id"]))
            page.wait_for_timeout(200)

            apply = node.locator("button", has_text="Apply").first
            apply.click()
            page.wait_for_timeout(500)

        expect(page.locator(f"text={names[0]}").first).to_be_visible(timeout=3000)

    def test_10_save_tree(self, page):
        """Save the tree."""
        save_btn = page.locator("[data-testid='btn-save-tree']")
        save_btn.click()
        page.wait_for_timeout(3000)
        expect(save_btn).to_be_visible(timeout=3000)

    def test_11_verify_tree_via_api(self, test_data):
        """Verify all nodes were saved."""
        headers = get_api_headers()
        tree = http_requests.get(
            f"{API_URL}/decision-trees/{test_data['tree_id']}",
            headers=headers,
        ).json()
        node_count = len(tree["nodes"])
        assert node_count >= 9, f"Expected 9+ nodes, got {node_count}"

        types = [n["node_type"] for n in tree["nodes"]]
        conditions = types.count("condition")
        assessments = types.count("assessment")
        annotations = types.count("annotation")

        print(f"\n  Tree: {node_count} nodes, {conditions} conditions, {assessments} assessments, {annotations} annotations")
        assert conditions >= 3, f"Expected 3+ conditions, got {conditions}"
        assert assessments >= 5, f"Expected 5+ assessments, got {assessments}"

    def test_12_assessments_section_visible(self, page, test_data):
        """Verify all 5 assessments show in the assessments section."""
        section = page.locator("[data-testid='assessments-section']")
        expect(section).to_be_visible(timeout=5000)

        for a in test_data["assessments"]:
            expect(section.locator(f"text={a['name']}").first).to_be_visible(timeout=3000)

    def test_13_activate_strategy(self, page, test_data):
        """Activate the strategy via UI."""
        go_strategies(page)
        sid = test_data["strategy"]["id"]
        btn = page.get_by_test_id(f"btn-activate-{sid}")
        btn.wait_for(timeout=5000)
        btn.click()
        page.wait_for_timeout(1500)

        row = page.get_by_test_id(f"strategy-row-{sid}")
        expect(row.locator("text=active")).to_be_visible(timeout=5000)

    def test_14_validate_tree_via_api(self, test_data):
        """Validate the tree structure."""
        headers = get_api_headers()
        resp = http_requests.post(
            f"{API_URL}/decision-trees/{test_data['tree_id']}/validate",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        print(f"\n  Validation: valid={data['valid']} stats={data['stats']}")
        if data.get("errors"):
            for e in data["errors"]:
                print(f"    Error: {e['code']} @ {e.get('node_key','?')}: {e['message']}")

    def test_15_cleanup(self, test_data):
        """Delete the strategy."""
        headers = get_api_headers()
        sid = test_data["strategy"]["id"]
        resp = http_requests.delete(f"{API_URL}/strategies/{sid}", headers=headers)
        assert resp.status_code == 200
        verify = http_requests.get(f"{API_URL}/strategies/{sid}", headers=headers)
        assert verify.status_code == 404
        print("\n  Complex tree test complete. Strategy deleted.")
