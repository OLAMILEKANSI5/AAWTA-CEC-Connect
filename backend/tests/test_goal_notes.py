"""Backend tests for Goal Progress Notes + Activity History feature.

Covers:
- POST /api/goals/{id}/notes appends notes + history (no overwrite)
- History captures 'Goal created', 'Progress changed', 'Status changed', 'Note added'
- 'Needs Support' status accepted
- Significant status changes (Achieved/Deferred/Needs Support) create in-app notifications
  for leadership under category 'Goals'
- Non-significant statuses (In Progress) do NOT notify leadership
- PUT /api/goals/{id} still works and appends history
- Member 403 on another member's goal notes
- Members can add notes to their own goal
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ambassador-hub-29.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = "tok_admtest"
AMB = "tok_amb_g3test"
OTHER = "tok_g3other"


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_member_ids():
    r = requests.get(f"{API}/members", headers=H(ADMIN))
    assert r.status_code == 200, r.text
    members = r.json()
    # find ambassador member linked to tok_amb_g3test (user_g3amb) => mem_memba per creds
    amb_member = next((m for m in members if m.get("user_id") == "user_g3amb"), None)
    other_member = next((m for m in members if m.get("user_id") == "user_g3other"), None)
    assert amb_member, "ambassador member not found"
    return {"amb": amb_member["id"], "other": other_member["id"] if other_member else None}


@pytest.fixture()
def amb_goal(admin_member_ids):
    """Create a fresh goal owned by ambassador member; cleanup after."""
    r = requests.post(f"{API}/goals", headers=H(ADMIN), json={
        "title": "QA Goal Notes Test", "category": "Outreach", "member_id": admin_member_ids["amb"]
    })
    assert r.status_code == 200, r.text
    g = r.json()
    yield g
    # cleanup
    try:
        requests.delete(f"{API}/goals/{g['id']}", headers=H(ADMIN))
    except Exception:
        pass


class TestGoalCreationSeeds:
    def test_new_goal_has_history_and_empty_notes(self, amb_goal):
        assert amb_goal["status"] == "Not Started"
        assert amb_goal["progress"] == 0
        assert amb_goal.get("notes") == []
        hist = amb_goal.get("history") or []
        assert len(hist) >= 1
        assert any("created" in (h.get("event") or "").lower() for h in hist)


class TestPostGoalNotes:
    def test_add_multiple_notes_preserves_all(self, amb_goal):
        gid = amb_goal["id"]
        for i, txt in enumerate(["QA note one", "QA note two", "QA note three"]):
            r = requests.post(f"{API}/goals/{gid}/notes", headers=H(ADMIN),
                              json={"note": txt, "progress": (i+1)*10})
            assert r.status_code == 200, r.text
        g = requests.get(f"{API}/goals", headers=H(ADMIN)).json()
        goal = next(x for x in g if x["id"] == gid)
        notes = goal.get("notes") or []
        assert len(notes) == 3, f"expected 3 notes preserved, got {len(notes)}"
        texts = [n["text"] for n in notes]
        assert texts == ["QA note one", "QA note two", "QA note three"]
        # each note has author + created_at + status/progress snapshot
        for n in notes:
            assert n.get("author_name")
            assert n.get("created_at")
            assert "status" in n and "progress" in n

    def test_history_records_note_status_progress_events(self, amb_goal):
        gid = amb_goal["id"]
        r = requests.post(f"{API}/goals/{gid}/notes", headers=H(ADMIN),
                          json={"note": "QA moving forward", "status": "In Progress", "progress": 25})
        assert r.status_code == 200
        goal = r.json()
        events = [h["event"] for h in (goal.get("history") or [])]
        assert any("Progress changed to 25%" == e for e in events)
        assert any("Status changed to In Progress" == e for e in events)
        assert any("Note added" == e for e in events)

    def test_empty_payload_rejected(self, amb_goal):
        r = requests.post(f"{API}/goals/{amb_goal['id']}/notes", headers=H(ADMIN), json={})
        assert r.status_code == 400


class TestNeedsSupportStatus:
    def test_needs_support_valid_status(self, amb_goal):
        gid = amb_goal["id"]
        r = requests.post(f"{API}/goals/{gid}/notes", headers=H(ADMIN),
                          json={"note": "QA blocked - need help", "status": "Needs Support"})
        assert r.status_code == 200
        assert r.json()["status"] == "Needs Support"


class TestLeadershipNotifications:
    def _latest_goal_notifs_count(self):
        r = requests.get(f"{API}/notifications", headers=H(ADMIN))
        assert r.status_code == 200
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        return sum(1 for n in items if (n.get("category") == "Goals"))

    def test_non_significant_status_no_notification(self, amb_goal):
        before = self._latest_goal_notifs_count()
        r = requests.post(f"{API}/goals/{amb_goal['id']}/notes", headers=H(ADMIN),
                          json={"status": "In Progress", "note": "QA started"})
        assert r.status_code == 200
        time.sleep(0.3)
        after = self._latest_goal_notifs_count()
        assert after == before, f"unexpected new Goals notifications: {before}->{after}"

    def test_significant_status_creates_notification(self, amb_goal):
        before = self._latest_goal_notifs_count()
        r = requests.post(f"{API}/goals/{amb_goal['id']}/notes", headers=H(ADMIN),
                          json={"status": "Needs Support", "note": "QA blocked"})
        assert r.status_code == 200
        time.sleep(0.5)
        after = self._latest_goal_notifs_count()
        assert after > before, f"expected new Goals notification, {before}->{after}"

    def test_deferred_status_creates_notification(self, amb_goal):
        before = self._latest_goal_notifs_count()
        r = requests.post(f"{API}/goals/{amb_goal['id']}/notes", headers=H(ADMIN),
                          json={"status": "Deferred", "note": "QA parked"})
        assert r.status_code == 200
        time.sleep(0.5)
        after = self._latest_goal_notifs_count()
        assert after > before


class TestPutGoalStillWorks:
    def test_put_goal_progress_appends_history(self, amb_goal):
        gid = amb_goal["id"]
        r = requests.put(f"{API}/goals/{gid}", headers=H(ADMIN), json={"progress": 55})
        assert r.status_code == 200
        goal = r.json()
        events = [h["event"] for h in (goal.get("history") or [])]
        assert any("Progress changed to 55%" == e for e in events)
        assert goal["progress"] == 55


class TestMemberPermissions:
    def test_member_can_add_note_to_own_goal(self, amb_goal):
        r = requests.post(f"{API}/goals/{amb_goal['id']}/notes", headers=H(AMB),
                          json={"note": "QA member self note", "progress": 40})
        assert r.status_code == 200, r.text
        assert any(n["text"] == "QA member self note" for n in r.json().get("notes", []))

    def test_other_member_403_on_someone_elses_goal(self, amb_goal):
        r = requests.post(f"{API}/goals/{amb_goal['id']}/notes", headers=H(OTHER),
                          json={"note": "QA should be forbidden"})
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


class TestRegressionActivityReports:
    def test_activity_report_endpoint_reachable(self):
        r = requests.get(f"{API}/activity-reports", headers=H(ADMIN))
        assert r.status_code in (200, 404)  # existence check; not 500
