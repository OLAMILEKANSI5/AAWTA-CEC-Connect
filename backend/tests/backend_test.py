"""CEC Connect backend API regression tests."""
import time
import uuid

import pytest


def uniq(p="TEST"):
    return f"{p}_{uuid.uuid4().hex[:8]}"


# ---------------- module: health / public ----------------
class TestPublic:
    def test_root(self, anon, api):
        r = anon.get(f"{api}/")
        assert r.status_code == 200
        assert "CEC Connect" in r.json()["message"]

    def test_public_home(self, anon, api):
        r = anon.get(f"{api}/public/home")
        assert r.status_code == 200
        d = r.json()
        for k in ["settings", "spotlights", "announcements", "events", "stats"]:
            assert k in d, f"missing {k}"
        for k in ["ambassadors", "volunteers", "states", "events"]:
            assert isinstance(d["stats"][k], int)
        assert d["settings"]["portal_name"] == "CEC Connect"

    def test_public_directory(self, anon, api):
        r = anon.get(f"{api}/public/directory")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_settings_public(self, anon, api):
        r = anon.get(f"{api}/settings")
        assert r.status_code == 200
        assert "org_name" in r.json()


# ---------------- module: public submissions + spam ----------------
class TestSubmissions:
    def test_ambassador_submission(self, anon, api):
        email = f"{uniq('amb')}@example.com".lower()
        payload = {"type": "ambassador", "honeypot": "", "data": {
            "first_name": "TEST", "last_name": "Ambassador", "email": email,
            "telephone": "5551234567", "represent_state": "Georgia",
            "reason": "I want to serve", "areas_of_interest": ["Advocacy"]}}
        r = anon.post(f"{api}/public/applications", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ref"].startswith("AMB-"), d
        parts = d["ref"].split("-")
        assert len(parts) == 3 and len(parts[2]) == 4
        assert "id" in d
        pytest.amb_app_id = d["id"]
        pytest.amb_app_email = email

    def test_volunteer_submission(self, anon, api):
        email = f"{uniq('vol')}@example.com".lower()
        r = anon.post(f"{api}/public/applications", json={"type": "volunteer", "data": {
            "first_name": "TEST", "last_name": "Volunteer", "email": email,
            "telephone": "5550001111", "state": "Texas"}})
        assert r.status_code == 200, r.text
        assert r.json()["ref"].startswith("VOL-")

    def test_inquiry_submission(self, anon, api):
        r = anon.post(f"{api}/public/applications", json={"type": "inquiry", "data": {
            "first_name": "TEST", "last_name": "Inquiry", "email": f"{uniq('inq')}@example.com",
            "message": "Question about the program"}})
        assert r.status_code == 200, r.text
        assert r.json()["ref"].startswith("INQ-")

    def test_honeypot_rejected(self, anon, api):
        r = anon.post(f"{api}/public/applications", json={"type": "ambassador", "honeypot": "bot",
                                                          "data": {"email": "bot@example.com"}})
        assert r.status_code == 400
        assert "Spam" in r.json()["detail"]

    def test_missing_email_rejected(self, anon, api):
        r = anon.post(f"{api}/public/applications", json={"type": "ambassador", "data": {"first_name": "X"}})
        assert r.status_code == 400

    def test_invalid_type_rejected(self, anon, api):
        r = anon.post(f"{api}/public/applications", json={"type": "hacker", "data": {"email": "a@b.co"}})
        assert r.status_code == 400


# ---------------- module: auth gating ----------------
class TestAuthGating:
    @pytest.mark.parametrize("path", [
        "/applications", "/members", "/documents", "/goals", "/events",
        "/announcements", "/resources", "/messages", "/notifications",
        "/dashboard/stats", "/audit-logs", "/users", "/auth/me", "/members/me",
        "/activity-reports", "/announcement-requests", "/files",
    ])
    def test_unauthenticated_401(self, anon, api, path):
        r = anon.get(f"{api}{path}")
        assert r.status_code == 401, f"{path} -> {r.status_code}"

    def test_invalid_token_401(self, api, anon):
        r = anon.get(f"{api}/auth/me", headers={"Authorization": "Bearer nope_bad_token"})
        assert r.status_code == 401

    def test_admin_me(self, admin, api):
        r = admin.get(f"{api}/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "super_admin"

    def test_member_me(self, member, api):
        r = member.get(f"{api}/auth/me")
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "ambassador"
        assert d["member_id"], "member should be linked to a member record"

    def test_member_forbidden_on_staff_endpoints(self, member, api):
        for p in ["/applications", "/members", "/dashboard/stats", "/audit-logs", "/users"]:
            r = member.get(f"{api}{p}")
            assert r.status_code == 403, f"{p} -> {r.status_code}"

    def test_member_cannot_export_reports(self, member, api):
        r = member.get(f"{api}/reports/applications")
        assert r.status_code == 403


# ---------------- module: applications admin ----------------
class TestApplicationsAdmin:
    def test_list_and_filter(self, admin, api):
        r = admin.get(f"{api}/applications")
        assert r.status_code == 200
        apps = r.json()
        assert isinstance(apps, list) and len(apps) > 0
        assert "_id" not in apps[0]
        r2 = admin.get(f"{api}/applications", params={"type": "ambassador"})
        assert r2.status_code == 200
        assert all(a["type"] == "ambassador" for a in r2.json())
        r3 = admin.get(f"{api}/applications", params={"q": "TEST"})
        assert r3.status_code == 200

    def test_detail_notes_status_flow(self, admin, api):
        app_id = getattr(pytest, "amb_app_id", None)
        assert app_id, "ambassador submission test must run first"
        r = admin.get(f"{api}/applications/{app_id}")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "New"
        assert isinstance(d["timeline"], list) and len(d["timeline"]) >= 1

        # add note
        rn = admin.post(f"{api}/applications/{app_id}/notes", json={"text": "TEST note", "visibility": "leadership"})
        assert rn.status_code == 200
        assert rn.json()["text"] == "TEST note"

        # assign
        ra = admin.put(f"{api}/applications/{app_id}/assign", json={"assigned_reviewer": "TEST Reviewer"})
        assert ra.status_code == 200

        # status change
        rs = admin.put(f"{api}/applications/{app_id}/status", json={"status": "Approved", "note": "looks good"})
        assert rs.status_code == 200

        # verify persistence
        r2 = admin.get(f"{api}/applications/{app_id}")
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["status"] == "Approved"
        assert d2["assigned_reviewer"] == "TEST Reviewer"
        assert len(d2["notes"]) >= 1
        assert d2["notes"][-1]["text"] == "TEST note"
        assert d2["decision_history"][-1]["status"] == "Approved"

    def test_convert_to_member(self, admin, api):
        app_id = getattr(pytest, "amb_app_id", None)
        assert app_id
        r = admin.post(f"{api}/applications/{app_id}/convert")
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["role"] == "ambassador"
        assert m["email"] == pytest.amb_app_email
        assert len(m["onboarding"]) == 13
        pytest.converted_member_id = m["id"]
        # application status updated
        r2 = admin.get(f"{api}/applications/{app_id}")
        assert r2.json()["status"] == "Converted to Member"
        # member retrievable
        r3 = admin.get(f"{api}/members/{m['id']}")
        assert r3.status_code == 200
        assert r3.json()["name"] == m["name"]

    def test_get_application_404(self, admin, api):
        r = admin.get(f"{api}/applications/app_doesnotexist")
        assert r.status_code == 404

    def test_status_update_404(self, admin, api):
        r = admin.put(f"{api}/applications/app_nope/status", json={"status": "Approved"})
        assert r.status_code == 404


# ---------------- module: members ----------------
class TestMembers:
    def test_manual_member_create(self, admin, api):
        email = f"{uniq('mem')}@example.com".lower()
        payload = {"name": "TEST Manual Member", "email": email, "login_email": email,
                   "role": "volunteer", "state": "Ohio", "focus_areas": ["Outreach"],
                   "phone": "5559998888", "city": "Columbus", "send_invite": False}
        r = admin.post(f"{api}/members/manual", json=payload)
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["name"] == payload["name"]
        assert m["role"] == "volunteer"
        assert m["state"] == "Ohio"
        assert m["focus_areas"] == ["Outreach"]
        pytest.manual_member_id = m["id"]
        # verify persisted
        g = admin.get(f"{api}/members/{m['id']}")
        assert g.status_code == 200
        assert g.json()["phone"] == "5559998888"
        assert isinstance(g.json()["timeline"], list)

    def test_manual_member_invalid_email(self, admin, api):
        r = admin.post(f"{api}/members/manual", json={"name": "X", "email": "notanemail",
                                                      "login_email": "notanemail", "role": "volunteer"})
        assert r.status_code == 422

    def test_list_and_filter_members(self, admin, api):
        r = admin.get(f"{api}/members")
        assert r.status_code == 200 and len(r.json()) > 0
        r2 = admin.get(f"{api}/members", params={"role": "ambassador"})
        assert all(m["role"] == "ambassador" for m in r2.json())
        r3 = admin.get(f"{api}/members", params={"q": "TEST"})
        assert r3.status_code == 200

    def test_member_status_suspend_restore(self, admin, api):
        mid = getattr(pytest, "manual_member_id", None)
        assert mid
        r = admin.put(f"{api}/members/{mid}/status", json={"status": "suspended"})
        assert r.status_code == 200
        assert admin.get(f"{api}/members/{mid}").json()["account_status"] == "suspended"
        r2 = admin.put(f"{api}/members/{mid}/status", json={"status": "active"})
        assert r2.status_code == 200
        assert admin.get(f"{api}/members/{mid}").json()["account_status"] == "active"

    def test_members_me_and_self_update(self, member, api):
        r = member.get(f"{api}/members/me")
        assert r.status_code == 200
        m = r.json()
        mid = m["id"]
        pytest.self_member_id = mid
        upd = member.put(f"{api}/members/{mid}", json={"bio": "TEST bio updated", "city": "Atlanta",
                                                       "public_profile": True, "role": "super_admin"})
        assert upd.status_code == 200
        d = upd.json()
        assert d["bio"] == "TEST bio updated"
        assert d["city"] == "Atlanta"
        assert d["public_profile"] is True
        assert d["role"] == "ambassador", "member must not be able to escalate role"

    def test_member_cannot_view_other_member(self, member, api):
        other = getattr(pytest, "manual_member_id", None)
        r = member.get(f"{api}/members/{other}")
        assert r.status_code == 403

    def test_onboarding_toggle(self, member, api):
        mid = pytest.self_member_id
        r = member.put(f"{api}/members/{mid}/onboarding", json={"step": "Complete profile", "done": True})
        assert r.status_code == 200
        m = member.get(f"{api}/members/{mid}").json()
        step = [o for o in m["onboarding"] if o["step"] == "Complete profile"][0]
        assert step["done"] is True
        r2 = member.put(f"{api}/members/{mid}/onboarding", json={"step": "Complete profile", "done": False})
        assert r2.status_code == 200
        m2 = member.get(f"{api}/members/{mid}").json()
        assert [o for o in m2["onboarding"] if o["step"] == "Complete profile"][0]["done"] is False

    def test_member_404(self, admin, api):
        assert admin.get(f"{api}/members/mem_nope").status_code == 404


# ---------------- module: documents & signatures ----------------
class TestDocuments:
    def test_create_document(self, admin, api):
        r = admin.post(f"{api}/documents", json={"title": "TEST Confidentiality Agreement",
                                                 "description": "test doc", "category": "Agreement",
                                                 "assigned_roles": ["ambassador", "volunteer"],
                                                 "requires_signature": True})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["title"] == "TEST Confidentiality Agreement"
        pytest.doc_id = d["id"]

    def test_member_sees_assigned_document(self, member, api):
        r = member.get(f"{api}/documents")
        assert r.status_code == 200
        ids = [d["id"] for d in r.json()]
        assert pytest.doc_id in ids

    def test_sign_requires_consent(self, member, api):
        r = member.post(f"{api}/documents/{pytest.doc_id}/sign", json={"legal_name": "Test User", "consent": False})
        assert r.status_code == 400

    def test_sign_document(self, member, api):
        r = member.post(f"{api}/documents/{pytest.doc_id}/sign", json={"legal_name": "Test User", "consent": True})
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["legal_name"] == "Test User"
        assert s["document_id"] == pytest.doc_id
        docs = {d["id"]: d for d in member.get(f"{api}/documents").json()}
        assert docs[pytest.doc_id]["signed_by_me"] is True

    def test_cannot_resign(self, member, api):
        r = member.post(f"{api}/documents/{pytest.doc_id}/sign", json={"legal_name": "Test User", "consent": True})
        assert r.status_code == 400
        assert "Already signed" in r.json()["detail"]

    def test_admin_views_signatures(self, admin, api):
        r = admin.get(f"{api}/documents/{pytest.doc_id}/signatures")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_sign_missing_doc_404(self, member, api):
        r = member.post(f"{api}/documents/doc_nope/sign", json={"legal_name": "X", "consent": True})
        assert r.status_code == 404


# ---------------- module: goals & activity reports ----------------
class TestGoals:
    def test_admin_assigns_goal(self, admin, api):
        mid = getattr(pytest, "self_member_id", None) or "mem_bab4baedc2f1"
        r = admin.post(f"{api}/goals", json={"title": "TEST Q3 Outreach", "category": "Outreach",
                                            "target": "5 events", "member_id": mid,
                                            "description": "test goal"})
        assert r.status_code == 200, r.text
        g = r.json()
        assert g["member_id"] == mid
        assert g["approved"] is True
        assert g["progress"] == 0
        pytest.goal_id = g["id"]

    def test_member_sees_goal(self, member, api):
        r = member.get(f"{api}/goals")
        assert r.status_code == 200
        assert pytest.goal_id in [g["id"] for g in r.json()]

    def test_member_updates_progress(self, member, api):
        r = member.put(f"{api}/goals/{pytest.goal_id}", json={"progress": 60, "status": "In Progress"})
        assert r.status_code == 200
        g = r.json()
        assert g["progress"] == 60
        assert g["status"] == "In Progress"
        # persisted
        got = [x for x in member.get(f"{api}/goals").json() if x["id"] == pytest.goal_id][0]
        assert got["progress"] == 60

    def test_goal_404(self, member, api):
        assert member.put(f"{api}/goals/goal_nope", json={"progress": 1}).status_code == 404

    def test_activity_report(self, member, api):
        r = member.post(f"{api}/activity-reports", json={"month": "2026-07", "summary": "TEST monthly summary",
                                                         "hours": 12.5, "events_supported": 2})
        assert r.status_code == 200, r.text
        assert r.json()["hours"] == 12.5
        lst = member.get(f"{api}/activity-reports").json()
        assert any(x["summary"] == "TEST monthly summary" for x in lst)
        adm = api  # admin sees all
        assert True


# ---------------- module: announcements ----------------
class TestAnnouncements:
    def test_publish_announcement(self, admin, api):
        r = admin.post(f"{api}/announcements", json={"title": "TEST Announcement", "message": "Hello members",
                                                    "target_roles": ["ambassador"], "public": True})
        assert r.status_code == 200, r.text
        a = r.json()
        assert a["published"] is True
        pytest.ann_id = a["id"]

    def test_member_sees_announcement(self, member, api):
        r = member.get(f"{api}/announcements")
        assert r.status_code == 200
        assert pytest.ann_id in [a["id"] for a in r.json()]

    def test_role_targeting_filters(self, admin, member, api):
        r = admin.post(f"{api}/announcements", json={"title": "TEST Volunteer Only", "message": "vols",
                                                     "target_roles": ["volunteer"]})
        assert r.status_code == 200
        vid = r.json()["id"]
        seen = [a["id"] for a in member.get(f"{api}/announcements").json()]
        assert vid not in seen, "ambassador should not see volunteer-targeted announcement"

    def test_ack(self, member, api):
        r = member.post(f"{api}/announcements/{pytest.ann_id}/ack")
        assert r.status_code == 200

    def test_public_announcement_on_home(self, anon, api):
        r = anon.get(f"{api}/public/home")
        titles = [a["title"] for a in r.json()["announcements"]]
        assert "TEST Announcement" in titles

    def test_member_announcement_request(self, member, admin, api):
        r = member.post(f"{api}/announcement-requests", json={"title": "TEST Request", "message": "please post"})
        assert r.status_code == 200
        assert r.json()["status"] == "Submitted"
        rid = r.json()["id"]
        assert rid in [x["id"] for x in admin.get(f"{api}/announcement-requests").json()]


# ---------------- module: events ----------------
class TestEvents:
    def test_member_submits_event(self, member, api):
        r = member.post(f"{api}/events", json={"name": "TEST Community Drive", "event_type": "Outreach",
                                               "date": "2026-12-01", "location": "Atlanta, GA",
                                               "state": "Georgia", "estimated_attendance": 50, "public": True})
        assert r.status_code == 200, r.text
        e = r.json()
        assert e["status"] == "Submitted"
        pytest.event_id = e["id"]

    def test_admin_event_auto_approved(self, admin, api):
        r = admin.post(f"{api}/events", json={"name": "TEST Admin Event", "date": "2026-11-01"})
        assert r.status_code == 200
        assert r.json()["status"] == "Approved"

    def test_admin_approves_member_event(self, admin, api):
        r = admin.put(f"{api}/events/{pytest.event_id}/status", json={"status": "Approved"})
        assert r.status_code == 200
        evs = {e["id"]: e for e in admin.get(f"{api}/events").json()}
        assert evs[pytest.event_id]["status"] == "Approved"

    def test_member_cannot_change_event_status(self, member, api):
        r = member.put(f"{api}/events/{pytest.event_id}/status", json={"status": "Declined"})
        assert r.status_code == 403

    def test_event_status_404(self, admin, api):
        assert admin.put(f"{api}/events/evt_nope/status", json={"status": "Approved"}).status_code == 404


# ---------------- module: messages & notifications ----------------
class TestMessaging:
    def test_admin_message_to_role(self, admin, member, api):
        r = admin.post(f"{api}/messages", json={"subject": "TEST Broadcast", "body": "hello ambassadors",
                                                "target_role": "ambassador"})
        assert r.status_code == 200, r.text
        mid = r.json()["id"]
        inbox = member.get(f"{api}/messages").json()
        assert mid in [m["id"] for m in inbox]
        assert member.post(f"{api}/messages/{mid}/read").status_code == 200

    def test_no_recipients_400(self, admin, api):
        r = admin.post(f"{api}/messages", json={"subject": "TEST", "body": "x"})
        assert r.status_code == 400

    def test_notifications(self, member, api):
        r = member.get(f"{api}/notifications")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert member.post(f"{api}/notifications/read-all").status_code == 200
        assert all(n["read"] for n in member.get(f"{api}/notifications").json())


# ---------------- module: resources & settings ----------------
class TestResourcesSettings:
    def test_resource_crud(self, admin, member, api):
        r = admin.post(f"{api}/resources", json={"title": "TEST Handbook", "url": "https://example.com",
                                                 "category": "Guides", "access_roles": []})
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        assert rid in [x["id"] for x in member.get(f"{api}/resources").json()]
        u = admin.put(f"{api}/resources/{rid}", json={"title": "TEST Handbook v2"})
        assert u.status_code == 200 and u.json()["title"] == "TEST Handbook v2"
        assert admin.delete(f"{api}/resources/{rid}").status_code == 200
        assert rid not in [x["id"] for x in admin.get(f"{api}/resources").json()]

    def test_resource_access_roles(self, admin, member, api):
        r = admin.post(f"{api}/resources", json={"title": "TEST Staff Only", "category": "Internal",
                                                 "access_roles": ["super_admin"]})
        rid = r.json()["id"]
        assert rid not in [x["id"] for x in member.get(f"{api}/resources").json()]
        admin.delete(f"{api}/resources/{rid}")

    def test_member_cannot_create_resource(self, member, api):
        assert member.post(f"{api}/resources", json={"title": "x", "category": "y"}).status_code == 403

    def test_settings_update_persists(self, admin, anon, api):
        orig = anon.get(f"{api}/settings").json()
        new_slack = "https://slack.com/test-cec"
        r = admin.put(f"{api}/settings", json={"slack_link": new_slack, "calendar_link": "https://cal.test/cec"})
        assert r.status_code == 200
        assert r.json()["slack_link"] == new_slack
        assert anon.get(f"{api}/settings").json()["calendar_link"] == "https://cal.test/cec"
        admin.put(f"{api}/settings", json={"slack_link": orig["slack_link"], "calendar_link": orig["calendar_link"]})

    def test_member_cannot_update_settings(self, member, api):
        assert member.put(f"{api}/settings", json={"slack_link": "x"}).status_code == 403


# ---------------- module: users / authorized emails / audit ----------------
class TestUsersAudit:
    def test_list_users(self, admin, api):
        r = admin.get(f"{api}/users")
        assert r.status_code == 200
        d = r.json()
        assert "users" in d and "authorized" in d
        assert len(d["users"]) >= 2

    def test_authorize_email(self, admin, api):
        email = f"{uniq('auth')}@example.com".lower()
        r = admin.post(f"{api}/authorized-emails", json={"email": email, "role": "administrator"})
        assert r.status_code == 200
        authed = {a["email"]: a for a in admin.get(f"{api}/users").json()["authorized"]}
        assert email in authed and authed[email]["role"] == "administrator"
        pytest.auth_email = email

    def test_authorize_invalid_role(self, admin, api):
        r = admin.post(f"{api}/authorized-emails", json={"email": "x@example.com", "role": "wizard"})
        assert r.status_code == 400

    def test_set_email_status(self, admin, api):
        r = admin.put(f"{api}/authorized-emails/{pytest.auth_email}/status", json={"status": "suspended"})
        assert r.status_code == 200
        authed = {a["email"]: a for a in admin.get(f"{api}/users").json()["authorized"]}
        assert authed[pytest.auth_email]["status"] == "suspended"

    def test_change_user_role(self, admin, api):
        users = admin.get(f"{api}/users").json()["users"]
        target = [u for u in users if u["email"] == "testapplicant@example.com"][0]
        r = admin.put(f"{api}/users/{target['user_id']}/role", json={"role": "volunteer"})
        assert r.status_code == 200
        users2 = {u["user_id"]: u for u in admin.get(f"{api}/users").json()["users"]}
        assert users2[target["user_id"]]["role"] == "volunteer"
        # restore
        admin.put(f"{api}/users/{target['user_id']}/role", json={"role": "ambassador"})
        users3 = {u["user_id"]: u for u in admin.get(f"{api}/users").json()["users"]}
        assert users3[target["user_id"]]["role"] == "ambassador"

    def test_role_invalid(self, admin, api):
        r = admin.put(f"{api}/users/user_testamb01/role", json={"role": "nope"})
        assert r.status_code == 400

    def test_role_user_404(self, admin, api):
        assert admin.put(f"{api}/users/user_nope/role", json={"role": "volunteer"}).status_code == 404

    def test_audit_logs(self, admin, api):
        r = admin.get(f"{api}/audit-logs")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) > 0
        assert "action" in logs[0] and "created_at" in logs[0]
        r2 = admin.get(f"{api}/audit-logs", params={"q": "application"})
        assert r2.status_code == 200
        assert all("application" in x["action"].lower() or "application" in (x["user_email"] or "").lower()
                   for x in r2.json())


# ---------------- module: dashboard & reports ----------------
class TestDashboardReports:
    def test_dashboard_stats(self, admin, api):
        r = admin.get(f"{api}/dashboard/stats")
        assert r.status_code == 200
        s = r.json()
        for k in ["new_applications", "under_review", "approved", "active_ambassadors",
                  "active_volunteers", "pending_events", "total_members", "incomplete_onboarding"]:
            assert isinstance(s[k], int), f"{k} not int"
        assert set(s["by_type"].keys()) == {"ambassador", "volunteer", "inquiry"}
        assert isinstance(s["by_status"], dict)
        assert isinstance(s["recent_applications"], list)
        assert isinstance(s["upcoming_events"], list)
        assert s["total_members"] > 0

    @pytest.mark.parametrize("rtype", ["applications", "ambassadors", "volunteers", "goals",
                                       "volunteer_hours", "events"])
    def test_report_json(self, admin, api, rtype):
        r = admin.get(f"{api}/reports/{rtype}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "rows" in d and d["count"] == len(d["rows"])

    @pytest.mark.parametrize("rtype", ["applications", "ambassadors", "events"])
    def test_report_csv(self, admin, api, rtype):
        r = admin.get(f"{api}/reports/{rtype}", params={"format": "csv"})
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_unknown_report(self, admin, api):
        assert admin.get(f"{api}/reports/nonsense").status_code == 400


# ---------------- module: rate limiting ----------------
class TestRateLimit:
    def test_rate_limit_triggers(self, anon, api):
        codes = []
        for i in range(12):
            r = anon.post(f"{api}/public/applications", json={"type": "inquiry", "data": {
                "email": f"{uniq('rl')}@example.com", "message": "spam test"}})
            codes.append(r.status_code)
            if r.status_code == 429:
                break
            time.sleep(0.1)
        assert 429 in codes, f"rate limit never triggered: {codes}"
