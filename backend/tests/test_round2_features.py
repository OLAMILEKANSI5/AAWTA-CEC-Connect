"""Round-2 feature tests: cron reminders, signed-document PDF, event ICS, directory search + quick regression."""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

from conftest import API, ADMIN_TOKEN, MEMBER_TOKEN

BE_ENV = dotenv_values("/app/backend/.env")
CRON_SECRET = BE_ENV.get("WEBHOOK_CRON_SECRET")
MONGO_URL = BE_ENV.get("MONGO_URL")
DB_NAME = BE_ENV.get("DB_NAME")


@pytest.fixture(scope="module")
def mdb():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def other_member(mdb):
    """A second, non-staff member (ambassador) used to assert cross-member 403s."""
    uid = "TEST_user_other"
    tok = "TEST_tok_other"
    mdb.users.insert_one({"user_id": uid, "email": "TEST_other@example.com", "name": "TEST Other",
                          "role": "ambassador", "account_status": "active", "created_at": "2026-07-01T00:00:00Z",
                          "last_login": "2026-07-01T00:00:00Z"})
    mdb.user_sessions.insert_one({"user_id": uid, "session_token": tok,
                                  "expires_at": "2030-01-01T00:00:00Z", "created_at": "2026-07-01T00:00:00Z"})
    mdb.members.insert_one({"id": "TEST_mem_other", "user_id": uid, "name": "TEST Other", "email": "TEST_other@example.com",
                            "role": "ambassador", "state": "Ohio", "focus_areas": ["Health"], "public_profile": False,
                            "account_status": "active", "onboarding": [], "created_at": "2026-07-01T00:00:00Z"})
    yield tok
    mdb.users.delete_one({"user_id": uid})
    mdb.user_sessions.delete_one({"session_token": tok})
    mdb.members.delete_one({"id": "TEST_mem_other"})
    mdb.notifications.delete_many({"user_id": uid})
    mdb.reminder_sent.delete_many({"key": {"$regex": "TEST_"}})


def s(token=None):
    sess = requests.Session()
    if token:
        sess.headers.update({"Authorization": f"Bearer {token}"})
    return sess


# ---------------- 1. CRON REMINDERS ----------------
class TestCronReminders:
    def test_no_auth_401(self):
        r = requests.post(f"{API}/cron/reminders", json={})
        assert r.status_code == 401, r.text

    def test_wrong_token_401(self):
        r = requests.post(f"{API}/cron/reminders", json={},
                          headers={"Authorization": "Bearer not-the-secret"})
        assert r.status_code == 401, r.text

    def test_valid_secret_acks_and_dedupes(self, mdb):
        assert CRON_SECRET, "WEBHOOK_CRON_SECRET missing in backend/.env"
        run_id = f"TEST_run_{uuid.uuid4().hex[:8]}"
        h = {"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": run_id}
        r1 = requests.post(f"{API}/cron/reminders", json={}, headers=h, timeout=20)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1.get("ok") is True
        assert d1.get("run_id") == run_id
        assert d1.get("duplicate") is not True

        r2 = requests.post(f"{API}/cron/reminders", json={}, headers=h, timeout=20)
        assert r2.status_code == 200, r2.text
        assert r2.json().get("duplicate") is True

        assert mdb.reminder_runs.count_documents({"run_id": run_id}) == 1
        mdb.reminder_runs.delete_many({"run_id": run_id})

    def test_dedupe_rows_and_notifications_exist(self, mdb):
        import time
        time.sleep(3)
        keys = [d["key"] for d in mdb.reminder_sent.find({}, {"_id": 0, "key": 1})]
        assert len(keys) >= 1, "no reminder_sent dedupe rows created"
        r = s(MEMBER_TOKEN).get(f"{API}/notifications")
        assert r.status_code == 200, r.text
        notes = r.json()
        assert isinstance(notes, list) and len(notes) >= 1
        types = {n.get("type") for n in notes}
        assert "reminder" in types, f"no reminder notifications: {types}"
        titles = " | ".join(n.get("title", "") for n in notes)
        assert "Onboarding reminder" in titles, titles

    def test_no_account_deactivated(self, mdb):
        assert mdb.users.count_documents({"account_status": {"$nin": ["active", None]}}) == 0
        assert mdb.members.count_documents({"account_status": "inactive"}) == 0


# ---------------- 2. SIGNED DOCUMENT PDF ----------------
class TestSignaturePDF:
    def test_owner_gets_pdf(self):
        r = s(MEMBER_TOKEN).get(f"{API}/signatures/sig1/pdf")
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:5] == b"%PDF-", r.content[:20]
        assert len(r.content) > 800
        assert "attachment" in r.headers.get("content-disposition", "")

    def test_staff_gets_pdf(self):
        r = s(ADMIN_TOKEN).get(f"{API}/signatures/sig1/pdf")
        assert r.status_code == 200, r.text
        assert r.content[:5] == b"%PDF-"

    def test_other_member_forbidden(self, other_member):
        r = s(other_member).get(f"{API}/signatures/sig1/pdf")
        assert r.status_code == 403, r.text

    def test_anonymous_unauthorized(self):
        r = requests.get(f"{API}/signatures/sig1/pdf")
        assert r.status_code == 401, r.status_code

    def test_missing_signature_404(self):
        r = s(ADMIN_TOKEN).get(f"{API}/signatures/does_not_exist/pdf")
        assert r.status_code == 404

    def test_documents_list_exposes_signature_id(self):
        r = s(MEMBER_TOKEN).get(f"{API}/documents")
        assert r.status_code == 200, r.text
        docs = r.json()
        doc1 = next((d for d in docs if d["id"] == "doc1"), None)
        assert doc1 is not None, docs
        assert doc1.get("signed_by_me") is True
        assert doc1.get("signature_id") == "sig1", doc1


# ---------------- 3. EVENT ICS ----------------
class TestEventICS:
    def test_ics_valid(self):
        r = requests.get(f"{API}/events/evt1/ics")
        assert r.status_code == 200, r.text
        assert "text/calendar" in r.headers.get("content-type", "")
        body = r.text
        for token in ["BEGIN:VCALENDAR", "VERSION:2.0", "BEGIN:VEVENT", "UID:evt1@cec-connect",
                      "DTSTART;VALUE=DATE:20260904", "SUMMARY:CEC Career Day", "END:VEVENT", "END:VCALENDAR"]:
            assert token in body, f"missing {token} in {body}"

    def test_ics_missing_event_404(self):
        r = requests.get(f"{API}/events/nope/ics")
        assert r.status_code == 404


# ---------------- 4. PUBLIC DIRECTORY SEARCH ----------------
class TestPublicDirectory:
    def test_no_filters_returns_amara(self):
        r = requests.get(f"{API}/public/directory")
        assert r.status_code == 200
        names = [m["name"] for m in r.json()]
        assert "Amara Bell" in names, names

    def test_state_and_focus_match(self):
        r = requests.get(f"{API}/public/directory", params={"state": "Georgia", "focus": "Education"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data) == 1 and data[0]["name"] == "Amara Bell", data
        assert data[0]["state"] == "Georgia"
        assert "Education" in data[0]["focus_areas"]

    def test_non_matching_state_empty(self):
        r = requests.get(f"{API}/public/directory", params={"state": "Texas"})
        assert r.status_code == 200
        assert r.json() == []

    def test_query_search(self):
        r = requests.get(f"{API}/public/directory", params={"q": "amara"})
        assert r.status_code == 200
        assert [m["name"] for m in r.json()] == ["Amara Bell"]
        r2 = requests.get(f"{API}/public/directory", params={"q": "zzzz"})
        assert r2.json() == []

    def test_non_matching_focus_empty(self):
        r = requests.get(f"{API}/public/directory", params={"focus": "Nonexistent Focus"})
        assert r.status_code == 200
        assert r.json() == []

    def test_no_mongo_id_leaked(self):
        r = requests.get(f"{API}/public/directory")
        for m in r.json():
            assert "_id" not in m


# ---------------- 5. QUICK REGRESSION ----------------
class TestQuickRegression:
    def test_file_download_requires_auth(self, mdb):
        f = mdb.files.find_one({}, {"_id": 0, "id": 1})
        fid = f["id"] if f else "file_missing"
        r = requests.get(f"{API}/files/{fid}/download", allow_redirects=False)
        assert r.status_code == 401, f"{r.status_code} {r.text[:200]}"

    def test_goal_cross_member_edit_forbidden(self, other_member):
        r = s(other_member).put(f"{API}/goals/goal1", json={"title": "TEST_hijack"})
        assert r.status_code == 403, f"{r.status_code} {r.text[:200]}"
        # ensure goal unchanged
        g = s(ADMIN_TOKEN).get(f"{API}/goals")
        assert g.status_code == 200
        goal1 = next((x for x in g.json() if x["id"] == "goal1"), None)
        assert goal1 is not None and goal1["title"] != "TEST_hijack"
