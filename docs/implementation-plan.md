# JobPilot — Implementation Plan (UI + Authentication)

## Baseline (before any change)

- Branch `main`, clean working tree.
- `uv run python -m pytest backend/tests -v`
  - Without `TEST_DATABASE_URL`: 157 passed, 26 errors (integration tests refuse to run without the variable — expected).
  - With `TEST_DATABASE_URL=postgresql+asyncpg://jobpilot:jobpilot@localhost:5432/jobpilot_test`: **183 passed**.
- Local Postgres (pgvector/pg17) and Redis running via `infrastructure/docker-compose.yml`. Dev DB at Alembic head `bb426ad300cd` with 1 candidate, 151 jobs, 3 applications, 9 documents.
- No frontend exists. No CORS middleware. No authentication.

## Conflict in the brief and how it is resolved

The brief says both "do not build authentication" (sections C, 11) and, in a dedicated section, "implement secure authentication… so it can eventually be deployed publicly". The dedicated section is the more specific instruction, so it wins:

- Each user account owns **at most one candidate profile** (`candidates.user_id`, unique). The frontend never chooses or stores a candidate UUID; it asks `GET /api/candidates/me`.
- Existing candidate-scoped routes keep their URLs (no breaking change), but every one verifies `candidate.user_id == current_user.id` and returns 404 otherwise (no existence oracle).

## What exists and maps directly to UI

| UI need | Existing endpoint |
|---|---|
| Profile read/update/create | `GET/PATCH /api/candidates/{id}`, `POST /api/candidates` |
| Skills CRUD | `/api/candidates/{id}/skills` (GET, POST, PATCH, DELETE) |
| Resume upload (PDF/DOCX ≤5 MB, extracts skills, re-matches) | `POST /api/candidates/{id}/resume/upload` |
| Job list, search, filters, ranking, pagination | `GET /api/jobs` |
| Discover (Jobicy / FreeHire) | `POST /api/jobs/discover`, `POST /api/jobs/discover/freehire` |
| Recalculate matches | `POST /api/jobs/match/{candidate_id}` |
| Top matches with confidence/coverage | `GET /api/jobs/matches/{candidate_id}` |
| AI analysis (cached by fingerprint) | `POST /api/jobs/{job_id}/analyze/{candidate_id}` |
| Applications list / summary / update / delete | `/api/applications/...` |
| Documents list / get / approve | `/api/applications/{id}/documents...` |
| Cover letter / tailored resume generation | `POST /api/applications/generate-cover-letter`, `/tailor-resume` |

## Minimal backend gaps (each justified)

1. **`GET /api/jobs/{job_id}`** — no single-job endpoint; a job detail route cannot load on refresh.
2. **`GET /api/jobs/{job_id}/analysis/{candidate_id}`** — the only analysis endpoint is a POST that may call the AI provider. Opening a job page must show the stored analysis without regenerating it.
3. **`GET /api/applications/{application_id}`** — application detail route needs to load on refresh.
4. **`job_id` filter on application list** — job page needs to know whether an application (and documents) already exists for the job.
5. **`score_coverage` in `GET /api/jobs` items** — the Matches page uses `/api/jobs` for filters/pagination; coverage is needed to present the score honestly.
6. **`GET /api/candidates/me`** — resolve the current user's profile.

## Authentication design

- `users` table (email, argon2id password hash, full name, active flag) + `user_sessions` (SHA-256 of a random session token, CSRF token hash, expiry, revocation) + `password_reset_tokens` (hashed, single use, 1 h).
- Session token in an **HttpOnly** cookie, `SameSite=Lax`, `Secure` outside local. Nothing in `localStorage`.
- CSRF: per-session token returned in JSON by `/api/auth/login` and `/api/auth/me`, held in memory by the SPA, sent as `X-CSRF-Token` on unsafe methods. Plus an `Origin` allow-list check on unsafe methods.
- Login brute-force protection: per-IP and per-email failure window (in-process; documented as single-instance limitation).
- Password reset via the existing SMTP email service; generic responses to avoid account enumeration; all sessions revoked on reset.
- `REGISTRATION_ENABLED` flag so a public deployment can be closed after the owner registers.
- CORS restricted to configured origins with credentials; security headers middleware; generic 500 responses; SQL echo split from `DEBUG` so hashes are not logged.
- Migration is additive (new tables, nullable `candidates.user_id`). Existing candidates stay unowned until claimed with `uv run python -m backend.app.commands.claim_candidate --candidate-email … --user-email …` (no auto-claim by email, which would be an account-takeover vector without email verification).

## Frontend

`frontend/` — Vite + React + TypeScript + Tailwind + shadcn/ui, React Router, TanStack Query, React Hook Form + Zod, Lucide. One typed API client (`src/lib/api.ts`), base URL from `VITE_API_BASE_URL`, `credentials: "include"`.

Screens: Login / Register / Forgot+Reset password, Dashboard, Discover Jobs, Matches, Job detail (+analysis, document generation), Applications list + detail (status, follow-up, notes, documents review/approval), Profile (profile form, resume upload, skills), Settings (account, backend health, sign out).

## Tests

- Backend: existing 183 tests kept; fixtures extended with an authenticated user where routes now require it. New tests for registration, login, logout, invalid credentials, session expiry, CSRF, brute-force lockout, password reset, cross-user isolation on every private endpoint.
- Frontend: Vitest + Testing Library for API client, form validation, list states, document approval, mutation failures.
- `tsc`, `vite build`, lint.
