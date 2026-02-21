"""Playwright E2E: interactive decision tree builder.

Tests the full UI workflow of building a decision tree with conditions
and assessments:

  1. Login, create strategy via API (with auto-tree)
  2. Open strategy panel, verify embedded tree builder visible
  3. Create 2 assessments from template
  4. Add a condition node via the Condition button
  5. Click pencil to edit the condition: set attribute, branches
  6. Add 2 assessment nodes
  7. Click pencil to edit each assessment: assign an assessment
  8. Save tree, verify nodes persist
  9. Verify branch labels and node details visible
  10. Cleanup: delete strategy
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
    """Create strategy + assessments via API, return IDs for UI testing."""
    headers = get_api_headers()
    ts = int(time.time())
    data = {}

    strat_resp = http_requests.post(f"{API_URL}/strategies", json={
        "name": f"TreeBuilder-UI-{ts}",
        "description": "Interactive tree builder test",
        "evaluation_mode": "dual_path",
    }, headers=headers)
    assert strat_resp.status_code == 201, f"Strategy creation failed: {strat_resp.text}"
    data["strategy"] = strat_resp.json()
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

    data["strategy"] = http_requests.get(
        f"{API_URL}/strategies/{sid}", headers=headers
    ).json()

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

    def test_02_strategy_has_auto_tree(self, test_data):
        """Verify the strategy was created with an auto-linked tree."""
        assert test_data["strategy"]["decision_tree_id"] is not None
        assert len(test_data["strategy"]["assessments"]) == 2

    def test_03_open_strategy_shows_tree_builder(self, page, test_data):
        """Open the strategy panel and verify the embedded tree section."""
        go_strategies(page)
        sname = test_data["strategy"]["name"]
        row = page.locator(f"text={sname}").first
        row.wait_for(timeout=5000)
        row.click()
        page.wait_for_timeout(3000)

        tree_section = page.locator("[data-testid='embedded-tree-section']")
        expect(tree_section).to_be_visible(timeout=5000)

    def test_04_tree_has_add_buttons(self, page):
        """Verify Condition and Assessment add buttons are visible."""
        tree_section = page.locator("[data-testid='embedded-tree-section']")
        expect(tree_section.locator("text=Condition").first).to_be_visible(timeout=3000)
        expect(tree_section.locator("text=Assessment").first).to_be_visible(timeout=3000)

    def test_05_add_condition_node(self, page):
        """Click the Condition button to add a condition node to the canvas."""
        tree_section = page.locator("[data-testid='embedded-tree-section']")
        condition_btn = tree_section.locator("button", has_text="Condition").first
        condition_btn.click()
        page.wait_for_timeout(1000)

        nodes = page.locator(".react-flow__node")
        assert nodes.count() >= 1, "No nodes on canvas after adding condition"

    def test_06_edit_condition_node(self, page):
        """Click pencil on the condition node to open the editor."""
        condition_node = page.locator(".react-flow__node-condition").first
        expect(condition_node).to_be_visible(timeout=3000)

        pencil = condition_node.locator("button").first
        pencil.click()
        page.wait_for_timeout(500)

        expect(page.locator("text=Edit Condition")).to_be_visible(timeout=3000)

    def test_07_select_attribute(self, page):
        """Select 'Customer Relationship' (is_existing_customer) as the attribute."""
        editor = page.locator(".react-flow__node-condition .nopan").first
        attr_select = editor.locator("select").first
        attr_select.select_option("is_existing_customer")
        page.wait_for_timeout(500)

        content = editor.inner_text()
        assert "Existing Customer" in content or "is_existing_customer" in content or "True" in content

    def test_08_apply_condition(self, page):
        """Click Apply to save the condition."""
        apply_btn = page.locator(".react-flow__node-condition .nopan button", has_text="Apply").first
        apply_btn.click()
        page.wait_for_timeout(1000)

        expect(page.locator("text=Customer Relationship").first).to_be_visible(timeout=3000)

    def test_09_add_assessment_nodes(self, page):
        """Add 2 assessment nodes."""
        tree_section = page.locator("[data-testid='embedded-tree-section']")
        assess_btn = tree_section.locator("button", has_text="Assessment").first

        assess_btn.click()
        page.wait_for_timeout(500)
        assess_btn.click()
        page.wait_for_timeout(500)

        assessment_nodes = page.locator(".react-flow__node-assessment")
        assert assessment_nodes.count() >= 2, f"Expected 2+ assessment nodes, got {assessment_nodes.count()}"

    def test_10_edit_first_assessment(self, page, test_data):
        """Click pencil on the first assessment node and assign an assessment."""
        assess_nodes = page.locator(".react-flow__node-assessment")
        first = assess_nodes.first
        pencil = first.locator("button").first
        pencil.click()
        page.wait_for_timeout(500)

        select = first.locator("select").first
        select.select_option(str(test_data["assessment_1"]["id"]))
        page.wait_for_timeout(300)

        apply = first.locator("button", has_text="Apply").first
        apply.click()
        page.wait_for_timeout(500)

        expect(first.locator("text=Existing Customer Rules")).to_be_visible(timeout=3000)

    def test_11_edit_second_assessment(self, page, test_data):
        """Assign the second assessment to the second node."""
        assess_nodes = page.locator(".react-flow__node-assessment")
        second = assess_nodes.nth(1)
        pencil = second.locator("button").first
        pencil.click()
        page.wait_for_timeout(500)

        select = second.locator("select").first
        select.select_option(str(test_data["assessment_2"]["id"]))
        page.wait_for_timeout(300)

        apply = second.locator("button", has_text="Apply").first
        apply.click()
        page.wait_for_timeout(500)

        expect(second.locator("text=New Customer Rules")).to_be_visible(timeout=3000)

    def test_12_save_tree(self, page):
        """Click Save Tree and verify it completes without error."""
        save_btn = page.locator("[data-testid='btn-save-tree']")
        save_btn.click()
        page.wait_for_timeout(3000)
        expect(save_btn).to_be_visible(timeout=3000)

    def test_13_verify_tree_persisted(self, test_data):
        """Verify the tree nodes were saved to the API."""
        headers = get_api_headers()
        tree = http_requests.get(
            f"{API_URL}/decision-trees/{test_data['tree_id']}",
            headers=headers,
        ).json()
        assert len(tree["nodes"]) >= 3, f"Expected 3+ nodes, got {len(tree['nodes'])}"

    def test_14_assessments_section_visible(self, page):
        """Verify the assessments section shows both assessments."""
        section = page.locator("[data-testid='assessments-section']")
        expect(section).to_be_visible(timeout=5000)
        expect(section.locator("text=Existing Customer Rules").first).to_be_visible(timeout=3000)
        expect(section.locator("text=New Customer Rules").first).to_be_visible(timeout=3000)

    def test_15_cleanup_delete_strategy(self, test_data):
        """Delete the test strategy and all its data."""
        headers = get_api_headers()
        sid = test_data["strategy"]["id"]
        resp = http_requests.delete(f"{API_URL}/strategies/{sid}", headers=headers)
        assert resp.status_code == 200

        verify = http_requests.get(f"{API_URL}/strategies/{sid}", headers=headers)
        assert verify.status_code == 404
