"""Remove UI-created TEST registrations from Phase B frontend testing."""
import asyncio
from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient

be = dotenv_values("/app/backend/.env")


async def main():
    db = AsyncIOMotorClient(be["MONGO_URL"])[be["DB_NAME"]]
    regs = await db.event_registrations.find({"name": {"$regex": "^TESTUI"}}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
    ids = [r["id"] for r in regs]
    print("deleting", regs)
    if ids:
        await db.event_registrations.delete_many({"id": {"$in": ids}})
        await db.audit_logs.delete_many({"related_id": {"$in": ids}})
        await db.email_log.delete_many({"related_id": {"$in": ids}})
        await db.consents.delete_many({"reg_id": {"$in": ids}})
    left = await db.event_registrations.count_documents({"event_id": "evt_246d20a66b31"})
    print("remaining regs on evt_246d20a66b31:", left)
    # sanity: seeded events still published
    for eid in ("evt_246d20a66b31", "evt_badgetest"):
        ev = await db.events.find_one({"id": eid}, {"_id": 0, "status": 1, "published": 1})
        print(eid, ev)

asyncio.run(main())
