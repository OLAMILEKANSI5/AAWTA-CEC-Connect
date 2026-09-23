"""Group 1 regression: Notification Templates + Communications APIs.
Exercises list/get/update/preview/test-send for templates and preview/send/list for comms.
"""
import os
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://ambassador-hub-29.preview.emergentagent.com"
API = BASE + "/api"
ADMIN_TOKEN = "tok_admtest"  # super_admin
HDRS = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}

EXPECTED_KEYS = {
    "application_received", "application_approved", "onboarding_profile",
    "missing_requirements", "onboarding_reminder", "fully_onboarded_welcome",
    "volunteer_event_assignment", "ambassador_update", "general_communication",
}


# ---------------- notification templates ----------------
class TestNotificationTemplates:
    def test_list_returns_nine_templates(self):
        r = requests.get(f"{API}/notification-templates", headers=HDRS, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "templates" in d and "placeholders" in d
        keys = {t["key"] for t in d["templates"]}
        assert keys == EXPECTED_KEYS, f"got {keys}"
        # placeholders is a non-empty list of strings
        assert isinstance(d["placeholders"], list) and len(d["placeholders"]) > 0
        assert "first_name" in d["placeholders"]

    def test_each_template_has_required_fields(self):
        r = requests.get(f"{API}/notification-templates", headers=HDRS, timeout=30)
        for t in r.json()["templates"]:
            for f in ("key", "name", "subject", "body", "mode", "enabled", "category"):
                assert f in t, f"missing {f} in {t.get('key')}"
            assert t["mode"] in ("automatic", "manual")

    def test_get_template_by_key(self):
        r = requests.get(f"{API}/notification-templates/application_received", headers=HDRS, timeout=30)
        assert r.status_code == 200
        t = r.json()
        assert t["key"] == "application_received"
        assert "{{ref}}" in t["subject"] or "{{first_name}}" in t["body"]

    def test_get_unknown_template_404(self):
        r = requests.get(f"{API}/notification-templates/does_not_exist", headers=HDRS, timeout=30)
        assert r.status_code == 404

    def test_update_template_persists(self):
        key = "ambassador_update"
        orig = requests.get(f"{API}/notification-templates/{key}", headers=HDRS).json()
        new_subject = f"TEST subject {int(time.time())}"
        r = requests.put(f"{API}/notification-templates/{key}", headers=HDRS,
                         json={"subject": new_subject, "enabled": True, "include_button": False,
                               "button_label": "", "mode": "manual"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["subject"] == new_subject
        assert r.json().get("updated_by")
        # verify GET reflects change
        got = requests.get(f"{API}/notification-templates/{key}", headers=HDRS).json()
        assert got["subject"] == new_subject
        # restore
        requests.put(f"{API}/notification-templates/{key}", headers=HDRS,
                     json={"subject": orig["subject"]}, timeout=30)

    def test_update_invalid_mode_400(self):
        r = requests.put(f"{API}/notification-templates/general_communication", headers=HDRS,
                         json={"mode": "invalid_mode"}, timeout=30)
        assert r.status_code == 400

    def test_update_unknown_key_404(self):
        r = requests.put(f"{API}/notification-templates/nope_key", headers=HDRS,
                         json={"subject": "x"}, timeout=30)
        assert r.status_code == 404

    def test_preview_renders_sample_context(self):
        r = requests.post(f"{API}/notification-templates/application_received/preview",
                          headers=HDRS, json={}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "subject" in d and "html" in d
        # sample ctx substitutes ref + first_name
        assert "{{" not in d["subject"], "unsubstituted placeholder in subject"
        assert "Jordan" in d["html"] or "AMB-2026" in d["html"] or "Ambassador" in d["html"]

    def test_preview_unknown_404(self):
        r = requests.post(f"{API}/notification-templates/nope/preview", headers=HDRS, json={}, timeout=30)
        assert r.status_code == 404

    def test_test_send_sandbox_delivered(self):
        r = requests.post(f"{API}/notification-templates/general_communication/test-send",
                          headers=HDRS, json={"to": "delivered@resend.dev"}, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("status") == "sent", d


# ---------------- communications ----------------
def _get_first_application_id():
    r = requests.get(f"{API}/applications?limit=5", headers=HDRS, timeout=30)
    assert r.status_code == 200
    apps = r.json()
    assert apps, "no applications seeded"
    # prefer one with a real deliverable email
    for a in apps:
        if a.get("email") and "resend.dev" in a["email"]:
            return a["id"], a["email"]
    return apps[0]["id"], apps[0].get("email")


class TestCommunications:
    app_id = None
    app_email = None

    @classmethod
    def setup_class(cls):
        cls.app_id, cls.app_email = _get_first_application_id()

    def test_comm_preview_returns_subst(self):
        r = requests.post(f"{API}/comms/preview", headers=HDRS,
                          json={"subject_type": "application", "subject_id": self.app_id,
                                "template_key": "application_received"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "subject" in d and "body" in d
        assert "{{" not in d["subject"] and "{{" not in d["body"]

    def test_comm_preview_invalid_subject_type(self):
        r = requests.post(f"{API}/comms/preview", headers=HDRS,
                          json={"subject_type": "widget", "subject_id": "x",
                                "template_key": "application_received"}, timeout=30)
        assert r.status_code == 400

    def test_comm_preview_unknown_template_404(self):
        r = requests.post(f"{API}/comms/preview", headers=HDRS,
                          json={"subject_type": "application", "subject_id": self.app_id,
                                "template_key": "no_such"}, timeout=30)
        assert r.status_code == 404

    def test_comm_send_email_and_history(self):
        # preview -> send
        prev = requests.post(f"{API}/comms/preview", headers=HDRS,
                             json={"subject_type": "application", "subject_id": self.app_id,
                                   "template_key": "general_communication"}, timeout=30).json()
        r = requests.post(f"{API}/comms/send", headers=HDRS,
                          json={"subject_type": "application", "subject_id": self.app_id,
                                "template_key": "general_communication",
                                "subject": prev["subject"] or "TEST subject",
                                "body": (prev["body"] or "Hello there.") + "\nTEST message.",
                                "channel": "email"}, timeout=60)
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["channel"] == "email"
        assert rec["subject_id"] == self.app_id
        assert rec["status"] in ("sent", "delivered", "failed")
        # history
        h = requests.get(f"{API}/comms?subject_type=application&subject_id={self.app_id}", headers=HDRS, timeout=30)
        assert h.status_code == 200
        rows = h.json()
        assert any(r2["id"] == rec["id"] for r2 in rows)
        # newest first
        if len(rows) > 1:
            assert rows[0]["created_at"] >= rows[-1]["created_at"]

    def test_comm_send_invalid_channel_400(self):
        r = requests.post(f"{API}/comms/send", headers=HDRS,
                          json={"subject_type": "application", "subject_id": self.app_id,
                                "subject": "x", "body": "y", "channel": "carrier_pigeon"}, timeout=30)
        assert r.status_code == 400

    def test_comm_send_empty_subject_400(self):
        r = requests.post(f"{API}/comms/send", headers=HDRS,
                          json={"subject_type": "application", "subject_id": self.app_id,
                                "subject": "  ", "body": "hello", "channel": "email"}, timeout=30)
        assert r.status_code == 400

    def test_comm_send_empty_body_400(self):
        r = requests.post(f"{API}/comms/send", headers=HDRS,
                          json={"subject_type": "application", "subject_id": self.app_id,
                                "subject": "s", "body": "", "channel": "email"}, timeout=30)
        assert r.status_code == 400

    def test_comm_send_invalid_subject_type_400(self):
        r = requests.post(f"{API}/comms/send", headers=HDRS,
                          json={"subject_type": "widget", "subject_id": "x",
                                "subject": "s", "body": "b", "channel": "email"}, timeout=30)
        assert r.status_code == 400

    def test_comm_send_portal_channel(self):
        r = requests.post(f"{API}/comms/send", headers=HDRS,
                          json={"subject_type": "application", "subject_id": self.app_id,
                                "subject": "Portal-only test", "body": "Body",
                                "channel": "portal"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["channel"] == "portal"

    def test_comm_send_email_no_email_on_record_400(self):
        # find or create app without email — try one with no email
        apps = requests.get(f"{API}/applications?limit=50", headers=HDRS).json()
        target = next((a for a in apps if not a.get("email")), None)
        if not target:
            pytest.skip("no application without email available")
        r = requests.post(f"{API}/comms/send", headers=HDRS,
                          json={"subject_type": "application", "subject_id": target["id"],
                                "subject": "s", "body": "b", "channel": "email"}, timeout=30)
        assert r.status_code == 400


# ---------------- auth / role checks ----------------
class TestAuthGates:
    def test_unauth_list_templates_401(self):
        r = requests.get(f"{API}/notification-templates", timeout=30)
        assert r.status_code in (401, 403)

    def test_unauth_list_comms_401(self):
        r = requests.get(f"{API}/comms?subject_type=application&subject_id=x", timeout=30)
        assert r.status_code in (401, 403)
