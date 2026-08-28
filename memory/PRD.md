# CEC Connect — AAWTA Community Engagement Portal (PRD)

## Original Problem Statement
Full-stack public website + private role-based member portal for the African American Women Trucking Association's Community Engagement Committee (CEC). Public marketing site, three application/inquiry forms, Google-only login gated by an allowlist, 5 roles, admin command center, member profiles + onboarding, document e-signatures, communications, announcements, events/calendar, monthly goals, resource center, automated notifications, reports, and audit log. Tagline: "Connecting Ambassadors. Engaging Communities. Driving Impact."

## Architecture
- **Backend**: FastAPI (`/app/backend/server.py`, all routes `/api`), MongoDB (motor). Helpers: `storage.py` (Emergent object storage), `emailer.py` (Emergent-managed Resend with safety guardrails).
- **Frontend**: React + Tailwind + shadcn/ui. Public pages `src/pages/public/*`, portal `src/pages/portal/*`. Auth context `src/auth.jsx`, layouts `PublicLayout`/`PortalLayout`.
- **Auth**: Emergent-managed Google OAuth. Session token in httpOnly cookie + Bearer. Allowlist collection `authorized_emails` gates access. `aawtassn@gmail.com` seeded as Super Administrator.
- **Branding**: AAWTA logo colors — magenta `#D6189B` + navy `#2E3192`. Fonts: Outfit (headings) + Manrope (body).

## User Personas / Roles
- **Super Administrator** (aawtassn@gmail.com): full access, role/permission management, integrations, audit, exports.
- **Director**: review applications, decisions, manual members, invites, onboarding, documents, announcements, goals, reports.
- **Administrator**: manage applications/members, documents, announcements, resources, communications, goals, events.
- **State Ambassador**: profile, onboarding, sign docs, goals, activity reports, events/announcement requests, resources, messages.
- **Volunteer**: profile, onboarding, sign docs, volunteer hours, availability, event reports, resources, messages.

## Implemented (2026-06)
- Public site: Home (live stats/spotlights/announcements/events), About, Ambassador Program, Volunteer, Programs, Directory, Resources, FAQ, Contact, Apply. Responsive, on-brand.
- 3 forms: Ambassador + Volunteer applications, General Inquiry. Ref numbers (atomic counter), duplicate detection, honeypot + rate limiting, confirmation + admin emails (Resend), file uploads (resume/headshot/supporting).
- Google login + allowlist gating with exact unauthorized message; sessions; suspend/restore/deactivate.
- Admin dashboard command center (12 stat cards, charts, recent apps, upcoming events).
- Applications: list/search/filter, detail (answers/files/notes/timeline), status (13 statuses), assignment, notes w/ visibility, decision history, convert-to-member.
- Members: manual add + invite, cards, detail (profile/onboarding/goals/timeline), public-directory toggle, suspend/restore.
- Member portal: dashboard, profile edit + headshot upload, onboarding checklist (13 steps, %).
- Documents + e-signatures (typed legal name, consent, audit; re-sign blocked). Categories.
- Messages (role/state/member targeting), notifications bell.
- Announcements (targeting, ack tracking, public) + announcement requests.
- Events (submission → approve/decline) + calendar link. Goals (assign/propose, progress, status, categories) + monthly activity reports/hours.
- Resource Center (quick links + custom resources w/ access control). Editable portal Settings (address/phone/email/website/calendar/slack/membership).
- User management (authorize emails, role changes), Audit log, Reports (6 types, JSON preview + CSV export).
- Security: backend-enforced roles, authenticated file downloads + separate public-image endpoint, goal IDOR fixed, frontend role-guarded routes.

## Verified
- 96/96 backend regression tests pass. E2E (public forms, admin + member portal flows) validated. Security fixes re-verified (download auth 401/200, public-file 404, goal IDOR 403, atomic refs).

## Implemented (2026-06, round 2)
- **Automated reminders**: platform cron (`.emergent/crons.yml` → `POST /api/cron/reminders`, bearer-secured, idempotent, backgrounded) sending onboarding, document-signature, goal-deadline, and 14/30/45/60-day inactivity nudges (portal notifications + emails; never auto-deactivates). Dedupe via `reminder_sent`.
- **Signed PDF copies**: `GET /api/signatures/{id}/pdf` generates a watermarked certificate PDF (legal name, email, timestamp, IP, version, signature id); owner or staff only. "Signed PDF" download button in Documents.
- **Calendar sync**: `GET /api/events/{id}/ics` (.ics download) + Add-to-Google-Calendar template links on approved/scheduled events; direct AAWTA calendar link retained.
- **Directory search**: public directory filter by name, state, and focus area with live count (frontend) + `?state=&focus=&q=` query support (backend).
- Verified: 21 new backend tests pass + Playwright UI flows; zero defects.

## Backlog (P1/P2)
- P1: Google Calendar 2-way sync; document reminder scheduler; inactivity reminders (14/30/45/60 day) via scheduled task; PDF export for reports; announcement read-receipt analytics UI.
- P2: reply threads/attachments in messages UI; per-focus-area/region message segmentation UI; post-event reports; signed-PDF generation & download of signed copy; CAPTCHA option; database backup automation.

## Next Tasks
- Wire scheduled reminders (crons) for deadlines & inactivity.
- Add PDF export + richer report filters.
- Signed-document PDF artifact generation.
