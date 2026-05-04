# Feature 01: Authentication, App Shell, and Overview

## Feature Goal and Expected User Outcome

Validate that a new user can start the product platform, sign in with the implemented local development auth flow, land on the governed app shell, select the seeded environment, inspect platform readiness, and sign out.

The expected outcome is a working authenticated session at `/overview`, visible global navigation, a selected `Development` environment, healthy or explainable dependency status, and a cleared session after logout.

## Implementation Surface

- Frontend routes: `/login`, `/overview`, `/settings` placeholder, and protected app shell routes in `frontend/src/app/router.tsx`.
- Global navigation: `frontend/src/components/layout/AppShell.tsx`, `SidebarNav.tsx`, `TopBar.tsx`, `EnvironmentSelector.tsx`, `SystemStatusIndicator.tsx`, `NotificationCenter.tsx`.
- Login UI: `frontend/src/components/auth/LoginScreen.tsx`.
- Auth API: `POST /api/v1/auth/dev-login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`.
- Tenant API: `GET /api/v1/organizations`, `GET /api/v1/environments`.
- System API: `GET /api/v1/system/config`, `GET /version`, `GET /api/v1/system/dependencies`, `/health`, and `/ready`.
- Tests: `tests/test_auth_*.py`, `tests/test_api_shell_*.py`, `frontend/src/components/auth/LoginScreen.test.tsx`, `frontend/src/features/overview/OverviewPage.test.tsx`.

## Prerequisites and Required Test Data

- API and frontend are running. See [README](README.md#local-startup).
- Use `admin@example.com`.
- Use role `Platform Admin`.
- Seeded organization is `org_default`.
- Seeded environment is `env_default` with display name `Development`.

## UI Validation Steps

1. Open `http://127.0.0.1:3000/`.
2. Expected URL change: the app redirects to `/login` if no session exists.
3. Confirm the login page displays:
   - Title `Ophanix Product Platform`
   - Description `Sign in to the local governance control plane.`
   - Field `Email` with default value `admin@example.com`
   - Field `Role` with default value `Platform Admin`
   - Button `Sign in`
4. Leave `Email` as `admin@example.com`.
5. Leave `Role` as `Platform Admin`.
6. Click `Sign in`.
7. Expected UI response: the button text changes to `Signing in` while the request is pending.
8. Expected URL change: `/login` changes to `/overview`.
9. Confirm the left navigation shows the product name `Ophanix` and the subtitle `Microsoft Agent Governance Toolkit`.
10. Confirm navigation groups and links are visible:
    - `Command`: `Overview`
    - `Governance`: `Agents`, `Policies`, `Trust`
    - `Security`: `MCP Security`
    - `Operations`: `Mesh`, `Runtime`, `Discovery`, `Observability`
    - `Ecosystem`: `Marketplace`, `Integrations`
    - `Automation`: `Workflows`, `Demo Lab`
    - `Administration`: `Settings`
11. Confirm the top bar displays:
    - Text `Agent Governance Control Plane`
    - `Environment` selector
    - System status badge such as `Healthy`, `Degraded`, or `Warning`
    - Notifications button
    - User display name `Demo Admin`
    - Role text `Platform Admin`
    - Sign-out icon button with accessible label `Sign out`
12. In the `Environment` selector, confirm `Development` is selected.
13. On the `/overview` page, confirm:
    - Page title `Overview`
    - Description `Governed estate summary, runtime health, and product platform readiness.`
    - Button `Refresh`
    - Metric `Session` with value `Demo Admin`
    - Metric `Healthy dependencies`
    - Metric `Build`
    - Table section `System dependencies`
    - Side panel `Foundation`
14. Click the system status badge in the top bar.
15. Expected UI response:
    - A popover titled `System status` opens.
    - If all dependencies are healthy, it says `All registered dependencies are healthy.`
    - If a dependency is missing or degraded, it says `One or more dependencies need attention.`
    - The popover lists dependency names and status badges.
16. Click the Notifications button.
17. Expected UI response: a popover titled `Notifications` opens and shows `No notifications`.
18. Click the `Settings` navigation link.
19. Expected URL change: `/overview` changes to `/settings`.
20. Expected UI response: because `Settings` is registered as a placeholder route, the page displays a feature placeholder rather than a full settings workspace. This is expected in the current implementation.
21. Click `Overview`.
22. Expected URL change: `/settings` changes back to `/overview`.
23. Click `Sign out`.
24. Expected URL change: `/overview` changes to `/login`.
25. Reload the browser.
26. Expected UI response: the login page remains visible because the session cookie was cleared.

## Expected Backend Effects

- `POST /api/v1/auth/dev-login` validates the allowlisted email and creates a signed session token.
- The API sets the `ophanix_session` HTTP-only cookie.
- `GET /api/v1/auth/me` returns the user principal with `email`, `display_name`, roles, organization ID, and permissions.
- `GET /api/v1/organizations` returns at least `org_default`.
- `GET /api/v1/environments` returns at least `env_default`.
- `POST /api/v1/auth/logout` deletes the session cookie.
- No Okta or external identity-provider redirect is executed in the implemented local UI.

## Programmatic Verification

```bash
API=http://127.0.0.1:8088
COOKIE=/tmp/ophanix.cookies

curl -i -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","roles":["Platform Admin"]}' \
  "$API/api/v1/auth/dev-login"

curl -s -b "$COOKIE" "$API/api/v1/auth/me" | jq '{email, display_name, roles, organization_id}'
curl -s -b "$COOKIE" "$API/api/v1/organizations" | jq
curl -s -b "$COOKIE" "$API/api/v1/environments" | jq
curl -s "$API/health" | jq
curl -s "$API/ready" | jq
curl -s -b "$COOKIE" "$API/api/v1/system/dependencies" | jq

curl -i -b "$COOKIE" -X POST "$API/api/v1/auth/logout"
```

Expected responses:

- Login returns HTTP 200 and a `Set-Cookie` header for `ophanix_session`.
- `/auth/me` includes `admin@example.com`, `Demo Admin`, and role `Platform Admin`.
- `/organizations` includes `org_default`.
- `/environments` includes `env_default`.
- Logout returns HTTP 200 with `{"status":"logged_out"}`.

Focused automated tests:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m unittest tests.test_auth_overall tests.test_api_shell_phase1 -v

cd frontend
npm test -- LoginScreen.test.tsx OverviewPage.test.tsx
```

## Edge Cases and Alternative Flows

- Invalid email format: enter `not-an-email` in `Email` and click `Sign in`. The form should show a validation error and should not navigate away from `/login`.
- Not allowlisted: set `OPHANIX_DEV_LOGIN_ALLOWED_EMAILS` to exclude the test email, restart the API, and try to sign in. Expected result is a visible error from the API and no session.
- Viewer access: sign in as `admin@example.com` with role `Viewer`. Some navigation links render disabled, and direct access to protected routes shows an access denied page.
- Missing environment: if no environments are available, the `Environment` selector shows `No environment` and feature APIs that require an environment may fail.
- Direct protected URL: open `/agents` without a session. Expected behavior is redirect to `/login`, then successful login sends the user to `/overview`, not automatically back to `/agents`.

## Integration Setup Required: Okta or External IdP

This feature currently validates local dev login only. External IdP variables exist, and deployment docs mention Okta-compatible OIDC settings, but a complete browser OIDC callback flow was not confirmed in the implemented frontend.

To prepare an external IdP pilot:

1. Create an OIDC application in Okta or the chosen IdP.
2. Set callback URL `https://app.example.com/auth/callback`.
3. Set logout URL `https://app.example.com/auth/logout`.
4. Export `OPHANIX_IDP_ISSUER_URL`.
5. Export `OPHANIX_IDP_AUDIENCE`.
6. Export a production `OPHANIX_SESSION_SECRET`.
7. Set `OPHANIX_DEV_LOGIN_ALLOWED_EMAILS=` to disable dev login.
8. Set `CORS_ALLOWED_ORIGINS=https://app.example.com`.
9. Restart the API and verify `/api/v1/system/dependencies`.

Needs verification before claiming success: the UI must expose an IdP sign-in action and complete a callback without relying on `/api/v1/auth/dev-login`.

## Troubleshooting

- Login shows a 403-style error: confirm the email is in `OPHANIX_DEV_LOGIN_ALLOWED_EMAILS`.
- Login succeeds in curl but not the browser: confirm frontend and API origins match `CORS_ALLOWED_ORIGINS`, and use `127.0.0.1` consistently if the app was started with that host.
- Overview is stuck loading: check `GET /api/v1/system/dependencies` and `GET /version`.
- Environment selector is empty: run the seed/start script again or verify `GET /api/v1/environments`.
- System status says `Warning`: inspect the dependency popover and `/api/v1/system/dependencies`; missing optional integrations may not block local feature validation.
