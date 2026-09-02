"""Phase B — registration management (list filters, manual reg, walk-in, edit, cancel,
archive, badge-printed, history, checkin audit/undo, authz)."""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = "tok_admtest"
MEMBER = "tok_memba"
EVENT = "evt_246d20a66b31"
TAG = uuid.uuid4().hex[:6]
PAYMENT_STATUSES = ["paid", "pending", "complimentary", "refunded", "not_applicable"]

created_regs = []


def sess(token=None):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


@pytest.fixture(scope="session")
def admin():
    s = sess(ADMIN)
    r = s.get(f"{API}/auth/me")
    if r.status_code != 200:
        pytest.fail(f"admin token invalid: {r.status_code} {r.text[:200]}")
    return s


@pytest.fixture(scope="session")
def member():
    return sess(MEMBER)


@pytest.fixture(scope="session")
def anon():
    return sess()


def mk_manual(admin, **over):
    body = {"first_name": f"TEST{TAG}", "last_name": "Manual",
            "email": f"delivered+{TAG}m{len(created_regs)}@resend.dev",
            "phone": "404-555-0101", "state": "Georgia", "city": "Atlanta", "zip_code": "30301",
            "member_status": "Yes", "business_name": f"TEST_Biz {TAG}", "business_website": "acme.com",
            "job_title": "CEO", "ticket_category": "VIP", "internal_notes": "note"}
    body.update(over)
    r = admin.post(f"{API}/events/{EVENT}/manual-registration", json=body)
    assert r.status_code == 200, r.text
    reg = r.json()
    created_regs.append(reg["id"])
    return reg


def mk_walkin(admin, **over):
    body = {"first_name": f"TEST{TAG}", "last_name": "Walkin",
            "email": f"delivered+{TAG}w{len(created_regs)}@resend.dev", "state": "Texas",
            "member_status": "No", "ticket_category": "General Admission"}
    body.update(over)
    r = admin.post(f"{API}/events/{EVENT}/registrations", json=body)
    assert r.status_code == 200, r.text
    reg = r.json()
    created_regs.append(reg["id"])
    return reg


@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    yield
    s = sess(ADMIN)
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import dotenv_values as dv
    be = dv("/app/backend/.env")

    async def _clean():
        cli = AsyncIOMotorClient(be["MONGO_URL"])
        db = cli[be["DB_NAME"]]
        await db.event_registrations.delete_many({"id": {"$in": created_regs}})
        await db.audit_logs.delete_many({"related_id": {"$in": created_regs}})
        await db.consents.delete_many({"reg_id": {"$in": created_regs}})
        await db.email_log.delete_many({"related_id": {"$in": created_regs}})
    asyncio.get_event_loop().run_until_complete(_clean())
    del s


# ---------------- manual registration ----------------
class TestManualRegistration:
    def test_manual_fields_and_defaults(self, admin):
        reg = mk_manual(admin)
        assert reg["source"] == "Manual Entry"
        assert reg["name"] == f"TEST{TAG} Manual"
        assert reg["business_website"] == "https://acme.com"
        assert reg["is_member"] is True
        assert reg["status"] == "registered" and reg["checked_in"] is False
        assert reg["payment_status"] == "not_applicable"
        assert reg["confirmation_number"].startswith("CEC-")
        assert isinstance(reg["checkin_token"], str) and len(reg["checkin_token"]) > 10
        assert reg["created_by"] and reg["created_by_id"] and reg["updated_by"]
        assert reg["created_at"] and reg["updated_at"]
        assert reg["confirmation_sent"] is False
        # GET verify persistence
        lst = admin.get(f"{API}/events/{EVENT}/registrations", params={"q": reg["confirmation_number"]}).json()
        assert lst["filtered"] == 1
        assert lst["registrations"][0]["id"] == reg["id"]

    def test_manual_no_auto_confirmation_email(self, admin):
        reg = mk_manual(admin, email=f"delivered+{TAG}noem@resend.dev")
        import time
        time.sleep(3)
        logs = admin.get(f"{API}/registrations/{reg['id']}/emails").json()
        assert [l for l in logs if l.get("template") == "registration_confirmation"] == [], logs
        # admin can then send it
        r = admin.post(f"{API}/registrations/{reg['id']}/send-confirmation")
        assert r.status_code == 200
        time.sleep(4)
        logs = admin.get(f"{API}/registrations/{reg['id']}/emails").json()
        conf = [l for l in logs if l.get("template") == "registration_confirmation"]
        assert len(conf) == 1
        assert conf[0]["status"] == "sent", conf[0]

    def test_manual_complimentary_and_checked_in(self, admin):
        reg = mk_manual(admin, complimentary=True, checked_in=True, payment_status="pending")
        assert reg["payment_status"] == "complimentary"
        assert reg["status"] == "checked_in" and reg["checked_in"] is True
        assert reg["checked_in_at"] and reg["checkin_method"] == "manual"

    def test_manual_optins_create_consents_only_when_true(self, admin):
        reg = mk_manual(admin, newsletter_opt_in=True, events_opt_in=False,
                        email=f"delivered+{TAG}cons@resend.dev")
        assert reg["newsletter_opt_in"] is True and reg["events_opt_in"] is False
        r = admin.get(f"{API}/admin/consents") if False else None
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import dotenv_values as dv
        be = dv("/app/backend/.env")

        async def _q():
            cli = AsyncIOMotorClient(be["MONGO_URL"])
            return await cli[be["DB_NAME"]].consents.find({"reg_id": reg["id"]}, {"_id": 0}).to_list(10)
        docs = asyncio.get_event_loop().run_until_complete(_q())
        assert len(docs) == 1 and docs[0]["type"] == "newsletter"
        assert docs[0]["source"] == "Manual Entry" and docs[0]["granted"] is True
        del r

    def test_manual_member_status_no_sets_is_member_false(self, admin):
        reg = mk_manual(admin, member_status="No")
        assert reg["is_member"] is False
        assert reg["badge_category"] == "General Attendee"

    def test_manual_missing_first_name_422(self, admin):
        r = admin.post(f"{API}/events/{EVENT}/manual-registration", json={"last_name": "X"})
        assert r.status_code == 422, r.text

    def test_manual_unknown_event_404(self, admin):
        r = admin.post(f"{API}/events/evt_doesnotexist/manual-registration",
                       json={"first_name": "A", "last_name": "B"})
        assert r.status_code == 404


# ---------------- walk-in ----------------
class TestWalkin:
    def test_walkin_created_checked_in(self, admin):
        reg = mk_walkin(admin)
        assert reg["source"] == "Walk-In"
        assert reg["status"] == "checked_in" and reg["checked_in"] is True
        assert reg["checkin_method"] == "walkin" and reg["checked_in_by"]
        assert reg["confirmation_number"].startswith("CEC-")
        assert reg["checkin_token"]
        assert reg["badge_category"] in ("General Admission", "Walk-In", "General Attendee")
        got = admin.get(f"{API}/events/{EVENT}/registrations", params={"source": "Walk-In"}).json()
        assert reg["id"] in [x["id"] for x in got["registrations"]]

    def test_walkin_badge_category_from_ticket(self, admin):
        reg = mk_walkin(admin, ticket_category="VIP")
        assert reg["badge_category"] == "VIP"

    def test_walkin_missing_name_rejected(self, admin):
        r = admin.post(f"{API}/events/{EVENT}/registrations", json={"email": "a@b.com"})
        assert r.status_code in (400, 422), r.text

    def test_walkin_blank_name_rejected(self, admin):
        r = admin.post(f"{API}/events/{EVENT}/registrations", json={"first_name": "   ", "email": "a@b.com"})
        assert r.status_code in (400, 422), r.text

    def test_walkin_requires_email_or_phone(self, admin):
        r = admin.post(f"{API}/events/{EVENT}/registrations", json={"first_name": f"TEST{TAG}", "last_name": "NoContact"})
        if r.status_code == 200:
            created_regs.append(r.json()["id"])
        assert r.status_code in (400, 422), (
            "walk-in with neither email nor phone was accepted (spec requires email or phone)")


# ---------------- edit ----------------
class TestEdit:
    def test_edit_updates_and_audits(self, admin):
        reg = mk_manual(admin)
        r = admin.put(f"{API}/registrations/{reg['id']}", json={
            "first_name": "Edited", "business_website": "newsite.org", "job_title": "CTO"})
        assert r.status_code == 200, r.text
        up = r.json()
        assert up["first_name"] == "Edited"
        assert up["name"] == f"Edited {reg['last_name']}"
        assert up["business_website"] == "https://newsite.org"
        assert up["job_title"] == "CTO"
        assert up["last_name"] == reg["last_name"]  # untouched
        assert up["updated_by"] and up["updated_at"] != reg["updated_at"]
        # persisted
        got = admin.get(f"{API}/events/{EVENT}/registrations", params={"q": reg["confirmation_number"]}).json()
        assert got["registrations"][0]["name"] == f"Edited {reg['last_name']}"
        # audit
        hist = admin.get(f"{API}/registrations/{reg['id']}/history").json()
        acts = [h["action"] for h in hist]
        assert acts[:2] == ["registration_updated", "registration_created"], acts
        ch = hist[0]["detail"]["changes"]
        assert ch["first_name"] == {"from": reg["first_name"], "to": "Edited"}
        assert ch["job_title"]["to"] == "CTO"

    def test_noop_edit_no_audit(self, admin):
        reg = mk_manual(admin)
        before = admin.get(f"{API}/registrations/{reg['id']}/history").json()
        r = admin.put(f"{API}/registrations/{reg['id']}", json={
            "first_name": reg["first_name"], "job_title": reg["job_title"]})
        assert r.status_code == 200
        assert r.json()["updated_at"] == reg["updated_at"]
        after = admin.get(f"{API}/registrations/{reg['id']}/history").json()
        assert len(after) == len(before), [h["action"] for h in after]

    def test_edit_unknown_reg_404(self, admin):
        r = admin.put(f"{API}/registrations/reg_nope/", json={"first_name": "x"})
        r2 = admin.put(f"{API}/registrations/reg_nope", json={"first_name": "x"})
        assert r2.status_code == 404, r2.text
        del r


# ---------------- cancel / archive / badge / history ----------------
class TestLifecycle:
    def test_staff_cancel(self, admin):
        reg = mk_walkin(admin)
        r = admin.post(f"{API}/registrations/{reg['id']}/cancel")
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["status"] == "cancelled" and c["checked_in"] is False
        hist = admin.get(f"{API}/registrations/{reg['id']}/history").json()
        assert "registration_cancelled" in [h["action"] for h in hist]
        # cancelled excluded from total count but still listed
        lst = admin.get(f"{API}/events/{EVENT}/registrations", params={"q": reg["confirmation_number"]}).json()
        assert lst["registrations"][0]["status"] == "cancelled"

    def test_archive_toggle_and_list_exclusion(self, admin):
        reg = mk_manual(admin)
        conf = reg["confirmation_number"]
        r = admin.put(f"{API}/registrations/{reg['id']}/archive", json={"archived": True})
        assert r.status_code == 200 and r.json()["archived"] is True
        lst = admin.get(f"{API}/events/{EVENT}/registrations", params={"q": conf}).json()
        assert lst["filtered"] == 0, lst
        inc = admin.get(f"{API}/events/{EVENT}/registrations",
                        params={"q": conf, "include_archived": "true"}).json()
        assert inc["filtered"] == 1
        # unarchive
        r = admin.put(f"{API}/registrations/{reg['id']}/archive", json={"archived": False})
        assert r.json()["archived"] is False
        lst = admin.get(f"{API}/events/{EVENT}/registrations", params={"q": conf}).json()
        assert lst["filtered"] == 1
        acts = [h["action"] for h in admin.get(f"{API}/registrations/{reg['id']}/history").json()]
        assert "registration_archived" in acts and "registration_unarchived" in acts

    def test_badge_printed(self, admin):
        reg = mk_manual(admin)
        for i in (1, 2):
            r = admin.post(f"{API}/registrations/{reg['id']}/badge-printed")
            assert r.status_code == 200 and r.json()["ok"] is True
            row = admin.get(f"{API}/events/{EVENT}/registrations",
                            params={"q": reg["confirmation_number"]}).json()["registrations"][0]
            assert row["badge_status"] == "printed"
            assert row["badge_print_count"] == i
            assert row["badge_printed_at"]
        acts = [h["action"] for h in admin.get(f"{API}/registrations/{reg['id']}/history").json()]
        assert acts.count("badge_printed") == 2

    def test_history_newest_first(self, admin):
        reg = mk_manual(admin)
        admin.put(f"{API}/registrations/{reg['id']}", json={"job_title": "New Title"})
        hist = admin.get(f"{API}/registrations/{reg['id']}/history").json()
        assert [h["action"] for h in hist] == ["registration_updated", "registration_created"]
        assert hist[0]["created_at"] >= hist[1]["created_at"]

    def test_history_unknown_404(self, admin):
        assert admin.get(f"{API}/registrations/reg_nope/history").status_code == 404


# ---------------- checkin audit + undo regression ----------------
class TestCheckin:
    def test_checkin_and_undo_walkin_restores_walkin(self, admin):
        reg = mk_walkin(admin)
        r = admin.put(f"{API}/registrations/{reg['id']}/checkin", json={"checked_in": False})
        assert r.status_code == 200
        row = admin.get(f"{API}/events/{EVENT}/registrations",
                        params={"q": reg["confirmation_number"]}).json()["registrations"][0]
        assert row["checked_in"] is False
        assert row["status"] == "walkin", f"expected walkin, got {row['status']}"
        # re-check-in
        r = admin.put(f"{API}/registrations/{reg['id']}/checkin", json={"checked_in": True, "method": "qr"})
        assert r.status_code == 200
        row = admin.get(f"{API}/events/{EVENT}/registrations",
                        params={"q": reg["confirmation_number"]}).json()["registrations"][0]
        assert row["status"] == "checked_in" and row["checked_in"] is True
        assert row["checkin_method"] == "qr" and row["checked_in_by"]
        acts = [h["action"] for h in admin.get(f"{API}/registrations/{reg['id']}/history").json()]
        assert "checkin" in acts and "checkin_undo" in acts

    def test_undo_waitlist_restores_waitlist(self, admin):
        # evt_badgetest is capacity-full -> new registration lands on waitlist
        import time
        email = f"delivered+{TAG}wl@resend.dev"
        r = requests.post(f"{API}/public/events/evt_badgetest/register", json={
            "first_name": f"TEST{TAG}", "last_name": "Waitlist", "email": email,
            "phone": "404-555-9999", "state": "Georgia", "member_status": "No",
            "is_member": False, "ticket_category": "General Admission"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "waitlist", r.json()
        rid = r.json()["id"]
        created_regs.append(rid)
        time.sleep(1)
        s = sess(ADMIN)
        assert s.put(f"{API}/registrations/{rid}/checkin", json={"checked_in": True}).status_code == 200
        assert s.put(f"{API}/registrations/{rid}/checkin", json={"checked_in": False}).status_code == 200
        rows = s.get(f"{API}/events/evt_badgetest/registrations").json()["registrations"]
        row = [x for x in rows if x["id"] == rid][0]
        assert row["status"] == "waitlist", f"expected waitlist restored, got {row['status']}"


# ---------------- list filters ----------------
class TestFilters:
    @pytest.fixture(scope="class", autouse=True)
    def seeded(self, admin):
        self.__class__.m = mk_manual(admin, state="Georgia", member_status="Yes",
                                     ticket_category="VIP", business_name=f"TEST_Filter{TAG}",
                                     phone="404-555-7777", complimentary=True,
                                     email=f"delivered{TAG}filter@resend.dev")
        self.__class__.w = mk_walkin(admin, state="Texas", member_status="No")
        return True

    def ids(self, admin, params):
        r = admin.get(f"{API}/events/{EVENT}/registrations", params=params)
        assert r.status_code == 200, r.text
        d = r.json()
        assert set(["registrations", "total", "filtered", "checked_in"]).issubset(d.keys())
        assert d["filtered"] == len(d["registrations"])
        return [x["id"] for x in d["registrations"]], d

    def test_response_shape(self, admin):
        _, d = self.ids(admin, {})
        assert isinstance(d["total"], int) and isinstance(d["checked_in"], int)
        assert all("_id" not in x for x in d["registrations"])
        # total = active non-cancelled non-archived
        active = [x for x in d["registrations"] if x.get("status") != "cancelled"]
        assert d["total"] == len(active), (d["total"], len(active))

    def test_q_matches_name_email_phone_business_conf(self, admin):
        m = self.m
        for p in [{"q": m["name"]}, {"q": m["email"]}, {"q": "555-7777"},
                  {"q": f"TEST_Filter{TAG}"}, {"q": m["confirmation_number"]}]:
            ids, _ = self.ids(admin, p)
            assert m["id"] in ids, p

    def test_q_special_chars_are_regex_escaped(self, admin):
        """q is injected raw into $regex; '+' in an email breaks the search."""
        plus = mk_manual(admin, email=f"delivered+{TAG}plus@resend.dev")
        ids, _ = self.ids(admin, {"q": plus["email"]})
        assert plus["id"] in ids, "q not re.escape()d — emails containing '+' cannot be searched"

    def test_state_filter(self, admin):
        ids, _ = self.ids(admin, {"state": "Texas"})
        assert self.w["id"] in ids and self.m["id"] not in ids

    def test_member_filter(self, admin):
        yes, _ = self.ids(admin, {"member": "yes"})
        no, _ = self.ids(admin, {"member": "no"})
        assert self.m["id"] in yes and self.m["id"] not in no
        assert self.w["id"] in no and self.w["id"] not in yes

    def test_business_filter(self, admin):
        ids, _ = self.ids(admin, {"business": f"filter{TAG}"})
        assert ids == [self.m["id"]]

    def test_category_filter(self, admin):
        ids, _ = self.ids(admin, {"category": "VIP"})
        assert self.m["id"] in ids and self.w["id"] not in ids

    @pytest.mark.parametrize("src", ["online", "Manual Entry", "Walk-In", "Bulk Import"])
    def test_source_filter(self, admin, src):
        ids, d = self.ids(admin, {"source": src})
        assert all(x["source"] == src for x in d["registrations"])
        if src == "Manual Entry":
            assert self.m["id"] in ids
        if src == "Walk-In":
            assert self.w["id"] in ids

    @pytest.mark.parametrize("pay", PAYMENT_STATUSES)
    def test_payment_filter(self, admin, pay):
        _, d = self.ids(admin, {"payment": pay})
        assert all(x["payment_status"] == pay for x in d["registrations"])
        if pay == "complimentary":
            assert self.m["id"] in [x["id"] for x in d["registrations"]]

    @pytest.mark.parametrize("conf", ["sent", "delivered", "opened", "failed", "bounced"])
    def test_confirmation_filter(self, admin, conf):
        _, d = self.ids(admin, {"confirmation": conf})
        assert all(x.get("confirmation_status") == conf for x in d["registrations"])

    def test_confirmation_not_sent_filter(self, admin):
        ids, d = self.ids(admin, {"confirmation": "not_sent"})
        assert all(x.get("confirmation_sent") is not True for x in d["registrations"])
        assert self.w["id"] in ids

    def test_checkin_filter(self, admin):
        cin, d1 = self.ids(admin, {"checkin": "in"})
        cout, d2 = self.ids(admin, {"checkin": "out"})
        assert all(x["checked_in"] is True for x in d1["registrations"])
        assert all(x.get("checked_in") is not True for x in d2["registrations"])
        assert self.w["id"] in cin and self.m["id"] in cout

    def test_badge_filter(self, admin):
        admin.post(f"{API}/registrations/{self.m['id']}/badge-printed")
        ids, d = self.ids(admin, {"badge": "printed"})
        assert self.m["id"] in ids
        assert all(x.get("badge_status") == "printed" for x in d["registrations"])

    def test_combined_filters(self, admin):
        ids, _ = self.ids(admin, {"state": "Texas", "source": "Walk-In", "checkin": "in", "member": "no"})
        assert self.w["id"] in ids and self.m["id"] not in ids

    def test_unknown_event_404(self, admin):
        assert admin.get(f"{API}/events/evt_nope/registrations").status_code == 404


# ---------------- authorization ----------------
class TestAuthz:
    @pytest.fixture(scope="class")
    def reg(self, admin):
        return mk_manual(admin)

    def endpoints(self, reg):
        return [
            ("get", f"{API}/events/{EVENT}/registrations", None),
            ("post", f"{API}/events/{EVENT}/manual-registration", {"first_name": "A", "last_name": "B"}),
            ("post", f"{API}/events/{EVENT}/registrations", {"first_name": "A", "email": "a@b.com"}),
            ("put", f"{API}/registrations/{reg['id']}", {"job_title": "x"}),
            ("post", f"{API}/registrations/{reg['id']}/cancel", None),
            ("put", f"{API}/registrations/{reg['id']}/archive", {"archived": True}),
            ("post", f"{API}/registrations/{reg['id']}/badge-printed", None),
            ("get", f"{API}/registrations/{reg['id']}/history", None),
            ("put", f"{API}/registrations/{reg['id']}/checkin", {"checked_in": True}),
        ]

    def test_anonymous_401(self, anon, reg):
        bad = []
        for meth, url, body in self.endpoints(reg):
            r = getattr(anon, meth)(url, json=body) if body is not None else getattr(anon, meth)(url)
            if r.status_code != 401:
                bad.append((meth, url, r.status_code))
        assert not bad, bad

    def test_non_owner_member_403(self, member, reg):
        bad = []
        for meth, url, body in self.endpoints(reg):
            r = getattr(member, meth)(url, json=body) if body is not None else getattr(member, meth)(url)
            if r.status_code != 403:
                bad.append((meth, url, r.status_code, r.text[:120]))
        assert not bad, bad
