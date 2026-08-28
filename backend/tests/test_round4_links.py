"""Round 4: Resource Center quick-link settings (slack_link / membership_link)."""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

SLACK = "https://aawtaworkspace.slack.com/archives/C0ALPLXG5T5"
MEMBERSHIP = "https://www.zeffy.com/ticketing/aawta-memberships--2025-2"

ADMIN = {"Authorization": "Bearer tok_admin"}
MEMBER = {"Authorization": "Bearer tok_amb"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestSettingsLinks:
    def test_get_settings_has_required_urls(self, client):
        r = client.get(f"{BASE_URL}/api/settings")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "_id" not in d
        assert d["slack_link"] == SLACK
        assert d["membership_link"] == MEMBERSHIP

    def test_member_cannot_update(self, client):
        r = client.put(f"{BASE_URL}/api/settings", json={"slack_link": "https://evil.example.com"},
                       headers=MEMBER)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:300]}"
        # ensure unchanged
        assert client.get(f"{BASE_URL}/api/settings").json()["slack_link"] == SLACK

    def test_unauthenticated_cannot_update(self, client):
        r = client.put(f"{BASE_URL}/api/settings", json={"slack_link": "https://evil.example.com"})
        assert r.status_code in (401, 403), r.text

    def test_staff_update_and_restore(self, client):
        tmp_slack = "https://aawtaworkspace.slack.com/archives/TEST_ROUND4"
        tmp_mem = "https://www.zeffy.com/ticketing/TEST_ROUND4"
        r = client.put(f"{BASE_URL}/api/settings",
                       json={"slack_link": tmp_slack, "membership_link": tmp_mem}, headers=ADMIN)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["slack_link"] == tmp_slack
        assert body["membership_link"] == tmp_mem
        # persistence check
        g = client.get(f"{BASE_URL}/api/settings").json()
        assert g["slack_link"] == tmp_slack
        assert g["membership_link"] == tmp_mem
        # other fields untouched
        assert g["website"] == "https://www.aawta.org"

        # restore
        r2 = client.put(f"{BASE_URL}/api/settings",
                        json={"slack_link": SLACK, "membership_link": MEMBERSHIP}, headers=ADMIN)
        assert r2.status_code == 200
        g2 = client.get(f"{BASE_URL}/api/settings").json()
        assert g2["slack_link"] == SLACK
        assert g2["membership_link"] == MEMBERSHIP
