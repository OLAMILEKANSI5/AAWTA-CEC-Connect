"""Group 3: Edit Event + Gallery approval workflow + public event image serving."""
import io
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
ADMIN = {"Authorization": "Bearer tok_admtest"}
AMB_TOKEN = "tok_amb_g3test"
AMB = {"Authorization": f"Bearer {AMB_TOKEN}"}

# 1x1 PNG
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00"
       b"\x00\x01\x01\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def ambassador():
    """Seed an ambassador user + session directly in mongo (no OAuth in preview)."""
    async def _seed():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = c[os.environ["DB_NAME"]]
        uid = "user_g3amb"
        await db.users.update_one({"user_id": uid}, {"$set": {
            "user_id": uid, "email": "g3amb@example.com", "name": "G3 Ambassador",
            "role": "ambassador", "account_status": "active", "created_at": _now()
        }}, upsert=True)
        await db.authorized_emails.update_one({"email": "g3amb@example.com"}, {"$set": {
            "email": "g3amb@example.com", "role": "ambassador", "status": "active"
        }}, upsert=True)
        await db.user_sessions.update_one({"session_token": AMB_TOKEN}, {"$set": {
            "user_id": uid, "session_token": AMB_TOKEN,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "created_at": _now()
        }}, upsert=True)
        c.close()
        return uid
    return asyncio.get_event_loop().run_until_complete(_seed())


def _upload(headers=ADMIN, category="event-image"):
    r = requests.post(f"{API}/upload",
                      headers=headers,
                      files={"file": (f"test_{uuid.uuid4().hex[:6]}.png", io.BytesIO(PNG), "image/png")},
                      data={"category": category})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _create_event(headers=ADMIN, **overrides):
    payload = {
        "name": f"TEST_G3_{uuid.uuid4().hex[:6]}",
        "date": (datetime.now(timezone.utc) + timedelta(days=15)).strftime("%Y-%m-%d"),
        "start_time": "10:00 AM",
        "category": "Community",
        "format": "In-Person",
        "city": "Atlanta",
        "state": "Georgia",
        "capacity": 20,
        "description": "seed",
        "public": True,
    }
    payload.update(overrides)
    r = requests.post(f"{API}/events", headers=headers, json=payload)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _approve_and_publish(eid):
    assert requests.put(f"{API}/events/{eid}/status", headers=ADMIN, json={"status": "Approved"}).status_code == 200
    assert requests.put(f"{API}/events/{eid}/publish", headers=ADMIN, json={"published": True}).status_code == 200


# ---------- Public event image ----------
class TestPublicEventImage:
    def test_public_file_serves_for_published_event(self):
        fid = _upload()
        ev = _create_event(image_file_id=fid)
        _approve_and_publish(ev["id"])
        r = requests.get(f"{API}/public/files/{fid}")
        assert r.status_code == 200, f"expected 200 got {r.status_code}"
        assert r.headers.get("content-type", "").startswith("image/")

    def test_public_file_404_for_unpublished(self):
        fid = _upload()
        _create_event(image_file_id=fid, public=False)  # not public
        r = requests.get(f"{API}/public/files/{fid}")
        assert r.status_code == 404


# ---------- Edit event ----------
class TestEditEvent:
    def test_staff_updates_in_place(self):
        ev = _create_event()
        eid = ev["id"]
        new_name = f"TEST_G3_EDITED_{uuid.uuid4().hex[:5]}"
        r = requests.put(f"{API}/events/{eid}", headers=ADMIN, json={
            "name": new_name, "capacity": 55, "description": "updated"
        })
        assert r.status_code == 200, r.text
        assert r.json()["id"] == eid
        assert r.json()["name"] == new_name
        # verify persistence via GET
        g = requests.get(f"{API}/events/{eid}", headers=ADMIN).json()
        assert g["name"] == new_name
        assert g["capacity"] == 55

    def test_missing_returns_404(self):
        assert requests.put(f"{API}/events/evt_nonexistent_xxx", headers=ADMIN, json={"name": "x"}).status_code == 404

    def test_owner_can_edit_own(self, ambassador):
        ev = _create_event(headers=AMB)
        r = requests.put(f"{API}/events/{ev['id']}", headers=AMB, json={"description": "amb updated"})
        assert r.status_code == 200
        assert r.json()["description"] == "amb updated"

    def test_non_owner_non_staff_forbidden(self, ambassador):
        # admin creates event, ambassador tries to edit
        ev = _create_event(headers=ADMIN)
        r = requests.put(f"{API}/events/{ev['id']}", headers=AMB, json={"name": "hack"})
        assert r.status_code == 403

    def test_name_change_updates_gallery_event_name(self):
        fid = _upload()
        ev = _create_event(image_file_id=fid)
        _approve_and_publish(ev["id"])
        # submit staff report -> auto approved gallery photo
        pid = _upload()
        rep = requests.post(f"{API}/events/{ev['id']}/report", headers=ADMIN, json={
            "outcomes": "Great", "photo_file_ids": [pid], "photo_captions": {pid: "hero"}
        })
        assert rep.status_code == 200
        # rename event
        new_name = f"TEST_G3_RENAMED_{uuid.uuid4().hex[:5]}"
        requests.put(f"{API}/events/{ev['id']}", headers=ADMIN, json={"name": new_name})
        # gallery reflects rename
        photos = requests.get(f"{API}/gallery/photos?event_id={ev['id']}", headers=ADMIN).json()["photos"]
        assert photos and all(p["event_name"] == new_name for p in photos)


# ---------- Gallery workflow ----------
class TestGalleryWorkflow:
    def test_staff_report_auto_approved_visible_publicly(self):
        ev = _create_event()
        _approve_and_publish(ev["id"])
        pid = _upload()
        rep = requests.post(f"{API}/events/{ev['id']}/report", headers=ADMIN, json={
            "outcomes": "Success", "photo_file_ids": [pid], "photo_captions": {pid: "moment"}
        })
        assert rep.status_code == 200
        # public gallery contains this photo
        pub = requests.get(f"{API}/public/gallery").json()
        assert any(g["photo_id"] == pid and g["caption"] == "moment" and g["event_name"] == ev["name"] for g in pub)
        assert requests.get(f"{API}/public/files/{pid}").status_code == 200

    def test_ambassador_report_pending_then_approve(self, ambassador):
        ev = _create_event(headers=AMB)
        _approve_and_publish(ev["id"])
        pid1 = _upload(headers=AMB)
        pid2 = _upload(headers=AMB)
        rep = requests.post(f"{API}/events/{ev['id']}/report", headers=AMB, json={
            "outcomes": "Amb report", "photo_file_ids": [pid1, pid2],
            "photo_captions": {pid1: "p1", pid2: "p2"}
        })
        assert rep.status_code == 200, rep.text
        # not in public gallery
        pub = requests.get(f"{API}/public/gallery").json()
        assert not any(g["photo_id"] in (pid1, pid2) for g in pub)
        # not publicly accessible
        assert requests.get(f"{API}/public/files/{pid1}").status_code == 404
        # appears in admin pending list
        pending = requests.get(f"{API}/gallery/photos?status=pending", headers=ADMIN).json()
        pend_map = {p["file_id"]: p for p in pending["photos"]}
        assert pid1 in pend_map and pid2 in pend_map
        # counts populated
        assert pending["counts"]["pending"] >= 2
        # approve first
        gid = pend_map[pid1]["id"]
        r = requests.put(f"{API}/gallery/photos/{gid}/status", headers=ADMIN, json={"status": "approved"})
        assert r.status_code == 200
        # now public
        pub2 = requests.get(f"{API}/public/gallery").json()
        assert any(g["photo_id"] == pid1 for g in pub2)
        assert requests.get(f"{API}/public/files/{pid1}").status_code == 200
        # pid2 still pending -> still 404
        assert requests.get(f"{API}/public/files/{pid2}").status_code == 404
        # test multiple photos stored under same event
        photos = requests.get(f"{API}/gallery/photos?event_id={ev['id']}", headers=ADMIN).json()["photos"]
        assert len({p["file_id"] for p in photos}) >= 2
        assert all(p["event_id"] == ev["id"] for p in photos)

    def test_reject_removes_from_public_and_reapprove_restores(self):
        ev = _create_event()
        _approve_and_publish(ev["id"])
        pid = _upload()
        requests.post(f"{API}/events/{ev['id']}/report", headers=ADMIN, json={
            "outcomes": "x", "photo_file_ids": [pid]
        })
        # find its gallery id
        photos = requests.get(f"{API}/gallery/photos?event_id={ev['id']}", headers=ADMIN).json()["photos"]
        gid = next(p["id"] for p in photos if p["file_id"] == pid)
        # reject
        r = requests.put(f"{API}/gallery/photos/{gid}/status", headers=ADMIN, json={"status": "rejected"})
        assert r.status_code == 200
        pub = requests.get(f"{API}/public/gallery").json()
        assert not any(g["photo_id"] == pid for g in pub)
        assert requests.get(f"{API}/public/files/{pid}").status_code == 404
        # re-approve
        r2 = requests.put(f"{API}/gallery/photos/{gid}/status", headers=ADMIN, json={"status": "approved"})
        assert r2.status_code == 200
        assert requests.get(f"{API}/public/files/{pid}").status_code == 200

    def test_invalid_status_returns_400(self):
        ev = _create_event()
        _approve_and_publish(ev["id"])
        pid = _upload()
        requests.post(f"{API}/events/{ev['id']}/report", headers=ADMIN, json={
            "outcomes": "x", "photo_file_ids": [pid]
        })
        photos = requests.get(f"{API}/gallery/photos?event_id={ev['id']}", headers=ADMIN).json()["photos"]
        gid = photos[0]["id"]
        r = requests.put(f"{API}/gallery/photos/{gid}/status", headers=ADMIN, json={"status": "bogus"})
        assert r.status_code == 400

    def test_non_staff_cannot_set_status(self, ambassador):
        ev = _create_event()
        _approve_and_publish(ev["id"])
        pid = _upload()
        requests.post(f"{API}/events/{ev['id']}/report", headers=ADMIN, json={
            "outcomes": "x", "photo_file_ids": [pid]
        })
        photos = requests.get(f"{API}/gallery/photos?event_id={ev['id']}", headers=ADMIN).json()["photos"]
        gid = photos[0]["id"]
        r = requests.put(f"{API}/gallery/photos/{gid}/status", headers=AMB, json={"status": "approved"})
        assert r.status_code == 403
        # ambassador listing photos also forbidden
        assert requests.get(f"{API}/gallery/photos", headers=AMB).status_code == 403


# ---------- Regression: Group 1 & Group 2 quick checks ----------
class TestRegressionSmoke:
    def test_comms_templates_exist(self):
        r = requests.get(f"{API}/notification-templates", headers=ADMIN)
        assert r.status_code == 200
        keys = {t["key"] for t in r.json()["templates"]}
        for k in ["application_received", "application_approved", "onboarding_profile", "fully_onboarded_welcome"]:
            assert k in keys, f"missing template {k}"

    def test_onboarding_pipeline_shape(self):
        r = requests.get(f"{API}/onboarding/pipeline", headers=ADMIN)
        assert r.status_code == 200
        d = r.json()
        assert "counts" in d and "entries" in d and "stage_order" in d
