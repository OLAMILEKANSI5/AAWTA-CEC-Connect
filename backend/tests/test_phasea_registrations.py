"""Phase A: public event registration, emails, payments, QR, manage/cancel, consents, authz, webhook."""
import os
import time
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE = base_url.rstrip("/") + "/api"

backend_env = dotenv_values("/app/backend/.env")
MONGO_URL = os.environ.get("MONGO_URL") or backend_env.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or backend_env.get("DB_NAME")

ADMIN_TOKEN = "tok_admtest"
MEMBER_TOKEN = "tok_memba"
FREE_EVENT = "evt_246d20a66b31"
FULL_EVENT = "evt_badgetest"
TAG = uuid.uuid4().hex[:8]
EMAIL_WAIT = 8


def mkemail(label):
    return f"TEST_phasea_{label}_{TAG}@example.com"


def payload(label, **over):
    d = {
        "first_name": "TESTFirst", "last_name": "TESTLast", "email": mkemail(label),
        "phone": "404-555-0111", "state": "GA", "is_member": True,
        "ticket_category": "General Admission",
    }
    d.update(over)
    return d


@pytest.fixture(scope="session")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"})
    r = s.get(f"{BASE}/auth/me", timeout=30)
    if r.status_code != 200:
        pytest.fail(f"admin session invalid ({r.status_code}): {r.text[:300]} - run seed_badge.py")
    return s


@pytest.fixture(scope="session")
def member():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {MEMBER_TOKEN}", "Content-Type": "application/json"})
    r = s.get(f"{BASE}/auth/me", timeout=30)
    if r.status_code != 200:
        pytest.fail(f"member session invalid ({r.status_code}) - run seed_phasea.py")
    return s


@pytest.fixture(scope="session")
def anon():
    return requests.Session()


@pytest.fixture(scope="session", autouse=True)
def cleanup(mongo):
    yield
    regs = list(mongo.event_registrations.find({"email": {"$regex": f"phasea_.*{TAG}|delivered\\+{TAG}"}}, {"id": 1}))
    ids = [r["id"] for r in regs]
    evs = list(mongo.events.find({"name": {"$regex": f"^TEST_PhaseA.*{TAG}"}}, {"id": 1}))
    ev_ids = [e["id"] for e in evs]
    ids += [r["id"] for r in mongo.event_registrations.find({"event_id": {"$in": ev_ids}}, {"id": 1})]
    if ids:
        mongo.event_registrations.delete_many({"id": {"$in": ids}})
        mongo.email_log.delete_many({"related_id": {"$in": ids}})
        mongo.consents.delete_many({"reg_id": {"$in": ids}})
    if ev_ids:
        mongo.events.delete_many({"id": {"$in": ev_ids}})


def register(sess, event_id, body, expect=200):
    r = sess.post(f"{BASE}/public/events/{event_id}/register", json=body, timeout=60)
    assert r.status_code == expect, f"{r.status_code}: {r.text[:400]}"
    return r


def emails(admin_s, reg_id, expect=200):
    r = admin_s.get(f"{BASE}/registrations/{reg_id}/emails", timeout=30)
    assert r.status_code == expect, f"{r.status_code}: {r.text[:300]}"
    return r.json() if expect == 200 else r


def wait_for_email(admin_s, reg_id, template, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        logs = emails(admin_s, reg_id)
        hit = [l for l in logs if l["template"] == template]
        if hit:
            return hit[0]
        time.sleep(2)
    logs = emails(admin_s, reg_id)
    pytest.fail(f"email template '{template}' not logged for {reg_id}; got {[l['template'] for l in logs]}")


# ---------------- free event registration ----------------
class TestFreeRegistration:
    def test_register_full_payload_and_persistence(self, anon, admin, mongo):
        body = payload("full", business_name="TEST Acme Co", business_website="acme.com",
                       job_title="CEO", city="Atlanta", zip_code="30303",
                       dietary="Vegan", accessibility="Wheelchair",
                       newsletter_opt_in=True, events_opt_in=True)
        data = register(anon, FREE_EVENT, body).json()
        assert data["status"] == "registered"
        assert data["id"].startswith("reg_")
        assert data["confirmation_number"].startswith("CEC-")
        assert len(data["confirmation_number"]) == 12

        reg = mongo.event_registrations.find_one({"id": data["id"]}, {"_id": 0})
        assert reg["business_website"] == "https://acme.com", "website not normalized"
        assert reg["first_name"] == "TESTFirst" and reg["last_name"] == "TESTLast"
        assert reg["name"] == "TESTFirst TESTLast"
        assert reg["email"] == body["email"].lower()
        assert reg["payment_status"] == "not_applicable"
        assert reg["ticket_category"] == "General Admission"
        assert reg["dietary"] == "Vegan" and reg["accessibility"] == "Wheelchair"
        assert reg["badge_category"] == "Member"
        assert reg["checkin_token"] and reg["source"] == "online"

        # consents stored for both opt-ins
        cons = list(mongo.consents.find({"reg_id": data["id"]}, {"_id": 0}))
        assert sorted(c["type"] for c in cons) == ["events", "newsletter"]
        for c in cons:
            assert c["granted"] is True and c["granted_at"]
            assert c["source"] == "online registration"
            assert c["event_id"] == FREE_EVENT
            assert c["opted_out_at"] is None

    def test_optins_default_false_and_no_consents(self, anon, mongo):
        data = register(anon, FREE_EVENT, payload("nooptin")).json()
        reg = mongo.event_registrations.find_one({"id": data["id"]}, {"_id": 0})
        assert reg["newsletter_opt_in"] is False and reg["events_opt_in"] is False
        assert mongo.consents.count_documents({"reg_id": data["id"]}) == 0

    def test_confirmation_email_sent_with_correct_subject(self, anon, admin, mongo):
        addr = f"delivered+{TAG}@resend.dev"
        data = register(anon, FREE_EVENT, payload("del", email=addr)).json()
        log = wait_for_email(admin, data["id"], "registration_confirmation")
        assert log["subject"] == "Registration Confirmed: Phase A Test Event", log["subject"]
        assert log["status"] == "sent", f"expected sent, got {log['status']} err={log.get('error')}"
        assert log["provider_id"], "no provider id returned"
        assert log["sent_at"]
        reg = mongo.event_registrations.find_one({"id": data["id"]}, {"_id": 0})
        assert reg["confirmation_sent"] is True
        assert reg["confirmation_status"] == "sent"

    def test_duplicate_registration_rejected(self, anon):
        body = payload("dup")
        register(anon, FREE_EVENT, body)
        register(anon, FREE_EVENT, body, expect=400)
        body2 = dict(body, email=body["email"].upper())
        register(anon, FREE_EVENT, body2, expect=400)

    def test_honeypot_rejected(self, anon, mongo):
        body = payload("honey", honeypot="http://spam.example")
        register(anon, FREE_EVENT, body, expect=400)
        assert mongo.event_registrations.count_documents({"email": body["email"]}) == 0

    def test_missing_required_field_422(self, anon):
        body = payload("req")
        body.pop("ticket_category")
        register(anon, FREE_EVENT, body, expect=422)
        body2 = payload("req2")
        body2.pop("state")
        register(anon, FREE_EVENT, body2, expect=422)

    def test_unknown_event_404(self, anon):
        register(anon, "evt_does_not_exist", payload("nf"), expect=404)


# ---------------- waitlist ----------------
class TestWaitlist:
    def test_full_event_goes_to_waitlist_with_waitlist_email(self, anon, admin):
        data = register(anon, FULL_EVENT, payload("wl")).json()
        assert data["status"] == "waitlist"
        log = wait_for_email(admin, data["id"], "waitlist")
        assert "waitlist" in log["subject"].lower()
        all_logs = emails(admin, data["id"])
        assert not [l for l in all_logs if l["template"] == "registration_confirmation"], \
            "waitlisted attendee received a confirmation email"


# ---------------- paid event flow ----------------
@pytest.fixture(scope="class")
def paid_event(admin):
    body = {"name": f"TEST_PhaseA Paid {TAG}", "date": "2026-12-01", "start_time": "6:00 PM",
            "category": "Networking", "format": "In-person", "city": "Atlanta", "state": "GA",
            "capacity": 20, "is_paid": True, "price": "25", "ticket_url": "tickets.example.com",
            "ticket_categories": ["General Admission", "VIP"], "allow_cancellation": True}
    r = admin.post(f"{BASE}/events", json=body, timeout=30)
    assert r.status_code == 200, r.text[:300]
    ev = r.json()
    assert "_id" not in ev
    p = admin.put(f"{BASE}/events/{ev['id']}/publish", json={"published": True}, timeout=30)
    assert p.status_code == 200, p.text[:300]
    return ev["id"]


class TestPaidFlow:
    def test_pending_payment_on_register(self, anon, admin, mongo, paid_event):
        data = register(anon, paid_event, payload("paid1")).json()
        assert data["status"] == "registered"
        reg = mongo.event_registrations.find_one({"id": data["id"]}, {"_id": 0})
        assert reg["payment_status"] == "pending"
        assert reg["confirmation_sent"] is False
        log = wait_for_email(admin, data["id"], "pending_payment")
        assert log["subject"].startswith("Payment Pending:")
        assert not [l for l in emails(admin, data["id"]) if l["template"] == "registration_confirmation"], \
            "confirmation sent before payment"

    def test_mark_paid_sends_confirmation_once(self, anon, admin, mongo, paid_event):
        data = register(anon, paid_event, payload("paid2")).json()
        rid = data["id"]
        wait_for_email(admin, rid, "pending_payment")

        r = admin.put(f"{BASE}/registrations/{rid}/payment", json={"payment_status": "paid", "note": "TEST paid"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        out = r.json()
        assert "_id" not in out
        assert out["payment_status"] == "paid"
        assert out["confirmation_sent"] is True
        hist = out["payment_history"]
        assert len(hist) == 1
        assert hist[0]["from"] == "pending" and hist[0]["to"] == "paid"
        assert hist[0]["by"] and hist[0]["at"]

        confs = [l for l in emails(admin, rid) if l["template"] == "registration_confirmation"]
        assert len(confs) == 1
        assert confs[0]["subject"] == f"Registration Confirmed: TEST_PhaseA Paid {TAG}"

        # repeat -> no duplicate confirmation
        r2 = admin.put(f"{BASE}/registrations/{rid}/payment", json={"payment_status": "paid"}, timeout=60)
        assert r2.status_code == 200
        time.sleep(3)
        confs2 = [l for l in emails(admin, rid) if l["template"] == "registration_confirmation"]
        assert len(confs2) == 1, f"duplicate confirmation sent: {len(confs2)}"
        # repeating the same status is a no-op: history only records actual transitions
        assert len(r2.json()["payment_history"]) == 1

    def test_complimentary_sends_confirmation(self, anon, admin, paid_event):
        data = register(anon, paid_event, payload("comp")).json()
        rid = data["id"]
        wait_for_email(admin, rid, "pending_payment")
        r = admin.put(f"{BASE}/registrations/{rid}/payment", json={"payment_status": "complimentary"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["payment_status"] == "complimentary"
        assert r.json()["confirmation_sent"] is True
        confs = [l for l in emails(admin, rid) if l["template"] == "registration_confirmation"]
        assert len(confs) == 1

    def test_invalid_payment_status_400(self, anon, admin, paid_event):
        rid = register(anon, paid_event, payload("badstatus")).json()["id"]
        r = admin.put(f"{BASE}/registrations/{rid}/payment", json={"payment_status": "bogus"}, timeout=30)
        assert r.status_code == 400, r.status_code

    def test_payment_unknown_registration_404(self, admin):
        r = admin.put(f"{BASE}/registrations/reg_nope/payment", json={"payment_status": "paid"}, timeout=30)
        assert r.status_code == 404


# ---------------- resend ----------------
class TestResend:
    def test_resend_confirmation(self, anon, admin, mongo):
        rid = register(anon, FREE_EVENT, payload("resend")).json()["id"]
        wait_for_email(admin, rid, "registration_confirmation")
        before = len(emails(admin, rid))
        r = admin.post(f"{BASE}/registrations/{rid}/resend-confirmation", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert "status" in r.json()
        reg = mongo.event_registrations.find_one({"id": rid}, {"_id": 0})
        assert reg["resend_count"] == 1
        assert reg["last_resend_at"]
        assert len(emails(admin, rid)) == before + 1


# ---------------- QR ----------------
class TestQR:
    def test_qr_png_and_404(self, anon, mongo):
        rid = register(anon, FREE_EVENT, payload("qr")).json()["id"]
        reg = mongo.event_registrations.find_one({"id": rid}, {"_id": 0})
        r = anon.get(f"{BASE}/public/qr/{reg['checkin_token']}.png", timeout=30)
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(r.content) > 100
        bad = anon.get(f"{BASE}/public/qr/notarealtoken.png", timeout=30)
        assert bad.status_code == 404


# ---------------- public manage + cancel ----------------
class TestPublicManage:
    def test_manage_detail_and_wrong_token(self, anon, mongo):
        data = register(anon, FREE_EVENT, payload("manage")).json()
        reg = mongo.event_registrations.find_one({"id": data["id"]}, {"_id": 0})
        conf, tok = data["confirmation_number"], reg["checkin_token"]
        r = anon.get(f"{BASE}/public/registrations/{conf}", params={"token": tok}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        j = r.json()
        assert j["registration"]["confirmation_number"] == conf
        assert j["registration"]["status"] == "registered"
        assert j["registration"]["checkin_token"] == tok
        assert j["event"]["id"] == FREE_EVENT
        assert j["event"]["name"] == "Phase A Test Event"
        assert j["event"]["allow_cancellation"] is True
        assert anon.get(f"{BASE}/public/registrations/{conf}", params={"token": "wrong"}, timeout=30).status_code == 404
        assert anon.get(f"{BASE}/public/registrations/CEC-XXXXXXXX", params={"token": tok}, timeout=30).status_code == 404

    def test_cancel_then_reregister(self, anon, mongo):
        body = payload("cancel")
        data = register(anon, FREE_EVENT, body).json()
        reg = mongo.event_registrations.find_one({"id": data["id"]}, {"_id": 0})
        conf, tok = data["confirmation_number"], reg["checkin_token"]
        bad = anon.post(f"{BASE}/public/registrations/{conf}/cancel", json={"token": "wrong"}, timeout=30)
        assert bad.status_code == 404
        r = anon.post(f"{BASE}/public/registrations/{conf}/cancel", json={"token": tok}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["status"] == "cancelled"
        det = anon.get(f"{BASE}/public/registrations/{conf}", params={"token": tok}, timeout=30).json()
        assert det["registration"]["status"] == "cancelled"
        # same email can register again
        again = register(anon, FREE_EVENT, body).json()
        assert again["confirmation_number"] != conf

    def test_cancel_blocked_when_not_allowed(self, anon, admin, mongo):
        body = {"name": f"TEST_PhaseA NoCancel {TAG}", "date": "2026-12-05", "capacity": 10,
                "allow_cancellation": False, "city": "Atlanta", "state": "GA"}
        ev = admin.post(f"{BASE}/events", json=body, timeout=30).json()
        admin.put(f"{BASE}/events/{ev['id']}/publish", json={"published": True}, timeout=30)
        data = register(anon, ev["id"], payload("nocancel")).json()
        reg = mongo.event_registrations.find_one({"id": data["id"]}, {"_id": 0})
        r = anon.post(f"{BASE}/public/registrations/{data['confirmation_number']}/cancel",
                      json={"token": reg["checkin_token"]}, timeout=30)
        assert r.status_code == 400, f"{r.status_code}: {r.text[:200]}"


# ---------------- authorization ----------------
class TestAuthorization:
    @pytest.fixture(scope="class")
    def reg_id(self, anon):
        return register(anon, FREE_EVENT, payload("authz")).json()["id"]

    def test_anonymous_401(self, anon, reg_id):
        assert anon.get(f"{BASE}/registrations/{reg_id}/emails", timeout=30).status_code == 401
        assert anon.put(f"{BASE}/registrations/{reg_id}/payment", json={"payment_status": "paid"}, timeout=30).status_code == 401
        assert anon.post(f"{BASE}/registrations/{reg_id}/resend-confirmation", timeout=30).status_code == 401

    def test_non_owner_member_403(self, member, reg_id):
        assert member.get(f"{BASE}/registrations/{reg_id}/emails", timeout=30).status_code == 403
        assert member.put(f"{BASE}/registrations/{reg_id}/payment", json={"payment_status": "paid"}, timeout=30).status_code == 403
        assert member.post(f"{BASE}/registrations/{reg_id}/resend-confirmation", timeout=30).status_code == 403

    def test_public_endpoints_need_no_auth(self, anon, mongo, reg_id):
        reg = mongo.event_registrations.find_one({"id": reg_id}, {"_id": 0})
        assert anon.get(f"{BASE}/public/qr/{reg['checkin_token']}.png", timeout=30).status_code == 200
        assert anon.get(f"{BASE}/public/registrations/{reg['confirmation_number']}",
                        params={"token": reg["checkin_token"]}, timeout=30).status_code == 200


# ---------------- resend webhook ----------------
class TestWebhook:
    def test_delivered_and_bounced_and_unknown(self, anon, admin, mongo):
        rid = register(anon, FREE_EVENT, payload("hook")).json()["id"]
        log = wait_for_email(admin, rid, "registration_confirmation")
        pid = log["provider_id"]
        if not pid:
            # sandbox rejects @example.com -> synthesize a provider id so the webhook path is testable
            pid = f"pid_test_{TAG}"
            mongo.email_log.update_one({"id": log["id"]}, {"$set": {"provider_id": pid}})
        r = anon.post(f"{BASE}/webhooks/resend", json={"type": "email.delivered", "data": {"email_id": pid}}, timeout=30)
        assert r.status_code == 200 and r.json()["ok"] is True
        doc = mongo.email_log.find_one({"provider_id": pid}, {"_id": 0})
        assert doc["status"] == "delivered"
        assert doc["delivered_at"]
        reg = mongo.event_registrations.find_one({"id": rid}, {"_id": 0})
        assert reg["confirmation_status"] == "delivered"

        r2 = anon.post(f"{BASE}/webhooks/resend",
                       json={"type": "email.bounced", "data": {"email_id": pid, "reason": "hard bounce"}}, timeout=30)
        assert r2.status_code == 200
        doc2 = mongo.email_log.find_one({"provider_id": pid}, {"_id": 0})
        assert doc2["status"] == "bounced"
        assert doc2["error"] == "hard bounce"

        r3 = anon.post(f"{BASE}/webhooks/resend",
                       json={"type": "email.delivered", "data": {"email_id": "nonexistent_pid"}}, timeout=30)
        assert r3.status_code == 200 and r3.json()["ok"] is True
