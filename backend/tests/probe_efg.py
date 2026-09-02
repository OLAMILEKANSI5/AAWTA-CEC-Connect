"""Edge-case probes for Phase E/F/G (security & robustness)."""
import os
import uuid

import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE}/api"
ADMIN = {"Authorization": "Bearer tok_admtest"}
MEMBER = {"Authorization": "Bearer tok_memba"}
EVT = "evt_246d20a66b31"
T = 60


def mk(**over):
    b = {"title": f"TEST_PROBE_{uuid.uuid4().hex[:6]}", "category": "Onboarding", "description": "probe"}
    b.update(over)
    r = requests.post(f"{API}/documents", json=b, headers=ADMIN, timeout=T)
    return r.json()


def rm(did):
    requests.put(f"{API}/documents/{did}", json={"title": "TEST_cleanup", "category": "Onboarding", "audience": "private_draft", "assigned_to": [], "assigned_roles": []}, headers=ADMIN, timeout=T)
    print("delete cleanup:", requests.delete(f"{API}/documents/{did}", headers=ADMIN, timeout=T).status_code)


print("=== 1. Member signing an invisible private_draft doc (should be 403) ===")
d = mk()
r = requests.post(f"{API}/documents/{d['id']}/sign", json={"legal_name": "Member PhaseA", "consent": True}, headers=MEMBER, timeout=T)
print("sign private_draft as member:", r.status_code, r.text[:160])
rm(d["id"])

print("=== 2. PUT /documents/{id} with partial payload -> assignments wiped? ===")
d = mk(audience="ambassadors_only", assigned_roles=["ambassador"])
requests.post(f"{API}/documents/{d['id']}/assign", json={"member_ids": ["mem_memba"], "notify": False}, headers=ADMIN, timeout=T)
before = requests.get(f"{API}/documents/{d['id']}", headers=ADMIN, timeout=T).json()
print("before edit: audience=%s assigned_to=%s roles=%s" % (before["audience"], before["assigned_to"], before["assigned_roles"]))
r = requests.put(f"{API}/documents/{d['id']}", json={"title": before["title"] + "_X", "category": "Onboarding"}, headers=ADMIN, timeout=T)
print("partial PUT status:", r.status_code)
after = requests.get(f"{API}/documents/{d['id']}", headers=ADMIN, timeout=T).json()
print("after edit: audience=%s assigned_to=%s roles=%s" % (after["audience"], after["assigned_to"], after["assigned_roles"]))
rm(d["id"])

print("=== 3. archive nonexistent doc (expect 404) ===")
r = requests.put(f"{API}/documents/doc_nonexistent/archive", json={"archived": True}, headers=ADMIN, timeout=T)
print("archive missing doc:", r.status_code, r.text[:120])

print("=== 4. invalid audience value accepted? ===")
d = mk(audience="not_a_real_audience")
print("create with bogus audience:", d.get("audience", d))
if d.get("id"):
    rm(d["id"])

print("=== 5. convert an application that is NOT approved ===")
app = requests.post(f"{API}/public/applications", json={"type": "volunteer", "data": {"first_name": "TEST_NotApproved", "last_name": "Probe", "email": "delivered@resend.dev", "state": "GA"}}, timeout=T).json()
r = requests.post(f"{API}/applications/{app['id']}/convert", headers=ADMIN, timeout=T)
print("convert New (not approved) application:", r.status_code, str(r.json())[:120])
mid = r.json().get("id") if r.status_code == 200 else None
from pymongo import MongoClient
env = dotenv_values("/app/backend/.env")
db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
if mid:
    db.members.delete_many({"id": mid})
    db.email_log.delete_many({"related_id": mid})
db.applications.delete_many({"id": app["id"]})
db.authorized_emails.delete_many({"email": "delivered@resend.dev"})

print("=== 6. Assigned check-in volunteer scope on other endpoints ===")
requests.put(f"{API}/events/{EVT}/checkin-assignees", json={"user_ids": ["user_memba"]}, headers=ADMIN, timeout=T)
regs = requests.get(f"{API}/events/{EVT}/registrations", headers=ADMIN, timeout=T).json()
items = regs if isinstance(regs, list) else (regs.get("registrations") or regs.get("items") or [])
rid = items[0]["id"]
for label, resp in [
    ("GET registrations (list)", requests.get(f"{API}/events/{EVT}/registrations", headers=MEMBER, timeout=T)),
    ("POST walkin", requests.post(f"{API}/events/{EVT}/registrations", json={"first_name": "TEST_Walkin", "last_name": "Probe", "email": "delivered@resend.dev", "member_status": "No"}, headers=MEMBER, timeout=T)),
    ("GET export", requests.get(f"{API}/events/{EVT}/export?format=csv", headers=MEMBER, timeout=T)),
    ("PUT edit reg", requests.put(f"{API}/registrations/{rid}", json={"job_title": "TEST"}, headers=MEMBER, timeout=T)),
    ("DELETE reg", requests.delete(f"{API}/registrations/{rid}", headers=MEMBER, timeout=T)),
    ("GET members", requests.get(f"{API}/members", headers=MEMBER, timeout=T)),
    ("GET audit-logs", requests.get(f"{API}/audit-logs", headers=MEMBER, timeout=T)),
]:
    print(f"  volunteer {label}: {resp.status_code}")
    if label == "POST walkin" and resp.status_code == 200:
        db.event_registrations.delete_many({"id": resp.json().get("id") or resp.json().get("registration", {}).get("id")})
requests.put(f"{API}/events/{EVT}/checkin-assignees", json={"user_ids": []}, headers=ADMIN, timeout=T)
db.event_registrations.delete_many({"first_name": "TEST_Walkin"})
print("cleanup done; assignees:", requests.get(f"{API}/events/{EVT}", headers=ADMIN, timeout=T).json().get("checkin_assignees"))
print("leftover TEST_ docs:", [d["title"] for d in db.documents.find({"title": {"$regex": "^TEST_"}}, {"title": 1})])
