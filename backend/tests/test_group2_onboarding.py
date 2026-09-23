"""Group 2 backend regression tests: Approve & Onboard + Onboarding Pipeline + automation triggers."""
import os
import time
import uuid
import requests
import pytest
from dotenv import dotenv_values

_env = dotenv_values("/app/frontend/.env")
_base = os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL")
BASE = _base.rstrip("/") + "/api"
H = {"Authorization": "Bearer tok_admtest", "Content-Type": "application/json"}


def _uniq(prefix):
    return f"TEST_{prefix}_{uuid.uuid4().hex[:8]}"


def _submit(app_type="ambassador", email=None):
    email = email or f"delivered+{uuid.uuid4().hex[:6]}@resend.dev"
    payload = {
        "type": app_type,
        "data": {
            "email": email,
            "first_name": "TEST",
            "last_name": uuid.uuid4().hex[:6],
            "state": "GA",
            "reason": "test",
        },
    }
    r = requests.post(f"{BASE}/public/applications", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    return r.json()  # {ref, id}


def _comms(subject_type, subject_id):
    r = requests.get(f"{BASE}/comms?subject_type={subject_type}&subject_id={subject_id}", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- automation trigger: submit -> application_received ----------
def test_submit_application_triggers_received_comm():
    a = _submit()
    # rate-limited email backoff can take ~4-6s per attempt (3 retries)
    time.sleep(20)
    items = _comms("application", a["id"])
    tks = [i.get("template_key") for i in items]
    assert "application_received" in tks, tks
    row = next(i for i in items if i.get("template_key") == "application_received")
    sender = (row.get("sent_by_name") or row.get("sender_name") or "").lower()
    assert sender.startswith("system") or row.get("automatic") is True, row


# ---------- automation: PUT status Approved -> application_approved comm ----------
def test_status_approved_triggers_approved_comm():
    a = _submit()
    r = requests.put(f"{BASE}/applications/{a['id']}/status",
                     json={"status": "Approved", "note": "ok"}, headers=H, timeout=30)
    assert r.status_code == 200, r.text
    time.sleep(15)
    tks = [i.get("template_key") for i in _comms("application", a["id"])]
    assert "application_approved" in tks, tks


# ---------- Approve & Onboard happy path ----------
@pytest.fixture(scope="module")
def onboarded():
    a = _submit("ambassador")
    r = requests.post(f"{BASE}/applications/{a['id']}/approve-onboard", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("member_id") and body.get("member")
    time.sleep(3)
    return {"app": a, "member": body["member"], "member_id": body["member_id"]}


def test_approve_onboard_member_stage_profile_incomplete(onboarded):
    m = requests.get(f"{BASE}/members/{onboarded['member_id']}", headers=H, timeout=30).json()
    assert m.get("approved_at"), m
    assert m.get("onboarding_stage") == "profile_incomplete", m.get("onboarding_stage")
    assert m.get("fully_onboarded_notified") in (False, None)


def test_approve_onboard_application_status_and_comms(onboarded):
    app_id = onboarded["app"]["id"]
    a = requests.get(f"{BASE}/applications/{app_id}", headers=H, timeout=30).json()
    assert a.get("status") == "Converted to Member"
    assert a.get("member_id") == onboarded["member_id"]
    dh = a.get("decision_history") or []
    assert any(e.get("status") == "Approved" for e in dh), dh
    items = _comms("application", app_id)
    tks = [i.get("template_key") for i in items]
    assert "application_approved" in tks, tks
    approved = next(i for i in items if i.get("template_key") == "application_approved")
    sender = (approved.get("sent_by_name") or approved.get("sender_name") or "").lower()
    # Should be the acting admin, NOT 'system'
    assert sender and not sender.startswith("system"), approved


def test_onboarding_invite_recorded_on_member(onboarded):
    tks = [i.get("template_key") for i in _comms("member", onboarded["member_id"])]
    assert "onboarding_profile" in tks, tks


def test_second_approve_onboard_returns_400(onboarded):
    r = requests.post(f"{BASE}/applications/{onboarded['app']['id']}/approve-onboard", headers=H, timeout=30)
    assert r.status_code == 400
    assert "already" in r.text.lower()


def test_inquiry_approve_onboard_rejected():
    a = _submit(app_type="inquiry")
    r = requests.post(f"{BASE}/applications/{a['id']}/approve-onboard", headers=H, timeout=30)
    assert r.status_code == 400


# ---------- Pipeline ----------
def test_pipeline_shape_and_filters():
    r = requests.get(f"{BASE}/onboarding/pipeline", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ("entries", "counts", "stage_order", "stage_labels"):
        assert k in d
    assert d["stage_order"] == ["applied", "under_review", "approved", "profile_incomplete",
                                 "docs_needed", "thirty_day", "fully_onboarded"]
    for k in d["stage_order"]:
        assert k in d["stage_labels"]
        assert k in d["counts"]
    for e in d["entries"]:
        for k in ("kind", "id", "name", "role", "stage", "stage_label", "outstanding",
                   "approved_at", "days_in_stage", "progress_pct", "stalled", "link"):
            assert k in e, e

    r2 = requests.get(f"{BASE}/onboarding/pipeline?role=ambassador", headers=H, timeout=30).json()
    assert all(e["role"] == "ambassador" for e in r2["entries"])
    r3 = requests.get(f"{BASE}/onboarding/pipeline?stage=profile_incomplete", headers=H, timeout=30).json()
    assert all(e["stage"] == "profile_incomplete" for e in r3["entries"])
    # counts should not be zeroed by stage filter (reflect role filter only)
    assert sum(r3["counts"].values()) >= len(r3["entries"])


def test_pipeline_excludes_declined():
    a = _submit()
    r = requests.put(f"{BASE}/applications/{a['id']}/status",
                     json={"status": "Declined", "note": "x"}, headers=H, timeout=30)
    assert r.status_code == 200
    d = requests.get(f"{BASE}/onboarding/pipeline", headers=H, timeout=30).json()
    ids = [e["id"] for e in d["entries"]]
    assert a["id"] not in ids


# ---------- fully_onboarded one-time trigger ----------
def test_fully_onboarded_one_time_trigger(onboarded):
    mid = onboarded["member_id"]
    m = requests.get(f"{BASE}/members/{mid}", headers=H, timeout=30).json()
    steps = [o["step"] for o in m.get("onboarding", [])]
    assert steps, "member should have onboarding steps"
    for s in steps:
        r = requests.put(f"{BASE}/members/{mid}/onboarding", json={"step": s, "done": True}, headers=H, timeout=30)
        assert r.status_code == 200
    time.sleep(15)
    m2 = requests.get(f"{BASE}/members/{mid}", headers=H, timeout=30).json()
    assert m2.get("fully_onboarded_notified") is True, m2
    assert m2.get("onboarding_stage") == "fully_onboarded", m2.get("onboarding_stage")

    tks = [i.get("template_key") for i in _comms("member", mid)]
    n_before = tks.count("fully_onboarded_welcome")
    assert n_before == 1, f"expected exactly one fully_onboarded_welcome, got {n_before} in {tks}"

    step0 = steps[0]
    requests.put(f"{BASE}/members/{mid}/onboarding", json={"step": step0, "done": False}, headers=H, timeout=30)
    requests.put(f"{BASE}/members/{mid}/onboarding", json={"step": step0, "done": True}, headers=H, timeout=30)
    time.sleep(10)
    n_after = [i.get("template_key") for i in _comms("member", mid)].count("fully_onboarded_welcome")
    assert n_after == 1, f"template re-fired: {n_after}"


# ---------- Group 1 regression ----------
def test_group1_templates_intact():
    r = requests.get(f"{BASE}/notification-templates", headers=H, timeout=30)
    assert r.status_code == 200
    body = r.json()
    tpls = body["templates"] if isinstance(body, dict) else body
    keys = {t["key"] for t in tpls}
    assert len(tpls) >= 9, f"expected 9+ templates, got {len(tpls)}"
    for k in ("application_received", "application_approved", "onboarding_profile", "fully_onboarded_welcome"):
        assert k in keys, keys


def test_group1_preview_and_send_ok():
    apps = requests.get(f"{BASE}/applications?limit=1", headers=H, timeout=30).json()
    if isinstance(apps, dict):
        apps = apps.get("items") or apps.get("applications") or apps.get("data") or []
    assert apps, "need at least one application"
    aid = apps[0]["id"]
    r = requests.post(f"{BASE}/comms/preview",
                      json={"subject_type": "application", "subject_id": aid,
                            "template_key": "application_received"}, headers=H, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "subject" in body and "body" in body

    r2 = requests.post(f"{BASE}/comms/send",
                       json={"subject_type": "application", "subject_id": aid,
                             "template_key": "application_received",
                             "subject": body["subject"], "body": body["body"], "channel": "email"},
                       headers=H, timeout=45)
    assert r2.status_code == 200, r2.text
