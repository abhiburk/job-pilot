# Implementation status (2026-10-20)

## Implemented

- **Authentication:** registration, login, logout, server-side sessions (HttpOnly cookie, SHA-256 token digests), CSRF header token plus Origin allow-list, Argon2id hashing, login throttling (429 + Retry-After), password change, password reset via SMTP, account update, `REGISTRATION_ENABLED` switch.
- **Authorization:** one candidate profile per user; ownership enforced on every candidate, skill, resume, matching, analysis, application, and document endpoint (foreign IDs → 404). Jobs remain shared.
- **Deployment hardening:** CORS restricted to configured origins with credentials, security headers (CSP, nosniff, frame deny, referrer, no-store on API, HSTS when Secure), generic 500 responses with server-side logging, `/docs` hidden outside local, SQL echo decoupled from `DEBUG`, SMTP certificate validation outside local.
- **Frontend (new, `frontend/`):** login/register/forgot/reset; dashboard; discover (Jobicy, FreeHire); matches; job detail with score breakdown, stored/on-demand AI analysis, document generation; applications list and detail (status, dates, notes, delete); document review with versions, warnings, change summary, copy/download, explicit approval with verification checklist; profile (form, resume upload, skills CRUD); settings (account, password, service status, sign out).

## Existing functionality reused, unchanged

Matching rules and scoring, AI prompts, resume tailoring and cover-letter services, document versioning and approval semantics, job ingestion, digests, resume parsing. No endpoint URL or response field was removed.

## Backend changes

| File | Change | Why |
|---|---|---|
| `models/entities.py`, migration `1bdf6da5551c` | `users`, `user_sessions`, `password_reset_tokens`; nullable unique `candidates.user_id` | Authentication and ownership (additive) |
| `api/deps.py`, `services/auth.py`, `schemas/auth.py`, `api/routes/auth.py` | New | Sessions, CSRF, hashing, throttling, auth endpoints |
| `api/routes/*.py` | Router-level auth; ownership checks | IDOR protection |
| `api/routes/candidates.py` | `GET /api/candidates/me`; one profile per account | Frontend resolves the profile server-side |
| `api/routes/jobs.py` | `GET /api/jobs/{id}`, `GET /api/jobs/{id}/analysis/{candidate_id}`; `score_coverage` and `is_active` in list items (shared serializer) | Job detail page reload; show stored analysis without calling the AI; honest score display |
| `api/routes/applications.py` | `GET /api/applications/{id}`; `job_id` filter on list | Application detail reload; job page finds its application |
| `services/job_matching.py` | Job-embedding failures fall back to rule-based scoring | **Bug found in E2E run:** Gemini quota 429 made `POST /match` return 500, contrary to the matcher's documented fallback |
| `core/config.py`, `core/database.py`, `services/email_service.py`, `main.py` | Auth/CORS settings, `SQL_ECHO`, `SMTP_VALIDATE_CERTS`, middleware | Deployment readiness |
| `commands/claim_candidate.py` | New | Link pre-auth candidates to accounts |

Existing tests were adapted only in their *arrangement* (an authenticated user, candidates owned by it, a fake DB row that mirrors the new `score_coverage` column). No assertion was removed or weakened.

## Tests actually run

| Suite | Command | Result |
|---|---|---|
| Backend baseline (before changes) | `TEST_DATABASE_URL=…/jobpilot_test uv run python -m pytest backend/tests` | 183 passed |
| Backend final | same | **238 passed** (183 existing + 18 authentication + 36 authorization, including 31 per-route unauthenticated checks, + 1 matcher fallback) |
| Backend without `TEST_DATABASE_URL` | `uv run python -m pytest backend/tests` | 159 passed, 79 errors: all DB-backed tests refusing to run without the variable (by design; baseline had the same behavior with 26) |
| Frontend unit/component | `npm test` | **35 passed** |
| Type check | `npm run typecheck` | clean |
| Lint | `npm run lint` | 0 errors; warnings only (fast-refresh hints for helper exports, React Compiler notes on `react-hook-form` `watch`) |
| Production build | `npm run build` | succeeds; single 805 kB JS chunk (244 kB gzip) |
| Migration | upgrade → downgrade → upgrade on an empty DB; upgrade on a restored copy of the dev DB | succeeded |

## Manual / end-to-end verification

The Chrome browser extension was not connected in this session, so **the UI was not clicked through in a real browser.** Instead, the full workflow was exercised over HTTP the way the SPA does it (cookie session, Origin header, CSRF header) against `jobpilot_e2e`, a restored copy of the dev database:

register → profile 404 before claim → `claim_candidate` → POST without CSRF rejected (403) → recalculate matches (151 jobs; worked after the embedding fallback fix) → ranked list → job detail → stored analysis read → **real Groq tailored resume** (v1, unapproved, 3 warnings) → persisted as draft → explicit approval → status `applied` + follow-up → fresh session sees status, follow-up, approval → logout → `/me` 401.

The frontend dev server was started and served the app (HTTP 200); its components are covered by the jsdom tests above.

## Dev database

- Backed up before migrating (`pg_dump -Fc` in the session scratchpad).
- Migrated to `1bdf6da5551c`. No rows changed. The existing candidate is **unowned** until you register and run `claim_candidate`.
- No test accounts were created in the dev database; the E2E run used the scratch copy, which was dropped afterwards.

## Known issues

- Not verified in a real browser (see above); responsive layout and keyboard flow are untested beyond the component tests.
- The existing candidate's `full_name` in the dev DB is the literal string `"string"` (an OpenAPI placeholder), which will appear on generated documents. Fix it on the Profile page.
- Gemini embedding quota was exhausted during testing; matching ran rules-only.
- 500 responses lack CORS headers (Starlette ordering), so the browser reports them as network errors.
- Login throttling is in-process only.
- Bundle not code-split.

## Remaining blockers

None for local use. Public deployment requires the [deployment checklist](deployment.md).

## Update: generic job discovery (2026-10-20)

- Providers are adapters behind one `JobSource` interface and registry (`backend/app/services/job_sources/`). Jobicy and FreeHire were wrapped without changing their normalization. **Remotive** was added as the third source.
- New `GET /api/jobs/sources` and `POST /api/jobs/discovery` (one query → all or selected sources, per-source outcome), and a `source` filter on `GET /api/jobs`. The old per-source endpoints still work and are marked deprecated in OpenAPI. They do **not** enforce request limits, and the UI no longer uses them.
- Provider request limits from their published terms are enforced via `agent_runs`: Jobicy 1 per hour, Remotive 1 per 6 hours. Previously the UI could call Jobicy more often than its terms allow.
- `discover_and_match_jobs` now uses the generic runner and accepts `--keywords/--country/--work-mode/--limit`. **Behavior change:** FreeHire is no longer queried with the hardcoded "Laravel PHP Python" unless `--keywords` is passed. That phrase returns 0 results on Jobicy, so it can't be shared across sources.
- The results limit is applied uniformly in the runner (Remotive ignores `limit` when searching).
- UI: the Discover page has one form (role/skill prefilled from the profile's first preferred title, country, work mode, results per source, source checkboxes from the registry) and a per-source results list. The source filter appears on Discover and Matches. Source names come from the registry. Settings shows every source with its filters, limits and last run.
- Tests: backend **252 passed** (12 discovery tests plus auth sweeps for the new routes); frontend **38 passed**; type check, lint (0 errors) and build clean. The Remotive adapter was checked live with one real request (12 listings fetched and normalized). The UI was not clicked through in a real browser.
