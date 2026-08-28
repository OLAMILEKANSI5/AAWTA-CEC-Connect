from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Form, Header, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, io, csv, json, asyncio, hmac
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta

import httpx
import storage as storage_mod
from emailer import send_safe, p as ep

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'aawtassn@gmail.com')
SUPER_ADMIN_EMAIL = os.environ.get('SUPER_ADMIN_EMAIL', 'aawtassn@gmail.com')
EMERGENT_AUTH_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ROLES = ["super_admin", "director", "administrator", "ambassador", "volunteer"]
STAFF_ROLES = ["super_admin", "director", "administrator"]
LEADERSHIP_ROLES = ["super_admin", "director"]

# ---------------- helpers ----------------
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def new_id(prefix="id"):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def clean(doc):
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc

async def log_audit(user, action, related_type=None, related_id=None, detail=None):
    await db.audit_logs.insert_one({
        "id": new_id("audit"),
        "user_id": user.get("user_id") if user else None,
        "user_email": user.get("email") if user else "system",
        "user_name": user.get("name") if user else "System",
        "action": action,
        "related_type": related_type,
        "related_id": related_id,
        "detail": detail or {},
        "created_at": now_iso(),
    })

async def add_timeline(related_type, related_id, event, actor=None, meta=None):
    await db.timeline.insert_one({
        "id": new_id("tl"),
        "related_type": related_type,
        "related_id": related_id,
        "event": event,
        "actor": (actor or {}).get("name") if actor else "System",
        "meta": meta or {},
        "created_at": now_iso(),
    })

async def notify_user(user_id, title, body, link=None, ntype="info"):
    await db.notifications.insert_one({
        "id": new_id("ntf"),
        "user_id": user_id,
        "title": title,
        "body": body,
        "link": link,
        "type": ntype,
        "read": False,
        "created_at": now_iso(),
    })

async def get_director_recipients():
    """Emails that receive director-level notifications."""
    emails = {ADMIN_EMAIL}
    async for a in db.authorized_emails.find({"role": {"$in": LEADERSHIP_ROLES}, "status": "active", "notify_directors": True}, {"_id": 0}):
        emails.add(a["email"])
    return list(emails)

async def notify_admins(subject, title, body_html):
    for em in await get_director_recipients():
        await send_safe(to=em, subject=subject, title=title, body_html=body_html)

# ---------------- auth ----------------
async def get_current_user(request: Request, authorization: Optional[str] = Header(None)):
    token = request.cookies.get("session_token")
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    exp = session["expires_at"]
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.get("account_status") in ("suspended", "deactivated"):
        raise HTTPException(status_code=403, detail="Account " + user.get("account_status"))
    return user

def require_roles(*roles):
    async def dep(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dep

@api_router.post("/auth/session")
async def create_session(request: Request, response: Response, x_session_id: Optional[str] = Header(None)):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing session id")
    async with httpx.AsyncClient(timeout=30) as hc:
        r = await hc.get(EMERGENT_AUTH_URL, headers={"X-Session-ID": x_session_id})
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Auth failed")
    data = r.json()
    email = data["email"].lower().strip()

    # authorization check
    auth_entry = await db.authorized_emails.find_one({"email": email}, {"_id": 0})
    if not auth_entry:
        raise HTTPException(status_code=403, detail="Your Google account has not been authorized for CEC Connect. Please contact AAWTA for assistance.")
    if auth_entry.get("status") in ("suspended", "deactivated"):
        raise HTTPException(status_code=403, detail="Your CEC Connect access has been " + auth_entry.get("status") + ". Please contact AAWTA for assistance.")

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        user = {
            "user_id": new_id("user"),
            "email": email,
            "name": data.get("name") or email,
            "picture": data.get("picture"),
            "role": auth_entry["role"],
            "account_status": "active",
            "created_at": now_iso(),
            "last_login": now_iso(),
        }
        await db.users.insert_one(dict(user))
    else:
        await db.users.update_one({"email": email}, {"$set": {
            "last_login": now_iso(),
            "name": data.get("name") or user["name"],
            "picture": data.get("picture") or user.get("picture"),
            "role": auth_entry["role"],
        }})
        user = await db.users.find_one({"email": email}, {"_id": 0})

    # link member record if exists
    await db.members.update_one({"login_email": email}, {"$set": {"user_id": user["user_id"], "linked": True}})

    session_token = new_id("sess") + uuid.uuid4().hex
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": now_iso(),
    })
    response.set_cookie("session_token", session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*3600)
    await log_audit(user, "login")
    return clean(user)

@api_router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    member = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return {**user, "member_id": member["id"] if member else None}

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}

# ---------------- settings (editable portal config) ----------------
DEFAULT_SETTINGS = {
    "id": "portal_settings",
    "org_name": "AAWTA",
    "portal_name": "CEC Connect",
    "portal_subtitle": "AAWTA Community Engagement Portal",
    "address": "5269 Buford Highway Suite 213, Buford Highway, Doraville GA 30340",
    "phone": "770 756 6768",
    "email": "aawtassn@gmail.com",
    "website": "https://www.aawta.org",
    "calendar_link": "https://calendar.google.com",
    "slack_link": "https://slack.com",
    "membership_link": "https://www.aawta.org",
}

async def get_settings_doc():
    s = await db.settings.find_one({"id": "portal_settings"}, {"_id": 0})
    if not s:
        await db.settings.insert_one(dict(DEFAULT_SETTINGS))
        s = dict(DEFAULT_SETTINGS)
    return s

@api_router.get("/settings")
async def get_settings():
    return await get_settings_doc()

@api_router.put("/settings")
async def update_settings(payload: Dict[str, Any], user=Depends(require_roles("super_admin", "director", "administrator"))):
    await get_settings_doc()
    payload.pop("id", None)
    await db.settings.update_one({"id": "portal_settings"}, {"$set": payload})
    await log_audit(user, "settings_updated", "settings", "portal_settings", payload)
    return await get_settings_doc()

# ---------------- applications & inquiries ----------------
class ApplicationIn(BaseModel):
    type: str  # ambassador | volunteer | inquiry
    data: Dict[str, Any]
    honeypot: Optional[str] = ""

APP_STATUSES = ["Submitted", "New", "Under Review", "More Information Requested", "Interview Requested",
                "Interview Scheduled", "Recommended", "Approved", "Waitlisted", "Declined", "Withdrawn",
                "Converted to Member", "Archived"]

# simple rate limit
_rate = {}
def rate_ok(key, limit=5, window=300):
    nowt = datetime.now(timezone.utc).timestamp()
    arr = [t for t in _rate.get(key, []) if nowt - t < window]
    if len(arr) >= limit:
        return False
    arr.append(nowt)
    _rate[key] = arr
    return True

@api_router.post("/public/applications")
async def submit_application(payload: ApplicationIn, request: Request):
    if payload.honeypot:
        raise HTTPException(status_code=400, detail="Spam detected")
    ip = request.client.host if request.client else "x"
    if not rate_ok(f"app_{ip}", limit=8, window=600):
        raise HTTPException(status_code=429, detail="Too many submissions. Please try again later.")
    if payload.type not in ("ambassador", "volunteer", "inquiry"):
        raise HTTPException(status_code=400, detail="Invalid type")
    email = (payload.data.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    prefix = {"ambassador": "AMB", "volunteer": "VOL", "inquiry": "INQ"}[payload.type]
    counter = await db.counters.find_one_and_update(
        {"id": f"app_{payload.type}"}, {"$inc": {"seq": 1}},
        upsert=True, return_document=True,
    )
    ref = f"{prefix}-{datetime.now().year}-{counter['seq']:04d}"

    # duplicate check
    dup = await db.applications.find_one({"type": payload.type, "email": email}, {"_id": 0})

    app_doc = {
        "id": new_id("app"),
        "ref": ref,
        "type": payload.type,
        "email": email,
        "name": (payload.data.get("first_name", "") + " " + payload.data.get("last_name", "")).strip() or payload.data.get("full_name") or email,
        "state": payload.data.get("state") or payload.data.get("represent_state"),
        "status": "New",
        "data": payload.data,
        "files": [],
        "assigned_reviewer": None,
        "assigned_director": None,
        "notes": [],
        "tasks": [],
        "interview": None,
        "decision_history": [],
        "possible_duplicate": bool(dup),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.applications.insert_one(dict(app_doc))
    await add_timeline("application", app_doc["id"], f"{payload.type.title()} application submitted ({ref})")

    # emails
    settings = await get_settings_doc()
    applicant_name = app_doc["name"]
    conf_body = (
        ep(f"Hi {applicant_name},") +
        ep(f"Thank you for your submission to the AAWTA Community Engagement Committee. Your reference number is <strong>{ref}</strong>.") +
        ep("Our team will review your submission and follow up soon. Submitting this form does not automatically grant portal access; access is granted after approval or invitation.")
    )
    asyncio.create_task(send_safe(to=email, subject=f"We received your CEC Connect submission ({ref})", title="Submission Received", body_html=conf_body))
    admin_body = (
        ep(f"A new <strong>{payload.type}</strong> submission was received.") +
        ep(f"Reference: <strong>{ref}</strong><br>Name: {applicant_name}<br>Email: {email}<br>State: {app_doc.get('state') or 'N/A'}") +
        (ep("&#9888; Possible duplicate detected for this email address.") if dup else "")
    )
    asyncio.create_task(notify_admins(f"New CEC {payload.type} submission ({ref})", "New Submission", admin_body))
    await log_audit(None, "application_submitted", "application", app_doc["id"], {"ref": ref, "type": payload.type})
    return {"ref": ref, "id": app_doc["id"]}

@api_router.get("/applications")
async def list_applications(user=Depends(require_roles(*STAFF_ROLES)),
                            type: Optional[str] = None, status: Optional[str] = None,
                            state: Optional[str] = None, q: Optional[str] = None):
    query = {}
    if type: query["type"] = type
    if status: query["status"] = status
    if state: query["state"] = state
    if q:
        query["$or"] = [{"name": {"$regex": q, "$options": "i"}}, {"email": {"$regex": q, "$options": "i"}}, {"ref": {"$regex": q, "$options": "i"}}]
    apps = await db.applications.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return apps

@api_router.get("/applications/{app_id}")
async def get_application(app_id: str, user=Depends(require_roles(*STAFF_ROLES))):
    a = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Not found")
    a["timeline"] = await db.timeline.find({"related_type": "application", "related_id": app_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return a

class StatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None

@api_router.put("/applications/{app_id}/status")
async def update_app_status(app_id: str, payload: StatusUpdate, user=Depends(require_roles(*STAFF_ROLES))):
    a = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Not found")
    entry = {"status": payload.status, "note": payload.note, "by": user["name"], "at": now_iso()}
    await db.applications.update_one({"id": app_id}, {"$set": {"status": payload.status, "updated_at": now_iso()}, "$push": {"decision_history": entry}})
    await add_timeline("application", app_id, f"Status changed to {payload.status}", user)
    await log_audit(user, "application_status_change", "application", app_id, entry)
    # notify applicant on major decisions
    subj_map = {"Approved": "approved", "Waitlisted": "waitlisted", "Declined": "declined", "More Information Requested": "needs more information"}
    if payload.status in subj_map:
        body = ep(f"Hi {a['name']},") + ep(f"Your CEC application <strong>{a['ref']}</strong> status is now: <strong>{payload.status}</strong>.") + (ep(payload.note) if payload.note else "")
        asyncio.create_task(send_safe(to=a["email"], subject=f"Your CEC application update ({a['ref']})", title="Application Update", body_html=body))
    return {"ok": True}

class AssignReviewer(BaseModel):
    assigned_reviewer: Optional[str] = None
    assigned_director: Optional[str] = None

@api_router.put("/applications/{app_id}/assign")
async def assign_app(app_id: str, payload: AssignReviewer, user=Depends(require_roles(*STAFF_ROLES))):
    if not await db.applications.find_one({"id": app_id}, {"_id": 0}):
        raise HTTPException(404, "Not found")
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    await db.applications.update_one({"id": app_id}, {"$set": {**upd, "updated_at": now_iso()}})
    await add_timeline("application", app_id, "Assignment updated", user)
    await log_audit(user, "application_assigned", "application", app_id, upd)
    return {"ok": True}

class NoteIn(BaseModel):
    text: str
    visibility: str = "leadership"  # leadership | shared_member | shared_team

@api_router.post("/applications/{app_id}/notes")
async def add_app_note(app_id: str, payload: NoteIn, user=Depends(require_roles(*STAFF_ROLES))):
    note = {"id": new_id("note"), "text": payload.text, "visibility": payload.visibility, "author": user["name"], "author_id": user["user_id"], "created_at": now_iso()}
    await db.applications.update_one({"id": app_id}, {"$push": {"notes": note}})
    await add_timeline("application", app_id, "Note added", user)
    await log_audit(user, "note_added", "application", app_id)
    return note

@api_router.post("/applications/{app_id}/convert")
async def convert_to_member(app_id: str, user=Depends(require_roles(*LEADERSHIP_ROLES))):
    a = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Not found")
    role = "ambassador" if a["type"] == "ambassador" else "volunteer"
    member = await create_member_record(
        name=a["name"], email=a["email"], role=role, state=a.get("state"),
        data=a.get("data", {}), created_by=user, source_application=app_id,
    )
    await db.applications.update_one({"id": app_id}, {"$set": {"status": "Converted to Member", "member_id": member["id"], "updated_at": now_iso()}})
    await add_timeline("application", app_id, "Converted to member", user)
    await log_audit(user, "application_converted", "application", app_id, {"member_id": member["id"]})
    return member

# ---------------- members ----------------
ONBOARDING_STEPS = [
    "Complete profile", "Upload headshot", "Review CEC orientation",
    "Sign confidentiality agreement", "Sign commitment agreement", "Sign code of conduct",
    "Review role description", "Review communication guidelines", "Join Slack",
    "Review AAWTA calendar", "Establish first monthly goals", "Attend orientation",
    "Receive final onboarding approval",
]

async def create_member_record(*, name, email, role, state=None, data=None, created_by=None, source_application=None, region=None, focus_areas=None, director=None, login_email=None, notes=None):
    data = data or {}
    member = {
        "id": new_id("mem"),
        "name": name,
        "email": email.lower().strip(),
        "login_email": (login_email or email).lower().strip(),
        "role": role,
        "state": state,
        "region": region,
        "focus_areas": focus_areas or data.get("areas_of_interest") or [],
        "assigned_director": director,
        "phone": data.get("phone") or data.get("telephone"),
        "city": data.get("city"),
        "county": data.get("county"),
        "company": data.get("company") or data.get("organization"),
        "job_title": data.get("job_title"),
        "bio": data.get("bio") or data.get("reason") or "",
        "linkedin": data.get("linkedin"),
        "facebook": data.get("facebook"),
        "instagram": data.get("instagram"),
        "membership_status": data.get("membership_status"),
        "photo": None,
        "public_profile": False,
        "account_status": "active",
        "start_date": now_iso(),
        "onboarding": [{"step": s, "done": False, "due": None} for s in ONBOARDING_STEPS],
        "internal_notes": notes,
        "linked": False,
        "user_id": None,
        "source_application": source_application,
        "created_at": now_iso(),
        "created_by": (created_by or {}).get("name"),
    }
    await db.members.insert_one(dict(member))
    # authorize the login email
    await db.authorized_emails.update_one(
        {"email": member["login_email"]},
        {"$setOnInsert": {"email": member["login_email"], "created_at": now_iso()},
         "$set": {"role": role, "status": "active", "notify_directors": False, "member_id": member["id"]}},
        upsert=True,
    )
    await add_timeline("member", member["id"], f"{role.title()} member record created")
    return clean(member)

class ManualMemberIn(BaseModel):
    name: str
    email: EmailStr
    login_email: EmailStr
    role: str  # ambassador | volunteer
    state: Optional[str] = None
    region: Optional[str] = None
    focus_areas: List[str] = []
    assigned_director: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    company: Optional[str] = None
    internal_notes: Optional[str] = None
    send_invite: bool = True

@api_router.post("/members/manual")
async def add_member_manual(payload: ManualMemberIn, user=Depends(require_roles(*STAFF_ROLES))):
    member = await create_member_record(
        name=payload.name, email=payload.email, role=payload.role, state=payload.state,
        data={"phone": payload.phone, "city": payload.city, "company": payload.company},
        created_by=user, region=payload.region, focus_areas=payload.focus_areas,
        director=payload.assigned_director, login_email=payload.login_email, notes=payload.internal_notes,
    )
    await log_audit(user, "member_added_manual", "member", member["id"])
    if payload.send_invite:
        settings = await get_settings_doc()
        body = (ep(f"Hi {payload.name},") +
                ep("You have been assigned access to the AAWTA CEC Connect portal. Please sign in with the Google account associated with this email to complete your onboarding.") +
                ep(f'<a href="{settings["website"]}" style="color:#E0189C">Learn more about AAWTA</a>'))
        asyncio.create_task(send_safe(to=str(payload.login_email), subject="You've been invited to CEC Connect", title="Portal Invitation", body_html=body))
        await add_timeline("member", member["id"], "Portal invitation sent", user)
        await log_audit(user, "portal_invitation_sent", "member", member["id"])
    return member

@api_router.get("/members")
async def list_members(user=Depends(require_roles(*STAFF_ROLES)), role: Optional[str] = None, state: Optional[str] = None, q: Optional[str] = None):
    query = {}
    if role: query["role"] = role
    if state: query["state"] = state
    if q:
        query["$or"] = [{"name": {"$regex": q, "$options": "i"}}, {"email": {"$regex": q, "$options": "i"}}]
    return await db.members.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)

@api_router.get("/members/me")
async def my_member(user=Depends(get_current_user)):
    m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not m:
        m = await db.members.find_one({"login_email": user["email"]}, {"_id": 0})
    if not m:
        raise HTTPException(404, "No member profile")
    return m

@api_router.get("/members/{member_id}")
async def get_member(member_id: str, user=Depends(get_current_user)):
    m = await db.members.find_one({"id": member_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES and m.get("user_id") != user["user_id"]:
        raise HTTPException(403, "Forbidden")
    m["timeline"] = await db.timeline.find({"related_type": "member", "related_id": member_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return m

@api_router.put("/members/{member_id}")
async def update_member(member_id: str, payload: Dict[str, Any], user=Depends(get_current_user)):
    m = await db.members.find_one({"id": member_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Not found")
    is_owner = m.get("user_id") == user["user_id"]
    if user["role"] not in STAFF_ROLES and not is_owner:
        raise HTTPException(403, "Forbidden")
    # members can only edit their own profile-ish fields
    if user["role"] not in STAFF_ROLES:
        allowed = {"bio", "phone", "city", "county", "company", "job_title", "linkedin", "facebook", "instagram", "photo", "public_profile", "membership_status"}
        payload = {k: v for k, v in payload.items() if k in allowed}
    payload.pop("id", None); payload.pop("_id", None)
    await db.members.update_one({"id": member_id}, {"$set": payload})
    await add_timeline("member", member_id, "Profile updated", user)
    await log_audit(user, "member_updated", "member", member_id)
    return await db.members.find_one({"id": member_id}, {"_id": 0})

@api_router.put("/members/{member_id}/onboarding")
async def update_onboarding(member_id: str, payload: Dict[str, Any], user=Depends(get_current_user)):
    m = await db.members.find_one({"id": member_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES and m.get("user_id") != user["user_id"]:
        raise HTTPException(403, "Forbidden")
    step = payload.get("step"); done = payload.get("done", True)
    onboarding = m.get("onboarding", [])
    for o in onboarding:
        if o["step"] == step:
            o["done"] = done
            o["completed_at"] = now_iso() if done else None
    await db.members.update_one({"id": member_id}, {"$set": {"onboarding": onboarding}})
    await add_timeline("member", member_id, f"Onboarding step '{step}' {'completed' if done else 'reopened'}", user)
    return {"ok": True}

@api_router.put("/members/{member_id}/status")
async def set_member_status(member_id: str, payload: Dict[str, Any], user=Depends(require_roles(*STAFF_ROLES))):
    status = payload.get("status")
    m = await db.members.find_one({"id": member_id}, {"_id": 0})
    if not m: raise HTTPException(404, "Not found")
    await db.members.update_one({"id": member_id}, {"$set": {"account_status": status}})
    await db.authorized_emails.update_one({"email": m["login_email"]}, {"$set": {"status": status}})
    if m.get("user_id"):
        await db.users.update_one({"user_id": m["user_id"]}, {"$set": {"account_status": status}})
    await log_audit(user, "member_status_change", "member", member_id, {"status": status})
    await add_timeline("member", member_id, f"Account {status}", user)
    return {"ok": True}

# ---------------- public directory & content ----------------
@api_router.get("/public/directory")
async def public_directory(state: Optional[str] = None, focus: Optional[str] = None, q: Optional[str] = None):
    query = {"role": "ambassador", "public_profile": True, "account_status": "active"}
    if state: query["state"] = state
    if focus: query["focus_areas"] = focus
    if q: query["name"] = {"$regex": q, "$options": "i"}
    members = await db.members.find(query, {"_id": 0}).to_list(500)
    out = []
    for m in members:
        out.append({"id": m["id"], "name": m["name"], "state": m.get("state"), "title": "State Ambassador",
                    "focus_areas": m.get("focus_areas", []), "bio": m.get("bio"), "photo": m.get("photo"),
                    "linkedin": m.get("linkedin"), "instagram": m.get("instagram"), "facebook": m.get("facebook")})
    return out

@api_router.get("/public/home")
async def public_home():
    settings = await get_settings_doc()
    spotlights = await db.members.find({"role": "ambassador", "public_profile": True, "account_status": "active"}, {"_id": 0}).limit(4).to_list(4)
    ann = await db.announcements.find({"public": True, "published": True}, {"_id": 0}).sort("created_at", -1).limit(3).to_list(3)
    events = await db.events.find({"status": {"$in": ["Approved", "Scheduled"]}, "public": True}, {"_id": 0}).sort("date", 1).limit(4).to_list(4)
    stats = {
        "ambassadors": await db.members.count_documents({"role": "ambassador"}),
        "volunteers": await db.members.count_documents({"role": "volunteer"}),
        "states": len(await db.members.distinct("state", {"role": "ambassador"})),
        "events": await db.events.count_documents({"status": {"$in": ["Approved", "Scheduled", "Completed"]}}),
    }
    return {"settings": settings, "spotlights": [{"id": m["id"], "name": m["name"], "state": m.get("state"), "photo": m.get("photo"), "focus_areas": m.get("focus_areas", []), "bio": m.get("bio")} for m in spotlights], "announcements": ann, "events": events, "stats": stats}

# ---------------- files ----------------
@api_router.post("/upload")
async def upload_file(file: UploadFile = File(...), category: str = Form("general"), user=Depends(get_current_user)):
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    fid = new_id("file")
    path = f"{storage_mod.APP_NAME}/uploads/{user['user_id']}/{fid}.{ext}"
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 25MB)")
    ctype = storage_mod.MIME_TYPES.get(ext, file.content_type or "application/octet-stream")
    result = await asyncio.to_thread(storage_mod.put_object, path, data, ctype)
    rec = {"id": fid, "storage_path": result["path"], "original_filename": file.filename, "content_type": ctype,
           "size": result.get("size", len(data)), "category": category, "uploaded_by": user["user_id"],
           "uploaded_by_name": user["name"], "is_deleted": False, "created_at": now_iso()}
    await db.files.insert_one(dict(rec))
    return clean(rec)

@api_router.post("/public/upload")
async def public_upload(file: UploadFile = File(...)):
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    fid = new_id("file")
    path = f"{storage_mod.APP_NAME}/public-uploads/{fid}.{ext}"
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 25MB)")
    ctype = storage_mod.MIME_TYPES.get(ext, file.content_type or "application/octet-stream")
    result = await asyncio.to_thread(storage_mod.put_object, path, data, ctype)
    rec = {"id": fid, "storage_path": result["path"], "original_filename": file.filename, "content_type": ctype,
           "size": result.get("size", len(data)), "category": "application", "is_deleted": False, "created_at": now_iso()}
    await db.files.insert_one(dict(rec))
    return {"id": fid, "storage_path": result["path"], "original_filename": file.filename}

@api_router.get("/files/{file_id}/download")
async def download_file(file_id: str, user=Depends(get_current_user)):
    rec = await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "File not found")
    data, ctype = await asyncio.to_thread(storage_mod.get_object, rec["storage_path"])
    return StreamingResponse(io.BytesIO(data), media_type=rec.get("content_type", ctype),
                             headers={"Content-Disposition": f'inline; filename="{rec["original_filename"]}"'})

async def _is_public_file(file_id: str) -> bool:
    if await db.members.find_one({"photo": file_id, "public_profile": True}, {"_id": 0}):
        return True
    if await db.announcements.find_one({"image_file_id": file_id, "public": True, "published": True}, {"_id": 0}):
        return True
    return False

@api_router.get("/public/files/{file_id}")
async def public_download_file(file_id: str):
    """Serves only images referenced by public member profiles or public announcements."""
    rec = await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not rec or not await _is_public_file(file_id):
        raise HTTPException(404, "File not found")
    data, ctype = await asyncio.to_thread(storage_mod.get_object, rec["storage_path"])
    return StreamingResponse(io.BytesIO(data), media_type=rec.get("content_type", ctype),
                             headers={"Content-Disposition": f'inline; filename="{rec["original_filename"]}"'})

@api_router.get("/files")
async def list_files(user=Depends(get_current_user)):
    if user["role"] in STAFF_ROLES:
        return await db.files.find({"is_deleted": False}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return await db.files.find({"is_deleted": False, "uploaded_by": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)

# ---------------- documents & signatures ----------------
class DocumentIn(BaseModel):
    title: str
    description: Optional[str] = ""
    category: str
    version: str = "1.0"
    required: bool = True
    file_id: Optional[str] = None
    assigned_to: List[str] = []  # member ids
    assigned_roles: List[str] = []
    due_date: Optional[str] = None
    requires_signature: bool = True

@api_router.post("/documents")
async def create_document(payload: DocumentIn, user=Depends(require_roles(*STAFF_ROLES))):
    doc = {"id": new_id("doc"), **payload.model_dump(), "created_by": user["name"], "created_at": now_iso()}
    await db.documents.insert_one(dict(doc))
    await log_audit(user, "document_created", "document", doc["id"], {"title": payload.title})
    # notify assigned members
    for mid in payload.assigned_to:
        m = await db.members.find_one({"id": mid}, {"_id": 0})
        if m and m.get("user_id"):
            await notify_user(m["user_id"], "New document assigned", f"{payload.title} requires your attention", "/portal/documents")
    return clean(doc)

@api_router.get("/documents")
async def list_documents(user=Depends(get_current_user)):
    if user["role"] in STAFF_ROLES:
        docs = await db.documents.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    else:
        m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
        mid = m["id"] if m else None
        docs = await db.documents.find({"$or": [{"assigned_to": mid}, {"assigned_roles": user["role"]}]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    # attach signature status for current user
    for d in docs:
        sig = await db.signatures.find_one({"document_id": d["id"], "user_id": user["user_id"]}, {"_id": 0})
        d["signed_by_me"] = bool(sig)
        d["signature_id"] = sig["id"] if sig else None
        d["signatures_count"] = await db.signatures.count_documents({"document_id": d["id"]})
    return docs

class SignIn(BaseModel):
    legal_name: str
    consent: bool

@api_router.post("/documents/{doc_id}/sign")
async def sign_document(doc_id: str, payload: SignIn, request: Request, user=Depends(get_current_user)):
    if not payload.consent:
        raise HTTPException(400, "Consent required")
    d = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Document not found")
    existing = await db.signatures.find_one({"document_id": doc_id, "user_id": user["user_id"]}, {"_id": 0})
    if existing:
        raise HTTPException(400, "Already signed. Signed documents cannot be overwritten.")
    sig = {"id": new_id("sig"), "document_id": doc_id, "document_title": d["title"], "document_version": d.get("version"),
           "user_id": user["user_id"], "legal_name": payload.legal_name, "signer_email": user["email"],
           "consent": True, "ip": request.client.host if request.client else None, "signed_at": now_iso()}
    await db.signatures.insert_one(dict(sig))
    await log_audit(user, "document_signed", "document", doc_id, {"version": d.get("version")})
    m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if m:
        await add_timeline("member", m["id"], f"Signed document: {d['title']}", user)
    return clean(sig)

@api_router.get("/documents/{doc_id}/signatures")
async def doc_signatures(doc_id: str, user=Depends(require_roles(*STAFF_ROLES))):
    return await db.signatures.find({"document_id": doc_id}, {"_id": 0}).to_list(1000)

# ---------------- messages ----------------
class MessageIn(BaseModel):
    subject: str
    body: str
    recipient_ids: List[str] = []  # user_ids
    target_role: Optional[str] = None
    target_state: Optional[str] = None
    file_ids: List[str] = []

@api_router.post("/messages")
async def send_message(payload: MessageIn, user=Depends(get_current_user)):
    recipients = set(payload.recipient_ids)
    if user["role"] in STAFF_ROLES and (payload.target_role or payload.target_state):
        q = {}
        if payload.target_role: q["role"] = payload.target_role
        if payload.target_state: q["state"] = payload.target_state
        async for m in db.members.find(q, {"_id": 0}):
            if m.get("user_id"):
                recipients.add(m["user_id"])
    if not recipients:
        raise HTTPException(400, "No recipients")
    thread_id = new_id("thread")
    msg = {"id": new_id("msg"), "thread_id": thread_id, "subject": payload.subject, "body": payload.body,
           "from_id": user["user_id"], "from_name": user["name"], "from_role": user["role"],
           "recipient_ids": list(recipients), "file_ids": payload.file_ids, "read_by": [], "created_at": now_iso()}
    await db.messages.insert_one(dict(msg))
    for rid in recipients:
        await notify_user(rid, f"New message: {payload.subject}", payload.body[:120], "/portal/messages")
    await log_audit(user, "message_sent", "message", msg["id"])
    return clean(msg)

@api_router.get("/messages")
async def list_messages(user=Depends(get_current_user)):
    msgs = await db.messages.find({"$or": [{"recipient_ids": user["user_id"]}, {"from_id": user["user_id"]}]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return msgs

@api_router.post("/messages/{msg_id}/read")
async def read_message(msg_id: str, user=Depends(get_current_user)):
    await db.messages.update_one({"id": msg_id}, {"$addToSet": {"read_by": user["user_id"]}})
    return {"ok": True}

# ---------------- announcements ----------------
class AnnouncementIn(BaseModel):
    title: str
    message: str
    image_file_id: Optional[str] = None
    target_roles: List[str] = []
    target_states: List[str] = []
    priority: str = "normal"
    public: bool = False
    email_notify: bool = False
    require_ack: bool = False
    expires_at: Optional[str] = None

@api_router.post("/announcements")
async def create_announcement(payload: AnnouncementIn, user=Depends(require_roles(*STAFF_ROLES))):
    ann = {"id": new_id("ann"), **payload.model_dump(), "published": True, "author": user["name"],
           "read_by": [], "acked_by": [], "created_at": now_iso()}
    await db.announcements.insert_one(dict(ann))
    await log_audit(user, "announcement_published", "announcement", ann["id"])
    q = {}
    if payload.target_roles: q["role"] = {"$in": payload.target_roles}
    if payload.target_states: q["state"] = {"$in": payload.target_states}
    async for m in db.members.find(q, {"_id": 0}):
        if m.get("user_id"):
            await notify_user(m["user_id"], f"Announcement: {payload.title}", payload.message[:120], "/portal/announcements")
    return clean(ann)

@api_router.get("/announcements")
async def list_announcements(user=Depends(get_current_user)):
    anns = await db.announcements.find({"published": True}, {"_id": 0}).sort("created_at", -1).to_list(500)
    if user["role"] in STAFF_ROLES:
        return anns
    m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
    state = m.get("state") if m else None
    out = []
    for a in anns:
        if (not a.get("target_roles") or user["role"] in a["target_roles"]) and (not a.get("target_states") or state in a["target_states"]):
            out.append(a)
    return out

@api_router.post("/announcements/{ann_id}/ack")
async def ack_announcement(ann_id: str, user=Depends(get_current_user)):
    await db.announcements.update_one({"id": ann_id}, {"$addToSet": {"read_by": user["user_id"], "acked_by": user["user_id"]}})
    return {"ok": True}

class AnnRequestIn(BaseModel):
    title: str
    message: str

@api_router.post("/announcement-requests")
async def create_ann_request(payload: AnnRequestIn, user=Depends(get_current_user)):
    req = {"id": new_id("annreq"), "title": payload.title, "message": payload.message, "status": "Submitted",
           "requested_by": user["name"], "requested_by_id": user["user_id"], "created_at": now_iso()}
    await db.announcement_requests.insert_one(dict(req))
    await log_audit(user, "announcement_request_submitted", "announcement_request", req["id"])
    return clean(req)

@api_router.get("/announcement-requests")
async def list_ann_requests(user=Depends(get_current_user)):
    if user["role"] in STAFF_ROLES:
        return await db.announcement_requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return await db.announcement_requests.find({"requested_by_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)

# ---------------- events ----------------
class EventIn(BaseModel):
    name: str
    event_type: Optional[str] = None
    date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    state: Optional[str] = None
    audience: Optional[str] = None
    description: Optional[str] = None
    requested_support: Optional[str] = None
    estimated_attendance: Optional[int] = None
    file_ids: List[str] = []
    public: bool = False

@api_router.post("/events")
async def create_event(payload: EventIn, user=Depends(get_current_user)):
    status = "Approved" if user["role"] in STAFF_ROLES else "Submitted"
    ev = {"id": new_id("evt"), **payload.model_dump(), "status": status, "submitted_by": user["name"],
          "submitted_by_id": user["user_id"], "created_at": now_iso()}
    await db.events.insert_one(dict(ev))
    await log_audit(user, "event_submitted", "event", ev["id"])
    if status == "Submitted":
        asyncio.create_task(notify_admins(f"New event request: {payload.name}", "Event Request",
                                          ep(f"{user['name']} submitted an event request: <strong>{payload.name}</strong>.")))
    return clean(ev)

@api_router.get("/events")
async def list_events(user=Depends(get_current_user)):
    return await db.events.find({}, {"_id": 0}).sort("date", 1).to_list(1000)

@api_router.put("/events/{event_id}/status")
async def update_event_status(event_id: str, payload: Dict[str, Any], user=Depends(require_roles(*STAFF_ROLES))):
    status = payload.get("status")
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev: raise HTTPException(404, "Not found")
    await db.events.update_one({"id": event_id}, {"$set": {"status": status}})
    await log_audit(user, "event_status_change", "event", event_id, {"status": status})
    if ev.get("submitted_by_id"):
        await notify_user(ev["submitted_by_id"], f"Event '{ev['name']}' {status}", "", "/portal/events")
    return {"ok": True}

# ---------------- goals ----------------
class GoalIn(BaseModel):
    title: str
    description: Optional[str] = ""
    category: str
    target: Optional[str] = None
    due_date: Optional[str] = None
    member_id: Optional[str] = None  # assigned to (staff sets), else self

@api_router.post("/goals")
async def create_goal(payload: GoalIn, user=Depends(get_current_user)):
    member_id = payload.member_id
    proposed = False
    if user["role"] in STAFF_ROLES and member_id:
        status = "Not Started"
    else:
        m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
        member_id = m["id"] if m else None
        status = "Not Started"
        proposed = True
    goal = {"id": new_id("goal"), "title": payload.title, "description": payload.description, "category": payload.category,
            "target": payload.target, "progress": 0, "due_date": payload.due_date, "member_id": member_id,
            "status": status, "proposed_by_member": proposed, "approved": user["role"] in STAFF_ROLES,
            "member_comments": [], "leadership_comments": [], "created_by": user["name"], "created_at": now_iso()}
    await db.goals.insert_one(dict(goal))
    await log_audit(user, "goal_created", "goal", goal["id"])
    if member_id:
        await add_timeline("member", member_id, f"Goal created: {payload.title}", user)
    return clean(goal)

@api_router.get("/goals")
async def list_goals(user=Depends(get_current_user), member_id: Optional[str] = None):
    if user["role"] in STAFF_ROLES:
        q = {"member_id": member_id} if member_id else {}
        return await db.goals.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return await db.goals.find({"member_id": m["id"] if m else "none"}, {"_id": 0}).sort("created_at", -1).to_list(1000)

@api_router.put("/goals/{goal_id}")
async def update_goal(goal_id: str, payload: Dict[str, Any], user=Depends(get_current_user)):
    g = await db.goals.find_one({"id": goal_id}, {"_id": 0})
    if not g: raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES:
        m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
        if not m or g.get("member_id") != m["id"]:
            raise HTTPException(403, "Forbidden")
        payload.pop("approved", None)  # members cannot self-approve goals
    allowed = {"progress", "status", "target", "description", "due_date", "approved", "evidence_file_id"}
    upd = {k: v for k, v in payload.items() if k in allowed}
    await db.goals.update_one({"id": goal_id}, {"$set": upd})
    await log_audit(user, "goal_updated", "goal", goal_id, upd)
    if upd.get("status") == "Achieved":
        await add_timeline("member", g["member_id"], f"Goal achieved: {g['title']}", user)
    return await db.goals.find_one({"id": goal_id}, {"_id": 0})

# ---------------- activity reports & volunteer hours ----------------
class ActivityReportIn(BaseModel):
    month: str
    summary: str
    hours: Optional[float] = None
    events_supported: Optional[int] = None
    file_ids: List[str] = []

@api_router.post("/activity-reports")
async def submit_report(payload: ActivityReportIn, user=Depends(get_current_user)):
    m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
    rep = {"id": new_id("rep"), **payload.model_dump(), "member_id": m["id"] if m else None,
           "member_name": user["name"], "created_at": now_iso()}
    await db.activity_reports.insert_one(dict(rep))
    await log_audit(user, "activity_report_submitted", "activity_report", rep["id"])
    return clean(rep)

@api_router.get("/activity-reports")
async def list_reports(user=Depends(get_current_user)):
    if user["role"] in STAFF_ROLES:
        return await db.activity_reports.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return await db.activity_reports.find({"member_id": m["id"] if m else "none"}, {"_id": 0}).sort("created_at", -1).to_list(1000)

# ---------------- resources ----------------
class ResourceIn(BaseModel):
    title: str
    description: Optional[str] = ""
    url: Optional[str] = None
    file_id: Optional[str] = None
    category: str = "General"
    icon: Optional[str] = "link"
    access_roles: List[str] = []  # empty = all

@api_router.post("/resources")
async def create_resource(payload: ResourceIn, user=Depends(require_roles(*STAFF_ROLES))):
    r = {"id": new_id("res"), **payload.model_dump(), "created_at": now_iso()}
    await db.resources.insert_one(dict(r))
    await log_audit(user, "resource_created", "resource", r["id"])
    return clean(r)

@api_router.get("/resources")
async def list_resources(user=Depends(get_current_user)):
    res = await db.resources.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    if user["role"] in STAFF_ROLES:
        return res
    return [r for r in res if not r.get("access_roles") or user["role"] in r["access_roles"]]

@api_router.delete("/resources/{res_id}")
async def delete_resource(res_id: str, user=Depends(require_roles(*STAFF_ROLES))):
    await db.resources.delete_one({"id": res_id})
    await log_audit(user, "resource_deleted", "resource", res_id)
    return {"ok": True}

@api_router.put("/resources/{res_id}")
async def update_resource(res_id: str, payload: Dict[str, Any], user=Depends(require_roles(*STAFF_ROLES))):
    payload.pop("id", None)
    await db.resources.update_one({"id": res_id}, {"$set": payload})
    return await db.resources.find_one({"id": res_id}, {"_id": 0})

# ---------------- notifications ----------------
@api_router.get("/notifications")
async def list_notifications(user=Depends(get_current_user)):
    return await db.notifications.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)

@api_router.post("/notifications/{nid}/read")
async def read_notification(nid: str, user=Depends(get_current_user)):
    await db.notifications.update_one({"id": nid, "user_id": user["user_id"]}, {"$set": {"read": True}})
    return {"ok": True}

@api_router.post("/notifications/read-all")
async def read_all_notifications(user=Depends(get_current_user)):
    await db.notifications.update_many({"user_id": user["user_id"]}, {"$set": {"read": True}})
    return {"ok": True}

# ---------------- users / authorized emails ----------------
class AuthorizeIn(BaseModel):
    email: EmailStr
    role: str
    notify_directors: bool = False

@api_router.get("/users")
async def list_users(user=Depends(require_roles("super_admin", "director"))):
    users = await db.users.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    authed = await db.authorized_emails.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return {"users": users, "authorized": authed}

@api_router.post("/authorized-emails")
async def authorize_email(payload: AuthorizeIn, user=Depends(require_roles("super_admin", "director"))):
    if payload.role not in ROLES:
        raise HTTPException(400, "Invalid role")
    await db.authorized_emails.update_one(
        {"email": payload.email.lower()},
        {"$set": {"role": payload.role, "status": "active", "notify_directors": payload.notify_directors},
         "$setOnInsert": {"email": payload.email.lower(), "created_at": now_iso()}},
        upsert=True,
    )
    await log_audit(user, "email_authorized", "authorized_email", payload.email.lower(), {"role": payload.role})
    return {"ok": True}

@api_router.put("/authorized-emails/{email}/status")
async def set_email_status(email: str, payload: Dict[str, Any], user=Depends(require_roles("super_admin", "director"))):
    status = payload.get("status")
    await db.authorized_emails.update_one({"email": email.lower()}, {"$set": {"status": status}})
    u = await db.users.find_one({"email": email.lower()}, {"_id": 0})
    if u:
        await db.users.update_one({"email": email.lower()}, {"$set": {"account_status": status}})
    await log_audit(user, "account_status_change", "authorized_email", email.lower(), {"status": status})
    return {"ok": True}

@api_router.put("/users/{user_id}/role")
async def set_user_role(user_id: str, payload: Dict[str, Any], user=Depends(require_roles("super_admin"))):
    role = payload.get("role")
    if role not in ROLES: raise HTTPException(400, "Invalid role")
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not u: raise HTTPException(404, "Not found")
    await db.users.update_one({"user_id": user_id}, {"$set": {"role": role}})
    await db.authorized_emails.update_one({"email": u["email"]}, {"$set": {"role": role}})
    await log_audit(user, "role_changed", "user", user_id, {"role": role})
    return {"ok": True}

# ---------------- dashboard ----------------
@api_router.get("/dashboard/stats")
async def dashboard_stats(user=Depends(require_roles(*STAFF_ROLES))):
    async def c(coll, q): return await coll.count_documents(q)
    now = datetime.now(timezone.utc).isoformat()
    stats = {
        "new_applications": await c(db.applications, {"status": {"$in": ["New", "Submitted"]}, "type": {"$ne": "inquiry"}}),
        "new_inquiries": await c(db.applications, {"status": {"$in": ["New", "Submitted"]}, "type": "inquiry"}),
        "under_review": await c(db.applications, {"status": "Under Review"}),
        "approved": await c(db.applications, {"status": "Approved"}),
        "waitlisted": await c(db.applications, {"status": "Waitlisted"}),
        "declined": await c(db.applications, {"status": "Declined"}),
        "active_ambassadors": await c(db.members, {"role": "ambassador", "account_status": "active"}),
        "active_volunteers": await c(db.members, {"role": "volunteer", "account_status": "active"}),
        "pending_events": await c(db.events, {"status": {"$in": ["Submitted", "Under Review"]}}),
        "overdue_goals": await c(db.goals, {"due_date": {"$lt": now, "$ne": None}, "status": {"$nin": ["Achieved", "Deferred"]}}),
        "announcement_requests": await c(db.announcement_requests, {"status": "Submitted"}),
        "total_members": await c(db.members, {}),
    }
    # onboarding incomplete
    incomplete = 0
    async for m in db.members.find({}, {"_id": 0, "onboarding": 1}):
        if any(not o.get("done") for o in m.get("onboarding", [])):
            incomplete += 1
    stats["incomplete_onboarding"] = incomplete
    # applications by type for chart
    stats["by_type"] = {t: await c(db.applications, {"type": t}) for t in ["ambassador", "volunteer", "inquiry"]}
    stats["by_status"] = {s: await c(db.applications, {"status": s}) for s in APP_STATUSES}
    stats["recent_applications"] = await db.applications.find({}, {"_id": 0}).sort("created_at", -1).limit(6).to_list(6)
    stats["upcoming_events"] = await db.events.find({"status": {"$in": ["Approved", "Scheduled"]}}, {"_id": 0}).sort("date", 1).limit(5).to_list(5)
    return stats

# ---------------- reports & audit ----------------
@api_router.get("/reports/{report_type}")
async def get_report(report_type: str, format: str = "json", user=Depends(require_roles(*STAFF_ROLES))):
    rows = []
    if report_type == "applications":
        for a in await db.applications.find({}, {"_id": 0}).to_list(5000):
            rows.append({"ref": a["ref"], "type": a["type"], "name": a["name"], "email": a["email"], "state": a.get("state"), "status": a["status"], "submitted": a["created_at"]})
    elif report_type == "ambassadors":
        for m in await db.members.find({"role": "ambassador"}, {"_id": 0}).to_list(5000):
            rows.append({"name": m["name"], "email": m["email"], "state": m.get("state"), "status": m["account_status"], "start_date": m.get("start_date")})
    elif report_type == "volunteers":
        for m in await db.members.find({"role": "volunteer"}, {"_id": 0}).to_list(5000):
            rows.append({"name": m["name"], "email": m["email"], "state": m.get("state"), "status": m["account_status"]})
    elif report_type == "goals":
        for g in await db.goals.find({}, {"_id": 0}).to_list(5000):
            rows.append({"title": g["title"], "category": g["category"], "status": g["status"], "progress": g["progress"], "due": g.get("due_date")})
    elif report_type == "volunteer_hours":
        for r in await db.activity_reports.find({}, {"_id": 0}).to_list(5000):
            rows.append({"member": r["member_name"], "month": r["month"], "hours": r.get("hours"), "events": r.get("events_supported")})
    elif report_type == "events":
        for e in await db.events.find({}, {"_id": 0}).to_list(5000):
            rows.append({"name": e["name"], "type": e.get("event_type"), "date": e.get("date"), "state": e.get("state"), "status": e["status"]})
    else:
        raise HTTPException(400, "Unknown report")
    if format == "csv":
        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        await log_audit(user, "report_exported", "report", report_type, {"format": "csv"})
        return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="{report_type}.csv"'})
    return {"rows": rows, "count": len(rows)}

@api_router.get("/audit-logs")
async def get_audit_logs(user=Depends(require_roles("super_admin", "director")), q: Optional[str] = None):
    query = {}
    if q:
        query["$or"] = [{"action": {"$regex": q, "$options": "i"}}, {"user_email": {"$regex": q, "$options": "i"}}]
    return await db.audit_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)

@api_router.get("/")
async def root():
    return {"message": "CEC Connect API"}

# ---------------- signature PDF ----------------
def _build_signature_pdf(sig: dict, doc: dict) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas as pdfcanvas
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=letter)
    w, h = letter
    # watermark
    c.saveState()
    c.setFont("Helvetica-Bold", 60)
    c.setFillColorRGB(0.84, 0.09, 0.61, 0.08)
    c.translate(w / 2, h / 2); c.rotate(35)
    c.drawCentredString(0, 0, "AAWTA CEC CONNECT")
    c.restoreState()
    # header bar
    c.setFillColorRGB(0.18, 0.19, 0.57); c.rect(0, h - 90, w, 90, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1); c.setFont("Helvetica-Bold", 22)
    c.drawString(inch, h - 55, "AAWTA CEC Connect")
    c.setFont("Helvetica", 12); c.drawString(inch, h - 75, "Certificate of Electronic Signature")
    # body
    y = h - 140
    c.setFillColorRGB(0.1, 0.1, 0.1)
    def line(label, val, gap=26):
        nonlocal y
        c.setFont("Helvetica-Bold", 11); c.drawString(inch, y, label)
        c.setFont("Helvetica", 11); c.drawString(inch + 170, y, str(val or "—"))
        y -= gap
    c.setFont("Helvetica-Bold", 15); c.setFillColorRGB(0.18, 0.19, 0.57)
    c.drawString(inch, y, doc.get("title", "Document")); y -= 34
    c.setFillColorRGB(0.1, 0.1, 0.1)
    line("Document Category", doc.get("category"))
    line("Document Version", sig.get("document_version") or doc.get("version"))
    line("Description", (doc.get("description") or "")[:70])
    y -= 6
    c.setStrokeColorRGB(0.85, 0.85, 0.9); c.line(inch, y, w - inch, y); y -= 26
    line("Signed by (legal name)", sig.get("legal_name"))
    line("Signer email", sig.get("signer_email"))
    line("Consent given", "Yes" if sig.get("consent") else "No")
    line("Date & time (UTC)", sig.get("signed_at"))
    line("IP address", sig.get("ip"))
    line("Signature ID", sig.get("id"))
    y -= 20
    c.setFont("Helvetica-Oblique", 9); c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(inch, y, "This certificate records an electronic signature captured by AAWTA CEC Connect and is tamper-evident.")
    c.drawString(inch, y - 14, "The original signed record is preserved and cannot be overwritten.")
    # signature block
    c.setStrokeColorRGB(0.84, 0.09, 0.61); c.setLineWidth(1.4)
    c.line(inch, y - 70, inch + 260, y - 70)
    c.setFont("Helvetica-BoldOblique", 18); c.setFillColorRGB(0.18, 0.19, 0.57)
    c.drawString(inch, y - 62, sig.get("legal_name") or "")
    c.setFont("Helvetica", 9); c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(inch, y - 84, "Authorized electronic signature")
    c.showPage(); c.save()
    return buf.getvalue()

@api_router.get("/signatures/{sig_id}/pdf")
async def signature_pdf(sig_id: str, user=Depends(get_current_user)):
    sig = await db.signatures.find_one({"id": sig_id}, {"_id": 0})
    if not sig:
        raise HTTPException(404, "Signature not found")
    if user["role"] not in STAFF_ROLES and sig["user_id"] != user["user_id"]:
        raise HTTPException(403, "Forbidden")
    doc = await db.documents.find_one({"id": sig["document_id"]}, {"_id": 0}) or {}
    pdf = await asyncio.to_thread(_build_signature_pdf, sig, doc)
    fname = f"signed-{(doc.get('title') or 'document').replace(' ', '_')}.pdf"
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})

# ---------------- event calendar (ICS) ----------------
def _fmt_ics_date(d):
    try:
        dt = datetime.fromisoformat(str(d).replace("Z", "+00:00"))
        return dt.strftime("%Y%m%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y%m%d")

@api_router.get("/events/{event_id}/ics")
async def event_ics(event_id: str):
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev:
        raise HTTPException(404, "Event not found")
    start = _fmt_ics_date(ev.get("date"))
    end_dt = datetime.strptime(start, "%Y%m%d") + timedelta(days=1)
    end = end_dt.strftime("%Y%m%d")
    def esc(s): return str(s or "").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
    ics = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//AAWTA//CEC Connect//EN", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT", f"UID:{ev['id']}@cec-connect",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;VALUE=DATE:{start}", f"DTEND;VALUE=DATE:{end}",
        f"SUMMARY:{esc(ev.get('name'))}",
        f"DESCRIPTION:{esc(ev.get('description'))}",
        f"LOCATION:{esc(ev.get('location'))}",
        "END:VEVENT", "END:VCALENDAR",
    ])
    return StreamingResponse(io.BytesIO(ics.encode()), media_type="text/calendar",
                             headers={"Content-Disposition": f'attachment; filename="event.ics"'})

# ---------------- automated reminders (cron-driven) ----------------
def _days_since(iso_str):
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None

def _days_until(iso_str):
    d = _days_since(iso_str)
    return None if d is None else -d

async def _remind_once(key: str, user_id, title, body, link, email_to=None):
    """Send a portal notification + optional email at most once per key."""
    if await db.reminder_sent.find_one({"key": key}):
        return
    await db.reminder_sent.insert_one({"key": key, "created_at": now_iso()})
    if user_id:
        await notify_user(user_id, title, body, link, "reminder")
    if email_to:
        await send_safe(to=email_to, subject=title, title=title, body_html=ep(body))

async def run_reminders():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # 1. Onboarding incomplete (weekly bucket)
    week = datetime.now(timezone.utc).strftime("%Y-W%U")
    async for m in db.members.find({"account_status": "active", "user_id": {"$ne": None}}, {"_id": 0}):
        remaining = [o for o in m.get("onboarding", []) if not o.get("done")]
        if remaining and m.get("user_id"):
            await _remind_once(f"onboard:{m['id']}:{week}", m["user_id"],
                               "Onboarding reminder",
                               f"You still have {len(remaining)} onboarding step(s) to complete. Finish onboarding to get fully activated.",
                               "/portal/onboarding", m.get("email"))
    # 2. Document signatures due/overdue
    async for d in db.documents.find({"requires_signature": True}, {"_id": 0}):
        du = _days_until(d.get("due_date")) if d.get("due_date") else None
        if du is None or du > 3:
            continue
        assignee_ids = list(d.get("assigned_to", []))
        role_targets = d.get("assigned_roles", [])
        members = []
        if assignee_ids:
            members += await db.members.find({"id": {"$in": assignee_ids}}, {"_id": 0}).to_list(500)
        if role_targets:
            members += await db.members.find({"role": {"$in": role_targets}}, {"_id": 0}).to_list(500)
        for m in members:
            if not m.get("user_id"):
                continue
            if await db.signatures.find_one({"document_id": d["id"], "user_id": m["user_id"]}, {"_id": 0}):
                continue
            state = "overdue" if du < 0 else f"due in {du} day(s)"
            await _remind_once(f"sign:{d['id']}:{m['id']}:{today}", m["user_id"],
                               "Signature reminder",
                               f"Document '{d['title']}' is {state}. Please review and sign it.",
                               "/portal/documents", m.get("email"))
    # 3. Goal due dates
    async for g in db.goals.find({"status": {"$nin": ["Achieved", "Deferred"]}, "due_date": {"$ne": None}}, {"_id": 0}):
        du = _days_until(g.get("due_date"))
        if du is None or du > 3:
            continue
        m = await db.members.find_one({"id": g.get("member_id")}, {"_id": 0})
        if not m:
            continue
        state = "overdue" if du < 0 else f"due in {du} day(s)"
        if m.get("user_id"):
            await _remind_once(f"goal:{g['id']}:{m['id']}:{today}", m["user_id"],
                               "Goal reminder", f"Your goal '{g['title']}' is {state}.",
                               "/portal/goals", m.get("email"))
        # notify assigned director when overdue
        if du < 0 and g.get("assigned_director"):
            await _remind_once(f"goaldir:{g['id']}:{today}", None,
                               "Member goal overdue",
                               f"Goal '{g['title']}' for {m['name']} is overdue and may need follow-up.",
                               None, ADMIN_EMAIL)
    # 4. Inactivity nudges (14 / 30 / 45 / 60 days) — never auto-deactivate
    async for u in db.users.find({"account_status": "active", "role": {"$in": ["ambassador", "volunteer"]}}, {"_id": 0}):
        d = _days_since(u.get("last_login"))
        if d is None:
            continue
        if d >= 60:
            await _remind_once(f"inact60:{u['user_id']}:{today}", None,
                               "Member inactive 60+ days — review",
                               f"{u['name']} ({u['email']}) has not logged in for {d} days. Administrative review recommended (no automatic deactivation).",
                               None, ADMIN_EMAIL)
        elif d >= 45:
            await _remind_once(f"inact45:{u['user_id']}:{today}", None,
                               "Member inactive 45+ days",
                               f"{u['name']} ({u['email']}) has not logged in for {d} days. Director follow-up suggested.",
                               None, ADMIN_EMAIL)
        elif d >= 30:
            await _remind_once(f"inact30:{u['user_id']}:{today}", u["user_id"],
                               "We miss you at CEC Connect",
                               "It's been over 30 days since your last visit. Log in to check your goals, documents, and announcements.",
                               "/portal", u.get("email"))
        elif d >= 14:
            await _remind_once(f"inact14:{u['user_id']}:{today}", u["user_id"],
                               "Friendly reminder from CEC Connect",
                               "It's been a couple of weeks — log in to stay on top of your onboarding and activity.",
                               "/portal", u.get("email"))

@api_router.post("/cron/reminders")
async def cron_reminders(request: Request, authorization: Optional[str] = Header(None), x_webhook_id: Optional[str] = Header(None)):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    token = authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else ""
    if not secret or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        body = await request.json()
    except Exception:
        body = {}
    run_id = x_webhook_id or body.get("run_id") or new_id("run")
    if await db.reminder_runs.find_one({"run_id": run_id}):
        return {"ok": True, "duplicate": True}
    await db.reminder_runs.insert_one({"run_id": run_id, "created_at": now_iso()})
    asyncio.create_task(run_reminders())
    return {"ok": True, "run_id": run_id}

# ---------------- startup ----------------
@app.on_event("startup")
async def startup():
    await db.authorized_emails.update_one(
        {"email": SUPER_ADMIN_EMAIL.lower()},
        {"$set": {"role": "super_admin", "status": "active", "notify_directors": True},
         "$setOnInsert": {"email": SUPER_ADMIN_EMAIL.lower(), "created_at": now_iso()}},
        upsert=True,
    )
    await get_settings_doc()
    try:
        await asyncio.to_thread(storage_mod.init_storage)
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    logger.info("CEC Connect startup complete")

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
