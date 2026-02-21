"""Playwright E2E: interactive decision tree builder.

Tests two scenarios:
A) UI interactions: adding nodes, editing conditions/assessments via pencil
B) Pre-built tree: a proper connected tree built via API, then verified
   and interacted with through the UI

Honest about limitations: ReactFlow edge-dragging (connecting nodes by
dragging handles) is not reliably automatable in headless Playwright.
Tree structure is built via API (same payload as UI "Save Tree").
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
    """Create strategy with 2 assessments and a connected tree."""
    headers = get_api_headers()
    ts = int(time.time())
    data = {}

    strat = http_requests.post(f"{API_URL}/strategies", json={
        "name": f"TreeBuilder-UI-{ts}",
        "description": "Interactive tree builder test",
        "evaluation_mode": "dual_path",
    }, headers=headers)
    assert strat.status_code == 201
    data["strategy"] = strat.json()
    sid = data["strategy"]["id"]
    data["tree_id"] = data["strategy"]["decision_tree_id"]

    a1 = http_requests.post(
        f"{API_URL}/assessments/from-template?strategy_id={sid}&name=Existing+Customer+Rules",
        headers=headers,
    )
    assert a1.status_code == 201
    data["assessment_1"] = a1.json()

    a2 = http_requests.post(
        f"{API_URL}/assessments/from-template?strategy_id={sid}&name=New+Customer+Rules",
        headers=headers,
    )
    assert a2.status_code == 201
    data["assessment_2"] = a2.json()

    http_requests.put(f"{API_URL}/decision-trees/{data['tree_id']}", json={
        "nodes": [
            {"node_key": "root", "node_type": "annotation", "label": "Application Received",
             "is_root": True, "position_x": 300, "position_y": 0},
            {"node_key": "cust_type", "node_type": "condition", "label": "Customer Type",
             "condition_type": "binary", "attribute": "is_existing_customer",
             "branches": {"Existing Customer": {"value": True}, "New Customer": {"value": False}},
             "parent_node_key": "root", "branch_label": "evaluate",
             "is_root": False, "position_x": 300, "position_y": 140},
            {"node_key": "a_existing", "node_type": "assessment", "label": "Existing Customer Rules",
             "assessment_id": data["assessment_1"]["id"],
             "parent_node_key": "cust_type", "branch_label": "Existing Customer",
             "is_root": False, "position_x": 100, "position_y": 300},
            {"node_key": "a_new", "node_type": "assessment", "label": "New Customer Rules",
             "assessment_id": data["assessment_2"]["id"],
             "parent_node_key": "cust_type", "branch_label": "New Customer",
             "is_root": False, "position_x": 500, "position_y": 300},
        ],
    }, headers=headers)

    tree = http_requests.get(f"{API_URL}/decision-trees/{data['tree_id']}", headers=headers).json()
    assert len(tree["nodes"]) == 4, f"Expected 4 nodes, got {len(tree['nodes'])}"

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


class TestTreeBuilderInteractive:

    def test_01_login(self, page):
        login(page)

    def test_02_tree_has_connected_nodes(self, test_data):
        """Verify the fixture built a proper connected tree."""
        headers = get_api_headers()
        tree = http_requests.get(f"{API_URL}/decision-trees/{test_data['tree_id']}", headers=headers).json()
        assert len(tree["nodes"]) == 4
        root = next(n for n in tree["nodes"] if n["is_root"])
        assert root["node_type"] == "annotation"
        children = [n for n in tree["nodes"] if n["parent_node_id"] is not None]
        assert len(children) == 3

    def test_03_open_strategy_shows_tree_builder(self, page, test_data):
        go_strategies(page)
        sname = test_data["strategy"]["name"]
        page.locator(f"text={sname}").first.click()
        page.wait_for_timeout(3000)
        expect(page.locator("[data-testid='embedded-tree-section']")).to_be_visible(timeout=5000)

    def test_04_all_four_nodes_on_canvas(self, page):
        nodes = page.locator(".react-flow__node")
        assert nodes.count() == 4, f"Expected 4 nodes, got {nodes.count()}"

    def test_05_root_node_visible(self, page):
        expect(page.locator("text=Application Received").first).to_be_visible(timeout=3000)

    def test_06_condition_node_visible(self, page):
        expect(page.locator("text=Customer Type").first).to_be_visible(timeout=3000)
        expect(page.locator("text=is_existing_customer").first).to_be_visible(timeout=3000)

    def test_07_assessment_nodes_visible(self, page):
        expect(page.locator("text=Existing Customer Rules").first).to_be_visible(timeout=3000)
        expect(page.locator("text=New Customer Rules").first).to_be_visible(timeout=3000)

    def test_08_branch_labels_on_edges(self, page):
        expect(page.locator("text=Existing Customer").first).to_be_visible(timeout=3000)
        expect(page.locator("text=New Customer").first).to_be_visible(timeout=3000)

    def test_09_edit_condition_opens_editor(self, page):
        cond_node = page.locator(".react-flow__node-condition").first
        pencil = cond_node.locator("button").first
        pencil.click()
        page.wait_for_timeout(500)
        expect(page.locator("text=Edit Condition")).to_be_visible(timeout=3000)

        editor = page.locator(".react-flow__node-condition .nopan").first
        attr_select = editor.locator("select").first
        attr_select.select_option("is_existing_customer")
        page.wait_for_timeout(300)

        editor.locator("button", has_text="Apply").click()
        page.wait_for_timeout(500)
        expect(page.locator("text=is_existing_customer").first).to_be_visible(timeout=3000)

    def test_10_edit_assessment_opens_editor(self, page, test_data):
        assess_node = page.locator(".react-flow__node-assessment").first
        pencil = assess_node.locator("button").first
        pencil.click()
        page.wait_for_timeout(500)

        select = assess_node.locator("select").first
        expect(select).to_be_visible(timeout=3000)
        select.select_option(str(test_data["assessment_1"]["id"]))
        page.wait_for_timeout(200)

        assess_node.locator("button", has_text="Apply").first.click()
        page.wait_for_timeout(500)
        expect(assess_node.locator("text=Existing Customer Rules")).to_be_visible(timeout=3000)

    def test_11_add_node_via_ui(self, page):
        """Add a condition node via the UI button to verify it works."""
        tree = page.locator("[data-testid='embedded-tree-section']")
        tree.locator("button", has_text="Condition").first.click()
        page.wait_for_timeout(500)
        nodes = page.locator(".react-flow__node")
        assert nodes.count() == 5, f"Expected 5 nodes after adding, got {nodes.count()}"

    def test_12_delete_node_via_ui(self, page):
        """Select and delete the node we just added."""
        nodes = page.locator(".react-flow__node-condition")
        nodes.last.click()
        page.wait_for_timeout(300)
        delete_btn = page.locator("[data-testid='btn-delete-tree-node']")
        expect(delete_btn).to_be_visible(timeout=3000)
        delete_btn.click()
        page.wait_for_timeout(500)
        all_nodes = page.locator(".react-flow__node")
        assert all_nodes.count() == 4, f"Expected 4 nodes after delete, got {all_nodes.count()}"

    def test_13_save_tree(self, page):
        save_btn = page.locator("[data-testid='btn-save-tree']")
        save_btn.click()
        page.wait_for_timeout(3000)
        expect(save_btn).to_be_visible(timeout=3000)

    def test_14_tree_still_has_four_connected_nodes(self, test_data):
        """Verify save preserved the connected tree structure."""
        headers = get_api_headers()
        tree = http_requests.get(f"{API_URL}/decision-trees/{test_data['tree_id']}", headers=headers).json()
        assert len(tree["nodes"]) == 4, f"Expected 4 nodes, got {len(tree['nodes'])}"
        connected = [n for n in tree["nodes"] if n["parent_node_id"] is not None]
        assert len(connected) == 3, f"Expected 3 connected nodes, got {len(connected)}"

    def test_15_assessments_section_visible(self, page):
        section = page.locator("[data-testid='assessments-section']")
        expect(section).to_be_visible(timeout=5000)
        expect(section.locator("text=Existing Customer Rules").first).to_be_visible(timeout=3000)
        expect(section.locator("text=New Customer Rules").first).to_be_visible(timeout=3000)

    def test_16_cleanup(self, test_data):
        headers = get_api_headers()
        resp = http_requests.delete(f"{API_URL}/strategies/{test_data['strategy']['id']}", headers=headers)
        assert resp.status_code == 200
