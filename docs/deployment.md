# Deployment checklist

JobPilot has authentication, ownership checks, CSRF protection and secure-cookie support, but **it has not yet been deployed or verified in a production environment**. Work through this list in the target environment before exposing it publicly.

## Topology

Serve the SPA and API from the **same site** so the `SameSite=Lax` session cookie is sent:

- Recommended: one origin behind a reverse proxy, e.g. `https://jobpilot.example.com` serving `frontend/dist` and proxying `/api` and `/health` to uvicorn. Build with `VITE_API_BASE_URL=https://jobpilot.example.com`.
- Also works: `app.example.com` + `api.example.com` (same registrable domain). Different registrable domains will **not** work with the current cookie settings.

Keep PostgreSQL and Redis on a private network. Never publish ports 5432/6379.

## Environment (production values)

| Variable | Value |
|---|---|
| `APP_ENV` | `production`: enables Secure cookies, HSTS, SMTP certificate validation, hides `/docs` and `/openapi.json` |
| `DEBUG` | `false` |
| `SQL_ECHO` | `false` |
| `DATABASE_URL` | Strong, unique credentials, not `jobpilot:jobpilot` |
| `CORS_ALLOWED_ORIGINS` | Exactly the public frontend origin(s), `https://…`, no trailing slash |
| `FRONTEND_URL` | Public frontend URL (used in reset emails) |
| `REGISTRATION_ENABLED` | `false` after creating your account |
| `SESSION_TTL_HOURS` | Shorten if you prefer (default 7 days) |
| `SMTP_*` | Real provider; leave `SMTP_VALIDATE_CERTS` unset (validates in production) |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | From a secret store, never committed |

Change the Docker Compose credentials for anything beyond local use.

## Checklist

- [ ] HTTPS terminates in front of the app; HTTP redirects to HTTPS.
- [ ] uvicorn runs behind the proxy with `--proxy-headers --forwarded-allow-ips=<proxy IP>` so login throttling sees real client IPs (otherwise all users share the proxy's IP bucket).
- [ ] `uv run alembic upgrade head` run as part of each deploy, before starting the new version.
- [ ] Pre-authentication candidates linked with `claim_candidate`, or intentionally left unowned.
- [ ] `REGISTRATION_ENABLED=false` once accounts exist (unless you intend open sign-up).
- [ ] `curl -I https://…/api/auth/me` shows `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Cache-Control: no-store`.
- [ ] Signing in from the public URL sets a cookie with `Secure; HttpOnly; SameSite=Lax`.
- [ ] A request with a foreign `Origin` header to a POST endpoint returns 403.
- [ ] `/docs` and `/openapi.json` return 404.
- [ ] Password-reset email arrives and the link opens the deployed frontend.
- [ ] Automated PostgreSQL backups (e.g. nightly `pg_dump -Fc`) with a tested restore. The database holds resumes and personal data.
- [ ] Logs shipped somewhere private. Application logs include request paths and recipient email addresses for sent mail, but not passwords, tokens or document content. Keep `SQL_ECHO=false`.
- [ ] Scheduled jobs (`discover_and_match_jobs`, `send_job_digest`) configured and observed once.
- [ ] Rate limiting at the proxy for `/api/auth/*` and the AI endpoints (`/analyze`, `/tailor-resume`, `/generate-cover-letter`), which spend provider quota.

## Known gaps to decide on before opening to other people

- Login throttling is per-process and in memory. With several workers or instances, move it to Redis (already in the stack) or enforce it at the proxy.
- No email verification and no MFA.
- Any signed-in user can trigger job discovery, which writes to the shared job table and uses external APIs.
- The SMTP client validated certificates only when `APP_ENV` is not local; verify your provider works with validation on.
- Unhandled-error responses (500) are generated before CORS headers are added, so the browser reports them as network errors. The server log has the detail.
