"""Probe: does PUT /registrations/{id}/payment return confirmation_sent=True, and does the
flag eventually flip in the DB? (Phase A regression triage)"""
import os
import time

import requests
from dotenv import dotenv_values

BASE = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
S = requests.Session()
S.headers["Authorization"] = "Bearer tok_admtest"
EVENT = "evt_246d20a66b31"

r = S.post(f"{BASE}/events/{EVENT}/manual-registration", json={
    "first_name": "TEST_Probe", "last_name": "Flag", "email": "delivered@resend.dev",
    "phone": "555-999-8888", "member_status": "No", "ticket_category": "General Admission",
    "payment_status": "pending"})
print("create", r.status_code)
reg = r.json()
rid = reg["id"]
p = S.put(f"{BASE}/registrations/{rid}/payment", json={"payment_status": "paid"})
print("payment resp confirmation_sent =", p.json().get("confirmation_sent"))
for i in range(10):
    time.sleep(1)
    cur = [x for x in S.get(f"{BASE}/events/{EVENT}/registrations", params={"q": "TEST_Probe"}).json()["registrations"] if x["id"] == rid][0]
    if cur.get("confirmation_sent"):
        print(f"flag flipped after {i+1}s; status={cur.get('confirmation_status')}")
        break
else:
    print("flag NEVER flipped")
d = S.delete(f"{BASE}/registrations/{rid}")
print("cleanup", d.status_code)
