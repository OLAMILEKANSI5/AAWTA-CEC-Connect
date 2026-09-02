"""Remove Phase C test artifacts (imported rows, temp owner event)."""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]


async def main():
    r1 = await db.event_registrations.delete_many({"source": "Bulk Import"})
    r2 = await db.event_registrations.delete_many({"event_id": "evt_phasec_owner"})
    r3 = await db.events.delete_many({"id": "evt_phasec_owner"})
    r4 = await db.event_registrations.delete_many({"name": {"$regex": "^TEST_"}})
    print(f"bulk-import regs={r1.deleted_count} owner-regs={r2.deleted_count} events={r3.deleted_count} test-regs={r4.deleted_count}")


asyncio.run(main())
