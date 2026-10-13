# Account authentication and saved inputs

Goal: Email/password signup and signin with a private, persistent set of all 55 inputs per account.

Architecture: FastAPI owns authentication, opaque cookie sessions, and database writes.
MySQL 8.4 runs in Docker with a named volume. Next.js forwards session cookies through
its same-origin API proxy. The browser holds edits locally; successful /predict
requests atomically replace the authenticated account's latest inputs.

Scope:
- Argon2 password hashes, normalized unique email, expiring and revocable sessions.
- Signup, signin, signout, and current-session endpoints.
- Restore saved inputs on sign-in and page refresh; new accounts use reference values.
- Validate and calculate before saving. Failed validation/inference never overwrites inputs.
- Keep user data isolated by authenticated account ID. No client-supplied account ID.
- Preserve the existing minimal exports and all assessment functionality.

Implementation:
1. Add database models and authentication API in cardio_nb/database.py and auth.py.
   Add isolated tests for password hashing, sessions, account isolation, and save timing.
2. Protect /predict and persist all validated inputs only after successful calculation.
   Update existing API tests to authenticate through the real signup flow.
3. Add AuthGate signup/signin forms, account controls, restored inputs, and save-status copy.
   Extend the Next.js proxy with cookie forwarding and same-origin mutation checks.
4. Configure Docker MySQL, private credentials, persistent volume, and startup health checks.
   Document local setup, session configuration, and persistence behavior.
5. Verify backend tests, browser signup/signin/save/restore/isolation, production build,
   and the actual MySQL-backed Docker application.

Review focus:
- Invalid assessment leaves the previous saved inputs intact.
- Editing or resetting without running an assessment performs no input writes.
- A second account cannot see the first account's values.
- Expired/signed-out sessions cannot predict; credentials and tokens are never returned.
- All 55 values including nulls and category types survive a signout/signin round trip.
