"""Phase 2 (reactivate + dashboard aging) + Phase 3 (image ?w= resize) API tests."""
import os, io, asyncio
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ambassador-hub-29.preview.emergentagent.com").rstrip("/")
ADMIN = "tok_admtest"
VOLUNTEER = "tok_g3other"
CRON_SECRET = "cec_cron_9f3a71b2e8d4c6057aa1be24f0d9c3e5"


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


# --- Seed a test inactive member for reactivate + UI ---
@pytest.fixture(scope="module")
def inactive_member_id():
    import pymongo
    client = pymongo.MongoClient("mongodb://localhost:27017")
    db = client["test_database"]
    mid = "mem_p2ui"
    uid = "user_p2ui"
    iso = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    db.users.delete_many({"user_id": uid})
    db.members.delete_many({"id": mid})
    db.users.insert_one({"user_id": uid, "email": "p2ui@example.com", "name": "P2UI Inactive",
                         "role": "ambassador", "account_status": "active", "last_login": iso})
    db.members.insert_one({"id": mid, "name": "P2UI Inactive", "email": "p2ui@example.com",
                           "login_email": "p2ui@example.com", "role": "ambassador",
                           "account_status": "active", "user_id": uid, "onboarding": [],
                           "inactive": True, "inactive_since": iso, "created_at": iso})
    yield mid
    db.users.delete_many({"user_id": uid})
    db.members.delete_many({"id": mid})
    client.close()


class TestReactivateAuth:
    def test_reactivate_forbidden_for_member(self, inactive_member_id):
        r = requests.put(f"{BASE_URL}/api/members/{inactive_member_id}/reactivate", headers=H(VOLUNTEER))
        assert r.status_code == 403, r.text

    def test_reactivate_staff_ok(self, inactive_member_id):
        # First re-set inactive true, since fixture only runs once
        r = requests.put(f"{BASE_URL}/api/members/{inactive_member_id}/reactivate", headers=H(ADMIN))
        assert r.status_code == 200, r.text
        # verify GET member shows inactive false
        g = requests.get(f"{BASE_URL}/api/members/{inactive_member_id}", headers=H(ADMIN))
        assert g.status_code == 200
        m = g.json()
        assert m.get("inactive") in (False, None), m


class TestDashboardAging:
    def test_aging_applications_field(self):
        r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=H(ADMIN))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "aging_applications" in data, list(data.keys())
        assert isinstance(data["aging_applications"], list)


class TestCron:
    def test_cron_no_auth(self):
        r = requests.post(f"{BASE_URL}/api/cron/reminders")
        assert r.status_code == 401

    def test_cron_with_secret(self):
        r = requests.post(f"{BASE_URL}/api/cron/reminders",
                          headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert r.status_code == 200, r.text


class TestImageResize:
    """Upload a large PNG then verify ?w= returns smaller Content-Length."""

    @pytest.fixture(scope="class")
    def uploaded_file_id(self):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed locally")
        buf = io.BytesIO()
        img = Image.new("RGB", (1600, 1200), color=(120, 80, 200))
        img.save(buf, format="PNG")
        buf.seek(0)
        files = {"file": ("phase3.png", buf.getvalue(), "image/png")}
        r = requests.post(f"{BASE_URL}/api/upload", headers=H(ADMIN), files=files)
        assert r.status_code == 200, r.text
        fid = r.json().get("file_id") or r.json().get("id")
        assert fid, r.json()
        return fid

    def test_public_file_full_vs_resized(self, uploaded_file_id):
        full = requests.get(f"{BASE_URL}/api/files/{uploaded_file_id}/download", headers=H(ADMIN))
        assert full.status_code == 200, full.text
        assert full.headers.get("Content-Type", "").startswith("image/")
        full_len = len(full.content)

        small = requests.get(f"{BASE_URL}/api/files/{uploaded_file_id}/download?w=200", headers=H(ADMIN))
        assert small.status_code == 200, small.text
        assert small.headers.get("Content-Type", "").startswith("image/")
        small_len = len(small.content)

        print(f"full={full_len} bytes, w=200 -> {small_len} bytes")
        assert small_len < full_len, f"resized ({small_len}) should be smaller than full ({full_len})"
        assert small_len < full_len * 0.7  # substantially smaller

    def test_cache_control_header(self, uploaded_file_id):
        # Backend sets Cache-Control but ingress may override to no-store; just ensure endpoint responds.
        r = requests.get(f"{BASE_URL}/api/files/{uploaded_file_id}/download?w=200", headers=H(ADMIN))
        assert r.status_code == 200
        # note: cache header may be overridden by ingress; test kept informational
        print(f"Cache-Control on private download w=200: {r.headers.get('Cache-Control')}")

    def test_public_event_image_resize(self):
        """Actual public event image via /api/public/files/{id}?w=200 - real end-user path."""
        evs = requests.get(f"{BASE_URL}/api/public/events").json()
        img_id = next((e.get("image_file_id") for e in evs if e.get("image_file_id")), None)
        if not img_id:
            pytest.skip("no public event image seeded")
        full = requests.get(f"{BASE_URL}/api/public/files/{img_id}")
        assert full.status_code == 200, full.text
        small = requests.get(f"{BASE_URL}/api/public/files/{img_id}?w=200")
        assert small.status_code == 200, small.text
        print(f"public event img: full={len(full.content)} vs w=200={len(small.content)}")
        if len(full.content) > 20000:
            assert len(small.content) < len(full.content) * 0.7
