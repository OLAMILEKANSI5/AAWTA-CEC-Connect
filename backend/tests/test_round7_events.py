"""Round 7 — Public AAWTA CEC Events Calendar, registration, publish lifecycle,
dashboard registrations/check-in, and role visibility."""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE = base_url.rstrip("/") + "/api"

ADMIN = {"Authorization": "Bearer tokA"}
AMB = {"Authorization": "Bearer tok_amb_t7"}


@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def created(s):
    ids = []
    yield ids
    from motor.motor_asyncio import AsyncIOMotorClient  # cleanup directly in DB
    import asyncio
    env = dotenv_values("/app/backend/.env")
    cl = AsyncIOMotorClient(env["MONGO_URL"])
    db = cl[env["DB_NAME"]]

    async def clean():
        for eid in ids:
            await db.events.delete_many({"id": eid})
            await db.event_registrations.delete_many({"event_id": eid})
    asyncio.get_event_loop().run_until_complete(clean())


# ---------- health / auth ----------
def test_admin_session_valid(s):
    r = s.get(f"{BASE}/auth/me", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "super_admin"


# ---------- public listing ----------
def test_public_events_unauthenticated(s):
    r = s.get(f"{BASE}/public/events")
    assert r.status_code == 200, r.text
    evs = r.json()
    assert isinstance(evs, list)
    for e in evs:
        assert "_id" not in e
        assert e.get("published") is True
        assert e.get("archived") is not True
        assert e.get("status") in ("Approved", "Scheduled")
        assert "registered_count" in e
    assert any(e["name"] == "Career Fair" for e in evs)


def test_public_home_includes_events(s):
    r = s.get(f"{BASE}/public/home")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "events" in data
    for e in data["events"]:
        assert e.get("published") is True and e.get("status") in ("Approved", "Scheduled")


def test_public_events_filters(s):
    seed = s.get(f"{BASE}/public/events").json()[0]
    for key, val in (("category", seed.get("category")), ("state", seed.get("state")), ("format", seed.get("format"))):
        if not val:
            continue
        r = s.get(f"{BASE}/public/events", params={key: val})
        assert r.status_code == 200
        assert any(e["id"] == seed["id"] for e in r.json()), key
    r = s.get(f"{BASE}/public/events", params={"q": "Career"})
    assert r.status_code == 200 and any("Career" in e["name"] for e in r.json())
    r = s.get(f"{BASE}/public/events", params={"q": "zzz-no-match-zzz"})
    assert r.status_code == 200 and r.json() == []


def test_public_event_detail_and_404(s):
    eid = s.get(f"{BASE}/public/events").json()[0]["id"]
    r = s.get(f"{BASE}/public/events/{eid}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["id"] == eid and "_id" not in d and "registered_count" in d
    assert s.get(f"{BASE}/public/events/evt_does_not_exist").status_code == 404


# ---------- publish lifecycle ----------
def test_publish_lifecycle_and_notification(s, created):
    # ambassador submits -> Submitted + unpublished
    name = f"TEST_R7_Lifecycle_{uuid.uuid4().hex[:6]}"
    r = s.post(f"{BASE}/events", headers=AMB, json={
        "name": name, "date": "2026-11-05", "start_time": "10:00", "city": "Atlanta", "state": "Georgia",
        "category": "Career Development", "format": "In-person", "capacity": 1, "is_paid": False,
        "description": "round7 lifecycle"})
    assert r.status_code == 200, r.text
    ev = r.json()
    created.append(ev["id"])
    assert ev["status"] == "Submitted" and ev["published"] is False

    # not public yet
    assert s.get(f"{BASE}/public/events/{ev['id']}").status_code == 404
    assert all(e["id"] != ev["id"] for e in s.get(f"{BASE}/public/events").json())

    # member cannot publish
    assert s.put(f"{BASE}/events/{ev['id']}/publish", headers=AMB, json={"published": True}).status_code == 403

    # staff publishes
    r = s.put(f"{BASE}/events/{ev['id']}/publish", headers=ADMIN, json={"published": True})
    assert r.status_code == 200, r.text
    assert r.json()["published"] is True
    d = s.get(f"{BASE}/public/events/{ev['id']}")
    assert d.status_code == 200
    assert d.json()["status"] == "Approved"

    # submitting ambassador notified
    n = s.get(f"{BASE}/notifications", headers=AMB)
    assert n.status_code == 200, n.text
    items = n.json() if isinstance(n.json(), list) else n.json().get("notifications", [])
    assert any(name in (i.get("title", "") + i.get("body", "")) for i in items), items

    # unpublish hides it
    assert s.put(f"{BASE}/events/{ev['id']}/publish", headers=ADMIN, json={"published": False}).status_code == 200
    assert s.get(f"{BASE}/public/events/{ev['id']}").status_code == 404

    # republish then archive
    s.put(f"{BASE}/events/{ev['id']}/publish", headers=ADMIN, json={"published": True})
    assert s.put(f"{BASE}/events/{ev['id']}/archive", headers=ADMIN).status_code == 200
    assert s.get(f"{BASE}/public/events/{ev['id']}").status_code == 404
    # still in dashboard list
    assert any(e["id"] == ev["id"] for e in s.get(f"{BASE}/events", headers=ADMIN).json())


# ---------- registration + capacity ----------
def test_registration_capacity_duplicate_honeypot(s, created):
    r = s.post(f"{BASE}/events", headers=ADMIN, json={
        "name": f"TEST_R7_Reg_{uuid.uuid4().hex[:6]}", "date": "2026-12-01", "start_time": "09:00",
        "city": "Savannah", "state": "Georgia", "category": "Community Outreach", "format": "In-person",
        "capacity": 1, "is_paid": False})
    ev = r.json()
    created.append(ev["id"])
    assert s.put(f"{BASE}/events/{ev['id']}/publish", headers=ADMIN, json={"published": True}).status_code == 200

    e1 = f"test_r7_a_{uuid.uuid4().hex[:6]}@example.com"
    r1 = s.post(f"{BASE}/public/events/{ev['id']}/register", json={"name": "TEST A", "email": e1})
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "registered"

    # duplicate blocked
    dup = s.post(f"{BASE}/public/events/{ev['id']}/register", json={"name": "TEST A", "email": e1.upper()})
    assert dup.status_code == 400, dup.text

    # capacity reached -> waitlist
    r2 = s.post(f"{BASE}/public/events/{ev['id']}/register",
                json={"name": "TEST B", "email": f"test_r7_b_{uuid.uuid4().hex[:6]}@example.com"})
    assert r2.status_code == 200 and r2.json()["status"] == "waitlist", r2.text

    # honeypot blocked
    hp = s.post(f"{BASE}/public/events/{ev['id']}/register",
                json={"name": "Bot", "email": f"bot_{uuid.uuid4().hex[:6]}@example.com", "honeypot": "x"})
    assert hp.status_code == 400

    # invalid email -> 422
    assert s.post(f"{BASE}/public/events/{ev['id']}/register",
                  json={"name": "X", "email": "not-an-email"}).status_code == 422

    # register on nonexistent/unpublished event -> 404
    assert s.post(f"{BASE}/public/events/evt_nope/register",
                  json={"name": "X", "email": "x@example.com"}).status_code == 404

    # counts reflected publicly
    det = s.get(f"{BASE}/public/events/{ev['id']}").json()
    assert det["registered_count"] == 1


# ---------- registrations / check-in / walk-in ----------
def test_registrations_checkin_and_permissions(s, created):
    ev = s.post(f"{BASE}/events", headers=AMB, json={
        "name": f"TEST_R7_Manage_{uuid.uuid4().hex[:6]}", "date": "2026-12-05", "capacity": 10}).json()
    created.append(ev["id"])
    s.put(f"{BASE}/events/{ev['id']}/publish", headers=ADMIN, json={"published": True})
    email = f"test_r7_m_{uuid.uuid4().hex[:6]}@example.com"
    reg = s.post(f"{BASE}/public/events/{ev['id']}/register", json={"name": "TEST M", "email": email}).json()

    # owner (ambassador) can list
    r = s.get(f"{BASE}/events/{ev['id']}/registrations", headers=AMB)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1 and body["checked_in"] == 0
    assert body["registrations"][0]["email"] == email

    # search
    r = s.get(f"{BASE}/events/{ev['id']}/registrations", headers=AMB, params={"q": "TEST M"})
    assert r.status_code == 200 and r.json()["total"] == 1

    # anonymous blocked
    assert s.get(f"{BASE}/events/{ev['id']}/registrations").status_code == 401

    # check-in
    assert s.put(f"{BASE}/registrations/{reg['id']}/checkin", headers=ADMIN, json={"checked_in": True}).status_code == 200
    body = s.get(f"{BASE}/events/{ev['id']}/registrations", headers=ADMIN).json()
    assert body["checked_in"] == 1
    assert body["registrations"][0]["status"] == "checked_in"
    # undo
    s.put(f"{BASE}/registrations/{reg['id']}/checkin", headers=ADMIN, json={"checked_in": False})
    assert s.get(f"{BASE}/events/{ev['id']}/registrations", headers=ADMIN).json()["checked_in"] == 0

    # walk-in
    w = s.post(f"{BASE}/events/{ev['id']}/registrations", headers=ADMIN, json={"name": "TEST Walkin"})
    assert w.status_code == 200, w.text
    wd = w.json()
    assert wd["status"] == "walkin" and wd["checked_in"] is True and "_id" not in wd
    assert s.get(f"{BASE}/events/{ev['id']}/registrations", headers=ADMIN).json()["total"] == 2

    # unknown registration checkin -> 404
    assert s.put(f"{BASE}/registrations/reg_nope/checkin", headers=ADMIN, json={"checked_in": True}).status_code == 404


def test_registrations_forbidden_for_non_owner_member(s, created):
    # staff-owned event -> ambassador is not owner
    ev = s.post(f"{BASE}/events", headers=ADMIN, json={
        "name": f"TEST_R7_Forbid_{uuid.uuid4().hex[:6]}", "date": "2026-12-09"}).json()
    created.append(ev["id"])
    r = s.get(f"{BASE}/events/{ev['id']}/registrations", headers=AMB)
    assert r.status_code == 403, r.text
    r = s.post(f"{BASE}/events/{ev['id']}/registrations", headers=AMB, json={"name": "X"})
    assert r.status_code == 403, r.text


# ---------- role visibility ----------
def test_member_cannot_see_other_private_pending_event(s, created):
    ev = s.post(f"{BASE}/events", headers=ADMIN, json={
        "name": f"TEST_R7_Private_{uuid.uuid4().hex[:6]}", "date": "2026-12-11", "public": False}).json()
    created.append(ev["id"])
    # force pending status (staff-created defaults to Approved) via status endpoint
    assert s.put(f"{BASE}/events/{ev['id']}/status", headers=ADMIN, json={"status": "Submitted"}).status_code == 200
    amb_list = s.get(f"{BASE}/events", headers=AMB).json()
    assert all(e["id"] != ev["id"] for e in amb_list), "member can see another user's private pending event"
    staff_list = s.get(f"{BASE}/events", headers=ADMIN).json()
    assert any(e["id"] == ev["id"] for e in staff_list)


def test_events_requires_auth(s):
    assert s.get(f"{BASE}/events").status_code == 401


# ---------- registration_status variants ----------
def _make_public_event(s, created, name_suffix, extra=None):
    payload = {"name": f"TEST_R7_{name_suffix}_{uuid.uuid4().hex[:6]}", "date": "2026-12-20"}
    if extra:
        payload.update(extra)
    ev = s.post(f"{BASE}/events", headers=ADMIN, json=payload).json()
    created.append(ev["id"])
    s.put(f"{BASE}/events/{ev['id']}/publish", headers=ADMIN, json={"published": True})
    return ev


def test_registration_status_waitlist_and_closed(s, created):
    ev = _make_public_event(s, created, "Waitlist", {"capacity": 100})
    # flip to waitlist mode directly through DB-independent path: staff update endpoint is not exposed,
    # so use the events collection via API-created value: assert default is open first
    det = s.get(f"{BASE}/public/events/{ev['id']}").json()
    assert det["registration_status"] == "open"

    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    env = dotenv_values("/app/backend/.env")
    db = AsyncIOMotorClient(env["MONGO_URL"])[env["DB_NAME"]]

    async def set_status(val):
        await db.events.update_one({"id": ev["id"]}, {"$set": {"registration_status": val}})
    loop = asyncio.new_event_loop()
    loop.run_until_complete(set_status("waitlist"))
    r = s.post(f"{BASE}/public/events/{ev['id']}/register",
               json={"name": "TEST W", "email": f"test_r7_w_{uuid.uuid4().hex[:6]}@example.com"})
    assert r.status_code == 200 and r.json()["status"] == "waitlist", r.text

    loop.run_until_complete(set_status("closed"))
    r = s.post(f"{BASE}/public/events/{ev['id']}/register",
               json={"name": "TEST C", "email": f"test_r7_c_{uuid.uuid4().hex[:6]}@example.com"})
    assert r.status_code == 400, r.text
    loop.close()


def test_uncheckin_does_not_clobber_waitlist_status(s, created):
    """Regression guard: un-check-in must restore the prior status, not force 'registered'."""
    ev = _make_public_event(s, created, "Waitlist2", {"capacity": 1})
    s.post(f"{BASE}/public/events/{ev['id']}/register",
           json={"name": "TEST P1", "email": f"test_r7_p1_{uuid.uuid4().hex[:6]}@example.com"})
    r2 = s.post(f"{BASE}/public/events/{ev['id']}/register",
                json={"name": "TEST P2", "email": f"test_r7_p2_{uuid.uuid4().hex[:6]}@example.com"})
    assert r2.json()["status"] == "waitlist"
    rid = r2.json()["id"]
    s.put(f"{BASE}/registrations/{rid}/checkin", headers=ADMIN, json={"checked_in": True})
    s.put(f"{BASE}/registrations/{rid}/checkin", headers=ADMIN, json={"checked_in": False})
    regs = s.get(f"{BASE}/events/{ev['id']}/registrations", headers=ADMIN).json()["registrations"]
    after = next(r for r in regs if r["id"] == rid)
    assert after["status"] == "waitlist", f"waitlist status lost after un-check-in: {after['status']}"
