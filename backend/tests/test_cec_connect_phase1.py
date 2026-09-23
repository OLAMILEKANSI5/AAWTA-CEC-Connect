"""CEC Connect Phase 1: member->leadership messaging fix, signature notifications,
signers detail endpoint, notification categories, and staff regressions."""
import os, io, time, pytest, requests
from dotenv import dotenv_values

_env = dotenv_values("/app/frontend/.env")
_base = os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL")
assert _base, "REACT_APP_BACKEND_URL missing"
BASE = _base.rstrip('/') + '/api'
ADMIN = {"Authorization": "Bearer tok_admtest"}
AMB = {"Authorization": "Bearer tok_amb_g3test"}


def _get(path, headers=ADMIN, **kw):
    return requests.get(BASE + path, headers=headers, timeout=30, **kw)

def _post(path, json=None, headers=ADMIN, **kw):
    return requests.post(BASE + path, headers=headers, json=json, timeout=30, **kw)


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def leadership_ids():
    r = _get("/users")
    assert r.status_code == 200, r.text
    data = r.json()
    users = data.get("users") if isinstance(data, dict) else data
    lead = [u for u in users if u.get("role") in ("super_admin", "director", "administrator")
            and u.get("account_status") not in ("suspended", "deactivated")]
    ids = [u["user_id"] for u in lead]
    return ids

@pytest.fixture(scope="module")
def amb_user():
    r = _get("/auth/me", headers=AMB)
    assert r.status_code == 200, r.text
    return r.json()


STATE = {}


# ---------- Messages: member -> leadership routing ----------
class TestMemberMessaging:
    def test_member_can_send_without_recipients(self, leadership_ids, amb_user):
        subject = f"TEST_P1 Member ping {int(time.time())}"
        r = _post("/messages", {"subject": subject, "body": "Hello leadership from ambassador."},
                  headers=AMB)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["to_leadership"] is True
        assert data["from_id"] == amb_user["user_id"]
        # Excludes self
        assert amb_user["user_id"] not in data["recipient_ids"]
        # All recipients are leadership
        expected = set(leadership_ids) - {amb_user["user_id"]}
        assert set(data["recipient_ids"]) == expected, (data["recipient_ids"], expected)
        assert data.get("member_id"), "member_id should be set from linked member profile"
        STATE["thread_id"] = data["thread_id"]
        STATE["msg_id"] = data["id"]

    def test_member_message_creates_messages_category_notifications(self, leadership_ids, amb_user):
        r = _get("/notifications", headers=ADMIN)
        assert r.status_code == 200
        notes = r.json()
        matches = [n for n in notes if n.get("title", "").startswith("New message:") and n.get("category") == "Messages"]
        assert matches, "expected a Messages-category notification for admin"

    def test_leadership_can_view_thread(self):
        r = _get(f"/messages/{STATE['thread_id']}/thread", headers=ADMIN)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["thread_id"] == STATE["thread_id"]
        assert len(data["messages"]) >= 1

    def test_leadership_can_reply_and_member_sees_it(self, amb_user):
        r = _post(f"/messages/{STATE['thread_id']}/reply", {"body": "Thanks, we got it."}, headers=ADMIN)
        assert r.status_code == 200, r.text
        r2 = _get(f"/messages/{STATE['thread_id']}/thread", headers=AMB)
        assert r2.status_code == 200
        bodies = [m["body"] for m in r2.json()["messages"]]
        assert "Thanks, we got it." in bodies

    def test_member_without_subject_blocked_by_validation(self):
        r = _post("/messages", {"body": "no subject"}, headers=AMB)
        assert r.status_code in (400, 422)


# ---------- Staff regression: targeted messaging ----------
class TestStaffMessagingRegression:
    def test_staff_send_to_specific_recipient(self, amb_user):
        r = _post("/messages", {
            "subject": "TEST_P1 staff->member",
            "body": "hello",
            "recipient_ids": [amb_user["user_id"]],
        }, headers=ADMIN)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["to_leadership"] is False
        assert amb_user["user_id"] in d["recipient_ids"]

    def test_staff_requires_recipients(self):
        r = _post("/messages", {"subject": "TEST_P1 empty", "body": "x"}, headers=ADMIN)
        assert r.status_code == 400

    def test_staff_target_role(self):
        r = _post("/messages", {"subject": "TEST_P1 targeted role", "body": "ambassadors!",
                                "target_role": "ambassador"}, headers=ADMIN)
        assert r.status_code == 200
        d = r.json()
        assert len(d["recipient_ids"]) >= 1


# ---------- Signature notification + signers endpoint ----------
class TestSignFlow:
    @classmethod
    def setup_class(cls):
        # Create a document assigned to the ambassador's member profile.
        me = _get("/auth/me", headers=AMB).json()
        mm = requests.get(BASE + "/members", headers=ADMIN, timeout=30).json()
        mem = next((m for m in mm if m.get("user_id") == me["user_id"]), None)
        assert mem, "ambassador should have linked member profile"
        cls.member_id = mem["id"]
        # need a file_id: upload minimal PDF
        files = {"file": ("t.pdf", b"%PDF-1.4\n%TEST\n", "application/pdf")}
        r = requests.post(BASE + "/upload", headers=ADMIN, files=files, data={"category": "document"}, timeout=30)
        assert r.status_code == 200, r.text
        file_id = r.json()["id"]
        r = _post("/documents", {"title": f"TEST_P1 Doc {int(time.time())}", "category": "Policies",
                                 "file_id": file_id, "requires_signature": True,
                                 "assigned_to": [cls.member_id]}, headers=ADMIN)
        assert r.status_code == 200, r.text
        cls.doc_id = r.json()["id"]

    def test_signers_endpoint_pre_sign(self):
        r = _get(f"/documents/{self.doc_id}/signers", headers=ADMIN)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "signed" in data and "pending" in data and "file_id" in data
        assert data["signed"] == []
        assert any(p["member_id"] == self.member_id for p in data["pending"])

    def test_signers_non_staff_forbidden(self):
        r = _get(f"/documents/{self.doc_id}/signers", headers=AMB)
        assert r.status_code == 403

    def test_sign_creates_leadership_signatures_notifications(self, leadership_ids, amb_user):
        # baseline
        r = _get("/notifications", headers=ADMIN)
        before = len([n for n in r.json() if n.get("category") == "Signatures"])
        r = _post(f"/documents/{self.doc_id}/sign", {"legal_name": "Amb Test", "consent": True},
                  headers=AMB)
        assert r.status_code == 200, r.text
        # Notification appears for admin
        r = _get("/notifications", headers=ADMIN)
        sig_notes = [n for n in r.json() if n.get("category") == "Signatures"]
        assert len(sig_notes) >= before + 1
        latest = sig_notes[0]
        assert latest["title"] == "Document signed"
        assert f"/portal/members/{self.member_id}" == latest["link"]

    def test_signers_endpoint_after_sign(self, amb_user):
        r = _get(f"/documents/{self.doc_id}/signers", headers=ADMIN)
        assert r.status_code == 200
        data = r.json()
        sig_uids = [s.get("member_id") for s in data["signed"]]
        assert self.member_id in sig_uids
        entry = next(s for s in data["signed"] if s.get("member_id") == self.member_id)
        for k in ("name", "role", "member_id", "signed_at", "legal_name", "signature_id"):
            assert k in entry, f"missing {k}"
        assert all(p["member_id"] != self.member_id for p in data["pending"])


# ---------- Notifications feed / bell ----------
class TestNotificationsBell:
    def test_list_returns_category_field(self):
        r = _get("/notifications", headers=ADMIN)
        assert r.status_code == 200
        notes = r.json()
        assert isinstance(notes, list) and notes
        # At least one should have category set (Messages or Signatures)
        cats = {n.get("category") for n in notes}
        assert cats & {"Messages", "Signatures"}, cats

    def test_mark_read_and_read_all(self):
        r = _get("/notifications", headers=ADMIN)
        notes = r.json()
        unread = next((n for n in notes if not n.get("read")), None)
        if unread:
            r2 = _post(f"/notifications/{unread['id']}/read", headers=ADMIN)
            assert r2.status_code == 200
        r3 = _post("/notifications/read-all", headers=ADMIN)
        assert r3.status_code == 200
        r4 = _get("/notifications", headers=ADMIN)
        assert all(n.get("read") for n in r4.json())
