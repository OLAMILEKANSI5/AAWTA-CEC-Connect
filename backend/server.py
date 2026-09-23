from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Form, Header, Query, Body
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, io, csv, json, asyncio, hmac, re, secrets
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta

import httpx
import storage as storage_mod
from emailer import send_safe, send_email, _wrap, p as ep
from urllib.parse import urlencode
from html import escape as hesc

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'aawtassn@gmail.com')
SUPER_ADMIN_EMAIL = os.environ.get('SUPER_ADMIN_EMAIL', 'aawtassn@gmail.com')
PUBLIC_BASE_URL = (os.environ.get('PUBLIC_BASE_URL') or '').rstrip('/')
EMERGENT_AUTH_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ROLES = ["super_admin", "director", "administrator", "ambassador", "volunteer"]
STAFF_ROLES = ["super_admin", "director", "administrator"]


def _can_checkin(ev, user):
    if not ev:
        return False
    if user["role"] in STAFF_ROLES or ev.get("submitted_by_id") == user["user_id"]:
        return True
    if user["user_id"] in (ev.get("checkin_assignees") or []) and ev.get("status") not in ("Completed", "Archived") and not ev.get("archived"):
        return True
    return False
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

async def notify_user(user_id, title, body, link=None, ntype="info", category=None):
    await db.notifications.insert_one({
        "id": new_id("ntf"),
        "user_id": user_id,
        "title": title,
        "body": body,
        "link": link,
        "type": ntype,
        "category": category,
        "read": False,
        "created_at": now_iso(),
    })

async def _leadership_user_ids():
    ids = []
    async for u in db.users.find({"role": {"$in": STAFF_ROLES}, "account_status": {"$nin": ["suspended", "deactivated"]}}, {"_id": 0, "user_id": 1}):
        if u.get("user_id"):
            ids.append(u["user_id"])
    return ids

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
    "slack_link": "https://aawtaworkspace.slack.com/archives/C0ALPLXG5T5",
    "membership_link": "https://www.zeffy.com/ticketing/aawta-memberships--2025-2",
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
    asyncio.create_task(send_template_email("application_received", "application", app_doc["id"], actor=None))
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
    subj_map = {"Waitlisted": "waitlisted", "Declined": "declined", "More Information Requested": "needs more information"}
    if payload.status == "Approved" and a.get("type") in ("ambassador", "volunteer"):
        asyncio.create_task(send_template_email("application_approved", "application", app_id, actor=user))
    elif payload.status in subj_map:
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

async def _assign_onboarding_docs(member, role, user):
    docs = await db.documents.find({"auto_onboarding": True, "status": {"$ne": "archived"}, "onboarding_profiles": role}, {"_id": 0}).to_list(500)
    for d in docs:
        if member["id"] in (d.get("assigned_to") or []):
            continue
        await db.documents.update_one({"id": d["id"]}, {"$addToSet": {"assigned_to": member["id"]}, "$set": {"updated_at": now_iso()}})
        if member.get("user_id"):
            await notify_user(member["user_id"], "Onboarding document assigned", f"Please review and sign: {d['title']}", "/portal/documents")
        await log_audit(user, "onboarding_doc_assigned", "document", d["id"], {"member_id": member["id"], "role": role})


async def _send_welcome(member, role):
    # Sends the onboarding invitation using the Group 1 template system + records a communication.
    log = await send_template_email("onboarding_profile", "member", member["id"], actor=None, force=True)
    if member.get("user_id"):
        await notify_user(member["user_id"], "Welcome to CEC Connect!", f"You're approved as a {role}. Complete your onboarding to get started.", "/portal", "success")
    return log


APP_APPROVED_STATUSES = ("Approved", "Recommended", "Recommended for Approval")


async def _do_convert(a, user, approved_at=None):
    role = "ambassador" if a["type"] == "ambassador" else "volunteer"
    member = await create_member_record(
        name=a["name"], email=a["email"], role=role, state=a.get("state"),
        data=a.get("data", {}), created_by=user, source_application=a["id"],
    )
    await db.members.update_one({"id": member["id"]}, {"$set": {
        "approved_at": approved_at or now_iso(), "onboarding_stage": "profile_incomplete",
        "onboarding_stage_since": now_iso(), "fully_onboarded_notified": False}})
    await _assign_onboarding_docs(member, role, user)
    await _send_welcome(member, role)  # fires the onboarding_profile template + records communication
    await db.applications.update_one({"id": a["id"]}, {"$set": {"status": "Converted to Member", "member_id": member["id"], "updated_at": now_iso()}})
    await add_timeline("application", a["id"], "Converted to member", user)
    await log_audit(user, "application_converted", "application", a["id"], {"member_id": member["id"]})
    return await db.members.find_one({"id": member["id"]}, {"_id": 0})


@api_router.post("/applications/{app_id}/convert")
async def convert_to_member(app_id: str, user=Depends(require_roles(*LEADERSHIP_ROLES))):
    a = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Not found")
    if a.get("status") not in APP_APPROVED_STATUSES:
        raise HTTPException(400, "Only an approved application can be converted to a member")
    if a.get("member_id"):
        raise HTTPException(400, "This application has already been converted")
    return await _do_convert(a, user)


@api_router.post("/applications/{app_id}/approve-onboard")
async def approve_and_onboard(app_id: str, user=Depends(require_roles(*LEADERSHIP_ROLES))):
    a = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Not found")
    if a.get("type") not in ("ambassador", "volunteer"):
        raise HTTPException(400, "Only ambassador and volunteer applications can be onboarded")
    if a.get("member_id") or a.get("status") == "Converted to Member":
        raise HTTPException(400, "This applicant has already been onboarded")
    approved_at = now_iso()
    if a.get("status") not in APP_APPROVED_STATUSES:
        entry = {"status": "Approved", "note": "Approved via Approve & Onboard", "by": user["name"], "at": approved_at}
        await db.applications.update_one({"id": app_id}, {"$set": {"status": "Approved", "updated_at": approved_at}, "$push": {"decision_history": entry}})
        await add_timeline("application", app_id, "Status changed to Approved", user)
        await log_audit(user, "application_status_change", "application", app_id, entry)
        a["status"] = "Approved"
    # approval notification (Group 1 template) — recorded on the applicant's communication history
    await send_template_email("application_approved", "application", app_id, actor=user, force=True)
    member = await _do_convert(a, user, approved_at=approved_at)
    await log_audit(user, "approve_and_onboard", "application", app_id, {"member_id": member["id"]})
    return {"member": member, "member_id": member["id"]}


# ---------------- onboarding pipeline ----------------
STAGE_ORDER = ["applied", "under_review", "approved", "profile_incomplete", "docs_needed", "thirty_day", "fully_onboarded"]
STAGE_LABELS = {"applied": "Applied", "under_review": "Under Review", "approved": "Approved",
                "profile_incomplete": "Profile Incomplete", "docs_needed": "Documents/Signatures Needed",
                "thirty_day": "30-Day Onboarding", "fully_onboarded": "Fully Onboarded"}
STALL_DAYS = {"applied": 7, "under_review": 10, "approved": 5, "profile_incomplete": 7, "docs_needed": 7, "thirty_day": 30, "fully_onboarded": None}
APP_APPLIED = {"New", "Submitted"}
APP_REVIEW = {"Under Review", "More Information Requested", "Interview Requested", "Interview Scheduled"}
PROFILE_STEPS = ["Complete profile", "Upload headshot"]


def _stage_days(iso_str, now):
    if not iso_str:
        return 0
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (now - dt).days)
    except Exception:
        return 0


async def _member_onboarding_state(m):
    onboarding = m.get("onboarding") or []
    total = len(onboarding) or 1
    done = sum(1 for o in onboarding if o.get("done"))
    profile_done = all(any(o.get("step") == ps and o.get("done") for o in onboarding) for ps in PROFILE_STEPS)
    role = m.get("role")
    uid = m.get("user_id")
    docs = await db.documents.find({"status": {"$ne": "archived"},
                                    "$or": [{"assigned_to": m["id"]}, {"auto_onboarding": True, "onboarding_profiles": role}]}, {"_id": 0}).to_list(500)
    unsigned = []
    for d in docs:
        signed = bool(await db.signatures.find_one({"document_id": d["id"], "user_id": uid})) if uid else False
        if not signed:
            unsigned.append(d.get("title") or "Untitled document")
    all_done = done >= total
    if all_done:
        stage = "fully_onboarded"
    elif not profile_done:
        stage = "profile_incomplete"
    elif unsigned:
        stage = "docs_needed"
    else:
        stage = "thirty_day"
    outstanding = []
    if not profile_done:
        outstanding.append("Complete profile & upload photo")
    outstanding += [f"Sign: {t}" for t in unsigned]
    if stage == "thirty_day":
        outstanding += [o["step"] for o in onboarding if not o.get("done") and o.get("step") not in PROFILE_STEPS]
    return stage, outstanding, round(done / total * 100), all_done


def _pipeline_entry(kind, id_, name, role, stage, outstanding, approved_at, since, pct, now, email):
    days = _stage_days(since, now)
    stall = STALL_DAYS.get(stage)
    return {"kind": kind, "id": id_, "name": name, "role": role, "stage": stage, "stage_label": STAGE_LABELS[stage],
            "outstanding": outstanding, "approved_at": approved_at, "days_in_stage": days, "progress_pct": pct,
            "stalled": bool(stall and days >= stall),
            "link": f"/portal/members/{id_}" if kind == "member" else f"/portal/applications/{id_}", "email": email}


@api_router.get("/onboarding/pipeline")
async def onboarding_pipeline(user=Depends(require_roles(*STAFF_ROLES)), role: Optional[str] = None, stage: Optional[str] = None):
    now = datetime.now(timezone.utc)
    entries = []
    aq = {"type": {"$in": [role] if role else ["ambassador", "volunteer"]},
          "status": {"$nin": ["Converted to Member", "Declined", "Withdrawn", "Archived"]}}
    async for a in db.applications.find(aq, {"_id": 0}):
        st = a.get("status")
        if st in APP_APPLIED:
            s = "applied"
        elif st in APP_REVIEW:
            s = "under_review"
        elif st in APP_APPROVED_STATUSES:
            s = "approved"
        else:
            continue
        since = a.get("updated_at") or a.get("created_at")
        entries.append(_pipeline_entry("application", a["id"], a.get("name"), a.get("type"), s,
                                        [f"Awaiting {STAGE_LABELS[s].lower()}"], None, since, None, now, a.get("email")))
    mq = {"account_status": {"$ne": "deactivated"}, "role": {"$in": [role] if role else ["ambassador", "volunteer"]}}
    async for m in db.members.find(mq, {"_id": 0}):
        s, outstanding, pct, all_done = await _member_onboarding_state(m)
        if m.get("onboarding_stage") != s or not m.get("onboarding_stage_since"):
            await db.members.update_one({"id": m["id"]}, {"$set": {"onboarding_stage": s, "onboarding_stage_since": now_iso()}})
            m["onboarding_stage_since"] = now_iso()
        since = m.get("onboarding_stage_since") or m.get("approved_at") or m.get("start_date") or m.get("created_at")
        entries.append(_pipeline_entry("member", m["id"], m.get("name"), m.get("role"), s, outstanding,
                                       m.get("approved_at") or m.get("start_date"), since, pct, now, m.get("email")))
    counts = {s: 0 for s in STAGE_ORDER}
    for e in entries:
        counts[e["stage"]] += 1
    if stage:
        entries = [e for e in entries if e["stage"] == stage]
    entries.sort(key=lambda e: (STAGE_ORDER.index(e["stage"]), -e["days_in_stage"]))
    return {"entries": entries, "counts": counts, "stage_order": STAGE_ORDER, "stage_labels": STAGE_LABELS}

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
    # fully-onboarded trigger (only once, and only when every required step is complete)
    if onboarding and all(o.get("done") for o in onboarding):
        swapped = await db.members.find_one_and_update(
            {"id": member_id, "fully_onboarded_notified": {"$ne": True}},
            {"$set": {"fully_onboarded_notified": True, "onboarding_stage": "fully_onboarded", "onboarding_stage_since": now_iso()}})
        if swapped:
            asyncio.create_task(send_template_email("fully_onboarded_welcome", "member", member_id, actor=None))
            await add_timeline("member", member_id, "Fully onboarded", user)
            await log_audit(user, "member_fully_onboarded", "member", member_id)
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
    events = await db.events.find(_public_evq({"date": {"$gte": datetime.now(timezone.utc).strftime("%Y-%m-%d")}}), {"_id": 0}).sort("date", 1).limit(6).to_list(6)
    stats = {
        "ambassadors": await db.members.count_documents({"role": "ambassador"}),
        "volunteers": await db.members.count_documents({"role": "volunteer"}),
        "states": len(await db.members.distinct("state", {"role": "ambassador"})),
        "events": await db.events.count_documents({"status": {"$in": ["Approved", "Scheduled", "Completed"]}}),
    }
    return {"settings": settings, "spotlights": [{"id": m["id"], "name": m["name"], "state": m.get("state"), "photo": m.get("photo"), "focus_areas": m.get("focus_areas", []), "bio": m.get("bio")} for m in spotlights], "announcements": ann, "events": events, "stats": stats}

async def _add_gallery_photos(ev, report, submitter_role, submitter_name, submitter_id, default_status=None):
    """Create gallery_photos records for a post-event report's photos (idempotent per file+event)."""
    caps = report.get("photo_captions") or {}
    status = default_status or ("approved" if submitter_role in STAFF_ROLES else "pending")
    for pid in report.get("photo_file_ids", []):
        if await db.gallery_photos.find_one({"file_id": pid, "event_id": ev["id"]}, {"_id": 0}):
            continue
        doc = {"id": new_id("gph"), "file_id": pid, "event_id": ev["id"], "event_name": ev.get("name"),
               "report_id": report.get("id"), "caption": caps.get(pid), "state": ev.get("state"),
               "date": ev.get("date"), "location": ev.get("location"), "highlights": report.get("highlights"),
               "status": status, "submitted_by": submitter_name, "submitted_by_id": submitter_id,
               "reviewed_by": submitter_name if status == "approved" else None,
               "reviewed_at": now_iso() if status == "approved" else None, "created_at": now_iso()}
        await db.gallery_photos.insert_one(dict(doc))


async def _backfill_gallery():
    async for ev in db.events.find({"reports": {"$exists": True, "$ne": []}}, {"_id": 0}):
        for r in ev.get("reports", []):
            await _add_gallery_photos(ev, r, None, r.get("submitted_by"), r.get("submitted_by_id"),
                                      default_status="approved" if ev.get("public") else "pending")


@api_router.get("/public/gallery")
async def public_gallery():
    """Approved post-event photos — the public Community Impact gallery."""
    items = await db.gallery_photos.find({"status": "approved"}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [{"photo_id": g["file_id"], "event_id": g.get("event_id"), "event_name": g.get("event_name"),
             "state": g.get("state"), "date": g.get("date"), "location": g.get("location"),
             "highlights": g.get("highlights"), "caption": g.get("caption")} for g in items]


@api_router.get("/gallery/photos")
async def list_gallery_photos(status: Optional[str] = None, event_id: Optional[str] = None, user=Depends(require_roles(*STAFF_ROLES))):
    q = {}
    if status:
        q["status"] = status
    if event_id:
        q["event_id"] = event_id
    photos = await db.gallery_photos.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    counts = {s: await db.gallery_photos.count_documents({"status": s}) for s in ("pending", "approved", "rejected")}
    return {"photos": photos, "counts": counts}


class GalleryStatusIn(BaseModel):
    status: str


@api_router.put("/gallery/photos/{photo_id}/status")
async def set_gallery_photo_status(photo_id: str, payload: GalleryStatusIn, user=Depends(require_roles(*STAFF_ROLES))):
    if payload.status not in ("pending", "approved", "rejected"):
        raise HTTPException(400, "Invalid status")
    g = await db.gallery_photos.find_one({"id": photo_id}, {"_id": 0})
    if not g:
        raise HTTPException(404, "Photo not found")
    await db.gallery_photos.update_one({"id": photo_id}, {"$set": {"status": payload.status, "reviewed_by": user["name"], "reviewed_at": now_iso()}})
    await log_audit(user, f"gallery_photo_{payload.status}", "gallery_photo", photo_id, {"event_id": g.get("event_id")})
    return {"ok": True, "status": payload.status}

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
    if await db.events.find_one({"image_file_id": file_id, "archived": {"$ne": True}, "$or": [{"published": True}, {"public": True}]}, {"_id": 0}):
        return True
    if await db.gallery_photos.find_one({"file_id": file_id, "status": "approved"}, {"_id": 0}):
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
DOC_AUDIENCES = ["private_draft", "ambassadors_only", "volunteers_only", "interns_only", "ambassadors_volunteers", "specific_members", "all_active", "admins_only"]


class DocumentIn(BaseModel):
    title: str
    description: Optional[str] = ""
    category: str
    version: str = "1.0"
    required: bool = True
    file_id: Optional[str] = None
    assigned_to: List[str] = []
    assigned_roles: List[str] = []
    audience: str = "private_draft"
    status: str = "active"
    display_order: int = 0
    auto_onboarding: bool = False
    onboarding_profiles: List[str] = []
    due_date: Optional[str] = None
    requires_signature: bool = True


def _doc_visible_to(d, user, mid):
    if d.get("status") == "archived":
        return False
    aud = d.get("audience", "private_draft")
    role = user["role"]
    if mid and mid in (d.get("assigned_to") or []):
        return True
    if role in (d.get("assigned_roles") or []):
        return True
    if aud in ("private_draft", "admins_only", "specific_members"):
        return False
    if aud == "all_active":
        return True
    if aud == "ambassadors_only":
        return role == "ambassador"
    if aud == "volunteers_only":
        return role == "volunteer"
    if aud == "interns_only":
        return role == "intern"
    if aud == "ambassadors_volunteers":
        return role in ("ambassador", "volunteer")
    return False


@api_router.post("/documents")
async def create_document(payload: DocumentIn, user=Depends(require_roles(*STAFF_ROLES))):
    if payload.audience not in DOC_AUDIENCES:
        raise HTTPException(400, "Invalid audience")
    doc = {"id": new_id("doc"), **payload.model_dump(), "created_by": user["name"], "created_at": now_iso(), "updated_at": now_iso()}
    await db.documents.insert_one(dict(doc))
    await log_audit(user, "document_created", "document", doc["id"], {"title": payload.title, "audience": payload.audience})
    if payload.audience != "private_draft":
        for mid in payload.assigned_to:
            m = await db.members.find_one({"id": mid}, {"_id": 0})
            if m and m.get("user_id"):
                await notify_user(m["user_id"], "New document assigned", f"{payload.title} requires your attention", "/portal/documents")
    return clean(doc)


@api_router.get("/documents")
async def list_documents(user=Depends(get_current_user)):
    if user["role"] in STAFF_ROLES:
        docs = await db.documents.find({}, {"_id": 0}).sort([("display_order", 1), ("created_at", -1)]).to_list(1000)
    else:
        m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
        mid = m["id"] if m else None
        alld = await db.documents.find({}, {"_id": 0}).sort([("display_order", 1), ("created_at", -1)]).to_list(1000)
        docs = [d for d in alld if _doc_visible_to(d, user, mid)]
    for d in docs:
        sig = await db.signatures.find_one({"document_id": d["id"], "user_id": user["user_id"]}, {"_id": 0})
        d["signed_by_me"] = bool(sig)
        d["signature_id"] = sig["id"] if sig else None
        d["signatures_count"] = await db.signatures.count_documents({"document_id": d["id"]})
        d["assigned_count"] = len(d.get("assigned_to") or [])
    return docs


@api_router.get("/documents/{doc_id}")
async def get_document(doc_id: str, user=Depends(get_current_user)):
    d = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES:
        m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
        if not _doc_visible_to(d, user, m["id"] if m else None):
            raise HTTPException(403, "You do not have access to this document")
    return d


@api_router.put("/documents/{doc_id}")
async def edit_document(doc_id: str, payload: DocumentIn, user=Depends(require_roles(*STAFF_ROLES))):
    d = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    upd = payload.model_dump(exclude_unset=True)
    if "audience" in upd and upd["audience"] not in DOC_AUDIENCES:
        raise HTTPException(400, "Invalid audience")
    upd["updated_at"] = now_iso()
    await db.documents.update_one({"id": doc_id}, {"$set": upd})
    await log_audit(user, "document_updated", "document", doc_id, {"title": upd.get("title", d.get("title"))})
    return await db.documents.find_one({"id": doc_id}, {"_id": 0})


class DocAssignIn(BaseModel):
    member_ids: List[str] = []
    roles: List[str] = []
    audience: Optional[str] = None
    notify: bool = True


@api_router.post("/documents/{doc_id}/assign")
async def assign_document(doc_id: str, payload: DocAssignIn, user=Depends(require_roles(*STAFF_ROLES))):
    d = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    assigned = list(set((d.get("assigned_to") or []) + payload.member_ids))
    roles = list(set((d.get("assigned_roles") or []) + payload.roles))
    aud = payload.audience or ("specific_members" if payload.member_ids and not payload.roles else d.get("audience"))
    if aud == "private_draft":
        aud = "specific_members"
    await db.documents.update_one({"id": doc_id}, {"$set": {"assigned_to": assigned, "assigned_roles": roles, "audience": aud, "updated_at": now_iso()}})
    sent = 0
    if payload.notify:
        targets = set(payload.member_ids)
        if payload.roles:
            async for m in db.members.find({"role": {"$in": payload.roles}}, {"_id": 0, "id": 1}):
                targets.add(m["id"])
        for mid in targets:
            m = await db.members.find_one({"id": mid}, {"_id": 0})
            if m and m.get("user_id"):
                await notify_user(m["user_id"], "Document assigned", f"{d['title']} requires your attention", "/portal/documents")
                sent += 1
    await log_audit(user, "document_assigned", "document", doc_id, {"members": len(payload.member_ids), "roles": payload.roles, "notifications": sent})
    return {"ok": True, "assigned": len(assigned), "notifications_sent": sent}


@api_router.put("/documents/{doc_id}/archive")
async def archive_document(doc_id: str, payload: Dict[str, Any], user=Depends(require_roles(*STAFF_ROLES))):
    if not await db.documents.find_one({"id": doc_id}, {"_id": 1}):
        raise HTTPException(404, "Not found")
    val = "archived" if payload.get("archived", True) else "active"
    await db.documents.update_one({"id": doc_id}, {"$set": {"status": val, "updated_at": now_iso()}})
    await log_audit(user, "document_archived" if val == "archived" else "document_unarchived", "document", doc_id)
    return await db.documents.find_one({"id": doc_id}, {"_id": 0})


@api_router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user=Depends(require_roles(*STAFF_ROLES))):
    d = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    sigs = await db.signatures.count_documents({"document_id": doc_id})
    if sigs or (d.get("assigned_to") or []) or (d.get("assigned_roles") or []) or d.get("audience", "private_draft") != "private_draft":
        raise HTTPException(400, "This document has been assigned or signed and cannot be deleted — archive it instead.")
    await db.documents.delete_one({"id": doc_id})
    await log_audit(user, "document_deleted", "document", doc_id, {"title": d.get("title")})
    return {"ok": True}


@api_router.get("/documents/{doc_id}/assignments")
async def document_assignments(doc_id: str, user=Depends(require_roles(*STAFF_ROLES))):
    d = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    members = []
    for mid in (d.get("assigned_to") or []):
        m = await db.members.find_one({"id": mid}, {"_id": 0})
        if m:
            signed = bool(await db.signatures.find_one({"document_id": doc_id, "user_id": m.get("user_id")})) if m.get("user_id") else False
            members.append({"id": m["id"], "name": m.get("name"), "role": m.get("role"), "signed": signed})
    return {"audience": d.get("audience"), "roles": d.get("assigned_roles"), "members": members,
            "history": await db.audit_logs.find({"related_type": "document", "related_id": doc_id}, {"_id": 0}).sort("created_at", -1).to_list(200)}

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
    if user["role"] not in STAFF_ROLES:
        m0 = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
        if not _doc_visible_to(d, user, m0["id"] if m0 else None):
            raise HTTPException(403, "You do not have access to this document")
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
    signer_name = (m.get("name") if m else None) or payload.legal_name
    lead_link = f"/portal/members/{m['id']}" if m else "/portal/documents"
    for lid in await _leadership_user_ids():
        if lid != user["user_id"]:
            await notify_user(lid, "Document signed", f"{signer_name} completed and signed {d['title']}.", lead_link, "success", "Signatures")
    return clean(sig)


@api_router.get("/documents/{doc_id}/signers")
async def doc_signers(doc_id: str, user=Depends(require_roles(*STAFF_ROLES))):
    d = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    sigs = await db.signatures.find({"document_id": doc_id}, {"_id": 0}).sort("signed_at", -1).to_list(1000)
    signed = []
    signed_uids = set()
    for s in sigs:
        signed_uids.add(s.get("user_id"))
        m = await db.members.find_one({"user_id": s.get("user_id")}, {"_id": 0}) if s.get("user_id") else None
        signed.append({"name": (m or {}).get("name") or s.get("legal_name"), "role": (m or {}).get("role"),
                       "member_id": (m or {}).get("id"), "signed_at": s.get("signed_at"),
                       "legal_name": s.get("legal_name"), "signature_id": s.get("id"),
                       "assigned_at": (m or {}).get("start_date")})
    pending = []
    for mid in (d.get("assigned_to") or []):
        m = await db.members.find_one({"id": mid}, {"_id": 0})
        if m and m.get("user_id") not in signed_uids:
            pending.append({"name": m.get("name"), "role": m.get("role"), "member_id": m["id"], "assigned_at": m.get("start_date")})
    return {"title": d.get("title"), "file_id": d.get("file_id"), "signed": signed, "pending": pending}

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
    to_leadership = False
    member_id = None
    if user["role"] in STAFF_ROLES:
        recipients = set(payload.recipient_ids)
        if payload.target_role or payload.target_state:
            q = {}
            if payload.target_role: q["role"] = payload.target_role
            if payload.target_state: q["state"] = payload.target_state
            async for m in db.members.find(q, {"_id": 0}):
                if m.get("user_id"):
                    recipients.add(m["user_id"])
    else:
        # Members always route to the CEC leadership team (no admin directory exposed).
        to_leadership = True
        recipients = set(await _leadership_user_ids())
        recipients.discard(user["user_id"])
        mm = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0, "id": 1})
        member_id = (mm or {}).get("id")
    if not recipients:
        raise HTTPException(400, "No recipients available")
    thread_id = new_id("thread")
    msg = {"id": new_id("msg"), "thread_id": thread_id, "subject": payload.subject, "body": payload.body,
           "from_id": user["user_id"], "from_name": user["name"], "from_role": user["role"],
           "recipient_ids": list(recipients), "file_ids": payload.file_ids, "read_by": [],
           "to_leadership": to_leadership, "member_id": member_id, "created_at": now_iso()}
    await db.messages.insert_one(dict(msg))
    for rid in recipients:
        await notify_user(rid, f"New message: {payload.subject}", payload.body[:120], "/portal/messages", "info", "Messages")
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

class ReplyIn(BaseModel):
    body: str
    file_ids: List[str] = []

async def _files_meta(ids):
    out = []
    for fid in ids or []:
        f = await db.files.find_one({"id": fid}, {"_id": 0, "id": 1, "original_filename": 1})
        if f: out.append(f)
    return out

@api_router.get("/messages/{thread_id}/thread")
async def get_thread(thread_id: str, user=Depends(get_current_user)):
    msgs = await db.messages.find({"thread_id": thread_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    if not msgs:
        raise HTTPException(404, "Thread not found")
    allowed = set()
    for m in msgs:
        allowed |= set(m.get("recipient_ids", [])) | {m.get("from_id")}
    if user["role"] not in STAFF_ROLES and user["user_id"] not in allowed:
        raise HTTPException(403, "Forbidden")
    await db.messages.update_many({"thread_id": thread_id}, {"$addToSet": {"read_by": user["user_id"]}})
    for m in msgs:
        m["files"] = await _files_meta(m.get("file_ids"))
    return {"thread_id": thread_id, "subject": msgs[0].get("subject"), "messages": msgs}

@api_router.post("/messages/{thread_id}/reply")
async def reply_message(thread_id: str, payload: ReplyIn, user=Depends(get_current_user)):
    thread = await db.messages.find({"thread_id": thread_id}, {"_id": 0}).to_list(1000)
    if not thread:
        raise HTTPException(404, "Thread not found")
    participants = set()
    for m in thread:
        participants |= set(m.get("recipient_ids", [])) | {m.get("from_id")}
    if user["role"] not in STAFF_ROLES and user["user_id"] not in participants:
        raise HTTPException(403, "Forbidden")
    recipients = [p for p in participants if p and p != user["user_id"]]
    root = thread[0]
    msg = {"id": new_id("msg"), "thread_id": thread_id, "subject": root.get("subject"), "body": payload.body,
           "from_id": user["user_id"], "from_name": user["name"], "from_role": user["role"],
           "recipient_ids": recipients, "file_ids": payload.file_ids, "read_by": [user["user_id"]], "is_reply": True, "created_at": now_iso()}
    await db.messages.insert_one(dict(msg))
    for rid in recipients:
        await notify_user(rid, f"Reply: {root.get('subject')}", payload.body[:120], "/portal/messages")
    await log_audit(user, "message_replied", "message", msg["id"])
    return clean(msg)

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

# ---------------- notification templates & communications ----------------
TEMPLATE_PLACEHOLDERS = ["first_name", "name", "ref", "role", "org_email", "org_phone", "admin_name", "portal_link", "event_name", "event_date"]

DEFAULT_TEMPLATES = [
    {"key": "application_received", "name": "Application Received", "category": "Applications",
     "subject": "We received your CEC application ({{ref}})", "mode": "automatic", "trigger": "application_submitted",
     "enabled": True, "include_button": False, "button_label": "",
     "body": "Hi {{first_name}},\nThank you for applying to the AAWTA Community Engagement Committee as a {{role}}. Your reference number is {{ref}}.\nOur team will review your application and follow up with next steps. If you have questions, contact us at {{org_email}}.\nWarm regards,\nThe AAWTA CEC Team"},
    {"key": "application_approved", "name": "Application Approved", "category": "Applications",
     "subject": "Congratulations — your CEC application is approved ({{ref}})", "mode": "automatic", "trigger": "application_approved",
     "enabled": True, "include_button": True, "button_label": "Access CEC Connect",
     "body": "Hi {{first_name}},\nCongratulations! Your application to serve as a CEC {{role}} has been approved.\nThe next step is to activate your CEC Connect account and complete your onboarding profile.\nWe're excited to have you with us.\nThe AAWTA CEC Team"},
    {"key": "onboarding_profile", "name": "Complete Your Onboarding Profile", "category": "Onboarding",
     "subject": "Complete your CEC Connect onboarding profile", "mode": "automatic", "trigger": "member_converted",
     "enabled": True, "include_button": True, "button_label": "Complete My Profile",
     "body": "Hi {{first_name}},\nWelcome aboard! To finish setting up your CEC {{role}} account, please complete your onboarding profile and review your assigned documents.\nSign in with the Google account tied to this email — no password needed.\nThe AAWTA CEC Team"},
    {"key": "missing_requirements", "name": "Missing Requirements", "category": "Onboarding",
     "subject": "Action needed: complete your CEC onboarding requirements", "mode": "manual", "trigger": "manual",
     "enabled": True, "include_button": True, "button_label": "Complete Requirements",
     "body": "Hi {{first_name}},\nWe noticed a few onboarding items still need your attention. Please sign in to review and complete your outstanding requirements.\nIf you need help, contact us at {{org_email}}.\nThe AAWTA CEC Team"},
    {"key": "onboarding_reminder", "name": "Onboarding Reminder", "category": "Onboarding",
     "subject": "Reminder: finish your CEC onboarding", "mode": "automatic", "trigger": "onboarding_reminder",
     "enabled": True, "include_button": True, "button_label": "Continue Onboarding",
     "body": "Hi {{first_name}},\nThis is a friendly reminder to complete your CEC {{role}} onboarding. Finishing these steps unlocks your full access and helps us support your work.\nThe AAWTA CEC Team"},
    {"key": "fully_onboarded_welcome", "name": "Fully Onboarded / Welcome", "category": "Onboarding",
     "subject": "You're fully onboarded — welcome to the CEC!", "mode": "automatic", "trigger": "onboarding_complete",
     "enabled": True, "include_button": True, "button_label": "Go to My Dashboard",
     "body": "Hi {{first_name}},\nCongratulations on completing your onboarding! You're now a fully active CEC {{role}}.\nExplore your dashboard, set your goals, and jump into upcoming events. We're thrilled to have you.\nThe AAWTA CEC Team"},
    {"key": "volunteer_event_assignment", "name": "Volunteer Event Assignment", "category": "Events",
     "subject": "You've been assigned to {{event_name}}", "mode": "manual", "trigger": "event_assignment",
     "enabled": True, "include_button": True, "button_label": "View Event",
     "body": "Hi {{first_name}},\nYou've been assigned to support {{event_name}} on {{event_date}}. Please review the event details and check-in instructions in your portal.\nThank you for volunteering!\nThe AAWTA CEC Team"},
    {"key": "ambassador_update", "name": "Ambassador Update", "category": "General",
     "subject": "An update from the AAWTA CEC", "mode": "manual", "trigger": "manual",
     "enabled": True, "include_button": False, "button_label": "",
     "body": "Hi {{first_name}},\nWe wanted to share an important update with you.\n[Add your update here.]\nThank you for all you do as a CEC Ambassador.\nThe AAWTA CEC Team"},
    {"key": "general_communication", "name": "General Communication", "category": "General",
     "subject": "A message from the AAWTA CEC", "mode": "manual", "trigger": "manual",
     "enabled": True, "include_button": False, "button_label": "",
     "body": "Hi {{first_name}},\n[Write your message here.]\nThank you,\n{{admin_name}}\nAAWTA CEC"},
]


def _subst(text, ctx):
    return re.sub(r"{{\s*(\w+)\s*}}", lambda m: str(ctx.get(m.group(1), m.group(0))), text or "")


def _body_to_html(body_text, ctx=None, include_button=False, button_label=None):
    text = _subst(body_text, ctx or {})
    inner = "".join(ep(hesc(line)) for line in text.split("\n") if line.strip())
    if include_button:
        link = (ctx or {}).get("portal_link") or (PUBLIC_BASE_URL + "/portal")
        inner += ep(f'<a href="{hesc(link)}" style="background:#D6189B;color:#fff;padding:10px 18px;'
                    f'border-radius:999px;text-decoration:none;font-weight:bold">{hesc(button_label or "Open CEC Connect")}</a>')
    return inner


async def ensure_templates():
    for t in DEFAULT_TEMPLATES:
        await db.notification_templates.update_one(
            {"key": t["key"]},
            {"$setOnInsert": {**t, "is_system": True, "placeholders": TEMPLATE_PLACEHOLDERS,
                              "created_at": now_iso(), "updated_at": now_iso(), "updated_by": None}},
            upsert=True)


async def _comm_ctx(subject_type, subject_id, actor):
    settings = await get_settings_doc()
    base = PUBLIC_BASE_URL
    ctx = {"org_email": settings.get("email") or "", "org_phone": settings.get("phone") or "",
           "admin_name": (actor or {}).get("name") or "", "portal_link": base + "/portal",
           "first_name": "there", "name": "", "ref": "", "role": "", "event_name": "", "event_date": ""}
    target_email = None
    if subject_type == "application":
        a = await db.applications.find_one({"id": subject_id}, {"_id": 0})
        if a:
            ctx["name"] = a.get("name") or ""
            ctx["first_name"] = (a.get("data", {}).get("first_name") or (a.get("name") or "there").split(" ")[0]) or "there"
            ctx["ref"] = a.get("ref") or ""
            ctx["role"] = {"ambassador": "Ambassador", "volunteer": "Volunteer"}.get(a.get("type"), "")
            target_email = a.get("email")
    elif subject_type == "member":
        m = await db.members.find_one({"id": subject_id}, {"_id": 0})
        if m:
            ctx["name"] = m.get("name") or ""
            ctx["first_name"] = (m.get("name") or "there").split(" ")[0] or "there"
            ctx["role"] = (m.get("role") or "").replace("_", " ").title()
            target_email = m.get("email")
    else:  # generic sample for template editor
        ctx.update({"name": "Jordan Smith", "first_name": "Jordan", "ref": "AMB-2026-0001",
                    "role": "Ambassador", "event_name": "CEC Community Career Fair", "event_date": "2026-10-15"})
    return ctx, target_email


async def _resolve_target_user_id(subject_type, subject_id):
    if subject_type == "member":
        m = await db.members.find_one({"id": subject_id}, {"_id": 0, "user_id": 1})
        return (m or {}).get("user_id")
    if subject_type == "application":
        a = await db.applications.find_one({"id": subject_id}, {"_id": 0, "member_id": 1})
        if a and a.get("member_id"):
            m = await db.members.find_one({"id": a["member_id"]}, {"_id": 0, "user_id": 1})
            return (m or {}).get("user_id")
    return None


async def send_template_email(key, subject_type, subject_id, actor=None, extra_ctx=None, force=False):
    """Fire a template-driven email + log a communication record. Respects enabled/mode unless force."""
    await ensure_templates()
    tpl = await db.notification_templates.find_one({"key": key}, {"_id": 0})
    if not tpl or (not tpl.get("enabled") and not force):
        return None
    if not force and tpl.get("mode") != "automatic":
        return None
    ctx, target_email = await _comm_ctx(subject_type, subject_id, actor)
    if extra_ctx:
        ctx.update({k: v for k, v in extra_ctx.items() if v is not None})
    if not target_email:
        return None
    subject = _subst(tpl.get("subject", ""), ctx)
    inner = _body_to_html(tpl.get("body", ""), ctx, tpl.get("include_button"), tpl.get("button_label"))
    log = await log_and_send(to=target_email, subject=subject, inner_html=inner, title=subject,
                             template=key, related_type=subject_type, related_id=subject_id)
    rec = {"id": new_id("comm"), "subject_type": subject_type, "subject_id": subject_id, "channel": "email",
           "template_key": key, "template_name": tpl.get("name"), "subject": subject, "body": _subst(tpl.get("body", ""), ctx),
           "to_email": target_email, "sent_by_id": (actor or {}).get("user_id"), "sent_by_name": (actor or {}).get("name") or "System (automatic)",
           "automatic": actor is None, "status": log["status"],
           "email_log_id": log["id"], "provider_id": log.get("provider_id"), "created_at": now_iso()}
    await db.communications.insert_one(dict(rec))
    return log


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    mode: Optional[str] = None
    enabled: Optional[bool] = None
    include_button: Optional[bool] = None
    button_label: Optional[str] = None
    category: Optional[str] = None


class TestSendIn(BaseModel):
    to: EmailStr


@api_router.get("/notification-templates")
async def list_templates(user=Depends(require_roles(*STAFF_ROLES))):
    await ensure_templates()
    tpls = await db.notification_templates.find({}, {"_id": 0}).sort("category", 1).to_list(200)
    return {"templates": tpls, "placeholders": TEMPLATE_PLACEHOLDERS}


@api_router.get("/notification-templates/{key}")
async def get_template(key: str, user=Depends(require_roles(*STAFF_ROLES))):
    await ensure_templates()
    t = await db.notification_templates.find_one({"key": key}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Template not found")
    return t


@api_router.put("/notification-templates/{key}")
async def update_template(key: str, payload: TemplateUpdate, user=Depends(require_roles(*LEADERSHIP_ROLES))):
    await ensure_templates()
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "mode" in upd and upd["mode"] not in ("automatic", "manual"):
        raise HTTPException(400, "Invalid mode")
    upd["updated_at"] = now_iso()
    upd["updated_by"] = user["name"]
    r = await db.notification_templates.update_one({"key": key}, {"$set": upd})
    if not r.matched_count:
        raise HTTPException(404, "Template not found")
    await log_audit(user, "template_updated", "notification_template", key, {"fields": list(upd.keys())})
    return await db.notification_templates.find_one({"key": key}, {"_id": 0})


@api_router.post("/notification-templates/{key}/preview")
async def preview_template(key: str, user=Depends(require_roles(*STAFF_ROLES))):
    await ensure_templates()
    t = await db.notification_templates.find_one({"key": key}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Template not found")
    ctx, _ = await _comm_ctx("generic", None, user)
    subject = _subst(t.get("subject", ""), ctx)
    inner = _body_to_html(t.get("body", ""), ctx, t.get("include_button"), t.get("button_label"))
    return {"subject": subject, "html": _wrap(subject, inner)}


@api_router.post("/notification-templates/{key}/test-send")
async def test_send_template(key: str, payload: TestSendIn, user=Depends(require_roles(*STAFF_ROLES))):
    await ensure_templates()
    t = await db.notification_templates.find_one({"key": key}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Template not found")
    ctx, _ = await _comm_ctx("generic", None, user)
    subject = "[TEST] " + _subst(t.get("subject", ""), ctx)
    inner = _body_to_html(t.get("body", ""), ctx, t.get("include_button"), t.get("button_label"))
    log = await log_and_send(to=str(payload.to), subject=subject, inner_html=inner, title=subject,
                             template=f"test:{key}", related_type="notification_template", related_id=key)
    await log_audit(user, "template_test_sent", "notification_template", key, {"to": str(payload.to), "status": log["status"]})
    return {"status": log["status"], "error": log.get("error")}


class CommPreviewIn(BaseModel):
    subject_type: str
    subject_id: str
    template_key: str


class CommSendIn(BaseModel):
    subject_type: str
    subject_id: str
    template_key: Optional[str] = None
    subject: str
    body: str
    channel: str = "email"
    include_button: bool = False
    button_label: Optional[str] = None


@api_router.post("/comms/preview")
async def comm_preview(payload: CommPreviewIn, user=Depends(require_roles(*STAFF_ROLES))):
    if payload.subject_type not in ("application", "member"):
        raise HTTPException(400, "Invalid subject_type")
    await ensure_templates()
    t = await db.notification_templates.find_one({"key": payload.template_key}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Template not found")
    ctx, _ = await _comm_ctx(payload.subject_type, payload.subject_id, user)
    return {"subject": _subst(t.get("subject", ""), ctx), "body": _subst(t.get("body", ""), ctx),
            "include_button": t.get("include_button", False), "button_label": t.get("button_label") or ""}


@api_router.post("/comms/send")
async def comm_send(payload: CommSendIn, user=Depends(require_roles(*STAFF_ROLES))):
    if payload.subject_type not in ("application", "member"):
        raise HTTPException(400, "Invalid subject_type")
    if payload.channel not in ("email", "portal", "both"):
        raise HTTPException(400, "Invalid channel")
    if not payload.subject.strip() or not payload.body.strip():
        raise HTTPException(400, "Subject and message are required")
    ctx, target_email = await _comm_ctx(payload.subject_type, payload.subject_id, user)
    tpl_name = None
    if payload.template_key:
        t = await db.notification_templates.find_one({"key": payload.template_key}, {"_id": 0, "name": 1})
        tpl_name = (t or {}).get("name")
    email_log_id = None
    provider_id = None
    status = "portal_only"
    if payload.channel in ("email", "both"):
        if not target_email:
            raise HTTPException(400, "No email address on record for this recipient")
        inner = _body_to_html(payload.body, ctx, payload.include_button, payload.button_label)
        log = await log_and_send(to=target_email, subject=payload.subject, inner_html=inner, title=payload.subject,
                                 template=payload.template_key or "custom", related_type=payload.subject_type, related_id=payload.subject_id)
        email_log_id = log["id"]
        provider_id = log.get("provider_id")
        status = log["status"]
    if payload.channel in ("portal", "both"):
        uid = await _resolve_target_user_id(payload.subject_type, payload.subject_id)
        if uid:
            await notify_user(uid, payload.subject, payload.body[:140], "/portal", "info")
    rec = {"id": new_id("comm"), "subject_type": payload.subject_type, "subject_id": payload.subject_id, "channel": payload.channel,
           "template_key": payload.template_key, "template_name": tpl_name, "subject": payload.subject, "body": payload.body,
           "to_email": target_email, "sent_by_id": user["user_id"], "sent_by_name": user["name"], "automatic": False,
           "status": status, "email_log_id": email_log_id, "provider_id": provider_id, "created_at": now_iso()}
    await db.communications.insert_one(dict(rec))
    await add_timeline(payload.subject_type, payload.subject_id, f"Message sent: {payload.subject}", user)
    await log_audit(user, "communication_sent", payload.subject_type, payload.subject_id, {"template": payload.template_key, "channel": payload.channel})
    return clean(rec)


@api_router.get("/comms")
async def list_comms(subject_type: str, subject_id: str, user=Depends(require_roles(*STAFF_ROLES))):
    recs = await db.communications.find({"subject_type": subject_type, "subject_id": subject_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for r in recs:
        if r.get("email_log_id"):
            el = await db.email_log.find_one({"id": r["email_log_id"]}, {"_id": 0, "status": 1, "opened_at": 1, "delivered_at": 1, "error": 1})
            if el:
                r["status"] = el.get("status") or r.get("status")
                r["delivered_at"] = el.get("delivered_at")
                r["opened_at"] = el.get("opened_at")
                r["error"] = el.get("error")
    return recs

# ---------------- registration & email helpers ----------------
PAYMENT_STATUSES = ["paid", "pending", "complimentary", "refunded", "not_applicable"]
BADGE_CATEGORIES = ["General Attendee", "Member", "VIP", "Speaker", "Sponsor", "Exhibitor", "Partner", "Media", "Volunteer", "Ambassador", "Staff", "Walk-In"]
EMAIL_STATUS_MAP = {"email.sent": "sent", "email.delivered": "delivered", "email.delivery_delayed": "sent",
                    "email.opened": "opened", "email.clicked": "opened", "email.bounced": "bounced",
                    "email.complained": "failed", "email.failed": "failed"}


def gen_confirmation_number():
    a = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "CEC-" + "".join(secrets.choice(a) for _ in range(8))


def normalize_website(u):
    if not u:
        return u
    u = str(u).strip()
    if not u:
        return u
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    return u


async def log_and_send(*, to, subject, inner_html, title, template, related_type=None, related_id=None):
    log_id = new_id("elog"); provider_id = None; status = "failed"; error = None
    for attempt in range(3):
        try:
            provider_id = await send_email(to=to, subject=subject, html=_wrap(title, inner_html))
            if provider_id:
                status = "sent"; error = None; break
            error = "Provider did not return a message id"
        except Exception as e:
            error = str(e)
        if attempt < 2:
            await asyncio.sleep(1.5 * (attempt + 1))
    doc = {"id": log_id, "provider_id": provider_id, "to": to, "subject": subject, "template": template,
           "related_type": related_type, "related_id": related_id, "status": status, "error": error,
           "attempts": 1, "sent_at": now_iso() if status == "sent" else None, "delivered_at": None,
           "opened_at": None, "last_resend_at": None, "created_at": now_iso()}
    await db.email_log.insert_one(dict(doc))
    return doc


def _gcal_link(e):
    if not e.get("date"):
        return None
    d = str(e["date"]).replace("-", "")
    params = {"action": "TEMPLATE", "text": e.get("name") or "AAWTA Event", "dates": f"{d}/{d}"}
    if e.get("description"):
        params["details"] = str(e["description"])[:500]
    locv = e.get("venue_address") or e.get("location") or ""
    if locv:
        params["location"] = locv
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def build_registration_email(reg, e, settings, kind):
    base = PUBLIC_BASE_URL
    conf = reg["confirmation_number"]; token = reg["checkin_token"]
    manage = f"{base}/r/{conf}?t={token}"
    qr = f"{base}/api/public/qr/{token}.png"
    gcal = _gcal_link(e)
    fname = hesc(reg.get("first_name") or reg.get("name") or "there")

    def row(label, val):
        return (f'<tr><td style="padding:5px 14px 5px 0;color:#64748b;font-size:13px;white-space:nowrap;vertical-align:top">{hesc(label)}</td>'
                f'<td style="padding:5px 0;color:#0f172a;font-size:13px">{val}</td></tr>')
    rows = row("Confirmation #", f"<strong>{hesc(conf)}</strong>")
    rows += row("Registration", hesc(reg.get("ticket_category") or "General Admission"))
    if e.get("date"):
        rows += row("Date", hesc(e["date"]))
    tparts = [x for x in [e.get("start_time"), e.get("end_time")] if x]
    if tparts:
        tstr = " – ".join(tparts) + (f" {e['timezone']}" if e.get("timezone") else "")
        rows += row("Time", hesc(tstr))
    if e.get("format") == "Virtual":
        vl = normalize_website(e.get("virtual_link"))
        if vl and vl.startswith("https://"):
            rows += row("Join link", f'<a href="{hesc(vl)}" style="color:#D6189B">Open virtual event</a>')
        else:
            rows += row("Location", "Virtual — link provided before the event")
    else:
        if e.get("venue_name"):
            rows += row("Venue", hesc(e["venue_name"]))
        addr = e.get("venue_address") or e.get("location") or ", ".join([x for x in [e.get("city"), e.get("state")] if x])
        if addr:
            rows += row("Address", hesc(addr))
    table = f'<table role="presentation" style="border-collapse:collapse;margin:6px 0 14px">{rows}</table>'
    if kind == "confirmed":
        subject = f"Registration Confirmed: {e['name']}"
        title = "You're Registered!"
        intro = ep(f"Hi {fname}, your registration for <strong>{hesc(e['name'])}</strong> is confirmed. We can't wait to see you!")
    elif kind == "pending":
        subject = f"Payment Pending: {e['name']}"
        title = "Almost There — Payment Pending"
        intro = ep(f"Hi {fname}, we've received your registration for <strong>{hesc(e['name'])}</strong>. Your spot is confirmed once payment is complete.")
        tu = normalize_website(e.get("ticket_url"))
        if tu and tu.startswith("https://"):
            intro += ep(f'<a href="{hesc(tu)}" style="color:#D6189B">Complete your payment</a>')
    else:  # waitlist
        subject = f"You're on the waitlist: {e['name']}"
        title = "You're on the Waitlist"
        intro = ep(f"Hi {fname}, <strong>{hesc(e['name'])}</strong> is currently full. You've been added to the waitlist and we'll email you if a spot opens.")
    qr_block = (f'<div style="text-align:center;margin:14px 0"><img src="{qr}" width="150" height="150" '
                f'alt="Check-in QR code" style="border:1px solid #eee;border-radius:8px"/><br>'
                f'<span style="font-size:12px;color:#64748b">Show this QR code at check-in</span></div>')
    btns = (f'<p style="margin:16px 0"><a href="{manage}" style="background:#D6189B;color:#ffffff;padding:10px 18px;'
            f'border-radius:999px;text-decoration:none;font-size:14px;font-weight:bold">View or manage your registration</a>')
    if gcal:
        btns += f'&nbsp;&nbsp;<a href="{gcal}" style="color:#2E3192;font-size:14px">Add to Calendar</a>'
    btns += "</p>"
    ci = ep("<strong>Check-in:</strong> Please arrive 10–15 minutes early and have your QR code (in this email or on your badge) ready for a quick scan at the entrance.")
    contact = ep(f"Questions? Contact AAWTA at {hesc(settings.get('email') or '')}" + (f" or {hesc(settings.get('phone'))}" if settings.get("phone") else "") + ".")
    cancel = ep(f'If you can no longer attend, you may cancel from your <a href="{manage}" style="color:#D6189B">registration page</a>.') if e.get("allow_cancellation", True) else ""
    inner = intro + table + qr_block + btns + ci + contact + cancel
    return subject, title, inner


async def send_registration_confirmation(reg, e, settings, force=False):
    if reg.get("confirmation_sent") and not force:
        return None
    subject, title, inner = build_registration_email(reg, e, settings, "confirmed")
    log = await log_and_send(to=reg["email"], subject=subject, inner_html=inner, title=title,
                             template="registration_confirmation", related_type="registration", related_id=reg["id"])
    await db.event_registrations.update_one({"id": reg["id"]}, {"$set": {
        "confirmation_sent": True, "confirmation_status": log["status"], "confirmation_sent_at": log.get("sent_at"),
        "confirmation_error": log.get("error"), "confirmation_email_id": log["id"]}})
    return log


async def send_pending_payment_notice(reg, e, settings):
    subject, title, inner = build_registration_email(reg, e, settings, "pending")
    log = await log_and_send(to=reg["email"], subject=subject, inner_html=inner, title=title,
                             template="pending_payment", related_type="registration", related_id=reg["id"])
    await db.event_registrations.update_one({"id": reg["id"]}, {"$set": {"pending_notice_sent": True, "confirmation_status": "pending"}})
    return log


async def send_waitlist_notice(reg, e, settings):
    subject, title, inner = build_registration_email(reg, e, settings, "waitlist")
    return await log_and_send(to=reg["email"], subject=subject, inner_html=inner, title=title,
                              template="waitlist", related_type="registration", related_id=reg["id"])


async def store_consents(reg, source):
    for typ, granted in (("newsletter", reg.get("newsletter_opt_in")), ("events", reg.get("events_opt_in"))):
        if granted:
            await db.consents.insert_one({"id": new_id("cons"), "reg_id": reg["id"], "email": reg["email"],
                                          "event_id": reg["event_id"], "type": typ, "granted": True,
                                          "granted_at": now_iso(), "source": source, "opted_out_at": None,
                                          "created_at": now_iso()})


# ---------------- events ----------------
class EventIn(BaseModel):
    name: str
    event_type: Optional[str] = None
    category: Optional[str] = "Community Outreach"
    format: Optional[str] = "In-person"
    date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    virtual_link: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    audience: Optional[str] = None
    description: Optional[str] = None
    requested_support: Optional[str] = None
    estimated_attendance: Optional[int] = None
    capacity: Optional[int] = None
    is_paid: bool = False
    price: Optional[str] = None
    registration_url: Optional[str] = None
    ticket_url: Optional[str] = None
    ticket_categories: List[str] = []
    allow_cancellation: bool = True
    image_file_id: Optional[str] = None
    file_ids: List[str] = []
    public: bool = False

def _public_evq(extra=None):
    q = {"status": {"$in": ["Approved", "Scheduled"]}, "published": True, "archived": {"$ne": True}}
    if extra: q.update(extra)
    return q

@api_router.post("/events")
async def create_event(payload: EventIn, user=Depends(get_current_user)):
    status = "Approved" if user["role"] in STAFF_ROLES else "Submitted"
    ev = {"id": new_id("evt"), **payload.model_dump(), "status": status, "published": False, "archived": False,
          "registration_status": "open", "submitted_by": user["name"], "submitted_by_id": user["user_id"], "created_at": now_iso()}
    if not ev.get("ticket_categories"): ev["ticket_categories"] = ["General Admission"]
    ev["virtual_link"] = normalize_website(ev.get("virtual_link"))
    await db.events.insert_one(dict(ev))
    await log_audit(user, "event_submitted", "event", ev["id"])
    if status == "Submitted":
        asyncio.create_task(notify_admins(f"New event request: {payload.name}", "Event Request",
                                          ep(f"{user['name']} submitted an event request: <strong>{payload.name}</strong>.")))
    return clean(ev)

@api_router.get("/events")
async def list_events(user=Depends(get_current_user)):
    if user["role"] in STAFF_ROLES:
        q = {}
    else:
        q = {"$or": [{"public": True}, {"submitted_by_id": user["user_id"]}, {"status": {"$in": ["Approved", "Scheduled", "Completed"]}}]}
    return await db.events.find(q, {"_id": 0}).sort("date", 1).to_list(1000)


@api_router.get("/events/{event_id}")
async def get_event(event_id: str, user=Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev: raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES and ev.get("submitted_by_id") != user["user_id"] and not ev.get("public") and ev.get("status") not in ("Approved", "Scheduled", "Completed"):
        raise HTTPException(403, "Forbidden")
    ev["registered_count"] = await db.event_registrations.count_documents({"event_id": event_id, "status": {"$in": ["registered", "checked_in", "walkin"]}})
    return ev


class EventUpdate(BaseModel):
    name: Optional[str] = None
    event_type: Optional[str] = None
    category: Optional[str] = None
    format: Optional[str] = None
    date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    virtual_link: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    audience: Optional[str] = None
    description: Optional[str] = None
    requested_support: Optional[str] = None
    estimated_attendance: Optional[int] = None
    capacity: Optional[int] = None
    is_paid: Optional[bool] = None
    price: Optional[str] = None
    registration_url: Optional[str] = None
    ticket_url: Optional[str] = None
    ticket_categories: Optional[List[str]] = None
    allow_cancellation: Optional[bool] = None
    image_file_id: Optional[str] = None
    file_ids: Optional[List[str]] = None
    public: Optional[bool] = None


@api_router.put("/events/{event_id}")
async def update_event(event_id: str, payload: EventUpdate, user=Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev:
        raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES and ev.get("submitted_by_id") != user["user_id"]:
        raise HTTPException(403, "Forbidden")
    upd = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if "virtual_link" in upd:
        upd["virtual_link"] = normalize_website(upd.get("virtual_link"))
    if not upd:
        return ev
    upd["updated_at"] = now_iso()
    await db.events.update_one({"id": event_id}, {"$set": upd})
    await log_audit(user, "event_updated", "event", event_id, {"fields": list(upd.keys())})
    if "name" in upd:
        await db.gallery_photos.update_many({"event_id": event_id}, {"$set": {"event_name": upd["name"]}})
    return await db.events.find_one({"id": event_id}, {"_id": 0})


class CheckinAssigneesIn(BaseModel):
    user_ids: List[str] = []


@api_router.put("/events/{event_id}/checkin-assignees")
async def set_checkin_assignees(event_id: str, payload: CheckinAssigneesIn, user=Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev: raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES and ev.get("submitted_by_id") != user["user_id"]:
        raise HTTPException(403, "Forbidden")
    previous = set(ev.get("checkin_assignees") or [])
    new_ids = set(payload.user_ids)
    await db.events.update_one({"id": event_id}, {"$set": {"checkin_assignees": payload.user_ids}})
    for uid in (new_ids - previous):
        await notify_user(uid, "Check-In Volunteer assignment", f"You can now run check-in for {ev['name']}.", f"/portal/events/{event_id}/checkin")
        mem = await db.members.find_one({"user_id": uid}, {"_id": 0, "id": 1})
        if mem:
            await add_timeline("member", mem["id"], f"Assigned to check-in for event: {ev['name']}", user)
    await log_audit(user, "checkin_assignees_set", "event", event_id, {"count": len(payload.user_ids)})
    return {"ok": True, "checkin_assignees": payload.user_ids}

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

@api_router.put("/events/{event_id}/publish")
async def publish_event(event_id: str, payload: Dict[str, Any], user=Depends(require_roles(*STAFF_ROLES))):
    published = bool(payload.get("published", True))
    e = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not e: raise HTTPException(404, "Not found")
    upd = {"published": published}
    if published and e.get("status") not in ("Approved", "Scheduled"): upd["status"] = "Approved"
    await db.events.update_one({"id": event_id}, {"$set": upd})
    await log_audit(user, "event_published" if published else "event_unpublished", "event", event_id)
    if published and e.get("submitted_by_id"):
        await notify_user(e["submitted_by_id"], f"Your event '{e['name']}' is now live", "Approved and published to the public calendar.", "/portal/events")
        u = await db.users.find_one({"user_id": e["submitted_by_id"]}, {"_id": 0})
        if u: asyncio.create_task(send_safe(to=u["email"], subject=f"Your event is live: {e['name']}", title="Event Approved & Published", body_html=ep(f"Great news — your event <strong>{e['name']}</strong> has been approved and published to the public AAWTA CEC Events Calendar.")))
    return {"ok": True, "published": published}

@api_router.put("/events/{event_id}/archive")
async def archive_event(event_id: str, user=Depends(require_roles(*STAFF_ROLES))):
    if not await db.events.find_one({"id": event_id}, {"_id": 0}): raise HTTPException(404, "Not found")
    await db.events.update_one({"id": event_id}, {"$set": {"archived": True, "published": False}})
    await log_audit(user, "event_archived", "event", event_id)
    return {"ok": True}

@api_router.get("/public/events")
async def public_events(q: Optional[str] = None, category: Optional[str] = None, format: Optional[str] = None, state: Optional[str] = None):
    query = _public_evq({"date": {"$gte": datetime.now(timezone.utc).strftime("%Y-%m-%d")}})
    if category: query["category"] = category
    if format: query["format"] = format
    if state: query["state"] = state
    if q:
        query["$or"] = [{"name": {"$regex": q, "$options": "i"}}, {"city": {"$regex": q, "$options": "i"}}, {"state": {"$regex": q, "$options": "i"}}, {"description": {"$regex": q, "$options": "i"}}]
    evs = await db.events.find(query, {"_id": 0}).sort("date", 1).to_list(1000)
    for e in evs:
        e["registered_count"] = await db.event_registrations.count_documents({"event_id": e["id"], "status": {"$in": ["registered", "checked_in", "walkin"]}})
    return evs

@api_router.get("/public/events/{event_id}")
async def public_event_detail(event_id: str):
    e = await db.events.find_one(_public_evq({"id": event_id}), {"_id": 0})
    if not e: raise HTTPException(404, "Event not found")
    e["registered_count"] = await db.event_registrations.count_documents({"event_id": event_id, "status": {"$in": ["registered", "checked_in", "walkin"]}})
    return e

class RegistrationIn(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    state: str
    is_member: bool
    ticket_category: str
    business_name: Optional[str] = None
    business_website: Optional[str] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    dietary: Optional[str] = None
    accessibility: Optional[str] = None
    custom_answers: Dict[str, Any] = {}
    newsletter_opt_in: bool = False
    events_opt_in: bool = False
    honeypot: Optional[str] = ""
    company_website: Optional[str] = ""


@api_router.post("/public/events/{event_id}/register")
async def public_register(event_id: str, payload: RegistrationIn):
    if payload.honeypot or payload.company_website:
        raise HTTPException(400, "Spam detected")
    e = await db.events.find_one(_public_evq({"id": event_id}), {"_id": 0})
    if not e:
        raise HTTPException(404, "Event not found")
    if e.get("registration_status") == "closed":
        raise HTTPException(400, "Registration is closed for this event")
    email = payload.email.lower()
    if await db.event_registrations.find_one({"event_id": event_id, "email": email, "status": {"$ne": "cancelled"}}):
        raise HTTPException(400, "You are already registered for this event")
    count = await db.event_registrations.count_documents({"event_id": event_id, "status": {"$in": ["registered", "checked_in", "walkin"]}})
    status = "registered"
    if e.get("registration_status") == "waitlist" or (e.get("capacity") and count >= e["capacity"]):
        status = "waitlist"
    reg = {"id": new_id("reg"), "event_id": event_id, "event_name": e["name"],
           "first_name": payload.first_name.strip(), "last_name": payload.last_name.strip(),
           "name": f"{payload.first_name} {payload.last_name}".strip(),
           "email": email, "phone": payload.phone, "state": payload.state,
           "is_member": payload.is_member, "ticket_category": payload.ticket_category,
           "business_name": payload.business_name, "business_website": normalize_website(payload.business_website),
           "job_title": payload.job_title, "city": payload.city, "zip_code": payload.zip_code,
           "dietary": payload.dietary, "accessibility": payload.accessibility, "custom_answers": payload.custom_answers,
           "newsletter_opt_in": payload.newsletter_opt_in, "events_opt_in": payload.events_opt_in,
           "status": status, "checked_in": False,
           "confirmation_number": gen_confirmation_number(), "checkin_token": secrets.token_urlsafe(16),
           "source": "online", "payment_status": ("not_applicable" if not e.get("is_paid") else "pending"),
           "payment_history": [], "confirmation_sent": False, "resend_count": 0,
           "badge_category": ("Member" if payload.is_member else "General Attendee"), "created_at": now_iso()}
    await db.event_registrations.insert_one(dict(reg))
    await store_consents(reg, "online registration")
    settings = await get_settings_doc()
    if status == "waitlist":
        asyncio.create_task(send_waitlist_notice(reg, e, settings))
    elif not e.get("is_paid"):
        asyncio.create_task(send_registration_confirmation(reg, e, settings))
    else:
        asyncio.create_task(send_pending_payment_notice(reg, e, settings))
    if e.get("submitted_by_id"):
        await notify_user(e["submitted_by_id"], f"New registration: {e['name']}", f"{reg['name']} registered ({status}).", "/portal/events")
    await log_audit(None, "registration_created", "registration", reg["id"], {"event_id": event_id, "source": "online", "status": status})
    return {"status": status, "id": reg["id"], "confirmation_number": reg["confirmation_number"]}


async def _reg_and_authz(reg_id, user):
    reg = await db.event_registrations.find_one({"id": reg_id}, {"_id": 0})
    if not reg:
        raise HTTPException(404, "Registration not found")
    ev = await db.events.find_one({"id": reg["event_id"]}, {"_id": 0})
    if user["role"] not in STAFF_ROLES and (not ev or ev.get("submitted_by_id") != user["user_id"]):
        raise HTTPException(403, "Forbidden")
    return reg, ev


class PaymentUpdate(BaseModel):
    payment_status: str
    note: Optional[str] = None


@api_router.put("/registrations/{reg_id}/payment")
async def update_registration_payment(reg_id: str, payload: PaymentUpdate, user=Depends(get_current_user)):
    reg, ev = await _reg_and_authz(reg_id, user)
    if payload.payment_status not in PAYMENT_STATUSES:
        raise HTTPException(400, "Invalid payment status")
    old = reg.get("payment_status")
    set_fields = {"payment_status": payload.payment_status, "payment_updated_by": user["name"], "payment_updated_at": now_iso()}
    upd = {"$set": set_fields}
    if old != payload.payment_status:
        entry = {"from": old, "to": payload.payment_status, "by": user["name"], "by_id": user["user_id"], "note": payload.note, "at": now_iso()}
        upd["$push"] = {"payment_history": entry}
        await log_audit(user, "payment_status_changed", "registration", reg_id, entry)
    await db.event_registrations.update_one({"id": reg_id}, upd)
    reg = await db.event_registrations.find_one({"id": reg_id}, {"_id": 0})
    settings = await get_settings_doc()
    if payload.payment_status in ("paid", "complimentary") and not reg.get("confirmation_sent") and reg.get("status") != "waitlist":
        await send_registration_confirmation(reg, ev, settings)
    elif payload.payment_status == "pending" and not reg.get("pending_notice_sent"):
        await send_pending_payment_notice(reg, ev, settings)
    return await db.event_registrations.find_one({"id": reg_id}, {"_id": 0})


@api_router.post("/registrations/{reg_id}/send-confirmation")
async def send_confirmation_now(reg_id: str, user=Depends(get_current_user)):
    reg, ev = await _reg_and_authz(reg_id, user)
    settings = await get_settings_doc()
    log = await send_registration_confirmation(reg, ev, settings, force=True)
    await log_audit(user, "confirmation_sent", "registration", reg_id)
    return {"ok": True, "status": log["status"] if log else "unknown"}


@api_router.post("/registrations/{reg_id}/resend-confirmation")
async def resend_confirmation(reg_id: str, user=Depends(get_current_user)):
    reg, ev = await _reg_and_authz(reg_id, user)
    settings = await get_settings_doc()
    log = await send_registration_confirmation(reg, ev, settings, force=True)
    await db.event_registrations.update_one({"id": reg_id}, {"$inc": {"resend_count": 1}, "$set": {"last_resend_at": now_iso()}})
    if log:
        await db.email_log.update_one({"id": log["id"]}, {"$set": {"last_resend_at": now_iso()}})
    await log_audit(user, "confirmation_resent", "registration", reg_id, {"status": log["status"] if log else "n/a"})
    return {"ok": True, "status": log["status"] if log else "unknown"}


@api_router.get("/registrations/{reg_id}/emails")
async def registration_emails(reg_id: str, user=Depends(get_current_user)):
    await _reg_and_authz(reg_id, user)
    return await db.email_log.find({"related_type": "registration", "related_id": reg_id}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api_router.get("/public/qr/{token}.png")
async def registration_qr(token: str):
    reg = await db.event_registrations.find_one({"checkin_token": token}, {"_id": 0})
    if not reg or reg.get("status") == "cancelled":
        raise HTTPException(404, "Not found")
    import qrcode as _qr
    img = _qr.make(token)
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return StreamingResponse(buf, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@api_router.get("/public/registrations/{conf}")
async def public_registration_detail(conf: str, token: str):
    reg = await db.event_registrations.find_one({"confirmation_number": conf, "checkin_token": token}, {"_id": 0})
    if not reg:
        raise HTTPException(404, "Registration not found")
    e = await db.events.find_one({"id": reg["event_id"]}, {"_id": 0}) or {}
    return {
        "registration": {"confirmation_number": reg["confirmation_number"], "name": reg["name"],
                         "first_name": reg.get("first_name"), "email": reg["email"], "status": reg["status"],
                         "ticket_category": reg.get("ticket_category"), "payment_status": reg.get("payment_status"),
                         "checked_in": reg.get("checked_in"), "checkin_token": reg["checkin_token"]},
        "event": {"id": e.get("id"), "name": e.get("name"), "date": e.get("date"), "start_time": e.get("start_time"),
                  "end_time": e.get("end_time"), "timezone": e.get("timezone"), "venue_name": e.get("venue_name"),
                  "venue_address": e.get("venue_address"), "format": e.get("format"),
                  "virtual_link": e.get("virtual_link") if e.get("format") == "Virtual" else None,
                  "city": e.get("city"), "state": e.get("state"), "allow_cancellation": e.get("allow_cancellation", True)},
    }


class CancelIn(BaseModel):
    token: str


@api_router.post("/public/registrations/{conf}/cancel")
async def public_cancel_registration(conf: str, payload: CancelIn):
    reg = await db.event_registrations.find_one({"confirmation_number": conf, "checkin_token": payload.token}, {"_id": 0})
    if not reg:
        raise HTTPException(404, "Registration not found")
    e = await db.events.find_one({"id": reg["event_id"]}, {"_id": 0}) or {}
    if not e.get("allow_cancellation", True):
        raise HTTPException(400, "Cancellation is not permitted for this event")
    if reg.get("status") == "cancelled":
        return {"ok": True, "status": "cancelled"}
    await db.event_registrations.update_one({"id": reg["id"]}, {"$set": {"status": "cancelled", "cancelled_at": now_iso(), "checked_in": False}})
    await log_audit(None, "registration_cancelled", "registration", reg["id"], {"by": "attendee"})
    if e.get("submitted_by_id"):
        await notify_user(e["submitted_by_id"], f"Registration cancelled: {e.get('name')}", f"{reg['name']} cancelled their registration.", "/portal/events")
    return {"ok": True, "status": "cancelled"}


@api_router.post("/webhooks/resend")
async def resend_webhook(request: Request):
    secret = os.environ.get("RESEND_WEBHOOK_SECRET", "")
    if secret:
        provided = request.headers.get("x-webhook-secret") or request.headers.get("svix-signature") or ""
        if not hmac.compare_digest(provided, secret):
            raise HTTPException(401, "Invalid signature")
    raw = await request.body()
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    etype = data.get("type") or data.get("event")
    d = data.get("data") or {}
    if etype in ("contact.unsubscribed", "unsubscribed"):
        em = (d.get("email") or "").lower()
        if em:
            await db.consents.update_many({"email": em, "opted_out_at": None}, {"$set": {"opted_out_at": now_iso()}})
            await db.email_log.update_many({"to": em}, {"$set": {"status": "unsubscribed"}})
        return {"ok": True}
    pid = d.get("email_id") or d.get("id")
    status = EMAIL_STATUS_MAP.get(etype)
    if pid and status:
        upd = {"status": status}
        if status == "delivered":
            upd["delivered_at"] = now_iso()
        if status == "opened":
            upd["opened_at"] = now_iso()
        if status in ("bounced", "failed"):
            upd["error"] = d.get("reason") or d.get("bounce", {}).get("message") or etype
        await db.email_log.update_one({"provider_id": pid}, {"$set": upd})
        log = await db.email_log.find_one({"provider_id": pid}, {"_id": 0})
        if log and log.get("template") == "registration_confirmation" and log.get("related_id"):
            await db.event_registrations.update_one({"id": log["related_id"]}, {"$set": {"confirmation_status": status}})
    return {"ok": True}

@api_router.get("/events/{event_id}/registrations")
async def list_registrations(event_id: str, q: Optional[str] = None, state: Optional[str] = None,
                             member: Optional[str] = None, business: Optional[str] = None, category: Optional[str] = None,
                             source: Optional[str] = None, payment: Optional[str] = None, confirmation: Optional[str] = None,
                             checkin: Optional[str] = None, badge: Optional[str] = None, include_archived: bool = False,
                             user=Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev: raise HTTPException(404, "Not found")
    if not _can_checkin(ev, user):
        raise HTTPException(403, "Forbidden")
    query = {"event_id": event_id}
    if not include_archived:
        query["archived"] = {"$ne": True}
    if q:
        qe = re.escape(q)
        query["$or"] = [{"name": {"$regex": qe, "$options": "i"}}, {"email": {"$regex": qe, "$options": "i"}},
                        {"phone": {"$regex": qe, "$options": "i"}}, {"business_name": {"$regex": qe, "$options": "i"}},
                        {"confirmation_number": {"$regex": qe, "$options": "i"}}]
    if state: query["state"] = state
    if member in ("yes", "no"): query["is_member"] = (member == "yes")
    if business: query["business_name"] = {"$regex": re.escape(business), "$options": "i"}
    if category: query["ticket_category"] = category
    if source: query["source"] = source
    if payment: query["payment_status"] = payment
    if confirmation == "not_sent":
        query["confirmation_sent"] = {"$ne": True}
    elif confirmation:
        query["confirmation_status"] = confirmation
    if checkin == "in": query["checked_in"] = True
    elif checkin == "out": query["checked_in"] = {"$ne": True}
    if badge: query["badge_status"] = badge
    regs = await db.event_registrations.find(query, {"_id": 0}).sort("created_at", -1).to_list(5000)
    all_active = await db.event_registrations.count_documents({"event_id": event_id, "archived": {"$ne": True}, "status": {"$ne": "cancelled"}})
    return {"registrations": regs, "total": all_active, "filtered": len(regs),
            "checked_in": await db.event_registrations.count_documents({"event_id": event_id, "checked_in": True, "archived": {"$ne": True}, "status": {"$ne": "cancelled"}})}


class ManualRegistrationIn(BaseModel):
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    member_status: Optional[str] = "Unknown"
    business_name: Optional[str] = None
    business_website: Optional[str] = None
    job_title: Optional[str] = None
    ticket_category: str = "General Admission"
    payment_status: str = "not_applicable"
    complimentary: bool = False
    newsletter_opt_in: bool = False
    events_opt_in: bool = False
    internal_notes: Optional[str] = None
    badge_category: Optional[str] = None
    checked_in: bool = False


@api_router.post("/events/{event_id}/manual-registration")
async def add_manual_registration(event_id: str, payload: ManualRegistrationIn, user=Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev: raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES and ev.get("submitted_by_id") != user["user_id"]:
        raise HTTPException(403, "Forbidden")
    is_member = payload.member_status == "Yes"
    pay = "complimentary" if payload.complimentary else payload.payment_status
    if pay not in PAYMENT_STATUSES:
        raise HTTPException(400, "Invalid payment status")
    reg = {"id": new_id("reg"), "event_id": event_id, "event_name": ev["name"],
           "first_name": payload.first_name.strip(), "last_name": payload.last_name.strip(),
           "name": f"{payload.first_name} {payload.last_name}".strip(),
           "email": (payload.email or "").lower(), "phone": payload.phone, "state": payload.state,
           "city": payload.city, "zip_code": payload.zip_code, "member_status": payload.member_status, "is_member": is_member,
           "business_name": payload.business_name, "business_website": normalize_website(payload.business_website),
           "job_title": payload.job_title, "ticket_category": payload.ticket_category,
           "newsletter_opt_in": payload.newsletter_opt_in, "events_opt_in": payload.events_opt_in,
           "internal_notes": payload.internal_notes,
           "status": ("checked_in" if payload.checked_in else "registered"), "checked_in": payload.checked_in,
           "checked_in_at": now_iso() if payload.checked_in else None,
           "checkin_method": "manual" if payload.checked_in else None,
           "confirmation_number": gen_confirmation_number(), "checkin_token": secrets.token_urlsafe(16),
           "source": "Manual Entry", "payment_status": pay, "payment_history": [], "confirmation_sent": False, "resend_count": 0,
           "badge_category": payload.badge_category or ("Member" if is_member else "General Attendee"),
           "created_by": user["name"], "created_by_id": user["user_id"], "updated_by": user["name"],
           "created_at": now_iso(), "updated_at": now_iso()}
    await db.event_registrations.insert_one(dict(reg))
    await store_consents(reg, "Manual Entry")
    await log_audit(user, "registration_created", "registration", reg["id"], {"event_id": event_id, "source": "Manual Entry"})
    return await db.event_registrations.find_one({"id": reg["id"]}, {"_id": 0})


class WalkinIn(BaseModel):
    first_name: str
    last_name: Optional[str] = ""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    state: Optional[str] = None
    member_status: Optional[str] = "Unknown"
    business_name: Optional[str] = None
    business_website: Optional[str] = None
    job_title: Optional[str] = None
    ticket_category: Optional[str] = "General Admission"
    badge_category: Optional[str] = None


@api_router.post("/events/{event_id}/registrations")
async def add_walkin(event_id: str, payload: WalkinIn, user=Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev: raise HTTPException(404, "Not found")
    if not _can_checkin(ev, user):
        raise HTTPException(403, "Forbidden")
    name = payload.name or f"{payload.first_name} {payload.last_name or ''}".strip()
    if not name.strip():
        raise HTTPException(400, "Name required")
    if not (payload.email or payload.phone):
        raise HTTPException(400, "Email or phone required")
    is_member = payload.member_status == "Yes"
    reg = {"id": new_id("reg"), "event_id": event_id, "event_name": ev["name"],
           "first_name": payload.first_name.strip(), "last_name": (payload.last_name or "").strip(), "name": name,
           "email": (payload.email or "").lower(), "phone": payload.phone, "state": payload.state,
           "member_status": payload.member_status, "is_member": is_member,
           "business_name": payload.business_name, "business_website": normalize_website(payload.business_website),
           "job_title": payload.job_title, "ticket_category": payload.ticket_category or "General Admission",
           "status": "checked_in", "prev_status": "walkin", "checked_in": True, "checked_in_at": now_iso(),
           "checkin_method": "walkin", "checked_in_by": user["name"],
           "confirmation_number": gen_confirmation_number(), "checkin_token": secrets.token_urlsafe(16),
           "source": "Walk-In", "payment_status": "not_applicable", "payment_history": [], "confirmation_sent": False, "resend_count": 0,
           "badge_category": payload.badge_category or (payload.ticket_category if payload.ticket_category in BADGE_CATEGORIES else ("Member" if is_member else "Walk-In")),
           "created_by": user["name"], "created_by_id": user["user_id"], "created_at": now_iso(), "updated_at": now_iso()}
    await db.event_registrations.insert_one(dict(reg))
    await log_audit(user, "walkin_added", "registration", reg["id"], {"event_id": event_id})
    return await db.event_registrations.find_one({"id": reg["id"]}, {"_id": 0})


class RegEditIn(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    is_member: Optional[bool] = None
    business_name: Optional[str] = None
    business_website: Optional[str] = None
    job_title: Optional[str] = None
    ticket_category: Optional[str] = None
    badge_category: Optional[str] = None
    dietary: Optional[str] = None
    accessibility: Optional[str] = None
    internal_notes: Optional[str] = None


@api_router.put("/registrations/{reg_id}")
async def edit_registration(reg_id: str, payload: RegEditIn, user=Depends(get_current_user)):
    reg, ev = await _reg_and_authz(reg_id, user)
    changes = {}
    data = payload.model_dump(exclude_unset=True)
    if "business_website" in data:
        data["business_website"] = normalize_website(data["business_website"])
    for k, v in data.items():
        if reg.get(k) != v:
            changes[k] = {"from": reg.get(k), "to": v}
    if not changes:
        return reg
    upd = dict(data)
    if "first_name" in data or "last_name" in data:
        fn = data.get("first_name") if data.get("first_name") is not None else reg.get("first_name", "")
        ln = data.get("last_name") if data.get("last_name") is not None else reg.get("last_name", "")
        upd["name"] = f"{fn or ''} {ln or ''}".strip()
    upd["updated_by"] = user["name"]; upd["updated_at"] = now_iso()
    await db.event_registrations.update_one({"id": reg_id}, {"$set": upd})
    await log_audit(user, "registration_updated", "registration", reg_id, {"changes": changes})
    return await db.event_registrations.find_one({"id": reg_id}, {"_id": 0})


@api_router.post("/registrations/{reg_id}/cancel")
async def staff_cancel_registration(reg_id: str, user=Depends(get_current_user)):
    reg, ev = await _reg_and_authz(reg_id, user)
    await db.event_registrations.update_one({"id": reg_id}, {"$set": {"status": "cancelled", "cancelled_at": now_iso(), "checked_in": False}})
    await log_audit(user, "registration_cancelled", "registration", reg_id, {"by": "staff"})
    return await db.event_registrations.find_one({"id": reg_id}, {"_id": 0})


@api_router.put("/registrations/{reg_id}/archive")
async def archive_registration(reg_id: str, payload: Dict[str, Any], user=Depends(get_current_user)):
    reg, ev = await _reg_and_authz(reg_id, user)
    val = bool(payload.get("archived", True))
    await db.event_registrations.update_one({"id": reg_id}, {"$set": {"archived": val}})
    await log_audit(user, "registration_archived" if val else "registration_unarchived", "registration", reg_id)
    return await db.event_registrations.find_one({"id": reg_id}, {"_id": 0})


@api_router.post("/registrations/{reg_id}/badge-printed")
async def mark_badge_printed(reg_id: str, user=Depends(get_current_user)):
    reg, ev = await _reg_and_authz(reg_id, user)
    await db.event_registrations.update_one({"id": reg_id}, {"$set": {"badge_status": "printed", "badge_printed_at": now_iso()}, "$inc": {"badge_print_count": 1}})
    await log_audit(user, "badge_printed", "registration", reg_id)
    return {"ok": True}


@api_router.get("/registrations/{reg_id}/history")
async def registration_history(reg_id: str, user=Depends(get_current_user)):
    await _reg_and_authz(reg_id, user)
    return await db.audit_logs.find({"related_type": "registration", "related_id": reg_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api_router.put("/registrations/{reg_id}/checkin")
async def checkin_registration(reg_id: str, payload: Dict[str, Any], user=Depends(get_current_user)):
    reg = await db.event_registrations.find_one({"id": reg_id}, {"_id": 0})
    if not reg: raise HTTPException(404, "Not found")
    ev = await db.events.find_one({"id": reg["event_id"]}, {"_id": 0})
    if not _can_checkin(ev, user):
        raise HTTPException(403, "Forbidden")
    ci = bool(payload.get("checked_in", True))
    if ci:
        prev = reg.get("status") if reg.get("status") != "checked_in" else reg.get("prev_status", "registered")
        await db.event_registrations.update_one({"id": reg_id}, {"$set": {"checked_in": True, "prev_status": prev, "status": "checked_in", "checked_in_at": now_iso(), "checkin_method": payload.get("method", "manual"), "checked_in_by": user["name"]}})
        await log_audit(user, "checkin", "registration", reg_id, {"method": payload.get("method", "manual")})
    else:
        await db.event_registrations.update_one({"id": reg_id}, {"$set": {"checked_in": False, "status": reg.get("prev_status", "registered"), "checked_in_at": None, "checkin_method": None, "checked_in_by": None}})
        await log_audit(user, "checkin_undo", "registration", reg_id)
    return {"ok": True}

IMPORT_FIELDS = ["first_name", "last_name", "email", "phone", "state", "city", "zip_code", "member_status",
                 "business_name", "business_website", "job_title", "ticket_category", "payment_status",
                 "badge_category", "newsletter_opt_in", "events_opt_in", "internal_notes", "confirmation_number"]
EXPORT_FIELDS = ["name", "email", "phone", "state", "city", "member_status", "business_name", "business_website",
                 "job_title", "ticket_category", "source", "confirmation_number", "payment_status",
                 "confirmation_status", "checked_in", "checked_in_at", "badge_status", "newsletter_opt_in",
                 "events_opt_in", "created_at"]
CONTACT_FIELDS = {"email", "phone"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def _event_authz(event_id, user):
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev: raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES and ev.get("submitted_by_id") != user["user_id"]:
        raise HTTPException(403, "Forbidden")
    return ev


def _auto_map(columns):
    m = {}
    norm = {re.sub(r"[^a-z0-9]", "", c.lower()): c for c in columns}
    aliases = {"first_name": ["firstname", "first"], "last_name": ["lastname", "last", "surname"],
               "email": ["email", "emailaddress", "e-mail"], "phone": ["phone", "phonenumber", "mobile", "cell"],
               "state": ["state", "stateterritory"], "city": ["city"], "zip_code": ["zip", "zipcode", "postalcode"],
               "member_status": ["member", "memberstatus", "aawtamember"], "business_name": ["business", "businessname", "organization", "company"],
               "business_website": ["website", "businesswebsite", "url"], "job_title": ["jobtitle", "title", "role"],
               "ticket_category": ["category", "ticketcategory", "registrationcategory", "ticket"],
               "payment_status": ["payment", "paymentstatus"], "badge_category": ["badge", "badgecategory"],
               "newsletter_opt_in": ["newsletter", "newsletteroptin"], "events_opt_in": ["events", "eventsoptin", "upcomingevents"],
               "internal_notes": ["notes", "internalnotes"], "confirmation_number": ["confirmation", "confirmationnumber", "confirmationno"]}
    for field in IMPORT_FIELDS:
        for a in [re.sub(r"[^a-z0-9]", "", field)] + aliases.get(field, []):
            if a in norm:
                m[field] = norm[a]; break
    return m


def _row_to_record(row, mapping):
    rec = {}
    for field, col in mapping.items():
        if col and col in row:
            rec[field] = (row[col] or "").strip() if isinstance(row[col], str) else row[col]
    return rec


def _truthy(v):
    return str(v).strip().lower() in ("yes", "true", "1", "y", "x")


@api_router.get("/events/{event_id}/import-template.csv")
async def import_template(event_id: str, user=Depends(get_current_user)):
    await _event_authz(event_id, user)
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(IMPORT_FIELDS)
    w.writerow(["Jane", "Doe", "jane@example.com", "555-123-4567", "Georgia", "Atlanta", "30301", "Yes",
                "Doe Logistics", "doelogistics.com", "Owner", "General Admission", "paid", "Member", "Yes", "No", "", ""])
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=registration_import_template.csv"})


@api_router.post("/events/{event_id}/import/parse")
async def import_parse(event_id: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    await _event_authz(event_id, user)
    content = await file.read()
    name = (file.filename or "").lower()
    columns, rows = [], []
    if name.endswith(".xlsx"):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        header = next(it, None) or []
        columns = [str(h).strip() if h is not None else f"col{i}" for i, h in enumerate(header)]
        for r in it:
            if r is None: continue
            d = {columns[i]: ("" if v is None else str(v)) for i, v in enumerate(r) if i < len(columns)}
            if any(str(v).strip() for v in d.values()): rows.append(d)
    else:
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        columns = [c for c in (reader.fieldnames or []) if c]
        for r in reader:
            rows.append({k: (v or "") for k, v in r.items() if k})
    return {"columns": columns, "rows": rows[:2000], "count": len(rows), "mapping": _auto_map(columns)}


class ImportRowsIn(BaseModel):
    mapping: Dict[str, str]
    rows: List[Dict[str, Any]]
    duplicate_strategy: Optional[str] = "skip"


@api_router.post("/events/{event_id}/import/preview")
async def import_preview(event_id: str, payload: ImportRowsIn, user=Depends(get_current_user)):
    await _event_authz(event_id, user)
    existing = await db.event_registrations.find({"event_id": event_id}, {"_id": 0}).to_list(10000)
    by_email = {r.get("email", "").lower(): r for r in existing if r.get("email")}
    by_phone = {re.sub(r"\D", "", r.get("phone") or ""): r for r in existing if r.get("phone")}
    by_conf = {r.get("confirmation_number"): r for r in existing if r.get("confirmation_number")}
    by_namebiz = {f"{(r.get('first_name') or '').lower()}|{(r.get('last_name') or '').lower()}|{(r.get('business_name') or '').lower()}": r for r in existing}
    report = {"total": len(payload.rows), "valid": 0, "duplicates": 0, "missing_required": 0,
              "invalid_emails": 0, "invalid_phones": 0, "skipped": 0, "records": []}
    for idx, row in enumerate(payload.rows):
        rec = _row_to_record(row, payload.mapping)
        issues = []
        if not (rec.get("first_name") and rec.get("last_name")):
            issues.append("missing_required"); report["missing_required"] += 1
        email = (rec.get("email") or "").lower()
        if email and not _EMAIL_RE.match(email):
            issues.append("invalid_email"); report["invalid_emails"] += 1
        phone_d = re.sub(r"\D", "", rec.get("phone") or "")
        if rec.get("phone") and len(phone_d) < 7:
            issues.append("invalid_phone"); report["invalid_phones"] += 1
        dup = None; dup_reason = None
        if email and email in by_email: dup, dup_reason = by_email[email], "email"
        elif phone_d and phone_d in by_phone: dup, dup_reason = by_phone[phone_d], "phone"
        elif rec.get("confirmation_number") and rec["confirmation_number"] in by_conf: dup, dup_reason = by_conf[rec["confirmation_number"]], "confirmation_number"
        elif f"{(rec.get('first_name') or '').lower()}|{(rec.get('last_name') or '').lower()}|{(rec.get('business_name') or '').lower()}" in by_namebiz and rec.get("first_name"):
            dup, dup_reason = by_namebiz[f"{rec['first_name'].lower()}|{(rec.get('last_name') or '').lower()}|{(rec.get('business_name') or '').lower()}"], "name+business"
        is_dup = bool(dup)
        if is_dup: report["duplicates"] += 1
        will_skip = ("missing_required" in issues) or ("invalid_email" in issues)
        if will_skip: report["skipped"] += 1
        elif not is_dup: report["valid"] += 1
        report["records"].append({"row": idx + 1, "data": rec, "issues": issues, "is_duplicate": is_dup,
                                   "duplicate_reason": dup_reason, "duplicate_id": dup.get("id") if dup else None})
    return report


@api_router.post("/events/{event_id}/import/commit")
async def import_commit(event_id: str, payload: ImportRowsIn, user=Depends(get_current_user)):
    ev = await _event_authz(event_id, user)
    existing = await db.event_registrations.find({"event_id": event_id}, {"_id": 0}).to_list(10000)
    by_email = {r.get("email", "").lower(): r for r in existing if r.get("email")}
    by_phone = {re.sub(r"\D", "", r.get("phone") or ""): r for r in existing if r.get("phone")}
    by_conf = {r.get("confirmation_number"): r for r in existing if r.get("confirmation_number")}
    by_namebiz = {f"{(r.get('first_name') or '').lower()}|{(r.get('last_name') or '').lower()}|{(r.get('business_name') or '').lower()}": r for r in existing}
    strat = payload.duplicate_strategy or "skip"
    res = {"imported": 0, "updated": 0, "skipped": 0, "duplicates": 0, "failed": 0, "errors": []}
    for idx, row in enumerate(payload.rows):
        rec = _row_to_record(row, payload.mapping)
        if not (rec.get("first_name") and rec.get("last_name")):
            res["failed"] += 1; res["errors"].append({"row": idx + 1, "reason": "missing first/last name"}); continue
        email = (rec.get("email") or "").lower()
        if email and not _EMAIL_RE.match(email):
            res["failed"] += 1; res["errors"].append({"row": idx + 1, "reason": "invalid email"}); continue
        phone_d = re.sub(r"\D", "", rec.get("phone") or "")
        dup = by_email.get(email) if email else None
        if not dup and phone_d: dup = by_phone.get(phone_d)
        if not dup and rec.get("confirmation_number"): dup = by_conf.get(rec["confirmation_number"])
        if not dup and rec.get("first_name"):
            dup = by_namebiz.get(f"{rec['first_name'].lower()}|{(rec.get('last_name') or '').lower()}|{(rec.get('business_name') or '').lower()}")
        if dup:
            res["duplicates"] += 1
            if strat == "skip":
                res["skipped"] += 1; continue
            if strat == "update":
                upd = {k: v for k, v in rec.items() if v not in (None, "")}
                if "member_status" in upd: upd["is_member"] = upd["member_status"] == "Yes"
                if "business_website" in upd: upd["business_website"] = normalize_website(upd["business_website"])
                if "newsletter_opt_in" in upd: upd["newsletter_opt_in"] = _truthy(upd["newsletter_opt_in"])
                if "events_opt_in" in upd: upd["events_opt_in"] = _truthy(upd["events_opt_in"])
                upd["updated_by"] = user["name"]; upd["updated_at"] = now_iso()
                await db.event_registrations.update_one({"id": dup["id"]}, {"$set": upd})
                res["updated"] += 1; continue
        is_member = rec.get("member_status") == "Yes"
        pay = rec.get("payment_status") if rec.get("payment_status") in PAYMENT_STATUSES else "not_applicable"
        reg = {"id": new_id("reg"), "event_id": event_id, "event_name": ev["name"],
               "first_name": rec.get("first_name"), "last_name": rec.get("last_name"),
               "name": f"{rec.get('first_name', '')} {rec.get('last_name', '')}".strip(),
               "email": email, "phone": rec.get("phone"), "state": rec.get("state"), "city": rec.get("city"),
               "zip_code": rec.get("zip_code"), "member_status": rec.get("member_status") or "Unknown", "is_member": is_member,
               "business_name": rec.get("business_name"), "business_website": normalize_website(rec.get("business_website")),
               "job_title": rec.get("job_title"), "ticket_category": rec.get("ticket_category") or "General Admission",
               "badge_category": rec.get("badge_category") or ("Member" if is_member else "General Attendee"),
               "internal_notes": rec.get("internal_notes"),
               "newsletter_opt_in": _truthy(rec.get("newsletter_opt_in")), "events_opt_in": _truthy(rec.get("events_opt_in")),
               "status": "registered", "checked_in": False, "confirmation_number": rec.get("confirmation_number") or gen_confirmation_number(),
               "checkin_token": secrets.token_urlsafe(16), "source": "Bulk Import", "payment_status": pay, "payment_history": [],
               "confirmation_sent": False, "resend_count": 0, "created_by": user["name"], "created_by_id": user["user_id"],
               "created_at": now_iso(), "updated_at": now_iso()}
        await db.event_registrations.insert_one(dict(reg))
        await store_consents(reg, "Bulk Import")
        if email: by_email[email] = reg
        if phone_d: by_phone[phone_d] = reg
        res["imported"] += 1
    await log_audit(user, "registrations_imported", "event", event_id, {k: res[k] for k in ("imported", "updated", "skipped", "duplicates", "failed")})
    return res


def _segment_query(segment):
    return {
        "all": {}, "checked_in": {"checked_in": True}, "not_checked_in": {"checked_in": {"$ne": True}},
        "walkins": {"source": "Walk-In"}, "manual": {"source": "Manual Entry"}, "online": {"source": "online"},
        "imported": {"source": "Bulk Import"}, "members": {"is_member": True}, "nonmembers": {"is_member": {"$ne": True}},
        "newsletter": {"newsletter_opt_in": True}, "events": {"events_opt_in": True},
    }.get(segment, {})


@api_router.get("/events/{event_id}/export")
async def export_registrations(event_id: str, format: str = "csv", segment: str = "all", state: Optional[str] = None,
                               category: Optional[str] = None, fields: Optional[str] = None, ids: Optional[str] = None,
                               user=Depends(get_current_user)):
    ev = await _event_authz(event_id, user)
    if segment not in {"all", "checked_in", "not_checked_in", "walkins", "manual", "online", "imported", "members", "nonmembers", "newsletter", "events"}:
        raise HTTPException(400, "Invalid segment")
    is_staff = user["role"] in STAFF_ROLES
    query = {"event_id": event_id, "archived": {"$ne": True}}
    query.update(_segment_query(segment))
    if state: query["state"] = state
    if category: query["ticket_category"] = category
    if ids: query["id"] = {"$in": ids.split(",")}
    regs = await db.event_registrations.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)
    sel = [f for f in (fields.split(",") if fields else EXPORT_FIELDS) if f in EXPORT_FIELDS]
    if not is_staff:
        sel = [f for f in sel if f not in CONTACT_FIELDS]
    await log_audit(user, "registrations_exported", "event", event_id, {"segment": segment, "count": len(regs), "format": format})

    def fmt(r, f):
        v = r.get(f)
        if f == "checked_in": return "Yes" if v else "No"
        if f in ("newsletter_opt_in", "events_opt_in"): return "Yes" if v else "No"
        if f == "member_status": return "Member" if r.get("is_member") else (r.get("member_status") or "No")
        return "" if v is None else str(v)

    if format == "xlsx":
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "Registrations"
        ws.append([f.replace("_", " ").title() for f in sel])
        for r in regs: ws.append([fmt(r, f) for f in sel])
        out = io.BytesIO(); wb.save(out); out.seek(0)
        return StreamingResponse(out, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": f"attachment; filename=registrations_{event_id}.xlsx"})
    if format == "pdf":
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(letter), topMargin=40, bottomMargin=30, leftMargin=24, rightMargin=24)
        styles = getSampleStyleSheet()
        pdf_fields = [f for f in sel if f in ("name", "email", "phone", "state", "ticket_category", "source", "confirmation_number", "payment_status", "checked_in")][:9]
        head = [f.replace("_", " ").title() for f in pdf_fields]
        rowsd = [head] + [[fmt(r, f) for f in pdf_fields] for r in regs]
        story = [Paragraph(f"{ev['name']} — Attendee List ({len(regs)})", styles["Title"]), Spacer(1, 10)]
        t = Table(rowsd, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E3192")),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 7),
                               ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")])]))
        story.append(t); doc.build(story); buf.seek(0)
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": f"attachment; filename=attendees_{event_id}.pdf"})
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow([f.replace("_", " ").title() for f in sel])
    for r in regs: w.writerow([fmt(r, f) for f in sel])
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=registrations_{event_id}.csv"})


class BulkActionIn(BaseModel):
    action: str
    ids: List[str]
    value: Optional[str] = None


@api_router.post("/events/{event_id}/bulk")
async def bulk_action(event_id: str, payload: BulkActionIn, user=Depends(get_current_user)):
    ev = await _event_authz(event_id, user)
    regs = await db.event_registrations.find({"event_id": event_id, "id": {"$in": payload.ids}}, {"_id": 0}).to_list(10000)
    settings = await get_settings_doc()
    a = payload.action; affected = 0
    valid_actions = {"send_confirmation", "resend_confirmation", "change_category", "assign_badge_category", "mark_complimentary", "update_payment", "checkin", "cancel", "archive"}
    if a not in valid_actions:
        raise HTTPException(400, "Unknown bulk action")
    if a in ("change_category", "assign_badge_category") and not payload.value:
        raise HTTPException(400, "Value required")
    if a == "update_payment" and payload.value not in PAYMENT_STATUSES:
        raise HTTPException(400, "Invalid payment status")
    for r in regs:
        if a in ("send_confirmation", "resend_confirmation"):
            asyncio.create_task(send_registration_confirmation(r, ev, settings, force=True))
            await db.event_registrations.update_one({"id": r["id"]}, {"$inc": {"resend_count": 1}, "$set": {"last_resend_at": now_iso()}})
        elif a == "change_category":
            await db.event_registrations.update_one({"id": r["id"]}, {"$set": {"ticket_category": payload.value, "updated_at": now_iso()}})
        elif a == "assign_badge_category":
            await db.event_registrations.update_one({"id": r["id"]}, {"$set": {"badge_category": payload.value, "updated_at": now_iso()}})
        elif a == "mark_complimentary":
            await db.event_registrations.update_one({"id": r["id"]}, {"$set": {"payment_status": "complimentary", "updated_at": now_iso()}})
        elif a == "update_payment":
            await db.event_registrations.update_one({"id": r["id"]}, {"$set": {"payment_status": payload.value, "updated_at": now_iso()}})
        elif a == "checkin":
            prev = r.get("status") if r.get("status") != "checked_in" else r.get("prev_status", "registered")
            await db.event_registrations.update_one({"id": r["id"]}, {"$set": {"checked_in": True, "prev_status": prev, "status": "checked_in", "checked_in_at": now_iso(), "checkin_method": "bulk", "checked_in_by": user["name"]}})
        elif a == "cancel":
            await db.event_registrations.update_one({"id": r["id"]}, {"$set": {"status": "cancelled", "checked_in": False, "cancelled_at": now_iso()}})
        elif a == "archive":
            await db.event_registrations.update_one({"id": r["id"]}, {"$set": {"archived": True}})
        await log_audit(user, f"bulk_{a}", "registration", r["id"], {"value": payload.value})
        affected += 1
    await log_audit(user, f"bulk_{a}", "event", event_id, {"count": affected, "value": payload.value})
    return {"ok": True, "action": a, "affected": affected}



BADGE_COLORS = {"General Attendee": "#64748b", "Member": "#2E3192", "VIP": "#D6189B", "Speaker": "#7c3aed",
                "Sponsor": "#059669", "Exhibitor": "#0891b2", "Partner": "#ca8a04", "Media": "#dc2626",
                "Volunteer": "#0d9488", "Ambassador": "#db2777", "Staff": "#475569", "Walk-In": "#f59e0b", "Guest": "#64748b"}


def _badge_colors(event):
    return {**BADGE_COLORS, **((event.get("badge_config") or {}).get("category_colors") or {})}


def _badges_pdf_bytes(regs, event, w, h, colors_map):
    from reportlab.lib.units import inch
    from reportlab.lib import colors as rc
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdfcanvas
    import qrcode
    buf = io.BytesIO()
    W, H = w * inch, h * inch
    c = pdfcanvas.Canvas(buf, pagesize=(W, H))
    cfg = event.get("badge_config") or {}
    for reg in regs:
        cat = reg.get("badge_category") or "General Attendee"
        col = rc.HexColor(colors_map.get(cat, "#64748b"))
        barh = 0.12 * H
        c.setFillColor(rc.HexColor("#2E3192")); c.rect(0, H - barh, W, barh, fill=1, stroke=0)
        c.setFillColor(col); c.rect(0, 0, W, 0.05 * H, fill=1, stroke=0)
        cx = W / 2
        c.setFillColor(rc.white); c.setFont("Helvetica-Bold", max(7, w * 3.2)); c.drawCentredString(cx, H - barh * 0.68, "AAWTA CEC")
        y = H - barh - 0.4 * inch
        name = reg.get("name") or ""
        nsize = w * 7
        c.setFont("Helvetica-Bold", nsize)
        while nsize > 6 and c.stringWidth(name, "Helvetica-Bold", nsize) > W - 0.3 * inch:
            nsize -= 1; c.setFont("Helvetica-Bold", nsize)
        c.setFillColor(rc.HexColor("#0f172a")); c.drawCentredString(cx, y, name)
        y -= 0.32 * inch
        psize = max(6, w * 2.6)
        pill_w = c.stringWidth(cat.upper(), "Helvetica-Bold", psize) + 0.26 * inch
        c.setFillColor(col); c.roundRect(cx - pill_w / 2, y - 0.04 * inch, pill_w, psize + 0.13 * inch, 5, fill=1, stroke=0)
        c.setFillColor(rc.white); c.setFont("Helvetica-Bold", psize); c.drawCentredString(cx, y + 0.02 * inch, cat.upper())
        y -= 0.32 * inch
        if reg.get("business_name"):
            c.setFillColor(rc.HexColor("#334155")); c.setFont("Helvetica", max(6, w * 2.4)); c.drawCentredString(cx, y, str(reg["business_name"])[:42]); y -= 0.17 * inch
        if reg.get("business_website"):
            c.setFillColor(rc.HexColor("#64748b")); c.setFont("Helvetica", max(5, w * 2)); c.drawCentredString(cx, y, str(reg["business_website"])[:42]); y -= 0.15 * inch
        token = reg.get("checkin_token")
        if token:
            qimg = qrcode.make(token); bio = io.BytesIO(); qimg.save(bio, format="PNG"); bio.seek(0)
            qs = min(1.2 * inch, 0.26 * H)
            c.drawImage(ImageReader(bio), cx - qs / 2, 0.13 * H, qs, qs, mask="auto")
        c.setFillColor(rc.HexColor("#334155")); c.setFont("Helvetica-Bold", max(6, w * 2.2))
        c.drawCentredString(cx, 0.09 * H, (event.get("name") or "")[:46])
        footer = " · ".join([x for x in [cfg.get("website") or "aawta.org", cfg.get("contact_email"), (cfg.get("contact_phone") if cfg.get("show_phone") else None)] if x])
        if footer:
            c.setFillColor(rc.HexColor("#94a3b8")); c.setFont("Helvetica", max(4, w * 1.5)); c.drawCentredString(cx, 0.065 * H, footer[:60])
        c.showPage()
    c.save(); buf.seek(0)
    return buf.getvalue()


class BadgeConfigIn(BaseModel):
    default_w: Optional[float] = 4
    default_h: Optional[float] = 6
    address: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    show_phone: bool = False
    category_colors: Dict[str, str] = {}


@api_router.put("/events/{event_id}/badge-config")
async def set_badge_config(event_id: str, payload: BadgeConfigIn, user=Depends(get_current_user)):
    await _event_authz(event_id, user)
    await db.events.update_one({"id": event_id}, {"$set": {"badge_config": payload.model_dump()}})
    await log_audit(user, "badge_config_updated", "event", event_id)
    return payload.model_dump()


class BadgePdfIn(BaseModel):
    ids: List[str] = []
    w: float = 4
    h: float = 6
    combined: bool = True
    only_unprinted: bool = False
    checked_in_only: bool = False


@api_router.post("/events/{event_id}/badges/pdf")
async def badges_pdf(event_id: str, payload: BadgePdfIn, user=Depends(get_current_user)):
    ev = await _event_authz(event_id, user)
    q = {"event_id": event_id, "archived": {"$ne": True}, "status": {"$ne": "cancelled"}}
    if payload.ids: q["id"] = {"$in": payload.ids}
    if payload.checked_in_only: q["checked_in"] = True
    if payload.only_unprinted: q["badge_status"] = {"$ne": "printed"}
    regs = await db.event_registrations.find(q, {"_id": 0}).sort("name", 1).to_list(10000)
    if not regs: raise HTTPException(400, "No registrations to badge")
    colors_map = _badge_colors(ev)
    ids = [r["id"] for r in regs]
    if payload.combined:
        out = io.BytesIO(_badges_pdf_bytes(regs, ev, payload.w, payload.h, colors_map)); media = "application/pdf"; fn = f"badges_{event_id}.pdf"
    else:
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for r in regs:
                nm = re.sub(r"[^A-Za-z0-9_]", "", (r.get("name") or r["id"]).replace(" ", "_")) or r["id"]
                z.writestr(f"{nm}_{r['id'][-4:]}.pdf", _badges_pdf_bytes([r], ev, payload.w, payload.h, colors_map))
        buf.seek(0); out = buf; media = "application/zip"; fn = f"badges_{event_id}.zip"
    await db.event_registrations.update_many({"id": {"$in": ids}}, {"$set": {"badge_status": "printed", "badge_printed_at": now_iso()}, "$inc": {"badge_print_count": 1}})
    await log_audit(user, "badges_generated", "event", event_id, {"count": len(regs), "combined": payload.combined})
    return StreamingResponse(out, media_type=media, headers={"Content-Disposition": f"attachment; filename={fn}"})


class ManualBadgeIn(BaseModel):
    first_name: str
    last_name: Optional[str] = ""
    business_name: Optional[str] = None
    business_website: Optional[str] = None
    badge_category: Optional[str] = "Guest"
    confirmation_number: Optional[str] = None
    w: float = 4
    h: float = 6


@api_router.post("/events/{event_id}/badges/manual-pdf")
async def manual_badge_pdf(event_id: str, payload: ManualBadgeIn, user=Depends(get_current_user)):
    ev = await _event_authz(event_id, user)
    reg = {"name": f"{payload.first_name} {payload.last_name or ''}".strip(), "business_name": payload.business_name,
           "business_website": normalize_website(payload.business_website), "badge_category": payload.badge_category, "checkin_token": None}
    pdf = _badges_pdf_bytes([reg], ev, payload.w, payload.h, _badge_colors(ev))
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=badge.pdf"})


@api_router.get("/registrations/lookup")
async def lookup_registration(token: str, user=Depends(get_current_user)):
    reg = await db.event_registrations.find_one({"checkin_token": token}, {"_id": 0})
    if not reg: raise HTTPException(404, "Registration not found")
    ev = await db.events.find_one({"id": reg["event_id"]}, {"_id": 0})
    if not _can_checkin(ev, user):
        raise HTTPException(403, "Forbidden")
    return {"registration": reg, "already_checked_in": bool(reg.get("checked_in")), "checked_in_at": reg.get("checked_in_at"), "checked_in_by": reg.get("checked_in_by")}



class EventReportIn(BaseModel):
    actual_attendance: Optional[int] = None
    outcomes: str
    highlights: Optional[str] = None
    photo_file_ids: List[str] = []
    photo_captions: Dict[str, str] = {}
    file_ids: List[str] = []

@api_router.post("/events/{event_id}/report")
async def submit_event_report(event_id: str, payload: EventReportIn, user=Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev:
        raise HTTPException(404, "Event not found")
    if ev.get("status") not in ("Approved", "Scheduled", "Completed"):
        raise HTTPException(400, "Reports can only be submitted for approved events")
    if user["role"] not in STAFF_ROLES and ev.get("submitted_by_id") != user["user_id"]:
        raise HTTPException(403, "You can only report on your own events")
    report = {"id": new_id("erep"), **payload.model_dump(), "submitted_by": user["name"],
              "submitted_by_id": user["user_id"], "created_at": now_iso()}
    await db.events.update_one({"id": event_id}, {"$push": {"reports": report}, "$set": {"status": "Completed"}})
    await _add_gallery_photos(ev, report, user["role"], user["name"], user["user_id"])
    await log_audit(user, "event_report_submitted", "event", event_id)
    asyncio.create_task(notify_admins(f"Post-event report: {ev['name']}", "Post-Event Report",
                                      ep(f"{user['name']} submitted a post-event report for <strong>{ev['name']}</strong>.")))
    return report

@api_router.get("/events/{event_id}/reports")
async def get_event_reports(event_id: str, user=Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev:
        raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES and ev.get("submitted_by_id") != user["user_id"] and not ev.get("public"):
        raise HTTPException(403, "Forbidden")
    reports = ev.get("reports", [])
    for r in reports:
        r["photos"] = await _files_meta(r.get("photo_file_ids"))
        caps = r.get("photo_captions") or {}
        for ph in r["photos"]:
            ph["caption"] = caps.get(ph["id"])
        r["files"] = await _files_meta(r.get("file_ids"))
    return reports

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

# ---------------- service hours ----------------
HOUR_MILESTONES = [20, 50, 100]


async def _my_member_or_400(user):
    m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(400, "No member profile is linked to your account")
    return m


async def _event_name(event_id):
    if not event_id:
        return None
    e = await db.events.find_one({"id": event_id}, {"_id": 0, "name": 1})
    return (e or {}).get("name")


async def _hours_summary_for(member_id):
    approved = 0.0
    pending = 0.0
    active = None
    async for e in db.service_hours.find({"member_id": member_id}, {"_id": 0}):
        if e["status"] == "approved":
            approved += e.get("hours", 0) or 0
        elif e["status"] == "pending":
            pending += e.get("hours", 0) or 0
        elif e["status"] == "active":
            active = e
    m = await db.members.find_one({"id": member_id}, {"_id": 0, "hour_milestones": 1})
    return {"approved": round(approved, 2), "pending": round(pending, 2), "active": active,
            "earned_milestones": (m or {}).get("hour_milestones", [])}


async def _check_hour_milestones(member_id, user):
    total = 0.0
    async for e in db.service_hours.find({"member_id": member_id, "status": "approved"}, {"_id": 0, "hours": 1}):
        total += e.get("hours", 0) or 0
    m = await db.members.find_one({"id": member_id}, {"_id": 0})
    if not m:
        return []
    earned_before = set(m.get("hour_milestones") or [])
    should = {ms for ms in HOUR_MILESTONES if total >= ms}
    if should != earned_before:
        await db.members.update_one({"id": member_id}, {"$set": {"hour_milestones": sorted(should)}})
    for ms in sorted(should - earned_before):
        await add_timeline("member", member_id, f"Reached {ms} approved service hours", user)
        if m.get("user_id"):
            await notify_user(m["user_id"], f"Milestone reached: {ms} hours!",
                              f"You've completed {ms} approved service hours — download your certificate.",
                              "/portal/service-hours", "success")
    return sorted(should)


class ClockInIn(BaseModel):
    event_id: Optional[str] = None
    activity_type: str = "event"
    category: Optional[str] = None
    description: Optional[str] = None


class ManualHoursIn(BaseModel):
    date: str
    hours: float
    activity_type: str = "remote"
    category: Optional[str] = None
    description: Optional[str] = None
    event_id: Optional[str] = None


@api_router.post("/service-hours/clock-in")
async def clock_in(payload: ClockInIn, user=Depends(get_current_user)):
    m = await _my_member_or_400(user)
    if await db.service_hours.find_one({"member_id": m["id"], "status": "active"}, {"_id": 0}):
        raise HTTPException(400, "You are already clocked in. Clock out first.")
    doc = {"id": new_id("hrs"), "member_id": m["id"], "member_name": m.get("name"), "user_id": user["user_id"], "role": m.get("role"),
           "event_id": payload.event_id, "event_name": await _event_name(payload.event_id),
           "activity_type": payload.activity_type, "category": payload.category, "description": payload.description,
           "date": now_iso()[:10], "clock_in": now_iso(), "clock_out": None, "hours": 0.0,
           "source": "clock", "status": "active", "submitted_by_id": user["user_id"], "submitted_by_name": user["name"],
           "reviewed_by": None, "reviewed_at": None, "review_note": None, "created_at": now_iso(), "updated_at": now_iso()}
    await db.service_hours.insert_one(dict(doc))
    return clean(doc)


@api_router.post("/service-hours/clock-out")
async def clock_out(user=Depends(get_current_user)):
    m = await _my_member_or_400(user)
    active = await db.service_hours.find_one({"member_id": m["id"], "status": "active"}, {"_id": 0})
    if not active:
        raise HTTPException(400, "You are not clocked in")
    ci = datetime.fromisoformat(active["clock_in"])
    if ci.tzinfo is None:
        ci = ci.replace(tzinfo=timezone.utc)
    hrs = round((datetime.now(timezone.utc) - ci).total_seconds() / 3600.0, 2)
    await db.service_hours.update_one({"id": active["id"]}, {"$set": {"clock_out": now_iso(), "hours": hrs, "status": "pending", "updated_at": now_iso()}})
    if m.get("id"):
        await add_timeline("member", m["id"], f"Clocked out — {hrs}h submitted for review", user)
    return await db.service_hours.find_one({"id": active["id"]}, {"_id": 0})


@api_router.post("/service-hours")
async def submit_manual_hours(payload: ManualHoursIn, user=Depends(get_current_user)):
    m = await _my_member_or_400(user)
    if payload.hours <= 0 or payload.hours > 24:
        raise HTTPException(400, "Hours must be between 0 and 24")
    doc = {"id": new_id("hrs"), "member_id": m["id"], "member_name": m.get("name"), "user_id": user["user_id"], "role": m.get("role"),
           "event_id": payload.event_id, "event_name": await _event_name(payload.event_id),
           "activity_type": payload.activity_type, "category": payload.category, "description": payload.description,
           "date": payload.date, "clock_in": None, "clock_out": None, "hours": round(payload.hours, 2),
           "source": "manual", "status": "pending", "submitted_by_id": user["user_id"], "submitted_by_name": user["name"],
           "reviewed_by": None, "reviewed_at": None, "review_note": None, "created_at": now_iso(), "updated_at": now_iso()}
    await db.service_hours.insert_one(dict(doc))
    if m.get("id"):
        await add_timeline("member", m["id"], f"Submitted {doc['hours']}h for review", user)
    return clean(doc)


@api_router.get("/service-hours/me")
async def my_service_hours(user=Depends(get_current_user)):
    m = await db.members.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not m:
        return {"entries": [], "summary": {"approved": 0, "pending": 0, "active": None, "earned_milestones": []},
                "milestones_available": HOUR_MILESTONES, "member_id": None, "member_name": user["name"]}
    entries = await db.service_hours.find({"member_id": m["id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return {"entries": entries, "summary": await _hours_summary_for(m["id"]),
            "milestones_available": HOUR_MILESTONES, "member_id": m["id"], "member_name": m.get("name")}


@api_router.get("/service-hours/summary")
async def hours_summary(user=Depends(require_roles(*STAFF_ROLES)), month: Optional[str] = None):
    match = {"status": {"$in": ["approved", "pending"]}}
    if month:
        match["date"] = {"$regex": f"^{month}"}
    pipeline = [{"$match": match},
                {"$group": {"_id": {"member_id": "$member_id", "member_name": "$member_name", "role": "$role"},
                            "approved": {"$sum": {"$cond": [{"$eq": ["$status", "approved"]}, "$hours", 0]}},
                            "pending": {"$sum": {"$cond": [{"$eq": ["$status", "pending"]}, "$hours", 0]}},
                            "entries": {"$sum": 1}}},
                {"$sort": {"approved": -1}}]
    rows = []
    async for r in db.service_hours.aggregate(pipeline):
        rows.append({"member_id": r["_id"]["member_id"], "member_name": r["_id"]["member_name"], "role": r["_id"]["role"],
                     "approved": round(r["approved"], 2), "pending": round(r["pending"], 2), "entries": r["entries"]})
    return {"rows": rows}


@api_router.get("/service-hours/export.csv")
async def export_hours_csv(user=Depends(require_roles(*STAFF_ROLES)), status: Optional[str] = None, member_id: Optional[str] = None, month: Optional[str] = None):
    q = {}
    if status:
        q["status"] = status
    if member_id:
        q["member_id"] = member_id
    if month:
        q["date"] = {"$regex": f"^{month}"}
    entries = await db.service_hours.find(q, {"_id": 0}).sort("date", -1).to_list(5000)
    import csv as _csv
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["Date", "Volunteer", "Role", "Activity", "Category", "Event", "Hours", "Status", "Description", "Reviewed By"])
    for e in entries:
        w.writerow([e.get("date"), e.get("member_name"), e.get("role"), e.get("activity_type"), e.get("category"),
                    e.get("event_name"), e.get("hours"), e.get("status"), e.get("description"), e.get("reviewed_by")])
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=service_hours.csv"})


@api_router.get("/service-hours")
async def list_service_hours(user=Depends(require_roles(*STAFF_ROLES)), status: Optional[str] = None, member_id: Optional[str] = None,
                             event_id: Optional[str] = None, activity_type: Optional[str] = None, month: Optional[str] = None,
                             date_from: Optional[str] = None, date_to: Optional[str] = None):
    q = {}
    if status:
        q["status"] = status
    if member_id:
        q["member_id"] = member_id
    if event_id:
        q["event_id"] = event_id
    if activity_type:
        q["activity_type"] = activity_type
    if month:
        q["date"] = {"$regex": f"^{month}"}
    elif date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        q["date"] = rng
    entries = await db.service_hours.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
    qc = {k: v for k, v in q.items() if k != "status"}
    counts = {s: await db.service_hours.count_documents({**qc, "status": s}) for s in ("pending", "approved", "rejected", "active")}
    return {"entries": entries, "counts": counts,
            "totals": {"approved": round(sum(e.get("hours", 0) or 0 for e in entries if e["status"] == "approved"), 2),
                       "pending": round(sum(e.get("hours", 0) or 0 for e in entries if e["status"] == "pending"), 2)}}


class HoursStatusIn(BaseModel):
    status: str
    note: Optional[str] = None


@api_router.put("/service-hours/{hid}/status")
async def set_hours_status(hid: str, payload: HoursStatusIn, user=Depends(require_roles(*STAFF_ROLES))):
    if payload.status not in ("pending", "approved", "rejected"):
        raise HTTPException(400, "Invalid status")
    e = await db.service_hours.find_one({"id": hid}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Not found")
    await db.service_hours.update_one({"id": hid}, {"$set": {"status": payload.status, "review_note": payload.note,
                                                             "reviewed_by": user["name"], "reviewed_at": now_iso(), "updated_at": now_iso()}})
    await log_audit(user, f"service_hours_{payload.status}", "service_hours", hid, {"member_id": e.get("member_id")})
    if e.get("member_id"):
        if payload.status == "approved":
            await add_timeline("member", e["member_id"], f"{e.get('hours')}h approved", user)
        await _check_hour_milestones(e["member_id"], user)
    return await db.service_hours.find_one({"id": hid}, {"_id": 0})


class HoursEditIn(BaseModel):
    hours: Optional[float] = None
    description: Optional[str] = None
    activity_type: Optional[str] = None
    category: Optional[str] = None
    date: Optional[str] = None
    event_id: Optional[str] = None


@api_router.put("/service-hours/{hid}")
async def edit_hours(hid: str, payload: HoursEditIn, user=Depends(require_roles(*STAFF_ROLES))):
    e = await db.service_hours.find_one({"id": hid}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Not found")
    upd = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if "event_id" in upd:
        upd["event_name"] = await _event_name(upd["event_id"])
    upd["updated_at"] = now_iso()
    await db.service_hours.update_one({"id": hid}, {"$set": upd})
    await log_audit(user, "service_hours_edited", "service_hours", hid, {"fields": list(upd.keys())})
    if e.get("member_id"):
        await _check_hour_milestones(e["member_id"], user)
    return await db.service_hours.find_one({"id": hid}, {"_id": 0})


@api_router.delete("/service-hours/{hid}")
async def delete_hours(hid: str, user=Depends(get_current_user)):
    e = await db.service_hours.find_one({"id": hid}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES and e.get("user_id") != user["user_id"]:
        raise HTTPException(403, "Forbidden")
    if user["role"] not in STAFF_ROLES and e["status"] == "approved":
        raise HTTPException(400, "Approved hours cannot be deleted")
    await db.service_hours.delete_one({"id": hid})
    await log_audit(user, "service_hours_deleted", "service_hours", hid)
    if e.get("member_id"):
        await _check_hour_milestones(e["member_id"], user)
    return {"ok": True}


def _certificate_pdf_bytes(name, milestone, total_hours, role):
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors as rc
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib.units import inch
    buf = io.BytesIO()
    W, H = landscape(letter)
    c = pdfcanvas.Canvas(buf, pagesize=(W, H))
    c.setStrokeColor(rc.HexColor("#D6189B")); c.setLineWidth(6); c.rect(0.4 * inch, 0.4 * inch, W - 0.8 * inch, H - 0.8 * inch)
    c.setStrokeColor(rc.HexColor("#2E3192")); c.setLineWidth(2); c.rect(0.55 * inch, 0.55 * inch, W - 1.1 * inch, H - 1.1 * inch)
    cx = W / 2
    c.setFillColor(rc.HexColor("#2E3192")); c.setFont("Helvetica-Bold", 30); c.drawCentredString(cx, H - 1.6 * inch, "Certificate of Service")
    c.setFillColor(rc.HexColor("#64748b")); c.setFont("Helvetica", 13); c.drawCentredString(cx, H - 2.0 * inch, "AAWTA Community Engagement Committee")
    c.setFillColor(rc.HexColor("#334155")); c.setFont("Helvetica", 14); c.drawCentredString(cx, H - 2.7 * inch, "This certifies that")
    c.setFillColor(rc.HexColor("#0f172a")); c.setFont("Helvetica-Bold", 26); c.drawCentredString(cx, H - 3.35 * inch, name or "")
    c.setFillColor(rc.HexColor("#334155")); c.setFont("Helvetica", 14)
    c.drawCentredString(cx, H - 3.95 * inch, f"has completed {milestone}+ hours of dedicated {role or 'volunteer'} service")
    c.setFont("Helvetica", 12); c.drawCentredString(cx, H - 4.3 * inch, f"Total approved service hours: {total_hours}")
    c.setFillColor(rc.HexColor("#D6189B")); c.setFont("Helvetica-Bold", 48); c.drawCentredString(cx, H - 5.45 * inch, str(milestone))
    c.setFillColor(rc.HexColor("#64748b")); c.setFont("Helvetica", 11); c.drawCentredString(cx, H - 5.8 * inch, "HOURS OF SERVICE")
    c.setFillColor(rc.HexColor("#94a3b8")); c.setFont("Helvetica", 10)
    c.drawCentredString(cx, 0.95 * inch, f"Awarded {datetime.now(timezone.utc).strftime('%B %d, %Y')} · African American Women Trucking Association")
    c.showPage(); c.save(); buf.seek(0)
    return buf.getvalue()


@api_router.get("/members/{member_id}/certificate/{milestone}.pdf")
async def hours_certificate(member_id: str, milestone: int, user=Depends(get_current_user)):
    m = await db.members.find_one({"id": member_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Not found")
    if user["role"] not in STAFF_ROLES and m.get("user_id") != user["user_id"]:
        raise HTTPException(403, "Forbidden")
    if milestone not in HOUR_MILESTONES:
        raise HTTPException(400, "Invalid milestone")
    total = 0.0
    async for e in db.service_hours.find({"member_id": member_id, "status": "approved"}, {"_id": 0, "hours": 1}):
        total += e.get("hours", 0) or 0
    if total < milestone:
        raise HTTPException(400, f"Member has not reached {milestone} approved hours")
    pdf = _certificate_pdf_bytes(m.get("name"), milestone, round(total, 2), (m.get("role") or "volunteer").title())
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename=certificate_{milestone}h.pdf'})


@api_router.get("/checkin-assignable")
async def checkin_assignable(user=Depends(require_roles(*STAFF_ROLES))):
    users = await db.users.find({"account_status": {"$nin": ["suspended", "deactivated"]}},
                                {"_id": 0, "user_id": 1, "name": 1, "email": 1, "role": 1}).sort("name", 1).to_list(2000)
    return [{"user_id": u.get("user_id"), "name": u.get("name"), "email": u.get("email"), "role": u.get("role")}
            for u in users if u.get("user_id")]


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
    if format == "pdf":
        pdf = await asyncio.to_thread(_build_report_pdf, report_type, rows)
        await log_audit(user, "report_exported", "report", report_type, {"format": "pdf"})
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                                 headers={"Content-Disposition": f'attachment; filename="{report_type}.pdf"'})
    return {"rows": rows, "count": len(rows)}

def _build_report_pdf(report_type: str, rows: list) -> bytes:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), topMargin=54, bottomMargin=40, leftMargin=36, rightMargin=36)
    styles = getSampleStyleSheet()
    title = Paragraph(f"<b>AAWTA CEC Connect</b> — {report_type.replace('_', ' ').title()} Report", styles["Title"])
    sub = Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · {len(rows)} record(s)", styles["Normal"])
    elems = [title, sub, Spacer(1, 14)]
    if rows:
        headers = [h.replace("_", " ").title() for h in rows[0].keys()]
        data = [headers] + [[str(v if v is not None else "—")[:40] for v in r.values()] for r in rows]
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E3192")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAF5FB")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5E7EB")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elems.append(t)
    else:
        elems.append(Paragraph("No records found.", styles["Normal"]))
    doc.build(elems)
    return buf.getvalue()

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
    await _backfill_gallery()
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
