import asyncio, os, uuid
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def now():
    return datetime.now(timezone.utc).isoformat()


async def main():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ["DB_NAME"]]
    uid = "user_admtest"
    await db.users.update_one({"user_id": uid}, {"$set": {"user_id": uid, "email": "admin.test@example.com", "name": "Test Admin", "role": "super_admin", "account_status": "active", "created_at": now()}}, upsert=True)
    await db.authorized_emails.update_one({"email": "admin.test@example.com"}, {"$set": {"email": "admin.test@example.com", "role": "super_admin", "status": "active"}}, upsert=True)
    tok = "tok_admtest"
    await db.user_sessions.update_one({"session_token": tok}, {"$set": {"user_id": uid, "session_token": tok, "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(), "created_at": now()}}, upsert=True)
    future = (datetime.now(timezone.utc) + timedelta(days=20)).strftime("%Y-%m-%d")
    eid = "evt_badgetest"
    await db.events.update_one({"id": eid}, {"$set": {"id": eid, "name": "CEC Community Career Fair", "date": future, "start_time": "10:00 AM", "category": "Career Fair", "format": "In-Person", "city": "Atlanta", "state": "Georgia", "capacity": 3, "status": "Approved", "published": True, "archived": False, "registration_status": "open", "submitted_by": "Test Admin", "submitted_by_id": uid, "description": "A community career fair.", "created_at": now()}}, upsert=True)
    await db.event_registrations.delete_many({"event_id": eid})
    regs = [("Amara Bell", "amara@example.com", "registered", True), ("Jordan Lee", "jordan@example.com", "registered", False), ("Maya Cole", "maya@example.com", "registered", False), ("Nia Ford", "nia@example.com", "waitlist", False)]
    for n, e, s, ci in regs:
        await db.event_registrations.insert_one({"id": "reg_" + uuid.uuid4().hex[:8], "event_id": eid, "event_name": "CEC Community Career Fair", "name": n, "email": e, "status": s, "checked_in": ci, "checked_in_at": now() if ci else None, "created_at": now()})
    print("seeded event date", future, "| events", await db.events.count_documents({}), "| regs", await db.event_registrations.count_documents({"event_id": eid}))


asyncio.run(main())
