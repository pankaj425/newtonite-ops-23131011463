# Operations Under Pressure

A team-based operations management web application for creating, assigning,
tracking, and resolving operational work items (incidents, customer issues,
payment failures, compliance cases, and general tasks).

It provides a shared dashboard, a controlled status workflow, team-scoped
permissions enforced on the server, an append-only activity history, search,
filtering, server-side pagination, and protections against concurrent claims,
stale updates, and duplicate create requests.

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, JWT
- **Database:** PostgreSQL 16
- **Frontend:** React 18 + Vite
- **Tests:** Pytest + FastAPI TestClient, run against PostgreSQL

---

## 1. Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/) (for PostgreSQL and, optionally, the app services)
- Python 3.12+
- Node.js 20+ (for the frontend)

If you prefer, you can run PostgreSQL natively instead of with Docker; just
point `DATABASE_URL` and `TEST_DATABASE_URL` at your databases.

---

## 2. Quick start (Docker Compose)

```bash
# 1. Start PostgreSQL and the test database
docker compose up -d db db_test

# 2. Backend: create a virtualenv, install, configure, migrate, seed
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                  # cp .env.example .env on macOS/Linux
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000

# 3. Frontend (in a second terminal)
cd frontend
npm install
copy .env.example .env                  # cp .env.example .env on macOS/Linux
npm run dev
```

Then open <http://localhost:5173> and sign in with a demo account (section 6).

To run everything in containers instead of locally:

```bash
docker compose up --build
```

### Alternative: local PostgreSQL without Docker (Windows)

If Docker is unavailable, `scripts/db.ps1` creates and runs an isolated
PostgreSQL cluster in `backend/.pgdata` on port `5433` (the same port the
Compose test database uses), so `backend/.env.example` works unchanged.

```powershell
./scripts/db.ps1 start     # initdb on first run, start, create both databases
./scripts/db.ps1 status    # is it accepting connections?
./scripts/db.ps1 stop      # clean shutdown
./scripts/db.ps1 reset     # delete the cluster and start over
```

Set the `PGBIN` environment variable to the folder containing `pg_ctl.exe` if
the PostgreSQL binaries are not under `C:\Program Files\PostgreSQL`. After
`start`, run `alembic upgrade head` and `python scripts/seed.py` as usual.

---

## 3. Environment variables

Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to
`frontend/.env`. Never commit real secrets.

| Variable | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | backend | SQLAlchemy URL for the main database |
| `TEST_DATABASE_URL` | backend | SQLAlchemy URL for the pytest database |
| `JWT_SECRET` | backend | Signing secret for access tokens |
| `JWT_ALGORITHM` | backend | Token algorithm (default `HS256`) |
| `JWT_EXPIRES_MINUTES` | backend | Access-token lifetime (default 45) |
| `CORS_ORIGINS` | backend | Comma-separated allowed frontend origins |
| `IDEMPOTENCY_TTL_HOURS` | backend | Idempotency-key retention window (default 24) |
| `VITE_API_BASE_URL` | frontend | Base URL of the backend API |

---

## 4. Database: migrations and seed

```bash
cd backend

alembic upgrade head        # apply all migrations
python scripts/seed.py      # seed demo teams, users, memberships, and items
```

Useful extras:

```bash
alembic downgrade base      # drop everything
alembic revision --autogenerate -m "describe change"
```

The initial migration also installs a database trigger that makes
`activity_events` append-only (updates and deletes are rejected).

---

## 5. Running the tests

Tests run against a **PostgreSQL** database (not SQLite), because the
concurrency protections rely on real row locking.

`docker compose` exposes the test database on `localhost:5433`.

```bash
# 1. Start the test database (from the repo root)
docker compose up -d db_test

# 2. Run the whole suite with one command (from backend/)
cd backend
pytest
```

`pytest` reads `TEST_DATABASE_URL` (default
`postgresql+psycopg2://newtonite:newtonite@localhost:5433/newtonite_test`),
applies migrations, and resets data between tests. Override the URL with an
environment variable if needed:

```bash
TEST_DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db pytest
```

---

## 6. Demo credentials

All demo accounts use the password `Password123!`.

| Email | Roles |
|---|---|
| `admin@newtonite.dev` | admin in Payments, lead in Support |
| `lead@newtonite.dev` | lead in Payments |
| `member@newtonite.dev` | member in Payments and Support |
| `viewer@newtonite.dev` | viewer in Payments |
| `other@newtonite.dev` | member in Compliance (demonstrates cross-team isolation) |

> These are development-only credentials and must not be used in production.

---

## 7. API overview

Base URL: `http://localhost:8000`. Interactive docs at `/docs`.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/auth/login` | Authenticate a seeded user; returns a JWT |
| `GET` | `/me` | Current user and memberships |
| `GET` | `/teams` | Teams the current user belongs to |
| `GET` | `/teams/{team_id}/members` | Members of a team (assignee picker) |
| `GET` | `/items` | Search, filter, and paginate items (`view`, `status`, `priority`, `type`, `team_id`, `assignee_id`, `search`, `page`, `page_size`) |
| `POST` | `/items` | Create an item (supports `Idempotency-Key`) |
| `GET` | `/items/{item_id}` | Item details |
| `PATCH` | `/items/{item_id}` | Update an item (`version` required) |
| `POST` | `/items/{item_id}/claim` | Atomically claim an unassigned item |
| `POST` | `/items/{item_id}/transition` | Change status (`to_status`, `version`, optional `reason`) |
| `GET` | `/items/{item_id}/activity` | Activity timeline |
| `GET` | `/items/{item_id}/comments` | List comments |
| `POST` | `/items/{item_id}/comments` | Add a comment |

### Error response format

All errors share one shape:

```json
{
  "error": {
    "code": "version_conflict",
    "message": "The item was modified by someone else. Reload the latest version and retry.",
    "details": { "current_version": 5, "current_item": { } }
  }
}
```

| Status | When |
|---|---|
| `422` | Invalid input, invalid transition, idempotency key reused with a different body |
| `401` | Missing/invalid/expired token or bad credentials |
| `403` | Authenticated but the role is insufficient |
| `404` | Item/team missing **or** outside the user's teams |
| `409` | Claim conflict, stale version, concurrent idempotent request |

---

## 8. Repository layout

```text
newtonite-ops-23131011463/
├── backend/
│   ├── app/
│   │   ├── api/          # route handlers + error envelope
│   │   ├── auth/         # hashing, JWT, dependencies
│   │   ├── models/       # SQLAlchemy models + enums
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # workflow, claim, activity, idempotency, permissions
│   │   ├── config.py
│   │   ├── db.py
│   │   └── main.py
│   ├── alembic/          # migrations
│   ├── scripts/seed.py
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/             # React + Vite app
├── scripts/db.ps1        # local PostgreSQL helper (Windows)
├── docker-compose.yml
├── ENGINEERING_DECISIONS.md
└── README.md
```

---

## 9. Known limitations

- No email delivery or notifications.
- No file attachments.
- No SSO, refresh tokens, or password reset.
- No real-time updates (the UI reloads on demand rather than using WebSockets).
- Search is substring matching (`ILIKE`), not a dedicated search engine.
- No mobile application.
- Idempotency replay returns the stored response but does not re-run
  side effects, by design.
