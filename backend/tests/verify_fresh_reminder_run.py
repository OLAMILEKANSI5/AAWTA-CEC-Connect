"""One-off verification: clear dedupe rows + reminder notifications, trigger cron, confirm re-creation."""
import time
import uuid

import requests
from dotenv import dotenv_values
from pymongo import MongoClient

be = dotenv_values("/app/backend/.env")
fe = dotenv_values("/app/frontend/.env")
API = fe["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
db = MongoClient(be["MONGO_URL"])[be["DB_NAME"]]

before_keys = sorted(d["key"] for d in db.reminder_sent.find({}, {"key": 1}))
print("keys before:", before_keys)
db.reminder_sent.delete_many({})
db.notifications.delete_many({"type": "reminder"})
print("cleared. notifications(reminder) now:", db.notifications.count_documents({"type": "reminder"}))

run_id = f"TEST_fresh_{uuid.uuid4().hex[:8]}"
r = requests.post(API + "/cron/reminders", json={},
                  headers={"Authorization": "Bearer " + be["WEBHOOK_CRON_SECRET"], "X-Webhook-Id": run_id}, timeout=20)
print("cron status", r.status_code, r.json())
time.sleep(6)

after_keys = sorted(d["key"] for d in db.reminder_sent.find({}, {"key": 1}))
print("keys after:", after_keys)
notes = list(db.notifications.find({"type": "reminder"}, {"_id": 0, "user_id": 1, "title": 1, "link": 1}))
print("notifications created:", len(notes))
for n in notes:
    print("  ", n)
print("accounts deactivated?", db.users.count_documents({"account_status": {"$ne": "active"}}),
      db.members.count_documents({"account_status": {"$ne": "active"}}))
db.reminder_runs.delete_many({"run_id": run_id})
assert after_keys, "FAIL: no dedupe keys recreated"
assert notes, "FAIL: no reminder notifications created"
print("PASS: fresh reminder run recreated dedupe keys and notifications")
