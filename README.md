# JobPilot 🚀

**An AI-powered job search and application assistant built with Python, FastAPI, and PostgreSQL.**

JobPilot helps streamline the job search process by discovering opportunities from supported job sources, matching them against a candidate's skills and experience, generating tailored application documents, and tracking applications.

> **Project status:** Local MVP. Core backend workflows are implemented, and 183 automated tests have passed in the project owner's environment. Authentication and production deployment hardening are not yet implemented.

## ✨ Features

- **Candidate profiles** — Manage candidate information, skills, experience, and job preferences.
- **Job discovery** — Discover opportunities from supported job sources, including Jobicy and FreeHire.
- **Intelligent job matching** — Match job requirements against candidate skills and profile information.
- **AI job analysis** — Analyze opportunities in the context of a candidate's profile.
- **Resume parsing** — Upload and extract information from resumes.
- **AI resume tailoring** — Generate job-specific resume drafts based on available candidate and job information.
- **Cover letter generation** — Prepare tailored cover-letter drafts for individual opportunities.
- **Application tracking** — Track applications, statuses, notes, and follow-up dates.
- **Document management** — Store generated documents with versioning and explicit approval.
- **Job digests** — Generate relevant-job digests and support email notifications.
- **Local development infrastructure** — Run PostgreSQL and Redis using Docker Compose.

JobPilot assists with application preparation. Generated documents require human review, and applications are not submitted autonomously.

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python | Backend development |
| FastAPI | REST API |
| PostgreSQL | Relational database |
| SQLAlchemy | Asynchronous ORM |
| Alembic | Database migrations |
| Redis | Supporting infrastructure |
| Groq | AI text generation |
| Gemini | Embedding generation |
| Pydantic Settings | Application configuration |
| Docker Compose | Local infrastructure |
| Pytest | Automated testing |

## 🏗️ Architecture

```text
        Supported Job Sources
                 |
                 v
         Job Discovery
                 |
                 v
             PostgreSQL
                 ^
                 |
         Candidate Profile
                 |
                 v
          Job Matching
                 |
                 v
           AI Analysis
                 |
          +------+------+
          |             |
          v             v
      Job Digest    Application Prep
          |             |
          v             v
        Email      Resume / Cover Letter
                        |
                        v
                 Manual Review
                        |
                        v
                 Application Tracking
```

## 📋 Prerequisites

Before running JobPilot locally, make sure you have:

- Python compatible with the project's dependency configuration
- `uv`, if using the project's current dependency workflow
- Docker Desktop or Docker Engine with Docker Compose
- API credentials for the AI providers you intend to use
- SMTP credentials if you want to send email digests

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd job-pilot
```

Replace `<your-repository-url>` with your GitHub repository URL.

### 2. Configure environment variables

Create a `.env` file in the project root. Keep this file out of version control.

Example local configuration:

```dotenv
APP_NAME=JobPilot
APP_ENV=local
DEBUG=true

DATABASE_URL=postgresql+asyncpg://jobpilot:jobpilot@localhost:5432/jobpilot
REDIS_URL=redis://localhost:6379/0

GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b

GEMINI_API_KEY=
GEMINI_EMBEDDING_MODEL=gemini-embedding-2

SMTP_HOST=localhost
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=JobPilot
SMTP_USE_TLS=false
SMTP_START_TLS=true

JOB_DIGEST_MIN_SCORE=70
JOB_DIGEST_MAX_JOBS=10
JOB_DIGEST_TIMEZONE=Asia/Kolkata
JOB_DIGEST_MIN_COVERAGE=60
```

These are development examples. Verify the environment variable names and required values in `backend/app/core/config.py`. Configure credentials only for the integrations you use.

### 3. Start PostgreSQL and Redis

The Compose file is located in `infrastructure/`.

```bash
docker compose -f infrastructure/docker-compose.yml up -d
```

Verify the services:

```bash
docker compose -f infrastructure/docker-compose.yml ps
```

### 4. Install dependencies

If the repository uses `uv`:

```bash
uv sync
```

### 5. Run database migrations

From the project root:

```bash
uv run alembic upgrade head
```

### 6. Start the API

```bash
uv run uvicorn backend.app.main:app --reload
```

The API should be available at:

- API: `http://localhost:8000`
- Interactive documentation: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

## ❤️ Health Checks

Check whether the API is running:

```bash
curl -s http://localhost:8000/health
```

Check database connectivity:

```bash
curl -s http://localhost:8000/health/db
```

Both endpoints have been verified in the project owner's local environment.

## 🔌 API Overview

The current API exposes endpoints in the following areas:

| Area | Example endpoints |
|---|---|
| Health | `GET /health`, `GET /health/db` |
| Candidates | `/api/candidates` |
| Candidate skills | `/api/candidates/{candidate_id}/skills` |
| Resume upload | `POST /api/candidates/{candidate_id}/resume/upload` |
| Job listings | `GET /api/jobs` |
| Job discovery | `POST /api/jobs/discover`, `POST /api/jobs/discover/freehire` |
| Job matching | `POST /api/jobs/match/{candidate_id}` |
| Match results | `GET /api/jobs/matches/{candidate_id}` |
| Job analysis | `POST /api/jobs/{job_id}/analyze/{candidate_id}` |
| Applications | `/api/applications` |
| Application documents | `/api/applications/{application_id}/documents` |
| Cover letters | `POST /api/applications/generate-cover-letter` |
| Resume tailoring | `POST /api/applications/tailor-resume` |

Refer to `/docs` for the current request parameters, schemas, and response formats.

## 🧪 Running Tests

Run the automated test suite:

```bash
uv run python -m pytest backend/tests -v
```

**Current reported result: 183 tests passing.**

> **Important:** Integration tests may modify database tables. Configure `TEST_DATABASE_URL` to point to a dedicated test database before running them. Never use a database containing data you need to preserve.

## 📝 Typical Workflow

1. Create and maintain a candidate profile.
2. Add skills and upload a resume.
3. Discover jobs from supported sources.
4. Match jobs against the candidate profile.
5. Review the most relevant opportunities and verify the original job listings.
6. Generate a tailored resume and cover letter.
7. Review and approve the generated documents.
8. Apply manually.
9. Track application status and follow-up dates.
10. Use job digests to review new opportunities.

## 🔐 Security and Privacy

JobPilot is currently designed as a **local, single-user MVP**.

- Authentication and authorization have not been implemented.
- Do not expose the API publicly in its current state.
- Never commit `.env` files, API keys, resumes, or personal application data.
- Use strong, non-default database credentials outside local development.
- Restrict PostgreSQL and Redis to trusted interfaces.
- Disable debug mode and SQL query echoing in production.
- Add authentication, authorization, and appropriate ownership checks before allowing access by other users.

## ⚠️ Current Limitations

- Job freshness and availability depend on external job sources.
- Provider outages, rate limits, and API changes may affect discovery and AI generation.
- Scheduled discovery and email delivery should be verified in the target environment.
- AI-generated resumes and cover letters can contain errors and must be reviewed.
- Public production deployment requires additional security and configuration work.

## 🗺️ Project Direction

The current priority is to **stabilize and use the existing MVP**, rather than continually adding features.

Future improvements should be driven by real-world usage, job-match quality, and issues encountered during the job search.

## 📄 License

No license has been selected yet. Add a `LICENSE` file before distributing the project or accepting external contributions.

---

**Built to make the job search process more organized, relevant, and efficient.**