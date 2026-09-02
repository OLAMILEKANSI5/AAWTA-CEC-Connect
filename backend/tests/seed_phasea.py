import asyncio, os
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]


def now():
    return datetime.now(timezone.utc).isoformat()


async def main():
    # non-owner member (ambassador) used for 403 authorization checks
    await db.users.update_one({"user_id": "user_memba"}, {"$set": {
        "user_id": "user_memba", "email": "member.phasea@example.com", "name": "Member PhaseA",
        "role": "ambassador", "status": "active", "created_at": now()}}, upsert=True)
    await db.user_sessions.update_one({"session_token": "tok_memba"}, {"$set": {
        "user_id": "user_memba", "session_token": "tok_memba",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "created_at": now()}}, upsert=True)
    # member record linked to the session user (needed for document assignment/visibility tests)
    await db.members.update_one({"id": "mem_memba"}, {"$set": {
        "id": "mem_memba", "name": "Member PhaseA", "email": "member.phasea@example.com",
        "login_email": "member.phasea@example.com", "role": "ambassador", "state": "GA",
        "account_status": "active", "user_id": "user_memba", "linked": True,
        "public_profile": False, "onboarding": [], "created_at": now()}}, upsert=True)
    print("seeded member session tok_memba / user_memba + member mem_memba")


asyncio.run(main())
