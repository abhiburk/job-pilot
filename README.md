# JobPilot

**A personal job-search assistant: discover jobs, see how well they match your experience, prepare tailored application documents, and track applications from one place.**

JobPilot is a FastAPI + PostgreSQL backend with a React frontend. It is built for one person's daily job search first, with accounts and per-user data isolation so it can later be deployed beyond localhost.

> **Status:** Local MVP with authentication. Backend: 238 tests passing. Frontend: 35 tests passing, type check and production build clean. Not yet verified in a production deployment. See [docs/deployment.md](docs/deployment.md) before exposing it publicly.

JobPilot prepares and tracks applications. **It never submits applications.** AI-generated documents stay drafts until you approve them, and approving one does not send anything anywhere.

---

## Daily workflow

1. **Dashboard:** see strong matches you haven't reviewed, follow-ups due, and suggested next steps.
2. **Discover Jobs:** run one search across every connected job source, then recalculate matches.
3. **Job Matches:** browse jobs ranked by the rules-based matcher, filtered by score, location, work mode, and search.
4. **Job page:** read the description, the score breakdown, and (on request) an AI fit analysis.
5. **Generate** a tailored resume and/or cover letter for the job. Review it, check the warnings, and **approve** it explicitly.
6. **Apply yourself** on the original site, then mark the application *Applied* and set a follow-up date.

## Features

| Area | What it does |
|---|---|
| Accounts | Register, sign in/out, change password, password reset by email, change sign-in email |
| Profile | Contact details, headline, summary, preferences, salary, links, original resume text |
| Resume upload | PDF/DOCX ≤ 5 MB → text extracted, skills detected, jobs re-matched (the file itself is not stored) |
| Skills | Add, edit proficiency/years/primary, remove |
| Discovery | One search (role/skill, country, work mode, results per source) across all connected sources: Jobicy, FreeHire, Remotive. Per-source outcome, provider request limits enforced |
| Matching | Rules-based score 0–100 with breakdown (role relevance, skills, experience, preferences, salary) and data coverage; optional Gemini semantic signal with automatic fallback |
| AI analysis | On-demand Groq assessment (fit score, recommendation, strengths, gaps, concerns), cached by input fingerprint |
| Documents | Tailored resume and cover letter drafts, versioned, with generation warnings and change summaries; explicit approval; copy / download as .txt |
| Applications | Status (saved → preparing → applied → interviewing → offer / rejected / withdrawn), applied date, follow-up date, notes, delete |
| Digests | Email digest of new strong matches (`send_job_digest` command; configured on the server) |

## Architecture

```text
frontend/ (React SPA, Vite)  ──HTTP + session cookie──▶  backend/ (FastAPI)
                                                          │
     Job sources (Jobicy, FreeHire, Remotive, …) ◀── discovery ┤
                     Groq (text)       ◀── analysis, tailoring, cover letters
                     Gemini (embeddings, optional) ◀── matching
                                                          ▼
                                                   PostgreSQL (+ Redis infra)
```

- All business logic (matching, prompts, document versioning, approval) lives in the backend. The frontend only calls the API.
- Every private record belongs to a user: `users → candidates (one per user) → applications → application_documents`, plus matches and analyses keyed by candidate. Jobs are shared between users.

## Tech stack

**Backend:** Python 3.14, FastAPI, SQLAlchemy (async) + asyncpg, Alembic, PostgreSQL (pgvector image), Redis, Pydantic Settings, argon2-cffi, Groq, Google GenAI, Pytest.

**Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, shadcn/ui (Radix), React Router, TanStack Query, React Hook Form + Zod, Lucide, Sonner, Vitest + Testing Library.

## Prerequisites

- Python 3.14 and [`uv`](https://docs.astral.sh/uv/)
- Node.js 22+ and npm
- Docker with Docker Compose
- Optional: Groq API key (analysis and document generation), Gemini API key (semantic matching), SMTP account (digests and password reset)

## Setup

### 1. Configuration

```bash
cp .env.example .env
```

Edit `.env`. Every variable is described in [`.env.example`](.env.example). The ones you must set: `DATABASE_URL`, `REDIS_URL`, `SMTP_FROM_EMAIL`. Without `GROQ_API_KEY`, AI analysis and document generation return a clear "not configured" error; everything else works. Without `GEMINI_API_KEY`, matching uses rules only.

### 2. Backend

```bash
docker compose -f infrastructure/docker-compose.yml up -d   # PostgreSQL + Redis
uv sync
uv run alembic upgrade head
uv run uvicorn backend.app.main:app --reload                # http://localhost:8000
```

Interactive API docs: <http://localhost:8000/docs> (only when `APP_ENV=local`).

### 3. Frontend

```bash
cd frontend
cp .env.example .env        # VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev                 # http://localhost:5173
```

Open <http://localhost:5173>, create an account, then create your profile.

### API URL

The frontend reads the API location from `VITE_API_BASE_URL` (build-time). It must be an origin listed in the backend's `CORS_ALLOWED_ORIGINS`, and the browser must open the frontend on the **same hostname** as the API (`localhost` with `localhost`, not `127.0.0.1` with `localhost`), otherwise the `SameSite=Lax` session cookie is not sent.

## Job sources

Discovery is source-independent. Every provider is an adapter registered in `backend/app/services/job_sources/`, and the API, the scheduled command and the UI (search form, source filter, labels, Settings → Job sources) all read that registry, so no screen hardcodes a provider.

| Source | Filters applied by the provider | Notes |
|---|---|---|
| Jobicy | keywords | Remote only. Terms: at most one request per hour. |
| FreeHire | keywords, country, work mode | |
| Remotive | keywords | Remote only, listings delayed 24 h. Terms: about 4 requests per day (enforced as one per 6 h) and listings must link back to and credit Remotive. The UI shows "View on Remotive". |

A search sends the same query to each selected source. Filters a source can't apply are listed in the results instead of being silently dropped. Sources that only list remote jobs are skipped for hybrid/on-site searches. One source failing or being rate-limited doesn't stop the others. Each attempt is recorded in `agent_runs` (`run_type = job_discovery:<key>`), which is how request limits survive restarts. Switch a source off with `JOB_SOURCES_DISABLED=remotive,…`.

### Adding a source

1. Subclass `JobSource` (`job_sources/base.py`): set `key` (stored in `jobs.source`, never rename it), `label`, `description`, `homepage`, `supported_filters`, `remote_only`, `max_limit`, and `min_interval` if the provider's terms limit request frequency.
2. Implement `fetch(query)`, which returns raw listings, and `normalize(raw)`, which returns `Job` fields (title, job_url and source_job_id at minimum; company name goes in `source_metadata["company_name"]`) or `None`.
3. `register(YourSource())` in `job_sources/__init__.py`.
4. Add normalization tests next to `backend/tests/test_job_discovery.py`.

Only use providers whose terms allow this use, and follow their attribution and rate rules.

## Authentication

- Passwords are hashed with **Argon2id**. Sessions are random tokens stored server-side as SHA-256 digests and sent in an **HttpOnly**, `SameSite=Lax` cookie (`Secure` outside `APP_ENV=local`). Nothing is stored in `localStorage`.
- **CSRF:** every state-changing request needs the `X-CSRF-Token` header. The SPA gets the token from `/api/auth/login` or `/api/auth/me` and keeps it only in memory. Unsafe requests from origins outside `CORS_ALLOWED_ORIGINS` are rejected.
- **Brute force:** after `LOGIN_MAX_FAILURES` failed sign-ins per email or IP within `LOGIN_FAILURE_WINDOW_SECONDS`, login returns `429` with `Retry-After`.
- **Authorization:** every private endpoint checks that the candidate (and the application or document) belongs to the signed-in user. Other users' IDs return `404`, the same as missing ones.
- **Password reset** uses the SMTP settings. Links expire after `PASSWORD_RESET_TTL_MINUTES`, work once, and sign out all sessions. The response is the same whether or not the account exists.
- Set `REGISTRATION_ENABLED=false` once your own account exists on a public deployment.

### Migrating existing data (pre-authentication candidates)

The migration `1bdf6da5551c` only **adds** tables and a nullable `candidates.user_id` column; no data is changed or deleted. Candidates created before authentication have no owner and are invisible in the API until you link them to an account:

```bash
uv run alembic upgrade head
# Register in the UI, then:
uv run python -m backend.app.commands.claim_candidate --list
uv run python -m backend.app.commands.claim_candidate \
    --candidate-email <profile email> --user-email <your login email>
```

Linking is a deliberate operator step. Auto-claiming by matching email would let anyone who registered with that address take over the profile, since email ownership isn't verified.

## Tests

```bash
# Backend: integration tests need the dedicated test DB (it is wiped on each run)
docker exec jobpilot-postgres createdb -U jobpilot jobpilot_test   # once
TEST_DATABASE_URL=postgresql+asyncpg://jobpilot:jobpilot@localhost:5432/jobpilot_test \
  uv run python -m pytest backend/tests -v

# Frontend
cd frontend
npm test              # Vitest
npm run typecheck     # tsc -b
npm run lint          # oxlint
npm run build         # production build to frontend/dist
```

Without `TEST_DATABASE_URL`, the PostgreSQL-backed tests stop with a setup error by design, and the test fixture refuses any database not named `jobpilot_test`.

## Commands

| Command | Purpose |
|---|---|
| `uv run python -m backend.app.commands.discover_and_match_jobs [--keywords …] [--country IN] [--work-mode remote] [--limit 50]` | Search all enabled sources and re-match every candidate (for cron) |
| `uv run python -m backend.app.commands.send_job_digest` | Email each candidate their new strong matches |
| `uv run python -m backend.app.commands.claim_candidate` | Link a pre-authentication candidate to an account |

## API overview

All `/api/*` routes except sign-up, sign-in, sign-out and password reset require a session.

| Area | Endpoints |
|---|---|
| Health (public) | `GET /health`, `GET /health/db` |
| Auth | `POST /api/auth/register`, `/login`, `/logout`, `/password`, `/password-reset/request`, `/password-reset/confirm`; `GET/PATCH /api/auth/me` |
| Candidates | `GET /api/candidates/me`, `POST /api/candidates`, `GET/PATCH /api/candidates/{id}` |
| Skills | `GET/POST /api/candidates/{id}/skills`, `PATCH/DELETE /api/candidates/{id}/skills/{skill_id}` |
| Resume | `POST /api/candidates/{id}/resume/upload` |
| Jobs | `GET /api/jobs` (filters incl. `source`), `GET /api/jobs/{job_id}` |
| Discovery | `GET /api/jobs/sources`, `POST /api/jobs/discovery`; deprecated per-source `POST /api/jobs/discover`, `POST /api/jobs/discover/freehire` |
| Matching | `POST /api/jobs/match/{candidate_id}`, `GET /api/jobs/matches/{candidate_id}` |
| Analysis | `GET /api/jobs/{job_id}/analysis/{candidate_id}` (stored only), `POST /api/jobs/{job_id}/analyze/{candidate_id}` |
| Applications | `POST /api/applications`, `GET /api/applications/candidate/{id}` (`status`, `job_id` filters), `GET .../summary`, `GET/PATCH/DELETE /api/applications/{id}` |
| Documents | `GET /api/applications/{id}/documents[/{doc_id}]`, `PATCH .../{doc_id}/approve`, `POST /api/applications/tailor-resume`, `POST /api/applications/generate-cover-letter` |

## Troubleshooting

| Symptom | Fix |
|---|---|
| “Cannot reach the JobPilot API” | Backend not running, or `VITE_API_BASE_URL` wrong. `curl localhost:8000/health`. Restart `npm run dev` after editing `frontend/.env`. |
| Signed in, but every request is 401 | Frontend and API on different hostnames (`127.0.0.1` vs `localhost`), or `SESSION_COOKIE_SECURE=true` over plain HTTP. |
| `403 Origin not allowed` | Add the frontend origin (scheme + host + port, no trailing slash) to `CORS_ALLOWED_ORIGINS` and restart the backend. |
| `403 CSRF token missing or invalid` | Calling the API outside the SPA: send the `csrf_token` from `/api/auth/me` as `X-CSRF-Token`. |
| Profile shows “Create your profile” but data exists | The candidate predates authentication; run `claim_candidate` (see above). |
| Analysis / generation returns 503 | Groq key missing, rate-limited, or the model returned invalid output. Retry later. |
| Matching works but logs “Embedding provider unavailable” | Gemini key missing or quota exhausted; scores fall back to rules only. |
| Password reset email never arrives | Check the `SMTP_*` settings and backend logs; the API does not reveal delivery failures. |

## Security and limitations

- See [docs/deployment.md](docs/deployment.md) for the production checklist. **Do not call this production-ready until that checklist has been completed in the target environment.**
- Login throttling is in-process memory: it resets on restart and is per-worker.
- No email verification on registration; no MFA; no "sign out all devices" button (changing or resetting the password does that).
- Job discovery is open to every signed-in user and writes to the shared job table.
- Job descriptions are converted to plain text and never rendered as HTML; AI output is shown as plain text.
- AI-generated resumes, cover letters and analyses can be wrong. Always verify dates, skills, job history, responsibilities, achievements and contact details before approving.
- Job freshness depends on the external sources. Provider outages and rate limits affect discovery and AI features.
- Documents are plain text only (no PDF/DOCX export).

## License

No license has been selected yet. Add a `LICENSE` file before distributing the project or accepting external contributions.
