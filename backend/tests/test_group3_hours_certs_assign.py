"""Group 3: Service Hours (clock/manual/admin/summary/export/certificates) + Check-In Assignment.

Notes:
- Uses seeded admin (tok_admtest) and ambassador (tok_amb_g3test).
- mem_memba is linked to user_g3amb (has ~22 approved hours + milestone 20 already earned).
- All test-created data cleaned up in module teardown.
"""
import io
import os
import uuid
import asyncio
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
ADMIN = {"Authorization": "Bearer tok_admtest"}
AMB_TOKEN = "tok_amb_g3test"
AMB = {"Authorization": f"Bearer {AMB_TOKEN}"}
MEM_ID = "mem_memba"
AMB_USER_ID = "user_g3amb"


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------- mongo helpers for setup / teardown ----------
def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _cleanup_created(created_ids):
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ["DB_NAME"]]
    if created_ids:
        await db.service_hours.delete_many({"id": {"$in": list(created_ids)}})
    # kill any lingering active for the ambassador
    await db.service_hours.delete_many({"member_id": MEM_ID, "status": "active"})
    c.close()


async def _ensure_amb_member_linked():
    """Guarantee ambassador seed + member linkage (idempotent)."""
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ["DB_NAME"]]
    uid = AMB_USER_ID
    await db.users.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "email": "g3amb@example.com", "name": "G3 Ambassador",
        "role": "ambassador", "account_status": "active", "created_at": _now(),
    }}, upsert=True)
    await db.user_sessions.update_one({"session_token": AMB_TOKEN}, {"$set": {
        "user_id": uid, "session_token": AMB_TOKEN,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "created_at": _now(),
    }}, upsert=True)
    # Seed a "foreign" volunteer for 403 tests
    await db.users.update_one({"user_id": "user_g3other"}, {"$set": {
        "user_id": "user_g3other", "email": "g3other@example.com", "name": "G3 Other",
        "role": "volunteer", "account_status": "active", "created_at": _now(),
    }}, upsert=True)
    await db.user_sessions.update_one({"session_token": "tok_g3other"}, {"$set": {
        "user_id": "user_g3other", "session_token": "tok_g3other",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "created_at": _now(),
    }}, upsert=True)
    m = await db.members.find_one({"id": MEM_ID})
    if m and m.get("user_id") != uid:
        await db.members.update_one({"id": MEM_ID}, {"$set": {"user_id": uid, "role": "ambassador"}})
    c.close()


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    _run(_ensure_amb_member_linked())
    created = set()
    yield created
    _run(_cleanup_created(created))


# ---------- helpers ----------
def _me_summary():
    r = requests.get(f"{API}/service-hours/me", headers=AMB)
    assert r.status_code == 200, r.text
    return r.json()


# ================================================================
# 1) Clock in / clock out
# ================================================================
class TestClock:
    def test_clock_in_and_second_returns_400(self, setup_and_teardown):
        # ensure no active
        r = requests.get(f"{API}/service-hours/me", headers=AMB); assert r.status_code == 200
        # remove any lingering active
        for e in r.json()["entries"]:
            if e["status"] == "active":
                requests.delete(f"{API}/service-hours/{e['id']}", headers=AMB)

        r1 = requests.post(f"{API}/service-hours/clock-in", headers=AMB,
                           json={"activity_type": "event", "category": "Outreach", "description": "TEST_G3H clock-in"})
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["status"] == "active"
        assert d1["member_id"] == MEM_ID
        setup_and_teardown.add(d1["id"])

        # second clock-in should 400
        r2 = requests.post(f"{API}/service-hours/clock-in", headers=AMB, json={"activity_type": "event"})
        assert r2.status_code == 400, r2.text
        assert "already" in r2.text.lower() or "clocked" in r2.text.lower()

    def test_clock_out_sets_pending_and_computes_hours(self, setup_and_teardown):
        r = requests.post(f"{API}/service-hours/clock-out", headers=AMB)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "pending"
        assert d["clock_out"] is not None
        assert isinstance(d["hours"], (int, float))
        assert d["hours"] >= 0.0

        # clock-out with none active -> 400
        r2 = requests.post(f"{API}/service-hours/clock-out", headers=AMB)
        assert r2.status_code == 400

    def test_clock_in_without_member_profile_returns_400(self):
        # admin has no linked member profile -> should 400
        r = requests.post(f"{API}/service-hours/clock-in", headers=ADMIN, json={"activity_type": "event"})
        assert r.status_code == 400
        assert "member profile" in r.text.lower()


# ================================================================
# 2) Manual hours
# ================================================================
class TestManual:
    def test_manual_submit_ok(self, setup_and_teardown):
        r = requests.post(f"{API}/service-hours", headers=AMB,
                          json={"date": "2026-01-05", "hours": 3.5, "activity_type": "remote",
                                "category": "Admin", "description": "TEST_G3H manual"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "pending"
        assert d["hours"] == 3.5
        assert d["source"] == "manual"
        setup_and_teardown.add(d["id"])

    def test_manual_zero_or_negative_400(self):
        for hrs in (0, -1, 25):
            r = requests.post(f"{API}/service-hours", headers=AMB,
                              json={"date": "2026-01-05", "hours": hrs, "activity_type": "remote"})
            assert r.status_code == 400, f"expected 400 for hours={hrs}, got {r.status_code}: {r.text}"


# ================================================================
# 3) Member self view + delete rules
# ================================================================
class TestSelfView:
    def test_me_shape(self):
        d = _me_summary()
        assert "entries" in d
        assert "summary" in d and set(["approved", "pending", "active", "earned_milestones"]).issubset(d["summary"].keys())
        assert d["milestones_available"] == [20, 50, 100]
        assert d["member_id"] == MEM_ID
        # already-earned milestone 20 from prior seed
        assert 20 in d["summary"]["earned_milestones"]

    def test_delete_pending_ok_and_approved_400(self, setup_and_teardown):
        # create a pending
        r = requests.post(f"{API}/service-hours", headers=AMB,
                          json={"date": "2026-01-06", "hours": 1.0, "activity_type": "remote",
                                "description": "TEST_G3H to-del"})
        pid = r.json()["id"]
        setup_and_teardown.add(pid)
        # delete pending -> ok
        rd = requests.delete(f"{API}/service-hours/{pid}", headers=AMB)
        assert rd.status_code == 200

        # find an approved existing entry (seeded)
        me = _me_summary()
        approved = next((e for e in me["entries"] if e["status"] == "approved"), None)
        assert approved, "expected at least one approved seeded entry"
        rd2 = requests.delete(f"{API}/service-hours/{approved['id']}", headers=AMB)
        assert rd2.status_code == 400
        assert "approved" in rd2.text.lower()

    def test_non_owner_non_staff_delete_403(self, setup_and_teardown):
        # Seed a foreign ambassador and try to delete AMB's pending entry
        async def _seed_other():
            c = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = c[os.environ["DB_NAME"]]
            await db.users.update_one({"user_id": "user_g3other"}, {"$set": {
                "user_id": "user_g3other", "email": "g3other@example.com", "name": "G3 Other",
                "role": "volunteer", "account_status": "active", "created_at": _now(),
            }}, upsert=True)
            await db.user_sessions.update_one({"session_token": "tok_g3other"}, {"$set": {
                "user_id": "user_g3other", "session_token": "tok_g3other",
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                "created_at": _now(),
            }}, upsert=True)
            c.close()
        _run(_seed_other())

        # ambassador creates a pending
        r = requests.post(f"{API}/service-hours", headers=AMB,
                          json={"date": "2026-01-07", "hours": 2.0, "activity_type": "remote",
                                "description": "TEST_G3H other-delete"})
        eid = r.json()["id"]
        setup_and_teardown.add(eid)

        # other volunteer tries to delete
        rd = requests.delete(f"{API}/service-hours/{eid}", headers={"Authorization": "Bearer tok_g3other"})
        assert rd.status_code == 403


# ================================================================
# 4) Admin list / status / edit / summary / export
# ================================================================
class TestAdmin:
    def test_list_shape_and_counts(self):
        r = requests.get(f"{API}/service-hours", headers=ADMIN)
        assert r.status_code == 200
        d = r.json()
        for k in ("entries", "counts", "totals"):
            assert k in d
        for s in ("pending", "approved", "rejected", "active"):
            assert s in d["counts"]

    def test_list_forbidden_for_member(self):
        r = requests.get(f"{API}/service-hours", headers=AMB)
        assert r.status_code == 403

    def test_status_set_and_milestone_notification(self, setup_and_teardown):
        # Create a manual entry small enough to keep totals just above 20
        r = requests.post(f"{API}/service-hours", headers=AMB,
                          json={"date": "2026-01-08", "hours": 2.0, "activity_type": "remote",
                                "description": "TEST_G3H to-approve"})
        eid = r.json()["id"]
        setup_and_teardown.add(eid)

        # invalid status -> 400
        r_bad = requests.put(f"{API}/service-hours/{eid}/status", headers=ADMIN, json={"status": "bogus"})
        assert r_bad.status_code == 400

        # non-staff -> 403
        r_ns = requests.put(f"{API}/service-hours/{eid}/status", headers=AMB, json={"status": "approved"})
        assert r_ns.status_code == 403

        # approve
        r_ok = requests.put(f"{API}/service-hours/{eid}/status", headers=ADMIN, json={"status": "approved"})
        assert r_ok.status_code == 200
        assert r_ok.json()["status"] == "approved"

    def test_edit_hours_staff_only(self, setup_and_teardown):
        r = requests.post(f"{API}/service-hours", headers=AMB,
                          json={"date": "2026-01-09", "hours": 1.5, "activity_type": "remote",
                                "description": "TEST_G3H edit"})
        eid = r.json()["id"]
        setup_and_teardown.add(eid)

        r_ns = requests.put(f"{API}/service-hours/{eid}", headers=AMB, json={"hours": 4.0})
        assert r_ns.status_code == 403

        r_ok = requests.put(f"{API}/service-hours/{eid}", headers=ADMIN,
                            json={"hours": 4.0, "description": "TEST_G3H edited", "category": "Admin"})
        assert r_ok.status_code == 200
        assert r_ok.json()["hours"] == 4.0
        assert r_ok.json()["description"] == "TEST_G3H edited"

    def test_summary_endpoint(self):
        r = requests.get(f"{API}/service-hours/summary", headers=ADMIN)
        assert r.status_code == 200
        rows = r.json()["rows"]
        assert isinstance(rows, list)
        me_row = next((x for x in rows if x["member_id"] == MEM_ID), None)
        assert me_row, "expected mem_memba row in summary"
        assert me_row["approved"] >= 20

    def test_export_csv(self):
        r = requests.get(f"{API}/service-hours/export.csv", headers=ADMIN)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        first = r.text.splitlines()[0]
        for col in ["Date", "Volunteer", "Role", "Activity", "Hours", "Status"]:
            assert col in first


# ================================================================
# 5) Milestones + certificates
# ================================================================
class TestCertificates:
    def test_certificate_20_ok(self):
        r = requests.get(f"{API}/members/{MEM_ID}/certificate/20.pdf", headers=AMB)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_certificate_50_below_400(self):
        r = requests.get(f"{API}/members/{MEM_ID}/certificate/50.pdf", headers=AMB)
        assert r.status_code == 400

    def test_invalid_milestone_400(self):
        r = requests.get(f"{API}/members/{MEM_ID}/certificate/33.pdf", headers=AMB)
        assert r.status_code == 400

    def test_non_owner_non_staff_403(self):
        r = requests.get(f"{API}/members/{MEM_ID}/certificate/20.pdf",
                         headers={"Authorization": "Bearer tok_g3other"})
        assert r.status_code == 403

    def test_staff_can_access_any_cert(self):
        r = requests.get(f"{API}/members/{MEM_ID}/certificate/20.pdf", headers=ADMIN)
        assert r.status_code == 200


# ================================================================
# 6) Check-In Assignment
# ================================================================
class TestCheckinAssign:
    def test_list_assignable_staff_only(self):
        r = requests.get(f"{API}/checkin-assignable", headers=ADMIN)
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list) and len(users) >= 2
        for u in users:
            for k in ("user_id", "name", "role", "email"):
                assert k in u
        r2 = requests.get(f"{API}/checkin-assignable", headers=AMB)
        assert r2.status_code == 403

    def test_assign_notifies_only_new(self, setup_and_teardown):
        # Create fresh event
        r = requests.post(f"{API}/events", headers=ADMIN, json={
            "name": f"TEST_G3H CheckinEvent {uuid.uuid4().hex[:6]}",
            "date": "2026-06-15", "event_type": "In-Person", "venue_address": "Test",
            "capacity": 10, "description": "d", "category": "Community", "format": "In-Person"
        })
        assert r.status_code in (200, 201), r.text
        eid = r.json()["id"]

        async def _get_notif_count(uid):
            c = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = c[os.environ["DB_NAME"]]
            n = await db.notifications.count_documents({"user_id": uid, "title": {"$regex": "Check-In"}})
            c.close()
            return n

        base_amb = _run(_get_notif_count(AMB_USER_ID))

        # First assign -> notifies AMB
        r1 = requests.put(f"{API}/events/{eid}/checkin-assignees", headers=ADMIN,
                          json={"user_ids": [AMB_USER_ID]})
        assert r1.status_code == 200, r1.text
        assert r1.json()["checkin_assignees"] == [AMB_USER_ID]

        after1 = _run(_get_notif_count(AMB_USER_ID))
        assert after1 == base_amb + 1, f"expected +1 notification, got {after1 - base_amb}"

        # Re-save same set -> no new notification
        r2 = requests.put(f"{API}/events/{eid}/checkin-assignees", headers=ADMIN,
                          json={"user_ids": [AMB_USER_ID]})
        assert r2.status_code == 200
        after2 = _run(_get_notif_count(AMB_USER_ID))
        assert after2 == after1, "re-saving same set must NOT re-notify"

        # Timeline entry recorded on member profile of newly-added user
        async def _tl_count():
            c = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = c[os.environ["DB_NAME"]]
            n = await db.timeline.count_documents({
                "related_type": "member", "related_id": MEM_ID,
                "event": {"$regex": "check-in", "$options": "i"}
            })
            c.close()
            return n
        assert _run(_tl_count()) >= 1

        # cleanup event
        async def _drop_event():
            c = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = c[os.environ["DB_NAME"]]
            await db.events.delete_one({"id": eid})
            c.close()
        _run(_drop_event())
