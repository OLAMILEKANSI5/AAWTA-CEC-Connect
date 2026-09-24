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

## Phases E-G — Verified (iteration_13: 32/32 E-F-G, 150/151 A-D)
- All 6 iteration_12 fixes verified: sign_document visibility enforcement (403), non-destructive partial PUT (exclude_unset), audience validation (400), archive 404 on missing, delete guard incl assigned_roles, convert gated on Approved status.
- Added email retry/backoff (3 attempts) in log_and_send to survive transient provider "no message id" responses.
- Remaining (optional/low, non-blocking): DocumentEditIn for true PATCH (title/category still required on PUT); a11y aria-describedby on Documents dialogs; 'Assign to all active' data-testid; move audience validation into a Pydantic validator; split 2839-line server.py into routers; remove dead 'intern' role branch or add the role.
- Known infra flake: Emergent email provider intermittently returns no message id (rate limit) — now mitigated with retry; not a product bug.

## Implemented (2026-06, Group 1 — Communication Core)
Part of a large Ambassador/Volunteer lifecycle overhaul (build order: Messaging → Templates → Approval Automation → Onboarding Dashboard → Service Hours → Event fixes → Check-In Assignment → iOS readiness → E2E). User approved seeding 9 templates with on-brand placeholder copy (official AAWTA wording to be pasted later via editor).
### Notification Template Editor
- New collection `notification_templates` (key, name, category, subject, body plain-text w/ {{placeholders}}, mode automatic|manual, trigger, enabled, include_button, button_label, is_system). Lazy-seeded 9 defaults via `ensure_templates()`: application_received, application_approved, onboarding_profile, missing_requirements, onboarding_reminder, fully_onboarded_welcome, volunteer_event_assignment, ambassador_update, general_communication.
- Endpoints: GET /api/notification-templates ({templates, placeholders}); GET/PUT /api/notification-templates/{key} (PUT leadership-only, invalid mode 400, sets updated_by); POST .../preview (rendered subject+html w/ sample ctx); POST .../test-send {to} (uses log_and_send, returns status).
- Helpers: `_subst` ({{var}} regex), `_body_to_html` (paragraphs + optional portal button), `_comm_ctx` (builds real recipient context from application/member or generic sample), `send_template_email` (trigger-driven send + comm log — WIRED IN GROUP 2).
- Frontend `/portal/templates` (TemplateEditor.jsx, STAFF nav 'Message Templates'): cards grouped by category w/ Auto/Manual + enabled badges, Preview dialog (rendered HTML), Edit dialog (subject/body, placeholder chips, enabled + automatic toggles, portal button + label), Test-send field. Editing gated to super_admin/director (admin can view/test).
### Applicant & Member Messaging + Communication History
- New collection `communications` (subject_type application|member, subject_id, channel email|portal|both, template_key/name, subject, body, to_email, sent_by, status, email_log_id, provider_id, created_at).
- Endpoints: POST /api/comms/preview (fills template w/ real recipient data); POST /api/comms/send (email/portal/both, records comm, timeline + audit, validations: invalid channel/subject_type 400, empty subject/body 400, email w/o address 400); GET /api/comms?subject_type=&subject_id= (history newest-first, delivery status refreshed from email_log).
- Frontend `CommsPanel.jsx` reused in ApplicationDetail + MemberDetail 'Communications' tab: Send Message dialog (pick template auto-fills subject/body, edit, choose channel, optional portal button), history list w/ status/sender/template/date.
- Verified: iteration_14 — 21/21 backend pytest + full UI flows pass. Reusable suite at /app/backend/tests/test_group1_comms_templates.py. Fixed non-blocking a11y (added DialogDescription to Send Message / template Preview + Edit dialogs).

## Implemented (2026-06, Group 2 — Approval → Onboarding Automation + Live Onboarding Dashboard)
### Approve & Onboard + automation
- POST /api/applications/{id}/approve-onboard (leadership): sets status Approved (+decision_history), fires 'application_approved' template (recorded on application comms w/ acting admin), converts to member via shared `_do_convert` (approved_at, onboarding_stage=profile_incomplete, fully_onboarded_notified=False), assigns auto-onboarding docs, fires 'onboarding_profile' invite (recorded on member comms). 400 on repeat / inquiry type. NEVER marks fully onboarded on approval.
- Trigger wiring (all via Group 1 templates + recorded in communications): submit → application_received (auto); PUT /applications/{id}/status=Approved → application_approved (auto); all onboarding steps done in PUT /members/{id}/onboarding → fully_onboarded_welcome (one-time, atomic find_one_and_update guard, sets stage=fully_onboarded). _send_welcome now uses onboarding_profile template (force=True).
### Live Onboarding Dashboard
- GET /api/onboarding/pipeline?role=&stage= → {entries, counts, stage_order, stage_labels}. Stages: applied/under_review/approved (applications) → profile_incomplete/docs_needed/thirty_day/fully_onboarded (members). Each entry: name, role, stage, outstanding[], approved_at, days_in_stage, progress_pct, stalled (per-stage STALL_DAYS threshold), link. `_member_onboarding_state` derives stage from profile steps + unsigned assigned/auto docs + checklist completion. Stage persisted lazily on read.
- Frontend /portal/onboarding-board (OnboardingDashboard.jsx, STAFF nav 'Onboarding Board'): 7 funnel count cards (click to filter), role + stage filters, table w/ stage badge, outstanding list, approved date, days-in-stage (stalled rows highlighted + warning icon), 30-day progress bar, open-profile, and a Send-reminder dialog (reuses /comms/preview + /comms/send). ApplicationDetail has 'Approve & Onboard' button.
- Verified: iteration_15 — 12/12 backend pytest + full UI. Fixed fully_onboarded race via atomic find_one_and_update. Reusable suite /app/backend/tests/test_group2_onboarding.py.
- Known infra: Emergent email provider 429-throttles under bursty sends; log_and_send retries 3x (~4.5s) and still records status (failed if all fail) — not a product bug.

## Implemented (2026-06, Event & Post-Event fixes — pre-Group-3)
### Fix: published event images
- Root cause: `_is_public_file` didn't authorize an event's `image_file_id`, so `/public/files/{id}` 404'd → hero images vanished once published. Fixed to serve images for events that are `published` (or legacy `public`) and not archived. Verified: image 404 before publish, 200 after Publish alone.
### Edit Event
- PUT /api/events/{id} (staff or owner; 403 otherwise, 404 missing): updates the existing record in place (exclude_unset), normalizes virtual_link, syncs gallery_photos event_name on rename. Frontend: 'Edit' button (edit-event-{id}) on staff event cards (both active & awaiting) reuses the create dialog PREFILLED; Save = PUT (no duplicate). Title 'Edit Event' / button 'Save Changes'.
### Post-Event Report → Gallery approval workflow
- New `gallery_photos` collection connects report photos to the public gallery (no double upload). On report submit, `_add_gallery_photos` creates a record per photo: staff submitter → approved; ambassador/member → pending. `_backfill_gallery` (startup) migrates existing report photos (approved if event.public else pending).
- Endpoints: GET /api/public/gallery (approved only, w/ event_name+caption+state+date), GET /api/gallery/photos?status=&event_id= (staff, +counts), PUT /api/gallery/photos/{id}/status {pending|approved|rejected} (staff; invalid→400). `_is_public_file` serves approved gallery photos; reject → removed from public + 404.
- Frontend: staff-only 'Photo Gallery' subtab on /portal/events → GalleryReview.jsx (pending/approved/rejected tabs w/ counts, thumbnails, Approve/Reject/Reset). Public Gallery unchanged (reads /public/gallery).
- Verified: iteration_16 — 14/14 backend pytest + full UI (desktop + iPhone 390px). Suite /app/backend/tests/test_group3_events_gallery.py. Fixed post-review: public-image predicate aligned to `published`; Edit dialog a11y (DialogDescription).

## Implemented (2026-06, Group 3 — Volunteer Service Hours + Check-In Assignment + Milestone Certificates)
### Service hours / time tracking (`service_hours` collection; intern-reusable)
- Member: POST /api/service-hours/clock-in (one 'active' at a time; 2nd→400), /clock-out (computes hours→'pending'), POST /api/service-hours (manual, 0<h≤24), GET /service-hours/me (entries+summary{approved,pending,active,earned_milestones}), DELETE own pending/active (approved→400, non-owner→403). Requires a linked member profile.
- Admin: GET /service-hours?status=&member_id=&event_id=&activity_type=&month=&date_from/to (+counts+totals), GET /service-hours/summary (per-volunteer totals), GET /service-hours/export.csv, PUT /service-hours/{id}/status (approve/reject/pending), PUT /service-hours/{id} (edit). Only APPROVED hours count.
- Milestones 20/50/100: `_check_hour_milestones` is a full RECONCILE (adds on cross, revokes on demote/delete) → member.hour_milestones; notifies member on new milestone. Called from status change, edit, and delete.
- Certificates: GET /api/members/{id}/certificate/{20|50|100}.pdf (reportlab landscape cert; 400 if below/invalid, 403 non-owner non-staff).
### Check-In Volunteer Assignment
- GET /api/checkin-assignable (staff; excludes suspended/deactivated). PUT /events/{id}/checkin-assignees now notifies ONLY newly-added users + writes a timeline entry on their member profile (no re-notify on resave).
### Frontend
- /portal/service-hours (ServiceHours.jsx, nav 'Service Hours', all roles): role-adaptive — members get clock in/out + manual submit + summary + recognition certificate downloads + history; staff get review tabs (pending/approved/rejected/active) w/ counts, month filter, CSV export, per-volunteer totals, approve/reject/edit.
- EventManage 'Volunteers' tab: searchable assignee checkboxes + Save. MemberDetail 'Service Hours' tab (MemberHoursTab.jsx): totals, certificate buttons, approve/reject.
- Verified: iteration_17 — 21/21 new backend pytest + 47/48 regression + full UI (member & admin). Suite /app/backend/tests/test_group3_hours_certs_assign.py. Post-review fix: milestone reconcile on demote/delete (verified reject→revoke, re-approve→restore); assignable filters inactive users.

## Implemented (2026-06, Legal Links + Programs enhancement)
- Footer (PublicLayout): persistent **Terms & Conditions | Privacy Policy** links (aawta.org/terms-and-conditions, /privacy-policy) — responsive, on every public page. Acknowledgment "By submitting/continuing, you acknowledge AAWTA's Terms & Privacy" (clickable) added to Apply form, event registration dialog, and Login.
- Programs & Community Impact page rebuilt (kept existing content): prominent **Driven Together Education Program** gradient hero with 2 CTAs (Explore Education Programs → dt-platform.emergent.host/programs, Take the FREE SMART Assessment → /intake) + SMART note; 9-card ecosystem grid (Education/Career, Workforce, Trucking, Community Outreach, Ambassador Leadership, Volunteer Service, Events, Youth/Workforce, Entrepreneurship); CTA band (Become an Ambassador, Volunteer, Explore Education, SMART Assessment, View Events) routing to correct pages/external links. Verified rendering on mobile.

## Implemented (2026-06, Group 5 — Mobile / iOS Beta Readiness — initial pass)
- index.html iOS web-app meta: viewport-fit=cover (safe areas), apple-mobile-web-app-capable + status-bar-style + title, mobile-web-app-capable, format-detection=telephone=no.
- Full Apple Beta Readiness matrix (Ready/Needs Work/Not Yet) at **/app/memory/APPLE_BETA_READINESS.md**. Verdict: no core re-architecture needed. P0 gaps for beta: native token auth (ASWebAuthenticationSession + Keychain; backend already accepts Bearer), App Privacy label + camera/photo permission strings. P1: APNs push (fan-out from central notify_user + device-registration endpoint), Universal Links (apple-app-site-association). P2: notification preference center, accessibility pass. Role-scoped mobile nav already in place.

## Implemented (2026-06, Phase 2 — Reminders & Account Lifecycle + Phase 3 — Image Performance)
### Phase 2 (items 4-8) — all cron-driven via existing POST /api/cron/reminders (daily-reminders in .emergent/crons.yml)
- **5-day inactivity nudge**: friendly member notification+email at 5+ days no login (once, tracked via reminder_sent). Kept existing 14/45/60-day nudges.
- **30-day inactivity SOFT security flag**: at 30+ days no login, member is flagged `inactive:true` + `inactive_since` (NEVER deleted, access NOT blocked — soft flag only per user choice). Leadership notified ("Member flagged inactive", category Members). Cleared automatically on Google re-auth (create_session clears member+user `inactive`, writes reactivation timeline) OR by leadership via PUT /api/members/{id}/reactivate (staff-only).
- **48h unanswered message follow-up**: for member→leadership (`to_leadership`) threads whose latest message is from a member and >48h old with no staff reply, all leadership get a portal notification ("Unanswered member message"). Auto-clears on staff reply; re-alerts on each new member message (keyed by last member msg id + leader id).
- **Application aging alerts (15/30 days)**: leadership notified once per milestone for applications in PENDING_APP_STATUSES (non-inquiry) awaiting a decision 15+/30+ days. Also surfaced on the leadership Dashboard as an amber "Applications Awaiting a Decision" card (GET /api/dashboard/stats → `aging_applications`), rows click through to the application.
- Frontend: Dashboard aging card (testid aging-applications / aging-app-<id>); MemberDetail amber inactive badge (testid inactive-badge) + Reactivate button (testid reactivate-btn).
### Phase 3 (item 10) — Event/gallery/profile image performance
- Server-side on-the-fly resize+compress via Pillow: GET /api/public/files/{id}?w=<n> and /api/files/{id}/download?w=<n> return a width-constrained, quality-82 JPEG/PNG/WEBP copy (no-op for non-images or when already smaller; w capped 2000). Cache-Control headers set (public 86400 / private 3600) — NOTE: preview ingress/Cloudflare rewrites these to `no-store`, so browser caching gain is infra-limited; the ~74× payload reduction (2.9MB→39KB at w=200) still delivers the perf win.
- Frontend now requests thumbnails with `loading="lazy"`: EventCard w=500, Gallery grid w=500 (lightbox full-res), Home spotlights w=400, Directory w=500, PublicEventDetail hero w=1200.
- Verified: iteration_19 — 8/8 backend pytest (test_phase2_phase3.py) + 5/5 verify_phase2.py + full UI. No defects.

## Implemented (2026-06, Goal Progress Notes + Activity History)
- Each goal now has `notes[]` (text, author name/role, status & progress at time of note, timestamp) and `history[]` timeline (Goal created / Progress changed / Status changed / Note added, with actor + timestamp). Notes never overwrite — full history preserved.
- NEW `POST /api/goals/{id}/notes` (body {note?, status?, progress?}) — add a note and optionally change status/progress in one submit; staff-or-owner only (403 otherwise). `PUT /api/goals/{id}` also records history now.
- New goal status **"Needs Support"**. On update to **Achieved / Deferred / Needs Support**, all Leadership get an in-app notification (category "Goals") + an email to directors (notify_admins). Non-significant statuses do not notify.
- Frontend: reusable `components/GoalCard.jsx` (quick slider/status kept + "Update / Add Note" dialog + expandable "Notes & History"). Used on Goals page and MemberDetail Goals tab (leadership can see the "why"). Mobile-friendly. Monthly Activity Report unchanged.
- Verified: iteration_20 — 12/12 backend pytest (test_goal_notes.py) + full UI, 100% pass, no defects.

## Next Tasks (remaining from the 10-part request)
- P1: **Notification Center UI** — consolidate leadership notifications with category filters (Messages, Applications, Onboarding, Documents, Members) + quick action links.
- P2: **Server refactor** — split 3800+ line server.py into routers (files/images, members, applications, reminders, dashboards); migrate deprecated @app.on_event startup/shutdown → lifespan.
- P2: External Google Calendar 2-way sync (currently .ics downloads + add-to-calendar links).

## Implemented (2026-06, Comms/Docs Phase 1 — items 1,2,3,9)
- notify_user gains `category`; `_leadership_user_ids()` = active users with role in STAFF_ROLES (super_admin/director/administrator).
- Signature completion → in-app notification to all leadership ("[Name] completed and signed [Doc].", category Signatures, links to /portal/members/{id}).
- GET /documents/{id}/signers (staff): {signed[name,role,signed_at,legal_name,signature_id], pending[name,role], file_id}. Documents page: clickable "N signed" → signers dialog with per-signer PDF + pending list + preview.
- Member-initiated messaging fixed: non-staff POST /messages auto-routes to leadership (to_leadership, member_id); frontend "Contact CEC Leadership" (no admin directory), attachments kept. Reply + first-message notifications categorized "Messages".
- Verified: iteration_18 — 14/14 new pytest + 56/57 regression + full UI (desktop+mobile). Suite test_cec_connect_phase1.py.
- GROUP 4: Resources Calendar button → /events; fix event image not showing on published events; Edit/Update published events (all fields).
- GROUP 5: Mobile/iOS readiness (responsive/touch pass, role-scoped mobile nav, deep-link + push-ready architecture, Apple Beta Readiness matrix).
- GROUP 6: E2E workflow testing; then P2 (Google Calendar sync, server.py router refactor, recognition/certificates, reporting enhancements).
