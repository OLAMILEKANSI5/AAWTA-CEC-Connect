# CEC Connect — Apple Beta Readiness Review
_Target: iOS beta via TestFlight, Oct 1, 2026. Assessed 2026-06._

**Verdict:** No core re-architecture required. Backend is a clean, reusable REST API (`/api/*`) fully decoupled from the web UI, and auth already accepts a bearer token — a solid foundation for a native shell (WebView/Capacitor) or a future native client. The gaps below are additive.

## Status matrix (Ready / Needs Work / Not Yet)

| # | Apple / mobile requirement | Status | Notes |
|---|---|---|---|
| 1 | All screens mobile responsive & touch-friendly | **Ready** | Tailwind responsive utilities throughout; dense admin tables use horizontal scroll. Minor touch-target polish recommended. |
| 2 | Navigation works on iPhone-sized screens | **Ready** | Portal has a hamburger drawer; public site has a mobile menu. |
| 3 | Forms/dashboards/onboarding/messaging/events/hours work on mobile | **Ready** | All flows use responsive dialogs/tables; verified on 390px. |
| 4 | Auth/session appropriate for mobile-app use | **Needs Work** | Web uses Emergent Google OAuth redirect + cookie/bearer session (30-day). Bearer-token support already exists server-side. Native app should use `ASWebAuthenticationSession` and store the token in Keychain. |
| 5 | Backend exposed via reusable APIs (not web-only) | **Ready** | All functionality is `/api/*` REST JSON; the web UI is just one client. |
| 6 | Image/file uploads from mobile | **Ready** | Multipart `/api/upload`; `accept="image/*"` enables camera/photo-library capture on iOS. |
| 7 | Deep linking into app screens | **Needs Work** | Web routes exist for every screen (e.g. `/portal/events/:id`). For native Universal Links, add an `apple-app-site-association` file + associated-domains entitlement once the App ID exists. Onboarding/invite links already point at stable paths. |
| 8 | Apple push notifications (approvals, reminders, messages, assignments) | **Not Yet** | In-app + email notifications exist via a central `notify_user()` — architecture-ready. Need: device-token registration endpoint, APNs provider credentials, and to fan out `notify_user` to APNs. |
| 9 | User-managed notification preferences | **Needs Work** | Event/newsletter opt-ins captured today; no granular per-channel (push/email/in-app) preference center yet. |
| 10 | Camera/photo permissions requested only when required | **Ready** | QR check-in scanner requests the camera only when the scanner is opened; uploads only when the user picks a file. |
| 11 | Privacy disclosures & App Store data handling | **Needs Work** | Terms & Conditions and Privacy Policy now linked in the footer + on application/registration/login. Still need the App Store "App Privacy" label mapping (data collected: name, email, phone, address, photos; usage: app functionality). |
| 12 | Secure sign-in / logout / account management | **Ready** | Logout revokes the session; role-based access enforced server-side. |
| 13 | Accessibility & readable mobile layouts | **Needs Work** | Good contrast and brand type; recommend a pass for ≥44px touch targets and Dynamic Type sizing before public release. |

## Role-based mobile experience — Ready
Navigation is already role-scoped (each nav item declares `roles`); users see only their tools:
- **Ambassador:** onboarding, goals, events, resources, communications, service hours, activity.
- **Volunteer:** onboarding, event assignments, check-in/out, service hours, events, communications.
- **Intern (future):** reuses the service-hours + onboarding + communications stack already built.
- **Admin/Leadership:** applicant management, approvals, messaging, events, assignments, hours, reporting, onboarding oversight (Onboarding Board).

## Recommended before beta (priority order)
1. **P0 Native auth**: token-based sign-in via `ASWebAuthenticationSession`; persist bearer token in Keychain (backend already accepts `Authorization: Bearer`).
2. **P0 App Privacy label + permission strings** (`NSCameraUsageDescription`, `NSPhotoLibraryUsageDescription`).
3. **P1 Push notifications**: `POST /api/devices` to register APNs tokens + fan-out from `notify_user()`.
4. **P1 Universal Links**: host `apple-app-site-association`; keep deep-link routes stable.
5. **P2 Notification preference center** (push/email/in-app per category).
6. **P2 Accessibility pass** (touch targets, Dynamic Type, VoiceOver labels — `data-testid`s already aid automation).

## Shipped in this pass (code)
- iOS web-app meta in `index.html`: `viewport-fit=cover` (safe areas), `apple-mobile-web-app-capable`, status-bar style, app title, `format-detection=telephone=no`.
- Footer legal links (Terms & Privacy) across all public pages + acknowledgment on application, event registration, and login — supports App Store privacy requirements.
