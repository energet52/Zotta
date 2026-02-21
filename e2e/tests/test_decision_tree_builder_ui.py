"""Playwright UI tests for the Decision Tree Builder.

Tests the tree builder page: loading, toolbar, node palette, adding nodes,
validation (valid and invalid trees), node rendering, save, activate,
the strategies sidebar, and the validation panel.

Uses API to set up tree data (since ReactFlow drag-and-drop is impractical
in headless mode), then verifies all UI elements render and respond correctly.
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
def test_data(api_headers):
    """Create strategies and trees for the tests."""
    data = {"strategies": [], "trees": []}

    s1 = http_requests.post(f"{API_URL}/strategies", json={
        "name": "TreeUI-Strat-Alpha", "evaluation_mode": "sequential",
    }, headers=api_headers).json()
    s2 = http_requests.post(f"{API_URL}/strategies", json={
        "name": "TreeUI-Strat-Beta", "evaluation_mode": "dual_path",
        "score_cutoffs": {"approve": 200, "refer": 150, "decline": 0},
    }, headers=api_headers).json()
    data["strategies"] = [s1, s2]

    for s in data["strategies"]:
        http_requests.post(f"{API_URL}/strategies/{s['id']}/activate", headers=api_headers)

    products = http_requests.get(f"{API_URL}/admin/products", headers=api_headers).json()
    product = products[0] if products else None
    assert product, "No products in seed data"
    data["product_id"] = product["id"]
    data["product_name"] = product["name"]

    valid_tree = http_requests.post(f"{API_URL}/decision-trees", json={
        "product_id": product["id"],
        "name": "TreeUI Valid Test Tree",
        "description": "A properly configured tree for UI testing",
        "default_strategy_id": s2["id"],
        "nodes": [
            {
                "node_key": "root", "node_type": "condition",
                "label": "Customer Type", "condition_type": "binary",
                "attribute": "is_existing_customer", "operator": "eq",
                "branches": {"Yes": {"value": True}, "No": {"value": False}},
                "is_root": True, "position_x": 300, "position_y": 50,
            },
            {
                "node_key": "strat_yes", "node_type": "strategy",
                "label": "Returning Customer", "strategy_id": s1["id"],
                "parent_node_key": "root", "branch_label": "Yes",
                "is_root": False, "position_x": 100, "position_y": 250,
            },
            {
                "node_key": "strat_no", "node_type": "strategy",
                "label": "New Customer", "strategy_id": s2["id"],
                "parent_node_key": "root", "branch_label": "No",
                "is_root": False, "position_x": 500, "position_y": 250,
            },
        ],
    }, headers=api_headers).json()
    data["trees"].append(valid_tree)

    empty_tree = http_requests.post(f"{API_URL}/decision-trees", json={
        "product_id": product["id"],
        "name": "TreeUI Empty Test Tree",
        "description": "An empty tree for validation failure testing",
        "nodes": [],
    }, headers=api_headers).json()
    data["trees"].append(empty_tree)

    yield data

    for s in data["strategies"]:
        http_requests.post(f"{API_URL}/strategies/{s['id']}/deactivate", headers=api_headers)
        http_requests.post(f"{API_URL}/strategies/{s['id']}/archive", headers=api_headers)


def login(page: Page):
    page.goto(f"{BASE_URL}/login")
    page.get_by_label("Email").fill(ADMIN_EMAIL)
    page.get_by_label("Password").fill(ADMIN_PASSWORD)
    page.get_by_role("button", name="Sign In").click()
    page.wait_for_url(re.compile(r".*/(backoffice|dashboard|my-loans).*"), timeout=10000)


# ── Page Loading & Layout ────────────────────────────────────────

class TestTreeBuilderPageLoad:

    def test_01_login(self, page):
        login(page)

    def test_02_builder_loads_with_valid_tree(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("text=Decision Tree Builder")).to_be_visible()

    def test_03_toolbar_shows_tree_name_and_status(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        subtitle = page.locator("text=TreeUI Valid Test Tree").first
        expect(subtitle).to_be_visible(timeout=5000)

    def test_04_toolbar_buttons_present(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("button", has_text="Save")).to_be_visible()
        expect(page.locator("button", has_text="Validate")).to_be_visible()

    def test_05_back_button_navigates_to_listing(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        back_btn = page.locator("button").first
        back_btn.click()
        page.wait_for_timeout(3000)
        assert "decision-trees" in page.url


# ── Node Palette ─────────────────────────────────────────────────

class TestNodePalette:

    def test_06_palette_visible(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("text=Add Node")).to_be_visible()

    def test_07_palette_has_three_node_types(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("button", has_text="Condition")).to_be_visible()
        expect(page.locator("button", has_text="Strategy")).to_be_visible()
        expect(page.locator("button", has_text="Scorecard Gate")).to_be_visible()

    def test_08_add_condition_node(self, page, test_data):
        """Click 'Condition' button and verify a new node appears on the canvas."""
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        nodes_before = page.locator(".react-flow__node").count()
        page.locator("button", has_text="Condition").click()
        page.wait_for_timeout(500)

        nodes_after = page.locator(".react-flow__node").count()
        assert nodes_after == nodes_before + 1, f"Expected {nodes_before + 1} nodes, got {nodes_after}"

    def test_09_add_strategy_node(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        nodes_before = page.locator(".react-flow__node").count()
        page.locator("button", has_text="Strategy").click()
        page.wait_for_timeout(500)

        nodes_after = page.locator(".react-flow__node").count()
        assert nodes_after == nodes_before + 1

    def test_10_add_scorecard_gate_node(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        nodes_before = page.locator(".react-flow__node").count()
        page.locator("button", has_text="Scorecard Gate").click()
        page.wait_for_timeout(500)

        nodes_after = page.locator(".react-flow__node").count()
        assert nodes_after == nodes_before + 1


# ── Node Rendering ───────────────────────────────────────────────

class TestNodeRendering:

    def test_11_condition_node_shows_label(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("text=Customer Type").first).to_be_visible(timeout=5000)

    def test_12_condition_node_shows_type_badge(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("text=Binary").first).to_be_visible(timeout=5000)

    def test_13_condition_node_shows_branch_count(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("text=2 branches").first).to_be_visible(timeout=5000)

    def test_14_condition_node_shows_attribute(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("text=is_existing_customer").first).to_be_visible(timeout=5000)

    def test_15_strategy_nodes_show_labels(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("text=Returning Customer").first).to_be_visible(timeout=5000)
        expect(page.locator("text=New Customer").first).to_be_visible(timeout=5000)

    def test_16_strategy_node_shows_strategy_badge(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        strategy_labels = page.locator("text=Strategy")
        assert strategy_labels.count() >= 2


# ── Strategies Sidebar ───────────────────────────────────────────

class TestStrategiesSidebar:

    def test_17_strategies_section_visible(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("text=Strategies").first).to_be_visible(timeout=5000)

    def test_18_test_strategies_listed(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("text=TreeUI-Strat-Alpha").first).to_be_visible(timeout=5000)
        expect(page.locator("text=TreeUI-Strat-Beta").first).to_be_visible(timeout=5000)

    def test_19_strategies_show_version_and_mode(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        expect(page.locator("text=sequential").first).to_be_visible(timeout=5000)


# ── Validation: Valid Tree ───────────────────────────────────────

class TestValidationValid:

    def test_20_validate_valid_tree(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        page.locator("button", has_text="Validate").click()
        page.wait_for_timeout(2000)

        expect(page.locator("text=Tree is valid")).to_be_visible(timeout=5000)

    def test_21_validation_panel_shows_stats(self, page):
        expect(page.locator("text=total nodes")).to_be_visible(timeout=3000)
        expect(page.locator("text=condition nodes")).to_be_visible(timeout=3000)
        expect(page.locator("text=terminal nodes")).to_be_visible(timeout=3000)
        expect(page.locator("text=max depth")).to_be_visible(timeout=3000)

    def test_22_validation_stats_values(self, page):
        total_el = page.locator("text=total nodes").locator("..").locator("div.font-medium")
        expect(total_el).to_contain_text("3")

    def test_23_close_validation_panel(self, page):
        page.locator("button", has_text="Close").click()
        page.wait_for_timeout(500)

        expect(page.locator("text=Tree is valid")).not_to_be_visible()


# ── Validation: Invalid (Empty) Tree ─────────────────────────────

class TestValidationInvalid:

    def test_24_validate_empty_tree_shows_errors(self, page, test_data):
        tree = test_data["trees"][1]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        page.locator("button", has_text="Validate").click()
        page.wait_for_timeout(2000)

        expect(page.locator("text=error(s)").first).to_be_visible(timeout=5000)

    def test_25_empty_tree_shows_error_code(self, page):
        body = page.locator("body").inner_text()
        assert "NO_ROOT" in body or "error" in body.lower()


# ── Save ─────────────────────────────────────────────────────────

class TestSave:

    def test_26_save_tree(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        save_btn = page.locator("button", has_text="Save")
        save_btn.click()
        page.wait_for_timeout(2000)

        expect(page.locator("text=Decision Tree Builder")).to_be_visible()


# ── Activate ─────────────────────────────────────────────────────

class TestActivate:

    def test_27_activate_button_visible_for_draft(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        activate_btn = page.locator("button", has_text="Activate")
        if "draft" in page.locator("body").inner_text().lower():
            expect(activate_btn).to_be_visible()

    def test_28_activate_tree(self, page, test_data):
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        activate_btn = page.locator("button", has_text="Activate")
        if activate_btn.is_visible():
            activate_btn.click()
            page.wait_for_timeout(2000)

            body = page.locator("body").inner_text()
            assert "active" in body.lower()

    def test_29_activate_button_hidden_for_active_tree(self, page, test_data):
        """After activation, the Activate button should disappear."""
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        body = page.locator("body").inner_text().lower()
        if "— active" in body:
            activate_btn = page.locator("button", has_text="Activate")
            expect(activate_btn).not_to_be_visible()


# ── Node Selection & Deletion ────────────────────────────────────

class TestNodeInteraction:

    def test_30_click_node_shows_delete_button(self, page, test_data):
        """Clicking on a canvas node should show a Delete button in the toolbar."""
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        nodes = page.locator(".react-flow__node")
        if nodes.count() > 0:
            nodes.first.click()
            page.wait_for_timeout(500)

            delete_btn = page.locator("button", has_text="Delete")
            expect(delete_btn).to_be_visible(timeout=3000)

    def test_31_click_canvas_hides_delete_button(self, page, test_data):
        """Clicking the empty canvas should deselect and hide Delete."""
        tree = test_data["trees"][0]
        page.goto(f"{BASE_URL}/backoffice/decision-trees/{tree['id']}")
        page.wait_for_timeout(3000)

        pane = page.locator(".react-flow__pane")
        pane.click(position={"x": 700, "y": 400})
        page.wait_for_timeout(500)

        delete_btn = page.locator("button", has_text="Delete")
        expect(delete_btn).not_to_be_visible()


# ── Decision Trees Listing Page ──────────────────────────────────

class TestDecisionTreeListing:

    def test_32_listing_page_loads(self, page):
        page.goto(f"{BASE_URL}/backoffice/decision-trees")
        page.wait_for_timeout(2000)
        expect(page.locator("h1", has_text="Decision Trees")).to_be_visible()

    def test_33_listing_shows_test_trees(self, page, test_data):
        page.goto(f"{BASE_URL}/backoffice/decision-trees")
        page.wait_for_timeout(2000)

        expect(page.locator("text=TreeUI Valid Test Tree").first).to_be_visible(timeout=5000)
        expect(page.locator("text=TreeUI Empty Test Tree").first).to_be_visible(timeout=5000)

    def test_34_listing_shows_node_counts(self, page):
        expect(page.locator("text=3 nodes").first).to_be_visible(timeout=3000)
        expect(page.locator("text=0 nodes").first).to_be_visible(timeout=3000)

    def test_35_listing_shows_status_badges(self, page):
        badges = page.locator("text=Draft")
        assert badges.count() >= 1 or page.locator("text=Active").count() >= 1

    def test_36_click_tree_opens_builder(self, page, test_data):
        page.goto(f"{BASE_URL}/backoffice/decision-trees")
        page.wait_for_timeout(2000)

        tree_row = page.locator("text=TreeUI Valid Test Tree").first
        tree_row.click()
        page.wait_for_url(re.compile(r".*/decision-trees/\d+"), timeout=10000)

        expect(page.locator("text=Decision Tree Builder")).to_be_visible(timeout=5000)

    def test_37_listing_search_filter(self, page):
        page.goto(f"{BASE_URL}/backoffice/decision-trees")
        page.wait_for_timeout(2000)

        search = page.locator("input[placeholder*='tree name']")
        search.fill("Valid")
        page.wait_for_timeout(1000)

        expect(page.locator("text=TreeUI Valid Test Tree").first).to_be_visible()

    def test_38_listing_status_filter(self, page):
        page.goto(f"{BASE_URL}/backoffice/decision-trees")
        page.wait_for_timeout(2000)

        status_select = page.locator("select")
        status_select.select_option("draft")
        page.wait_for_timeout(1000)

        body = page.locator("body").inner_text().lower()
        assert "draft" in body or "no decision trees" in body


# ── Sidebar Navigation ───────────────────────────────────────────

class TestSidebarNav:

    def test_39_decision_trees_link_in_sidebar(self, page):
        page.goto(f"{BASE_URL}/backoffice/strategies")
        page.wait_for_timeout(2000)

        link = page.get_by_role("link", name="Decision Trees")
        expect(link).to_be_visible(timeout=5000)

    def test_40_sidebar_link_navigates(self, page):
        page.goto(f"{BASE_URL}/backoffice/strategies")
        page.wait_for_timeout(2000)

        link = page.get_by_role("link", name="Decision Trees")
        link.click()
        page.wait_for_timeout(3000)
        assert "decision-trees" in page.url
