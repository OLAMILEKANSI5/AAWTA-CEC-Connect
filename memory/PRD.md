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

## Implemented (2026-06, round 8)
- **Public events past-event hygiene**: `GET /api/public/events` now excludes events with `date < today` (homepage already filtered). Detail/register links for recently-past events still resolve.
- **UTC off-by-one fix**: `PublicEvents.jsx` (calendar `byDay` + `upcoming`) and `portal/Events.jsx` card date now parse `date + "T00:00"` (local) — no more previous-day display for negative-UTC users. EventCard/PublicEventDetail were already fixed.
- **Search debounce**: `/events` public search debounced 300ms (no per-keystroke request storm).
- **Badge Center (P0, Msg 282)**: new `components/BadgeCenter.jsx` used in `EventManage.jsx` badges tab. Live scaled preview, preset sizes (4×6, 3×4, 2.5×3.5, 4×3) + custom W×H inches, manual badge entry (name + role), select/print-all/print-selected/per-attendee print, on-brand badge (navy header bar, magenta footer, AAWTA CEC, attendee name, role pill, event name + date + city). Client-side print-window rendering with @page sizing.
- Verified: backend curl (past-event exclusion, registered_count, registrations counts) + UI smoke of Badge Center preview & controls.

## Next Tasks
- P1: Decide direct Google Calendar API 2-way sync vs current `.ics` downloads (user originally wanted official AAWTA calendar sync).
- P2: Refactor 1600+ line `server.py` into routers (events, auth, applications).
- Backlog: richer report filters; announcement read-receipt analytics UI.
- (Optional) Add QR code to badges for scan-based check-in.

## Implemented (2026-06, Phase A — Registration & Confirmation Emails)
Part of a 7-phase event-management overhaul (A→G). Decisions: paid events use admin-managed `payment_status` (paid/pending/complimentary/refunded/not_applicable) + external ticket URL (no in-app Stripe); Emergent-managed Resend for mail; QR uses random non-PII confirmation number + checkin_token.
- Registration form (`PublicEventDetail.jsx`): required first/last/email/phone/State-or-Territory dropdown/AAWTA-member Y-N/ticket category; optional business name+website(auto-https)/job/city/zip/dietary/accessibility; two separate NON-preselected opt-ins (newsletter, events). Consents in `consents` (type, granted_at, source, event_id, opted_out_at).
- Confirmation emails: subject `Registration Confirmed: [Event Name]`; free → immediate; paid → pending notice then final on paid/complimentary (idempotent); waitlist → waitlist notice. Includes name/event/date/start-end time+tz/venue or virtual link/category/confirmation #/QR image/Add-to-Calendar/check-in instructions/AAWTA contact/manage+cancel link.
- Delivery tracking (`email_log`): sent/failed on send with provider id; `/api/webhooks/resend` maps delivered/opened/bounced/failed/unsubscribed (secret-gated). NOTE: Resend account is Emergent-managed, so live delivery/open events don't auto-populate in preview — only Sent/Failed + webhook receiver verifiable.
- Admin (`EventManage.jsx`): per-attendee confirmation #, payment dropdown, confirmation status, resend. Endpoints: PUT `/registrations/{id}/payment`, POST `/registrations/{id}/resend-confirmation`, POST `/registrations/{id}/send-confirmation`, GET `/registrations/{id}/emails`.
- Public manage `/r/{conf}?t={token}` (`ManageRegistration.jsx`): details + QR + cancel (when allow_cancellation). QR `/api/public/qr/{token}.png` (404 for cancelled).
- New event fields: end_time, timezone, venue_name, venue_address, virtual_link, ticket_categories, allow_cancellation.
- Verified: iteration_8 = 22/22 backend pytest + 3 frontend flows; post-fix self-test (honeypot alias, cancelled-QR gate, payment no-op history, non-blocking payment send) pass.

## Remaining Phases
- Phase B: registration management table (columns/search/filters/More Actions), manual + walk-in registration.
- Phase C: CSV/XLSX import (mapping + dedupe report), bulk export, bulk actions.
- Phase D: mobile Check-In Center (QR scan, live totals) + complete Badge Center (categories/colors, sizes, print-ready PDF/ZIP, manual badges, event badge/contact config).
- Phase E: document editing, descriptions in listing, visibility/audience (default Private Draft), send/assign, archive/eligible-delete, actions.
- Phase F: automatic onboarding assignment by approved profile + approval/welcome notifications.
- Phase G: role permissions incl. event-scoped Check-In Volunteer assignment (auto-expire) + expanded Audit History; final security review.

## Implemented (2026-06, Phase B — Registration Management, Manual & Walk-In)
- Registration management table (`RegistrationTable.jsx`, in `EventManage.jsx` Registrations tab): 18 columns (Select, Name, Member, State, Business, Website, Email, Phone, Category, Source, Confirmation #, Payment, Confirmation, Check-in, Check-in time, Badge, Print, Actions), search + filter bar (state/member/category/source/payment/confirmation/checkin/badge + Show Archived), inline payment dropdown, per-row Print Badge, and a More Actions menu (View, Edit, Send/Resend Confirmation, Check In/Undo, Change Category, Cancel, Archive, View Activity History).
- Manual registration: POST `/events/{id}/manual-registration` (source "Manual Entry", full fields, complimentary→payment, opt-ins→consent only when true, created/updated audit, no auto-email); post-save panel offers Send Confirmation / Check In / Print Badge / Add Another.
- Walk-in: POST `/events/{id}/registrations` (source "Walk-In", checked-in, badge category, requires first_name + email-or-phone server-side); enhanced Check-In tab form.
- Edit `PUT /registrations/{id}` (partial + field clearing via exclude_unset, name recompute, website normalize, field-level audit); staff cancel `/registrations/{id}/cancel`; archive `/registrations/{id}/archive`; badge-printed `/registrations/{id}/badge-printed`; activity history `/registrations/{id}/history`.
- Enhanced list filters with re.escape (safe regex), archived excluded by default. Check-in now audited + undo clears stale metadata; round-7 undo→prev_status regression still passes.
- BadgeCenter now exports `printBadges(regs,event,{w,h})` (reused by row Print).
- Verified: iteration_9 (48/50 backend, all frontend flows) + post-fix self-test (walk-in 400, manual invalid-payment 400, `+`-search, field clearing). Fixed: regex escape, walk-in contact validation, manual payment validation, editable clearing, Manage-dialog horizontal-overflow clipping, payment labels, `<span>`-in-`<option>`, Show Archived toggle.
- Deferred to Phase C: bulk-action bar for the existing row checkboxes.

## Implemented (2026-06, Phase C — Import / Export / Bulk Actions)
- CSV/XLSX import: GET import-template.csv; POST import/parse (auto column mapping), import/preview (validation report: total/valid/duplicates/missing_required/invalid_emails/invalid_phones/skipped; dup by email/phone/confirmation#/name+business), import/commit (strategy skip|update|new, source "Bulk Import", derived fields). Frontend ImportDialog wizard (upload→map→preview→result).
- Export: GET /events/{id}/export?format=csv|xlsx|pdf&segment=&fields=&ids=&state=&category=. 11 segments, field selection, print-ready PDF attendee list. STAFF-only gating strips email/phone for non-staff owners. Frontend ExportDialog.
- Bulk actions: POST /events/{id}/bulk {action, ids, value} — send/resend confirmation, change_category, assign_badge_category, mark_complimentary, update_payment, checkin, cancel, archive (+client-side print badges / export selected). 400 on unknown action/invalid value/segment. Per-registration audit written (shows in Activity History). Frontend bulk bar + BulkConfirmDialog (shows action/count/event/email note, destructive styling).
- Fixed pre-existing: PUT /registrations/{id}/payment now returns accurate confirmation_sent (awaits send + re-reads). Fixed HIGH Manage-dialog horizontal overflow (min-w-0 on RegistrationTable root + Tabs/TabsContent) so toolbar/columns stay inside the dialog.
- Verified: iteration_10 (49/49 Phase C backend, all frontend flows) + post-fix self-test (400s, payment flag accurate, bulk per-reg audit, modal buttons inside dialog).
- Deferred/minor (non-blocking): invalid-phone rows are warned but still importable; streaming for very large exports.

## Implemented (2026-06, Phase D — Mobile Check-In Center + Complete Badge Center)
- Check-In Center: mobile page /portal/events/:id/checkin (CheckInCenter.jsx) — live attendance totals + progress bar (auto-refresh), camera QR scan (html5-qrcode dynamic import), manual token entry, search (name/email/phone/business/confirmation), tap-to-check-in with duplicate-check-in guard (already-checked-in warning w/ time+staff + confirm re-checkin), walk-in registration, per-attendee badge print. New GET /api/events/{id} + GET /api/registrations/lookup?token=.
- Badge Center (server-side print-ready): POST /events/{id}/badges/pdf (combined PDF or ZIP of individual PDFs, only_unprinted/checked_in_only, sizes 4x6/4x3/3.5x2/2.25x3.5/custom, marks badge_status printed + badge_print_count, generate-before-mutate), POST /events/{id}/badges/manual-pdf (non-registered), PUT /events/{id}/badge-config (address/website/contact email+phone/show_phone/category_colors). Badge PDF: navy header, name, color-coded category pill, business+website when present, QR from checkin_token, event name/date, AAWTA contact footer. 12 badge categories with default colors + per-event overrides.
- Frontend Badge Center: 4 required sizes + custom, live preview, Download PDF / Download ZIP, Badge & contact settings panel (address/website/email/phone/show_phone + 12 category color pickers, saved via badge-config), manual entry + server manual-PDF button; client HTML print aligned to badge_category + colors.
- Fixed HIGH: checked_in counter now excludes archived/cancelled (Check-In totals never exceed 100%). Made already-checked-in rows tappable to reach the guard dialog. badges_pdf generates before mutating print state.
- Verified: iteration_11 (30/30 backend pytest, ~90% frontend) + post-fix self-test (counter 2/2, config+colors save, manual-pdf, combined pdf).
- Minor/deferred: split server.py into routers (2640+ lines); GET /events/{id} readable by any authed user for approved/public events (intentional).

## Implemented (2026-06, Phases E-G)
### Phase E — Documents overhaul
- DocumentIn expanded: audience (default private_draft), status, display_order, auto_onboarding, onboarding_profiles, required. 8 audiences (private_draft/ambassadors_only/volunteers_only/interns_only/ambassadors_volunteers/specific_members/all_active/admins_only) enforced via _doc_visible_to on GET /documents and GET /documents/{id} (direct-link access blocked for unauthorized).
- New: PUT /documents/{id} (edit, preserves signatures), POST /documents/{id}/assign (members/roles/audience + notify), PUT /documents/{id}/archive, DELETE /documents/{id} (only unassigned private drafts w/ no signatures, else 400 -> archive), GET /documents/{id}/assignments (audience/roles/members+signed/history).
- Frontend Documents.jsx: descriptions shown (2-line clamp + Read more), audience selector, auto-onboarding + profiles, edit/assign-to-all/archive/delete via More menu.
### Phase F — Auto-onboarding + welcome notifications
- convert_to_member now calls _assign_onboarding_docs (assigns docs where auto_onboarding + role in onboarding_profiles, dedup, notify + audit) and _send_welcome (role-specific welcome email via Resend + in-app notification; account-activation link, no passwords).
### Phase G — Check-in volunteer perms + audit
- Event.checkin_assignees + PUT /events/{id}/checkin-assignees (staff/owner). _can_checkin(ev,user) allows staff, owner, or assigned volunteer while event NOT Completed/Archived (auto-expiry). Applied to list_registrations(search), add_walkin, checkin_registration, lookup_registration. Volunteers remain blocked from edit/export/payment/cancel/delete/settings.
- Audit: all E-G actions logged (document_created/updated/assigned/archived/deleted, onboarding_doc_assigned, welcome via email_log, checkin_assignees_set, bulk_*, badges_generated, etc.). Existing /audit-logs + AuditLog page display them.
- Verified via curl: E (visibility, assign, delete-guard 400, archive), F (onboarding doc auto-assigned + welcome email sent), G (assigned volunteer lookup/checkin 200; non-assigned + post-unassign + edit = 403). Documents UI smoke-tested.
### Deferred (backend-ready, UI minimal/pending)
- Check-in volunteer ASSIGNMENT UI (endpoint exists; no dedicated picker yet — assign via API).
- Notification template editor / preview / test-send (welcome uses a fixed on-brand template).
- server.py (2600+ lines) still needs router refactor.
