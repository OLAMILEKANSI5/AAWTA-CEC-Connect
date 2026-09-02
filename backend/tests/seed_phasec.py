"""Seed a temporary event owned by user_memba (non-staff owner) + one registration,
for Phase C export contact-field gating tests. Idempotent."""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

EVENT_ID = "evt_phasec_owner"
REG_ID = "reg_phasec_owner1"


def now():
    return datetime.now(timezone.utc).isoformat()


async def main():
    start = (datetime.now(timezone.utc) + timedelta(days=25))
    await db.events.update_one({"id": EVENT_ID}, {"$set": {
        "id": EVENT_ID, "name": "TEST_ PhaseC Owner Event", "status": "Approved", "public": True,
        "published": True, "submitted_by": "Member PhaseA", "submitted_by_id": "user_memba",
        "event_type": "In-Person", "city": "Atlanta", "state": "Georgia", "capacity": 50,
        "is_free": True, "registration_enabled": True,
        "ticket_categories": [{"name": "General Admission", "price": 0}],
        "start_date": start.date().isoformat(), "date": start.date().isoformat(),
        "description": "temp test event", "created_at": now()}}, upsert=True)
    await db.event_registrations.update_one({"id": REG_ID}, {"$set": {
        "id": REG_ID, "event_id": EVENT_ID, "event_name": "TEST_ PhaseC Owner Event",
        "first_name": "Owner", "last_name": "Gate", "name": "Owner Gate",
        "email": "ownergate@example.com", "phone": "555-000-1111", "state": "Georgia",
        "city": "Atlanta", "member_status": "No", "is_member": False, "source": "online",
        "ticket_category": "General Admission", "status": "registered", "checked_in": False,
        "confirmation_number": "CEC-PHASEC-01", "checkin_token": "tok_phasec_ci",
        "payment_status": "not_applicable", "newsletter_opt_in": True, "events_opt_in": False,
        "created_at": now()}}, upsert=True)
    print(f"seeded {EVENT_ID} owned by user_memba + reg {REG_ID}")


asyncio.run(main())
