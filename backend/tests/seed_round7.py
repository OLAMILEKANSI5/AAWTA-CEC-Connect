"""Seed an ambassador (member) user + session for role-visibility tests."""
import asyncio
from datetime import datetime, timedelta, timezone

from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient

env = dotenv_values("/app/backend/.env")
client = AsyncIOMotorClient(env["MONGO_URL"])
db = client[env["DB_NAME"]]


async def main():
    exp = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    await db.users.update_one(
        {"user_id": "u_amb_t7"},
        {"$set": {"user_id": "u_amb_t7", "email": "amb.t7@example.com", "name": "TEST Ambassador T7",
                  "role": "ambassador", "account_status": "active", "picture": None}},
        upsert=True,
    )
    await db.user_sessions.update_one(
        {"session_token": "tok_amb_t7"},
        {"$set": {"session_token": "tok_amb_t7", "user_id": "u_amb_t7", "expires_at": exp,
                  "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    await db.authorized_emails.update_one(
        {"email": "amb.t7@example.com"},
        {"$set": {"email": "amb.t7@example.com", "role": "ambassador"}},
        upsert=True,
    )
    print("seeded tok_amb_t7 / u_amb_t7 (ambassador)")


asyncio.run(main())
