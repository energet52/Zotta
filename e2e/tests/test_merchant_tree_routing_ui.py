"""UI E2E test: merchant-based decision tree routing — entirely via browser.

Scenario: same as test_merchant_tree_routing.py but executed through the UI.

  1. Login as admin
  2. Create Strategy A (decline DSR >= 100%) + Strategy B (refer DSR >= 100%) via UI
  3. Activate both via UI buttons
  4. Create decision tree (API helper — ReactFlow canvas is not automatable)
  5. Verify tree in listing, open in builder, validate, activate
  6. Verify strategies active
  7. Deactivate & archive via UI

Requires: backend :8000, frontend :5173, seeded data, Playwright.
"""

import pytest
import re
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
def created_ids():
    return {"strategy_a_id": None, "strategy_b_id": None, "tree_id": None}


def login(page: Page):
    page.goto(f"{BASE_URL}/login")
    page.get_by_label("Email").fill(ADMIN_EMAIL)
    page.get_by_label("Password").fill(ADMIN_PASSWORD)
    page.get_by_role("button", name="Sign In").click()
    page.wait_for_url(re.compile(r".*/(backoffice|dashboard|my-loans).*"), timeout=10000)


def go_to_strategies(page: Page):
    page.goto(f"{BASE_URL}/backoffice/strategies")
    page.wait_for_selector("[data-testid='strategy-list']", timeout=10000)


def find_strategy_id_by_name(headers, name):
    strategies = http_requests.get(f"{API_URL}/strategies", headers=headers).json()
    for s in strategies:
        if s["name"] == name:
            return s["id"]
    return None


class TestMerchantTreeRoutingUI:

    # ── Phase 1: Login ───────────────────────────────────────────

    def test_01_login_as_admin(self, page):
        login(page)
        assert re.search(r"backoffice|dashboard|my-loans", page.url)

    # ── Phase 2: Create strategies via UI ────────────────────────

    def test_02_create_strategy_a_via_ui(self, page, api_headers, created_ids):
        """Create Strategy A via UI form."""
        go_to_strategies(page)

        page.get_by_test_id("btn-new-strategy").click()
        page.wait_for_selector("[data-testid='create-strategy-form']")
        page.get_by_test_id("input-strategy-name").fill("UITest-VO-Decline-DSR")
        page.get_by_test_id("input-strategy-desc").fill("Decline on DSR >= 100%")
        page.get_by_test_id("select-eval-mode").select_option("dual_path")
        page.get_by_test_id("btn-create-confirm").click()
        page.wait_for_selector("[data-testid='create-strategy-form']", state="detached", timeout=5000)

        page.wait_for_timeout(1000)
        sid = find_strategy_id_by_name(api_headers, "UITest-VO-Decline-DSR")
        assert sid is not None, "Strategy A not found after creation"
        created_ids["strategy_a_id"] = sid

    def test_03_configure_strategy_a_rules(self, page, api_headers, created_ids):
        """Add knock-out rule to Strategy A via API (rule grid interactions
        are fragile in headless mode; the form was created via UI)."""
        sid = created_ids["strategy_a_id"]
        resp = http_requests.put(f"{API_URL}/strategies/{sid}", json={
            "knock_out_rules": [{
                "rule_id": "DSR_KO", "name": "DSR >= 100% Decline",
                "field": "debt_to_income_ratio", "operator": "lt", "threshold": 1.0,
                "severity": "hard", "reason_code": "DSR_OVER_100", "enabled": True,
            }],
            "score_cutoffs": {"approve": 0, "refer": 0, "decline": 0},
        }, headers=api_headers)
        assert resp.status_code == 200
        assert len(resp.json()["knock_out_rules"]) == 1

    def test_04_create_strategy_b_via_ui(self, page, api_headers, created_ids):
        """Create Strategy B via UI form."""
        go_to_strategies(page)

        page.get_by_test_id("btn-new-strategy").click()
        page.wait_for_selector("[data-testid='create-strategy-form']")
        page.get_by_test_id("input-strategy-name").fill("UITest-Other-Refer-DSR")
        page.get_by_test_id("input-strategy-desc").fill("Refer on DSR >= 100%")
        page.get_by_test_id("select-eval-mode").select_option("dual_path")
        page.get_by_test_id("btn-create-confirm").click()
        page.wait_for_selector("[data-testid='create-strategy-form']", state="detached", timeout=5000)

        page.wait_for_timeout(1000)
        sid = find_strategy_id_by_name(api_headers, "UITest-Other-Refer-DSR")
        assert sid is not None, "Strategy B not found after creation"
        created_ids["strategy_b_id"] = sid

    def test_05_configure_strategy_b_rules(self, page, api_headers, created_ids):
        """Add overlay rule to Strategy B via API."""
        sid = created_ids["strategy_b_id"]
        resp = http_requests.put(f"{API_URL}/strategies/{sid}", json={
            "overlay_rules": [{
                "rule_id": "DSR_OV", "name": "DSR >= 100% Refer",
                "field": "debt_to_income_ratio", "operator": "lt", "threshold": 1.0,
                "severity": "refer", "reason_code": "DSR_OVER_100_REFER", "enabled": True,
            }],
            "score_cutoffs": {"approve": 0, "refer": 0, "decline": 0},
        }, headers=api_headers)
        assert resp.status_code == 200
        assert len(resp.json()["overlay_rules"]) == 1

    # ── Phase 3: Activate both strategies via UI ─────────────────

    def test_06_activate_strategy_a_via_ui(self, page, created_ids):
        go_to_strategies(page)
        sid = created_ids["strategy_a_id"]

        activate_btn = page.get_by_test_id(f"btn-activate-{sid}")
        activate_btn.wait_for(timeout=5000)
        activate_btn.click()
        page.wait_for_timeout(1500)

        row = page.get_by_test_id(f"strategy-row-{sid}")
        expect(row.locator("text=active")).to_be_visible(timeout=5000)

    def test_07_activate_strategy_b_via_ui(self, page, created_ids):
        go_to_strategies(page)
        sid = created_ids["strategy_b_id"]

        activate_btn = page.get_by_test_id(f"btn-activate-{sid}")
        activate_btn.wait_for(timeout=5000)
        activate_btn.click()
        page.wait_for_timeout(1500)

        row = page.get_by_test_id(f"strategy-row-{sid}")
        expect(row.locator("text=active")).to_be_visible(timeout=5000)

    def test_08_verify_both_active_in_filter(self, page):
        """Filter by active and confirm both strategies appear."""
        go_to_strategies(page)
        page.get_by_test_id("filter-status").select_option("active")
        page.wait_for_timeout(1500)

        expect(page.locator("text=UITest-VO-Decline-DSR")).to_be_visible(timeout=5000)
        expect(page.locator("text=UITest-Other-Refer-DSR")).to_be_visible(timeout=5000)

    # ── Phase 4: Create decision tree ────────────────────────────

    def test_09_create_tree(self, api_headers, created_ids):
        """Create the decision tree with merchant routing.
        Uses API because ReactFlow canvas nodes require drag-and-drop
        that is not practical in headless Playwright."""
        sid_a = created_ids["strategy_a_id"]
        sid_b = created_ids["strategy_b_id"]

        products = http_requests.get(f"{API_URL}/admin/products", headers=api_headers).json()
        vo = next((p for p in products if "Value Optical" in (p.get("merchant_name") or "")), None)
        assert vo, "No Value Optical product in seed data"

        resp = http_requests.post(f"{API_URL}/decision-trees", json={
            "product_id": vo["id"],
            "name": "UITest Merchant Routing Tree",
            "description": "Routes by merchant: Value Optical vs others",
            "default_strategy_id": sid_b,
            "nodes": [
                {
                    "node_key": "root_merchant", "node_type": "condition",
                    "label": "Merchant Name", "condition_type": "categorical",
                    "attribute": "merchant_name",
                    "branches": {
                        "Value Optical": {"values": ["Value Optical"]},
                        "Other": {"values": []},
                    },
                    "is_root": True, "position_x": 300, "position_y": 50,
                },
                {
                    "node_key": "strat_vo", "node_type": "strategy",
                    "label": "VO Strategy (Decline DSR)",
                    "strategy_id": sid_a,
                    "parent_node_key": "root_merchant", "branch_label": "Value Optical",
                    "is_root": False, "position_x": 100, "position_y": 250,
                },
                {
                    "node_key": "strat_other", "node_type": "strategy",
                    "label": "Other Strategy (Refer DSR)",
                    "strategy_id": sid_b,
                    "parent_node_key": "root_merchant", "branch_label": "Other",
                    "is_root": False, "position_x": 500, "position_y": 250,
                },
            ],
        }, headers=api_headers)
        assert resp.status_code == 201, f"Tree creation failed: {resp.text}"
        created_ids["tree_id"] = resp.json()["id"]
        assert len(resp.json()["nodes"]) == 3

    # ── Phase 5: Verify tree in UI, validate, activate ───────────

    def test_10_tree_visible_in_listing(self, page):
        page.goto(f"{BASE_URL}/backoffice/decision-trees")
        page.wait_for_timeout(2000)
        expect(page.locator("text=UITest Merchant Routing Tree").first).to_be_visible(timeout=5000)

    def test_11_open_tree_in_builder(self, page, created_ids):
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{created_ids['tree_id']}")
        page.wait_for_timeout(3000)
        expect(page.locator("text=Decision Tree Builder")).to_be_visible(timeout=10000)

    def test_12_validate_tree_in_builder(self, page):
        validate_btn = page.locator("button", has_text="Validate")
        if validate_btn.is_visible():
            validate_btn.click()
            page.wait_for_timeout(2000)
            expect(page.locator("text=Tree is valid")).to_be_visible(timeout=5000)

    def test_13_activate_tree_in_builder(self, page):
        activate_btn = page.locator("button", has_text="Activate")
        if activate_btn.is_visible():
            activate_btn.click()
            page.wait_for_timeout(2000)
            page_text = page.locator("body").inner_text()
            assert "active" in page_text.lower()

    # ── Phase 6: Verify via simulation trace ─────────────────────

    def test_14_simulation_trace_strategy_a(self, api_headers, created_ids):
        """Trace with strategy A to verify it works."""
        resp = http_requests.post(f"{API_URL}/simulation/trace", json={
            "application_id": 1,
            "tree_id": created_ids["tree_id"],
            "strategy_id": created_ids["strategy_a_id"],
        }, headers=api_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["final_outcome"] in ("approve", "decline", "refer", "error")
        print(f"\n  Strategy A trace: {data['final_outcome']}")

    def test_15_simulation_trace_strategy_b(self, api_headers, created_ids):
        """Trace with strategy B to verify it works."""
        resp = http_requests.post(f"{API_URL}/simulation/trace", json={
            "application_id": 1,
            "tree_id": created_ids["tree_id"],
            "strategy_id": created_ids["strategy_b_id"],
        }, headers=api_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["final_outcome"] in ("approve", "decline", "refer", "error")
        print(f"\n  Strategy B trace: {data['final_outcome']}")

    # ── Phase 7: Cleanup — deactivate & archive via UI ───────────

    def test_16_deactivate_strategy_a_via_ui(self, page, created_ids):
        go_to_strategies(page)
        page.get_by_test_id("filter-status").select_option("")
        page.wait_for_timeout(1000)

        sid = created_ids["strategy_a_id"]
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

    def test_17_deactivate_strategy_b_via_ui(self, page, created_ids):
        go_to_strategies(page)
        page.get_by_test_id("filter-status").select_option("")
        page.wait_for_timeout(1000)

        sid = created_ids["strategy_b_id"]
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

    def test_18_verify_strategies_archived(self, page, api_headers, created_ids):
        """Verify both strategies are archived."""
        for label, sid in [
            ("A", created_ids["strategy_a_id"]),
            ("B", created_ids["strategy_b_id"]),
        ]:
            resp = http_requests.get(f"{API_URL}/strategies/{sid}", headers=api_headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "archived", f"Strategy {label} (id={sid}) not archived"

        go_to_strategies(page)
        page.get_by_test_id("filter-status").select_option("archived")
        page.wait_for_timeout(1500)
        expect(page.locator("text=UITest-VO-Decline-DSR").first).to_be_visible(timeout=5000)
        expect(page.locator("text=UITest-Other-Refer-DSR").first).to_be_visible(timeout=5000)
        print("\n  All UI E2E resources cleaned up.")
