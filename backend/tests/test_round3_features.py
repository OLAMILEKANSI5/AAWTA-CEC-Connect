"""Round-3 feature tests: Slack link bug fix, report PDF export, message threads, post-event reports."""
import io
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

from conftest import API, ADMIN_TOKEN, MEMBER_TOKEN

BE_ENV = dotenv_values("/app/backend/.env")
ADMIN_UID = "user_admin1"
MEMBER_UID = "user_amb1"

SLACK_URL = "https://aawtaworkspace.slack.com/archives/C0ALPLXG5T5"
REPORT_TYPES = ["applications", "ambassadors", "volunteers", "goals", "volunteer_hours", "events"]


def _bearer(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _upload(session, name="TEST_attach.txt", content=b"hello attachment"):
    files = {"file": (name, io.BytesIO(content), "text/plain")}
    r = session.post(f"{API}/upload", files=files)
    assert r.status_code == 200, f"upload failed {r.status_code} {r.text[:300]}"
    data = r.json()
    assert "id" in data
    return data["id"]


# ---------------- fixtures ----------------
@pytest.fixture(scope="module")
def mdb():
    client = MongoClient(BE_ENV["MONGO_URL"])
    yield client[BE_ENV["DB_NAME"]]
    client.close()


@pytest.fixture(scope="module")
def other_token(mdb):
    """A second ambassador (non-participant, non-owner) used for 403 checks."""
    uid = "TEST_user_other3"
    tok = "TEST_tok_other3"
    mdb.users.insert_one({"user_id": uid, "email": "TEST_other3@example.com", "name": "TEST Other3",
                          "role": "ambassador", "account_status": "active",
                          "created_at": "2026-07-01T00:00:00Z", "last_login": "2026-08-27T00:00:00Z"})
    mdb.user_sessions.insert_one({"user_id": uid, "session_token": tok,
                                  "expires_at": "2030-01-01T00:00:00Z", "created_at": "2026-07-01T00:00:00Z"})
    mdb.members.insert_one({"id": "TEST_mem_other3", "user_id": uid, "name": "TEST Other3",
                            "email": "TEST_other3@example.com", "role": "ambassador", "state": "Ohio",
                            "focus_areas": ["Health"], "public_profile": False, "account_status": "active",
                            "onboarding": [], "created_at": "2026-07-01T00:00:00Z"})
    yield tok
    mdb.users.delete_one({"user_id": uid})
    mdb.user_sessions.delete_one({"session_token": tok})
    mdb.members.delete_one({"id": "TEST_mem_other3"})
    mdb.notifications.delete_many({"user_id": uid})


# ---------------- BUG FIX: Slack link ----------------
class TestSlackLink:
    def test_settings_slack_link(self, anon):
        r = anon.get(f"{API}/settings")
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("slack_link") == SLACK_URL, f"got {data.get('slack_link')}"


# ---------------- FEATURE: report PDF export ----------------
class TestReportExports:
    @pytest.mark.parametrize("rtype", REPORT_TYPES)
    def test_pdf_export(self, admin, rtype):
        r = admin.get(f"{API}/reports/{rtype}?format=pdf")
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:5] == b"%PDF-"
        assert len(r.content) > 800
        assert f"{rtype}.pdf" in r.headers.get("content-disposition", "")

    @pytest.mark.parametrize("rtype", REPORT_TYPES)
    def test_csv_still_works(self, admin, rtype):
        r = admin.get(f"{API}/reports/{rtype}?format=csv")
        assert r.status_code == 200, r.text[:300]
        assert "text/csv" in r.headers.get("content-type", "")

    def test_json_default(self, admin):
        r = admin.get(f"{API}/reports/events")
        assert r.status_code == 200
        body = r.json()
        assert "rows" in body and "count" in body
        assert body["count"] == len(body["rows"])

    def test_pdf_forbidden_for_member(self, member):
        r = member.get(f"{API}/reports/events?format=pdf")
        assert r.status_code == 403, f"expected 403 got {r.status_code}"

    def test_pdf_anonymous(self, anon):
        r = anon.get(f"{API}/reports/events?format=pdf")
        assert r.status_code in (401, 403)

    def test_unknown_report_type(self, admin):
        r = admin.get(f"{API}/reports/not_a_report?format=pdf")
        assert r.status_code == 400


# ---------------- FEATURE: message threads ----------------
class TestMessageThreads:
    def test_send_reply_and_thread_visibility(self, admin, member):
        # admin sends new message with attachment to ambassador user_amb1
        fid = _upload(_bearer(ADMIN_TOKEN))
        subject = f"TEST_thread {uuid.uuid4().hex[:6]}"
        r = admin.post(f"{API}/messages", json={
            "subject": subject, "body": "Initial staff message", "recipient_ids": [MEMBER_UID],
            "file_ids": [fid],
        })
        assert r.status_code == 200, r.text[:300]
        msg = r.json()
        assert "_id" not in msg
        thread_id = msg["thread_id"]
        assert thread_id

        # ambassador sees the thread in list
        lst = member.get(f"{API}/messages")
        assert lst.status_code == 200
        assert any(m["thread_id"] == thread_id for m in lst.json())

        # ambassador opens thread
        t = member.get(f"{API}/messages/{thread_id}/thread")
        assert t.status_code == 200, t.text[:300]
        tdata = t.json()
        assert tdata["subject"] == subject
        assert len(tdata["messages"]) == 1
        assert tdata["messages"][0]["files"][0]["id"] == fid

        # attachment downloadable by ambassador participant
        dl = member.get(f"{API}/files/{fid}/download", allow_redirects=True)
        assert dl.status_code == 200, f"attachment download {dl.status_code}"

        # ambassador replies with attachment
        rfid = _upload(_bearer(MEMBER_TOKEN), name="TEST_reply.txt", content=b"reply file")
        rep = member.post(f"{API}/messages/{thread_id}/reply", json={"body": "TEST reply body", "file_ids": [rfid]})
        assert rep.status_code == 200, rep.text[:300]
        reply = rep.json()
        assert reply["thread_id"] == thread_id
        assert reply["subject"] == subject
        assert reply["is_reply"] is True
        assert ADMIN_UID in reply["recipient_ids"] or len(reply["recipient_ids"]) >= 1

        # both users see 2 messages
        for sess, who in ((member, "member"), (admin, "admin")):
            t2 = sess.get(f"{API}/messages/{thread_id}/thread")
            assert t2.status_code == 200, who
            msgs = t2.json()["messages"]
            assert len(msgs) == 2, f"{who} sees {len(msgs)} messages"
            assert msgs[1]["body"] == "TEST reply body"
            assert msgs[1]["files"][0]["id"] == rfid

    def test_thread_404_unknown(self, admin):
        r = admin.get(f"{API}/messages/thread_nonexistent/thread")
        assert r.status_code == 404
        r2 = admin.post(f"{API}/messages/thread_nonexistent/reply", json={"body": "x"})
        assert r2.status_code == 404

    def test_non_participant_forbidden(self, admin, other_token):
        subject = f"TEST_private {uuid.uuid4().hex[:6]}"
        r = admin.post(f"{API}/messages", json={"subject": subject, "body": "private", "recipient_ids": [MEMBER_UID]})
        assert r.status_code == 200
        thread_id = r.json()["thread_id"]
        outsider = _bearer(other_token)
        g = outsider.get(f"{API}/messages/{thread_id}/thread")
        assert g.status_code == 403, f"expected 403 got {g.status_code}"
        p = outsider.post(f"{API}/messages/{thread_id}/reply", json={"body": "intrusion"})
        assert p.status_code == 403, f"expected 403 got {p.status_code}"

    def test_thread_anonymous(self, anon, admin):
        r = admin.post(f"{API}/messages", json={"subject": "TEST_anon", "body": "b", "recipient_ids": [MEMBER_UID]})
        thread_id = r.json()["thread_id"]
        assert anon.get(f"{API}/messages/{thread_id}/thread").status_code in (401, 403)


# ---------------- FEATURE: post-event reports ----------------
class TestEventReports:
    def test_owner_submit_report_and_view(self, member, admin):
        photo_id = _upload(_bearer(MEMBER_TOKEN), name="TEST_photo.png", content=b"\x89PNG\r\n\x1a\nfake")
        file_id = _upload(_bearer(MEMBER_TOKEN), name="TEST_summary.txt", content=b"summary")
        payload = {"actual_attendance": 42, "outcomes": "TEST outcomes recorded",
                   "highlights": "TEST highlights", "photo_file_ids": [photo_id], "file_ids": [file_id]}
        r = member.post(f"{API}/events/evt1/report", json=payload)
        assert r.status_code == 200, r.text[:300]
        rep = r.json()
        assert "_id" not in rep
        assert rep["actual_attendance"] == 42
        assert rep["outcomes"] == "TEST outcomes recorded"

        # event becomes Completed
        evs = member.get(f"{API}/events").json()
        evt1 = next(e for e in evs if e["id"] == "evt1")
        assert evt1["status"] == "Completed", f"status={evt1['status']}"

        # reports retrievable with photo metadata
        g = member.get(f"{API}/events/evt1/reports")
        assert g.status_code == 200
        reports = g.json()
        mine = [x for x in reports if x["id"] == rep["id"]]
        assert len(mine) == 1
        got = mine[0]
        assert got["photos"][0]["id"] == photo_id
        assert got["photos"][0]["original_filename"] == "TEST_photo.png"
        assert got["files"][0]["id"] == file_id
        assert got["submitted_by_id"] == MEMBER_UID

        # staff can also read
        assert admin.get(f"{API}/events/evt1/reports").status_code == 200

    def test_outcomes_required(self, member):
        r = member.post(f"{API}/events/evt1/report", json={"actual_attendance": 5})
        assert r.status_code == 422, f"expected validation error got {r.status_code}"

    def test_non_owner_non_staff_forbidden(self, member, admin, other_token):
        outsider = _bearer(other_token)
        r = outsider.post(f"{API}/events/evt1/report", json={"outcomes": "intrusion"})
        assert r.status_code == 403, f"expected 403 got {r.status_code}"

    def test_unapproved_event_rejected(self, member, admin):
        # member submits a new event -> status Submitted
        c = member.post(f"{API}/events", json={"name": "TEST_pending_event", "date": "2026-12-01"})
        assert c.status_code == 200, c.text[:300]
        eid = c.json()["id"]
        assert c.json()["status"] == "Submitted"
        r = member.post(f"{API}/events/{eid}/report", json={"outcomes": "too early"})
        assert r.status_code == 400, f"expected 400 got {r.status_code} {r.text[:200]}"

    def test_report_unknown_event(self, member):
        r = member.post(f"{API}/events/evt_nope/report", json={"outcomes": "x"})
        assert r.status_code == 404
        assert member.get(f"{API}/events/evt_nope/reports").status_code == 404

    def test_report_anonymous(self, anon):
        assert anon.post(f"{API}/events/evt1/report", json={"outcomes": "x"}).status_code in (401, 403)
