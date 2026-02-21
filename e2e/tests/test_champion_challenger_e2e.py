"""E2E: Champion-Challenger testing workflow.

Creates two strategies, starts a champion-challenger test, verifies it
appears in the list, checks the comparison dashboard, then discards.
"""

import pytest
import time
import requests as http_requests

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
def test_data():
    """Create two strategies for champion-challenger testing."""
    headers = api_headers()
    ts = int(time.time())
    data = {}

    s1 = http_requests.post(f"{API_URL}/strategies", json={
        "name": f"CC-Champion-{ts}", "evaluation_mode": "dual_path",
    }, headers=headers)
    assert s1.status_code == 201
    data["champion"] = s1.json()

    a1 = http_requests.post(
        f"{API_URL}/assessments/from-template?strategy_id={data['champion']['id']}&name=Champion+Rules",
        headers=headers,
    )
    assert a1.status_code == 201

    s2 = http_requests.post(f"{API_URL}/strategies", json={
        "name": f"CC-Challenger-{ts}", "evaluation_mode": "dual_path",
    }, headers=headers)
    assert s2.status_code == 201
    data["challenger"] = s2.json()

    a2 = http_requests.post(
        f"{API_URL}/assessments/from-template?strategy_id={data['challenger']['id']}&name=Challenger+Rules",
        headers=headers,
    )
    assert a2.status_code == 201

    http_requests.post(f"{API_URL}/strategies/{data['champion']['id']}/activate", headers=headers)
    http_requests.post(f"{API_URL}/strategies/{data['challenger']['id']}/activate", headers=headers)

    yield data

    http_requests.delete(f"{API_URL}/strategies/{data['champion']['id']}", headers=headers)
    http_requests.delete(f"{API_URL}/strategies/{data['challenger']['id']}", headers=headers)


class TestChampionChallengerWorkflow:

    def test_01_list_tests_initially_empty(self):
        headers = api_headers()
        resp = http_requests.get(f"{API_URL}/champion-challenger", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_02_create_test(self, test_data):
        headers = api_headers()
        resp = http_requests.post(f"{API_URL}/champion-challenger", json={
            "champion_strategy_id": test_data["champion"]["id"],
            "challenger_strategy_id": test_data["challenger"]["id"],
            "traffic_pct": 20,
            "min_volume": 100,
            "min_duration_days": 30,
        }, headers=headers)
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "active"
        assert data["traffic_pct"] == 20
        assert data["champion_strategy_id"] == test_data["champion"]["id"]
        assert data["challenger_strategy_id"] == test_data["challenger"]["id"]
        test_data["test_id"] = data["id"]

    def test_03_test_appears_in_list(self, test_data):
        headers = api_headers()
        resp = http_requests.get(f"{API_URL}/champion-challenger", headers=headers)
        assert resp.status_code == 200
        tests = resp.json()
        found = any(t["id"] == test_data["test_id"] for t in tests)
        assert found, f"Test {test_data['test_id']} not in list: {[t['id'] for t in tests]}"

    def test_04_get_comparison(self, test_data):
        headers = api_headers()
        resp = http_requests.get(f"{API_URL}/champion-challenger/{test_data['test_id']}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["test_id"] == test_data["test_id"]
        assert "agreement_rate" in data
        assert "disagreement_rate" in data
        assert "ready_for_decision" in data
        assert data["total_evaluated"] == 0
        assert data["agreement_rate"] == 0

    def test_05_filter_by_status(self, test_data):
        headers = api_headers()
        resp = http_requests.get(f"{API_URL}/champion-challenger?status=active", headers=headers)
        assert resp.status_code == 200
        tests = resp.json()
        assert all(t["status"] == "active" for t in tests)
        assert any(t["id"] == test_data["test_id"] for t in tests)

    def test_06_discard_test(self, test_data):
        headers = api_headers()
        resp = http_requests.delete(f"{API_URL}/champion-challenger/{test_data['test_id']}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["discarded"] is True

    def test_07_test_no_longer_active(self, test_data):
        headers = api_headers()
        resp = http_requests.get(f"{API_URL}/champion-challenger?status=active", headers=headers)
        assert resp.status_code == 200
        tests = resp.json()
        assert not any(t["id"] == test_data["test_id"] for t in tests)

    def test_08_create_and_promote(self, test_data):
        """Create a test and promote the challenger."""
        headers = api_headers()
        create = http_requests.post(f"{API_URL}/champion-challenger", json={
            "champion_strategy_id": test_data["champion"]["id"],
            "challenger_strategy_id": test_data["challenger"]["id"],
            "traffic_pct": 10,
            "min_volume": 0,
            "min_duration_days": 0,
        }, headers=headers)
        assert create.status_code == 201
        tid = create.json()["id"]

        promote = http_requests.post(f"{API_URL}/champion-challenger/{tid}/promote", headers=headers)
        assert promote.status_code == 200

        champ = http_requests.get(f"{API_URL}/strategies/{test_data['champion']['id']}", headers=headers).json()
        assert champ["status"] == "archived"
