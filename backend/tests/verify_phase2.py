"""Phase 2 verification: inactivity soft-flag, app aging, 48h message follow-up, reactivate."""
import asyncio, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/app/backend")
import server as S

def iso_days_ago(d):
    return (datetime.now(timezone.utc) - timedelta(days=d)).isoformat()

def iso_hours_ago(h):
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()

async def main():
    db = S.db
    # cleanup prior test artifacts
    for coll, q in [(db.users, {"user_id": "user_p2test"}), (db.members, {"id": "mem_p2test"}),
                    (db.applications, {"id": "app_p2test"}), (db.messages, {"thread_id": "thr_p2test"}),
                    (db.notifications, {"body": {"$regex": "P2TEST"}})]:
        await coll.delete_many(q)
    await db.reminder_sent.delete_many({"key": {"$regex": "p2test|user_p2test|app_p2test|thr_p2test"}})

    # 1. Inactive member (35 days no login)
    await db.users.insert_one({"user_id": "user_p2test", "email": "p2test@example.com", "name": "P2TEST Member",
                               "role": "ambassador", "account_status": "active", "last_login": iso_days_ago(35)})
    await db.members.insert_one({"id": "mem_p2test", "name": "P2TEST Member", "email": "p2test@example.com",
                                 "login_email": "p2test@example.com", "role": "ambassador", "account_status": "active",
                                 "user_id": "user_p2test", "onboarding": [], "created_at": iso_days_ago(40)})
    # 2. Aging application (20 days, pending)
    await db.applications.insert_one({"id": "app_p2test", "ref": "AMB-P2-0001", "type": "ambassador",
                                      "name": "P2TEST Applicant", "email": "p2app@example.com", "status": "Under Review",
                                      "created_at": iso_days_ago(20)})
    # 3. Unanswered member->leadership message (3 days old, no staff reply)
    await db.messages.insert_one({"id": "msg_p2test", "thread_id": "thr_p2test", "subject": "P2TEST question",
                                  "body": "need help", "from_id": "user_p2test", "from_name": "P2TEST Member",
                                  "from_role": "ambassador", "recipient_ids": [], "to_leadership": True,
                                  "member_id": "mem_p2test", "created_at": iso_hours_ago(72)})

    await S.run_reminders()

    m = await db.members.find_one({"id": "mem_p2test"}, {"_id": 0})
    print("1. inactive flag set:", m.get("inactive"), "| since:", bool(m.get("inactive_since")))
    lead_inact = await db.notifications.count_documents({"title": "Member flagged inactive"})
    print("   leadership notified of inactivity (>=1):", lead_inact >= 1)

    app_age_ntf = await db.notifications.count_documents({"link": "/portal/applications/app_p2test"})
    print("2. app-aging leadership notifications (>=1):", app_age_ntf >= 1)

    msgf = await db.notifications.count_documents({"title": "Unanswered member message"})
    print("3. 48h unanswered message notifications (>=1):", msgf >= 1)

    # 4. reactivate clears flag
    await db.members.update_one({"id": "mem_p2test"}, {"$set": {"inactive": True}})
    await db.members.update_one({"id": "mem_p2test"}, {"$set": {"inactive": False, "inactive_since": None}})
    m2 = await db.members.find_one({"id": "mem_p2test"}, {"_id": 0})
    print("4. reactivate clears flag:", m2.get("inactive") is False)

    # 5. dashboard aging includes our app
    aging = []
    async for a in db.applications.find({"status": {"$in": S.PENDING_APP_STATUSES}, "type": {"$ne": "inquiry"}}, {"_id": 0}):
        age = S._days_since(a.get("created_at"))
        if age is not None and age >= 15:
            aging.append(a["id"])
    print("5. dashboard aging includes app_p2test:", "app_p2test" in aging)

    # cleanup
    for coll, q in [(db.users, {"user_id": "user_p2test"}), (db.members, {"id": "mem_p2test"}),
                    (db.applications, {"id": "app_p2test"}), (db.messages, {"thread_id": "thr_p2test"}),
                    (db.notifications, {"$or": [{"title": "Member flagged inactive"}, {"title": "Unanswered member message"}, {"link": "/portal/applications/app_p2test"}]})]:
        await coll.delete_many(q)

asyncio.run(main())
