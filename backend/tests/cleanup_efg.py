"""Cleanup TEST_ artifacts created by Phase E/F/G testing."""
import os
from dotenv import dotenv_values
from pymongo import MongoClient

env = dotenv_values("/app/backend/.env")
db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]

docs = list(db.documents.find({"title": {"$regex": "^TEST_"}}, {"id": 1, "title": 1}))
ids = [d["id"] for d in docs]
print("removing docs:", [d["title"] for d in docs])
print("signatures:", db.signatures.delete_many({"document_id": {"$in": ids}}).deleted_count)
print("docs:", db.documents.delete_many({"id": {"$in": ids}}).deleted_count)
print("members:", db.members.delete_many({"name": {"$regex": "^TEST_"}}).deleted_count)
print("applications:", db.applications.delete_many({"name": {"$regex": "TEST_"}}).deleted_count)
print("regs:", db.event_registrations.delete_many({"first_name": {"$regex": "^TEST_"}}).deleted_count)
print("authorized_emails:", db.authorized_emails.delete_many({"email": "delivered@resend.dev"}).deleted_count)
db.events.update_one({"id": "evt_246d20a66b31"}, {"$set": {"checkin_assignees": []}})
ev = db.events.find_one({"id": "evt_246d20a66b31"}, {"status": 1, "published": 1, "checkin_assignees": 1, "_id": 0})
print("event state:", ev)
print("remaining TEST docs:", db.documents.count_documents({"title": {"$regex": "^TEST_"}}))
