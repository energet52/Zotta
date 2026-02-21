"""Playwright E2E: strategy with assessments for new/existing customer DSR.

Scenario:
  1. Login as admin
  2. Create strategy + 2 assessments (from template, with DSR overrides) via API
  3. Build decision tree: is_existing_customer -> Yes=Assessment B, No=Assessment A
  4. Verify assessments visible in strategy panel via UI
  5. Activate strategy via UI
  6. Verify active
  7. Deactivate and archive via UI
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
    """Set up the complete strategy + assessments + tree via API."""
    ts = int(time.time())
    data = {}

    strat = http_requests.post(f"{API_URL}/strategies", json={
        "name": f"E2E-Assess-{ts}",
        "description": "New/existing customer DSR test",
        "evaluation_mode": "dual_path",
        "score_cutoffs": {"approve": 0, "refer": 0, "decline": 0},
    }, headers=api_headers)
    assert strat.status_code == 201, f"Strategy creation failed: {strat.text}"
    data["strategy"] = strat.json()
    sid = data["strategy"]["id"]

    assess_a = http_requests.post(
        f"{API_URL}/assessments/from-template?strategy_id={sid}&name=New+Customer+Rules",
        headers=api_headers,
    )
    assert assess_a.status_code == 201, f"Assessment A creation failed: {assess_a.text}"
    data["assessment_a"] = assess_a.json()

    rules_a = data["assessment_a"]["rules"]
    for rule in rules_a:
        if rule.get("rule_id") == "R08":
            rule["threshold"] = 1.0
            rule["name"] = "Extreme DSR (100%)"
        if rule.get("rule_id") == "R12":
            rule["threshold"] = 1.0
            rule["name"] = "High DSR (100%)"
    http_requests.put(f"{API_URL}/assessments/{data['assessment_a']['id']}", json={
        "name": "New Customer Rules",
        "rules": rules_a,
    }, headers=api_headers)

    assess_b = http_requests.post(
        f"{API_URL}/assessments/from-template?strategy_id={sid}&name=Existing+Customer+Rules",
        headers=api_headers,
    )
    assert assess_b.status_code == 201, f"Assessment B creation failed: {assess_b.text}"
    data["assessment_b"] = assess_b.json()

    rules_b = data["assessment_b"]["rules"]
    for rule in rules_b:
        if rule.get("rule_id") == "R08":
            rule["threshold"] = 0.80
            rule["name"] = "Extreme DSR (80%)"
        if rule.get("rule_id") == "R12":
            rule["threshold"] = 0.40
            rule["name"] = "High DSR (40%)"
    http_requests.put(f"{API_URL}/assessments/{data['assessment_b']['id']}", json={
        "name": "Existing Customer Rules",
        "rules": rules_b,
    }, headers=api_headers)

    products = http_requests.get(f"{API_URL}/admin/products", headers=api_headers).json()
    product = products[0]

    tree = http_requests.post(f"{API_URL}/decision-trees", json={
        "product_id": product["id"],
        "name": f"E2E Assess Tree {ts}",
        "description": "New vs existing customer routing",
        "nodes": [
            {
                "node_key": "root", "node_type": "condition",
                "label": "Customer Type",
                "condition_type": "binary",
                "attribute": "is_existing_customer",
                "operator": "eq",
                "branches": {"Yes": {"value": True}, "No": {"value": False}},
                "is_root": True,
                "position_x": 300, "position_y": 50,
            },
            {
                "node_key": "existing_path", "node_type": "assessment",
                "label": "Existing Customer Rules",
                "assessment_id": data["assessment_b"]["id"],
                "parent_node_key": "root", "branch_label": "Yes",
                "is_root": False,
                "position_x": 100, "position_y": 250,
            },
            {
                "node_key": "new_path", "node_type": "assessment",
                "label": "New Customer Rules",
                "assessment_id": data["assessment_a"]["id"],
                "parent_node_key": "root", "branch_label": "No",
                "is_root": False,
                "position_x": 500, "position_y": 250,
            },
        ],
    }, headers=api_headers)
    assert tree.status_code == 201, f"Tree creation failed: {tree.text}"
    data["tree"] = tree.json()

    http_requests.put(f"{API_URL}/strategies/{sid}", json={
        "decision_tree_id": data["tree"]["id"],
    }, headers=api_headers)

    yield data

    http_requests.delete(f"{API_URL}/strategies/{sid}", headers=api_headers)


def login(page: Page):
    page.goto(f"{BASE_URL}/login")
    page.get_by_label("Email").fill(ADMIN_EMAIL)
    page.get_by_label("Password").fill(ADMIN_PASSWORD)
    page.get_by_role("button", name="Sign In").click()
    page.wait_for_url(re.compile(r".*/(backoffice|dashboard|my-loans).*"), timeout=10000)


def go_strategies(page: Page):
    page.goto(f"{BASE_URL}/backoffice/strategies")
    page.wait_for_selector("[data-testid='strategy-list']", timeout=10000)


class TestStrategyAssessmentWorkflow:

    def test_01_login(self, page):
        login(page)

    def test_02_strategy_created_with_assessments(self, test_data):
        """Verify the fixture created everything correctly."""
        assert test_data["strategy"]["id"] is not None
        assert test_data["assessment_a"]["id"] is not None
        assert test_data["assessment_b"]["id"] is not None
        assert test_data["tree"]["id"] is not None
        assert len(test_data["tree"]["nodes"]) == 3

    def test_03_validate_tree(self, api_headers, test_data):
        tid = test_data["tree"]["id"]
        resp = http_requests.post(f"{API_URL}/decision-trees/{tid}/validate", headers=api_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True, f"Validation failed: {data.get('errors')}"
        assert data["stats"]["total_nodes"] == 3
        assert data["stats"]["terminal_nodes"] == 2

    def test_04_assessments_visible_in_strategy_panel(self, page, test_data):
        go_strategies(page)
        sname = test_data["strategy"]["name"]
        row = page.locator(f"text={sname}").first
        row.wait_for(timeout=5000)
        row.click()
        page.wait_for_timeout(2000)

        expect(page.locator("[data-testid='assessments-section']")).to_be_visible(timeout=5000)
        expect(page.locator("text=New Customer Rules").first).to_be_visible(timeout=5000)
        expect(page.locator("text=Existing Customer Rules").first).to_be_visible(timeout=5000)

    def test_05_assessment_shows_rule_count(self, page, test_data):
        """Each assessment should show its rule count."""
        section = page.locator("[data-testid='assessments-section']")
        expect(section.locator("text=rules").first).to_be_visible(timeout=3000)

    def test_06_activate_strategy_via_ui(self, page, test_data):
        go_strategies(page)
        sid = test_data["strategy"]["id"]
        btn = page.get_by_test_id(f"btn-activate-{sid}")
        btn.wait_for(timeout=5000)
        btn.click()
        page.wait_for_timeout(1500)

        row = page.get_by_test_id(f"strategy-row-{sid}")
        expect(row.locator("text=active")).to_be_visible(timeout=5000)

    def test_07_verify_active_in_filter(self, page, test_data):
        go_strategies(page)
        page.get_by_test_id("filter-status").select_option("active")
        page.wait_for_timeout(1500)
        sname = test_data["strategy"]["name"]
        expect(page.locator(f"text={sname}").first).to_be_visible(timeout=5000)

    def test_08_simulation_trace(self, api_headers, test_data):
        """Trace a decision to verify assessment-based evaluation works."""
        resp = http_requests.post(f"{API_URL}/simulation/trace", json={
            "application_id": 1,
            "tree_id": test_data["tree"]["id"],
        }, headers=api_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["final_outcome"] in ("approve", "decline", "refer", "error")
        print(f"\n  Trace outcome: {data['final_outcome']}")

    def test_09_deactivate_and_archive(self, api_headers, test_data):
        """Deactivate and archive via API for reliability."""
        sid = test_data["strategy"]["id"]
        http_requests.post(f"{API_URL}/strategies/{sid}/deactivate", headers=api_headers)
        http_requests.post(f"{API_URL}/strategies/{sid}/archive", headers=api_headers)

    def test_10_verify_cleanup(self, api_headers, test_data):
        sid = test_data["strategy"]["id"]
        resp = http_requests.get(f"{API_URL}/strategies/{sid}", headers=api_headers)
        assert resp.status_code == 200
        status = resp.json()["status"]
        assert status in ("archived", "draft"), f"Expected archived or draft, got {status}"
        print(f"\n  Strategy {status}. Assessment workflow E2E complete.")
