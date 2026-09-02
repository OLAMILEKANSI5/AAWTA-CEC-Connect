"""Phase E (documents overhaul), F (auto-onboarding on convert), G (event-scoped check-in volunteer perms)."""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE}/api"
ADMIN = {"Authorization": "Bearer tok_admtest"}
MEMBER = {"Authorization": "Bearer tok_memba"}  # ambassador member user_memba
EVT = "evt_246d20a66b31"
T = 60


def _g(url, h=ADMIN, **kw):
    return requests.get(url, headers=h, timeout=T, **kw)


def _db():
    from pymongo import MongoClient
    env = dotenv_values("/app/backend/.env")
    return MongoClient(env["MONGO_URL"])[env["DB_NAME"]]


def _titles(docs):
    return {d["id"] for d in docs}


@pytest.fixture(scope="module")
def memba_member():
    r = _g(f"{API}/members")
    assert r.status_code == 200, r.text
    lst = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    m = [x for x in lst if x.get("user_id") == "user_memba"]
    assert m, "member record for user_memba missing (run seed_phasea.py)"
    return m[0]


def _mkdoc(**over):
    body = {"title": f"TEST_E_{uuid.uuid4().hex[:6]}", "category": "Onboarding", "description": "TEST description for phase E validation."}
    body.update(over)
    r = requests.post(f"{API}/documents", json=body, headers=ADMIN, timeout=T)
    assert r.status_code == 200, r.text
    return r.json()


def _rm(doc_id):
    requests.put(f"{API}/documents/{doc_id}", json={"title": "TEST_cleanup", "category": "Onboarding", "audience": "private_draft",
                                                   "assigned_to": [], "assigned_roles": []}, headers=ADMIN, timeout=T)
    requests.delete(f"{API}/documents/{doc_id}", headers=ADMIN, timeout=T)


# ---------------- Phase E ----------------
class TestDocumentDefaultsAndVisibility:
    def test_create_defaults_private_draft(self):
        d = _mkdoc()
        try:
            assert d["audience"] == "private_draft"
            assert d["status"] == "active"
            assert d["description"].startswith("TEST description")
            assert d["requires_signature"] is True
        finally:
            _rm(d["id"])

    def test_private_draft_hidden_from_member_then_visible_after_role_assign(self, memba_member):
        d = _mkdoc()
        did = d["id"]
        try:
            r = _g(f"{API}/documents", MEMBER)
            assert r.status_code == 200, r.text
            assert did not in _titles(r.json()), "private_draft doc leaked to member list"

            # direct link enforcement
            r = _g(f"{API}/documents/{did}", MEMBER)
            assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"
            assert _g(f"{API}/documents/{did}").status_code == 200

            a = requests.post(f"{API}/documents/{did}/assign", json={"roles": ["ambassador"], "notify": False}, headers=ADMIN, timeout=T)
            assert a.status_code == 200, a.text
            r = _g(f"{API}/documents", MEMBER)
            assert did in _titles(r.json()), "doc not visible after role assignment"
            assert _g(f"{API}/documents/{did}", MEMBER).status_code == 200
        finally:
            _rm(did)

    def test_admins_only_hidden_from_member(self):
        d = _mkdoc(audience="admins_only")
        try:
            assert d["id"] not in _titles(_g(f"{API}/documents", MEMBER).json())
            assert _g(f"{API}/documents/{d['id']}", MEMBER).status_code == 403
        finally:
            _rm(d["id"])

    def test_volunteers_only_not_visible_to_ambassador(self):
        d = _mkdoc(audience="volunteers_only")
        try:
            assert d["id"] not in _titles(_g(f"{API}/documents", MEMBER).json())
        finally:
            _rm(d["id"])

    def test_all_active_visible_to_member(self):
        d = _mkdoc(audience="all_active")
        try:
            assert d["id"] in _titles(_g(f"{API}/documents", MEMBER).json())
        finally:
            _rm(d["id"])

    def test_specific_members_assignment_visibility(self, memba_member):
        d = _mkdoc()
        did = d["id"]
        try:
            a = requests.post(f"{API}/documents/{did}/assign", json={"member_ids": [memba_member["id"]], "notify": False}, headers=ADMIN, timeout=T)
            assert a.status_code == 200, a.text
            assert a.json()["assigned"] == 1
            got = _g(f"{API}/documents/{did}").json()
            assert got["audience"] == "specific_members"
            assert did in _titles(_g(f"{API}/documents", MEMBER).json())
        finally:
            _rm(did)

    def test_member_cannot_create_or_edit(self):
        r = requests.post(f"{API}/documents", json={"title": "TEST_nope", "category": "Onboarding"}, headers=MEMBER, timeout=T)
        assert r.status_code == 403, r.text


class TestDocumentEditDeleteArchive:
    def test_edit_keeps_signatures_and_updates_fields(self, memba_member):
        d = _mkdoc(audience="ambassadors_only")
        did = d["id"]
        try:
            s = requests.post(f"{API}/documents/{did}/sign", json={"legal_name": "Member PhaseA", "consent": True}, headers=MEMBER, timeout=T)
            assert s.status_code == 200, s.text
            body = dict(d)
            body["title"] = d["title"] + "_EDITED"
            body["description"] = "TEST edited description"
            body["version"] = "2.0"
            r = requests.put(f"{API}/documents/{did}", json=body, headers=ADMIN, timeout=T)
            assert r.status_code == 200, r.text
            upd = r.json()
            assert upd["title"].endswith("_EDITED")
            assert upd["version"] == "2.0"
            # GET persistence
            got = _g(f"{API}/documents/{did}").json()
            assert got["title"] == upd["title"] and got["description"] == "TEST edited description"
            sigs = _g(f"{API}/documents/{did}/signatures")
            assert sigs.status_code == 200
            assert len(sigs.json()) >= 1, "signature lost after edit"
        finally:
            requests.delete(f"{API}/documents/{did}", headers=ADMIN, timeout=T)
            requests.put(f"{API}/documents/{did}/archive", json={"archived": True}, headers=ADMIN, timeout=T)

    def test_delete_unassigned_draft_ok(self):
        d = _mkdoc()
        r = requests.delete(f"{API}/documents/{d['id']}", headers=ADMIN, timeout=T)
        assert r.status_code == 200, r.text
        assert _g(f"{API}/documents/{d['id']}").status_code == 404

    def test_delete_assigned_doc_rejected(self, memba_member):
        d = _mkdoc()
        did = d["id"]
        try:
            requests.post(f"{API}/documents/{did}/assign", json={"member_ids": [memba_member["id"]], "notify": False}, headers=ADMIN, timeout=T)
            r = requests.delete(f"{API}/documents/{did}", headers=ADMIN, timeout=T)
            assert r.status_code == 400, f"expected 400 got {r.status_code}"
            assert "archive" in r.json().get("detail", "").lower()
            assert _g(f"{API}/documents/{did}").status_code == 200, "doc was deleted despite 400"
        finally:
            _rm(did)

    def test_delete_signed_doc_rejected(self):
        d = _mkdoc(audience="ambassadors_only")
        did = d["id"]
        try:
            s = requests.post(f"{API}/documents/{did}/sign", json={"legal_name": "Member PhaseA", "consent": True}, headers=MEMBER, timeout=T)
            assert s.status_code == 200, s.text
            r = requests.delete(f"{API}/documents/{did}", headers=ADMIN, timeout=T)
            assert r.status_code == 400
        finally:
            requests.put(f"{API}/documents/{did}/archive", json={"archived": True}, headers=ADMIN, timeout=T)

    def test_archive_toggle_hides_from_members(self):
        d = _mkdoc(audience="all_active")
        did = d["id"]
        try:
            assert did in _titles(_g(f"{API}/documents", MEMBER).json())
            r = requests.put(f"{API}/documents/{did}/archive", json={"archived": True}, headers=ADMIN, timeout=T)
            assert r.status_code == 200 and r.json()["status"] == "archived"
            assert did not in _titles(_g(f"{API}/documents", MEMBER).json()), "archived doc still visible to member"
            assert did in _titles(_g(f"{API}/documents").json()), "archived doc hidden from staff"
            r = requests.put(f"{API}/documents/{did}/archive", json={"archived": False}, headers=ADMIN, timeout=T)
            assert r.json()["status"] == "active"
            assert did in _titles(_g(f"{API}/documents", MEMBER).json())
        finally:
            _rm(did)

    def test_assignments_endpoint(self, memba_member):
        d = _mkdoc()
        did = d["id"]
        try:
            requests.post(f"{API}/documents/{did}/assign", json={"member_ids": [memba_member["id"]], "roles": ["volunteer"], "notify": False}, headers=ADMIN, timeout=T)
            r = _g(f"{API}/documents/{did}/assignments")
            assert r.status_code == 200, r.text
            j = r.json()
            assert set(["audience", "roles", "members", "history"]).issubset(j.keys())
            assert "volunteer" in j["roles"]
            ids = [m["id"] for m in j["members"]]
            assert memba_member["id"] in ids
            assert all("signed" in m for m in j["members"])
            assert any(h["action"] == "document_assigned" for h in j["history"]), j["history"]
            assert _g(f"{API}/documents/{did}/assignments", MEMBER).status_code == 403
        finally:
            _rm(did)


class TestIteration12Fixes:
    """Re-verification of the 6 fixes reported in iteration_12."""

    def test_sign_enforces_visibility_private_draft(self):
        d = _mkdoc()  # private_draft
        did = d["id"]
        try:
            s = requests.post(f"{API}/documents/{did}/sign", json={"legal_name": "Member PhaseA", "consent": True},
                              headers=MEMBER, timeout=T)
            assert s.status_code == 403, f"member signed an invisible private_draft: {s.status_code} {s.text[:200]}"
            sigs = _g(f"{API}/documents/{did}/signatures").json()
            assert len(sigs) == 0, f"signature row created despite 403: {sigs}"
        finally:
            _rm(did)

    def test_sign_enforces_visibility_admins_only(self):
        d = _mkdoc(audience="admins_only")
        did = d["id"]
        try:
            s = requests.post(f"{API}/documents/{did}/sign", json={"legal_name": "Member PhaseA", "consent": True},
                              headers=MEMBER, timeout=T)
            assert s.status_code == 403, f"member signed admins_only doc: {s.status_code}"
        finally:
            _rm(did)

    def test_sign_allowed_when_assigned(self, memba_member):
        d = _mkdoc()
        did = d["id"]
        try:
            a = requests.post(f"{API}/documents/{did}/assign",
                              json={"member_ids": [memba_member["id"]], "notify": False}, headers=ADMIN, timeout=T)
            assert a.status_code == 200, a.text
            s = requests.post(f"{API}/documents/{did}/sign", json={"legal_name": "Member PhaseA", "consent": True},
                              headers=MEMBER, timeout=T)
            assert s.status_code == 200, f"assigned member could not sign: {s.status_code} {s.text[:200]}"
            assert s.json()["document_id"] == did
            sigs = _g(f"{API}/documents/{did}/signatures").json()
            assert len(sigs) == 1
        finally:
            _db().signatures.delete_many({"document_id": did})
            _rm(did)

    def test_partial_put_preserves_audience_and_assignments(self, memba_member):
        d = _mkdoc(audience="specific_members", assigned_to=[memba_member["id"]], assigned_roles=["ambassador"])
        did = d["id"]
        try:
            r = requests.put(f"{API}/documents/{did}", json={"title": "TEST_partial_edit", "category": "Policy"},
                             headers=ADMIN, timeout=T)
            assert r.status_code == 200, r.text
            got = _g(f"{API}/documents/{did}").json()
            assert got["title"] == "TEST_partial_edit"
            assert got["category"] == "Policy"
            assert got["audience"] == "specific_members", f"audience wiped: {got['audience']}"
            assert got["assigned_to"] == [memba_member["id"]], f"assigned_to wiped: {got['assigned_to']}"
            assert got["assigned_roles"] == ["ambassador"], f"assigned_roles wiped: {got['assigned_roles']}"
            # member still has access
            assert _g(f"{API}/documents/{did}", MEMBER).status_code == 200
        finally:
            _rm(did)

    def test_full_object_put_still_works(self):
        d = _mkdoc()
        did = d["id"]
        try:
            body = dict(d)
            body.update({"title": "TEST_full_put", "audience": "all_active", "assigned_roles": ["volunteer"], "version": "3.1"})
            r = requests.put(f"{API}/documents/{did}", json=body, headers=ADMIN, timeout=T)
            assert r.status_code == 200, r.text
            got = _g(f"{API}/documents/{did}").json()
            assert got["title"] == "TEST_full_put"
            assert got["audience"] == "all_active"
            assert got["assigned_roles"] == ["volunteer"]
            assert got["version"] == "3.1"
        finally:
            _rm(did)

    def test_invalid_audience_rejected_on_create(self):
        r = requests.post(f"{API}/documents", json={"title": "TEST_bogus_aud", "category": "Onboarding", "audience": "bogus"},
                          headers=ADMIN, timeout=T)
        assert r.status_code == 400, f"expected 400 got {r.status_code} {r.text[:200]}"
        if r.status_code == 200:
            _rm(r.json()["id"])

    def test_invalid_audience_rejected_on_edit(self):
        d = _mkdoc()
        did = d["id"]
        try:
            r = requests.put(f"{API}/documents/{did}", json={"title": d["title"], "category": "Onboarding", "audience": "bogus"},
                             headers=ADMIN, timeout=T)
            assert r.status_code == 400, f"expected 400 got {r.status_code}"
            assert _g(f"{API}/documents/{did}").json()["audience"] == "private_draft"
        finally:
            _rm(did)

    def test_archive_nonexistent_404(self):
        r = requests.put(f"{API}/documents/doc_does_not_exist_zz/archive", json={"archived": True}, headers=ADMIN, timeout=T)
        assert r.status_code == 404, f"expected 404 got {r.status_code} {r.text[:200]}"

    def test_delete_blocked_when_assigned_roles_present(self):
        d = _mkdoc()
        did = d["id"]
        try:
            r = requests.put(f"{API}/documents/{did}", json={"title": d["title"], "category": "Onboarding",
                                                            "assigned_roles": ["ambassador"]}, headers=ADMIN, timeout=T)
            assert r.status_code == 200, r.text
            got = _g(f"{API}/documents/{did}").json()
            assert got["assigned_roles"] == ["ambassador"] and got["audience"] == "private_draft"
            dl = requests.delete(f"{API}/documents/{did}", headers=ADMIN, timeout=T)
            assert dl.status_code == 400, f"deleted a role-assigned doc: {dl.status_code}"
            assert "archive" in dl.json().get("detail", "").lower()
            assert _g(f"{API}/documents/{did}").status_code == 200
        finally:
            _rm(did)

    def test_convert_non_approved_application_400(self):
        app_body = {"type": "ambassador", "data": {"first_name": "TEST_NotApproved", "last_name": "Ambassador",
                                                  "email": "delivered@resend.dev", "phone": "4045551213",
                                                  "state": "GA", "city": "Atlanta"}}
        r = requests.post(f"{API}/public/applications", json=app_body, timeout=T)
        assert r.status_code == 200, r.text
        app_id = r.json()["id"]
        try:
            got = _g(f"{API}/applications/{app_id}").json()
            assert got["status"] == "New", got["status"]
            c = requests.post(f"{API}/applications/{app_id}/convert", headers=ADMIN, timeout=T)
            assert c.status_code == 400, f"converted a non-approved app: {c.status_code} {c.text[:200]}"
            # no member created
            mem = _db().members.find_one({"source_application": app_id})
            assert mem is None, "member created despite 400"
        finally:
            db_ = _db()
            db_.applications.delete_many({"id": app_id})
            db_.members.delete_many({"source_application": app_id})


# ---------------- Phase F ----------------
class TestOnboardingAutoAssign:
    def test_convert_assigns_ambassador_docs_and_sends_welcome(self):
        amb_doc = _mkdoc(audience="ambassadors_only", auto_onboarding=True, onboarding_profiles=["ambassador"])
        vol_doc = _mkdoc(audience="volunteers_only", auto_onboarding=True, onboarding_profiles=["volunteer"])
        email = "delivered@resend.dev"
        app_body = {"type": "ambassador", "data": {"first_name": "TEST_Convert", "last_name": "Ambassador",
                                                  "email": email, "phone": "4045551212", "state": "GA", "city": "Atlanta"}}
        r = requests.post(f"{API}/public/applications", json=app_body, timeout=T)
        assert r.status_code == 200, r.text
        app_id = r.json()["id"]
        member_id = None
        try:
            rs = requests.put(f"{API}/applications/{app_id}/status", json={"status": "Approved"}, headers=ADMIN, timeout=T)
            assert rs.status_code == 200, rs.text
            c = requests.post(f"{API}/applications/{app_id}/convert", headers=ADMIN, timeout=T)
            assert c.status_code == 200, c.text
            member = c.json()
            member_id = member["id"]
            assert member["role"] == "ambassador"

            asg = _g(f"{API}/documents/{amb_doc['id']}/assignments").json()
            assert member_id in [m["id"] for m in asg["members"]], "onboarding doc not auto-assigned"
            assert any(h["action"] == "onboarding_doc_assigned" for h in asg["history"])

            vasg = _g(f"{API}/documents/{vol_doc['id']}/assignments").json()
            assert member_id not in [m["id"] for m in vasg["members"]], "volunteer-only doc wrongly assigned to ambassador"

            logs = _db().email_log.find({"template": "welcome", "related_id": member_id}).sort("created_at", -1)
            mine = list(logs)
            assert mine, "no welcome email logged in email_log"
            assert mine[0].get("status") == "sent", f"welcome email status={mine[0].get('status')} err={mine[0].get('error')}"
            assert mine[0].get("to") == email
        finally:
            d = _db()
            if member_id:
                d.members.delete_many({"id": member_id})
                d.email_log.delete_many({"related_id": member_id})
            d.applications.delete_many({"id": app_id})
            _rm(amb_doc["id"])
            _rm(vol_doc["id"])


# ---------------- Phase G ----------------
def _assignees(ids):
    r = requests.put(f"{API}/events/{EVT}/checkin-assignees", json={"user_ids": ids}, headers=ADMIN, timeout=T)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def reg():
    r = _g(f"{API}/events/{EVT}/registrations")
    assert r.status_code == 200, r.text
    j = r.json()
    items = j if isinstance(j, list) else (j.get("registrations") or j.get("items") or [])
    items = [x for x in items if x.get("checkin_token")]
    assert items, "no registration with checkin_token"
    return items[0]


class TestCheckinVolunteerPerms:
    def test_before_assignment_403(self, reg):
        _assignees([])
        assert _g(f"{API}/registrations/lookup", MEMBER, params={"token": reg["checkin_token"]}).status_code == 403
        r = requests.put(f"{API}/registrations/{reg['id']}/checkin", json={"checked_in": True}, headers=MEMBER, timeout=T)
        assert r.status_code == 403, r.text

    def test_after_assignment_200_and_boundaries(self, reg):
        try:
            out = _assignees(["user_memba"])
            assert out["checkin_assignees"] == ["user_memba"]
            lk = _g(f"{API}/registrations/lookup", MEMBER, params={"token": reg["checkin_token"]})
            assert lk.status_code == 200, lk.text
            assert lk.json()["registration"]["id"] == reg["id"]
            ci = requests.put(f"{API}/registrations/{reg['id']}/checkin", json={"checked_in": True}, headers=MEMBER, timeout=T)
            assert ci.status_code == 200, ci.text
            # persistence
            lk2 = _g(f"{API}/registrations/lookup", MEMBER, params={"token": reg["checkin_token"]})
            assert lk2.json()["already_checked_in"] is True
            # boundaries: cannot edit, cannot export
            ed = requests.put(f"{API}/registrations/{reg['id']}", json={"job_title": "TEST_hack"}, headers=MEMBER, timeout=T)
            assert ed.status_code == 403, f"volunteer could edit registration: {ed.status_code}"
            ex = _g(f"{API}/events/{EVT}/export", MEMBER, params={"format": "csv"})
            assert ex.status_code == 403, f"volunteer could export: {ex.status_code}"
        finally:
            requests.put(f"{API}/registrations/{reg['id']}/checkin", json={"checked_in": False}, headers=ADMIN, timeout=T)
            _assignees([])

    def test_after_removal_403(self, reg):
        _assignees(["user_memba"])
        _assignees([])
        assert _g(f"{API}/registrations/lookup", MEMBER, params={"token": reg["checkin_token"]}).status_code == 403
        r = requests.put(f"{API}/registrations/{reg['id']}/checkin", json={"checked_in": True}, headers=MEMBER, timeout=T)
        assert r.status_code == 403

    def test_auto_expire_on_completed_event(self, reg):
        try:
            _assignees(["user_memba"])
            assert _g(f"{API}/registrations/lookup", MEMBER, params={"token": reg["checkin_token"]}).status_code == 200
            st = requests.put(f"{API}/events/{EVT}/status", json={"status": "Completed"}, headers=ADMIN, timeout=T)
            assert st.status_code == 200, st.text
            assert _g(f"{API}/registrations/lookup", MEMBER, params={"token": reg["checkin_token"]}).status_code == 403, "assignment not auto-expired on Completed"
            r = requests.put(f"{API}/registrations/{reg['id']}/checkin", json={"checked_in": True}, headers=MEMBER, timeout=T)
            assert r.status_code == 403
        finally:
            requests.put(f"{API}/events/{EVT}/status", json={"status": "Approved"}, headers=ADMIN, timeout=T)
            _assignees([])

    def test_member_cannot_set_assignees(self):
        r = requests.put(f"{API}/events/{EVT}/checkin-assignees", json={"user_ids": ["user_memba"]}, headers=MEMBER, timeout=T)
        assert r.status_code == 403, r.text

    def test_assignees_audit_logged(self):
        _assignees(["user_memba"])
        _assignees([])
        r = _g(f"{API}/audit-logs", params={"q": "checkin_assignees_set"})
        assert r.status_code == 200, r.text
        j = r.json()
        items = j if isinstance(j, list) else (j.get("items") or [])
        assert any(x.get("action") == "checkin_assignees_set" and x.get("related_id") == EVT for x in items), "no audit entry for checkin_assignees_set"


# ---------------- Regression: staff still full access ----------------
class TestStaffRegression:
    def test_staff_event_and_registration_ops(self, reg):
        assert _g(f"{API}/events/{EVT}").status_code == 200
        assert _g(f"{API}/events/{EVT}/registrations").status_code == 200
        assert _g(f"{API}/events/{EVT}/export", params={"format": "csv"}).status_code == 200
        assert _g(f"{API}/registrations/lookup", params={"token": reg["checkin_token"]}).status_code == 200
        r = requests.put(f"{API}/registrations/{reg['id']}", json={"job_title": "TEST_title"}, headers=ADMIN, timeout=T)
        assert r.status_code == 200, r.text

    def test_event_left_published(self):
        ev = _g(f"{API}/events/{EVT}").json()
        assert ev.get("status") in ("Approved", "Scheduled"), ev.get("status")
        assert not (ev.get("checkin_assignees") or []), "checkin_assignees not cleaned up"
