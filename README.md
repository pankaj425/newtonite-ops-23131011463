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
| `CORS_ORIGINS` | backend | Explicit comma-separated allowed frontend origins (never `*`) |
| `CORS_ORIGIN_REGEX` | backend | Optional regex for Vercel **preview** origins of this project only |
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
`activity_events` append-only (updates and deletes are rejected). Migration
`0002` adds a composite `(team_id, created_at)` index used by the team-scoped
list query. `alembic check` reports no drift between the models and the schema.

The seed script is **idempotent**: it inserts its six sample items only if an
item with the same `(team, title)` does not already exist, so repeated deploys
never duplicate demo data. Work-item titles are deliberately **not unique** —
two items may share a title, which is expected and not a duplication bug.

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

Results are ordered deterministically by `created_at DESC, id DESC`, and
`page_size` is clamped to `1..100` on the server. Assignees must belong to the
item's team and hold at least the **member** role (a viewer cannot be assigned).
Comment bodies must be non-blank: an empty or whitespace-only body is rejected
with `422` (`validation_error`).

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
├── frontend/             # React + Vite app (vercel.json / netlify.toml)
├── scripts/db.ps1        # local PostgreSQL helper (Windows)
├── .github/workflows/    # CI: pytest + frontend build
├── docker-compose.yml
├── render.yaml           # Render Blueprint (API + managed PostgreSQL)
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
- Assignees are restricted to team members with at least the member role.
- Free-tier hosting: the Render API sleeps when idle, so the first request can
  take 30-60 seconds. The frontend surfaces this as a clear timeout message.

---

## 11. Five-minute demo outline

Run against the live URLs or locally. Every behaviour below is implemented and
covered by tests (`backend/tests/`).

1. **Login** as `member@newtonite.dev` / `Password123!`; show the team-scoped
   dashboard (assigned to me, unassigned urgent, awaiting my approval).
2. **Open a work item** and show details, comments, and the activity timeline.
3. **Claim** the unassigned "Duplicate charge" item; it becomes assigned and an
   `item_claimed` event appears. (Two users claiming at once: one gets `409`.)
4. **Transition** `open → in_progress → awaiting_approval` as the member.
5. **Comment** on the item and show the new timeline row.
6. **Approve** as `lead@newtonite.dev` (`awaiting_approval → resolved`); the
   lead cannot approve an item they are assigned to (self-approval is blocked).
7. **Conflict:** open the same item in two tabs, edit in one, then save the
   other — the stale save returns `409` with a "reload" message.
8. **Isolation / permissions:** sign in as `viewer@newtonite.dev` (cannot
   create, claim, comment, or edit) and as `other@newtonite.dev` (Payments items
   return `404`).

### Talking points

- **Architecture:** Browser → React SPA (Vercel) → FastAPI (Render) → PostgreSQL.
- **Concurrent claim:** a single conditional `UPDATE ... WHERE assignee_id IS
  NULL`; `rowcount == 0` means someone else won → `409`.
- **Stale edits:** every mutation carries `version` and is applied with a
  `WHERE version = :expected` guard; zero rows updated → `409` with the current
  item so the UI can reload.
- **Duplicate creates:** `Idempotency-Key` + payload hash stored under a unique
  constraint; same key + same body replays the original response, same key +
  different body is `422`, concurrent duplicates cannot both insert.
- **Team permissions:** membership is the boundary; missing membership returns
  `404` so private items are not leaked; insufficient role returns `403`.
- **Activity history:** the item change and its event are written in one
  transaction (event rollback test included); a trigger blocks edits/deletes.
- **At 10x:** add per-team rate limits, a read replica for list queries, and a
  background worker plus transactional outbox for side effects.

---

## 10. Deployment (live demo)

The app is split into a hosted API + managed PostgreSQL (Render) and a static
frontend (Vercel, or Netlify as an alternative).

### Backend + database (Render)

The repository ships a [Render Blueprint](https://render.com/docs/blueprint-spec)
in `render.yaml` that provisions a free PostgreSQL 16 instance and the FastAPI
web service.

1. Push this repository to GitHub.
2. In Render: **New +** → **Blueprint** → select the repository → **Apply**.
3. Render builds `backend/`, runs `alembic upgrade head`, seeds the demo data,
   and starts `uvicorn` on `$PORT`.
4. The Blueprint sets `CORS_ORIGINS` to the production frontend origin
   (`https://newtonite-ops-23131011463.vercel.app`) plus `http://localhost:5173`,
   and `CORS_ORIGIN_REGEX` to this project's Vercel preview URLs only. Edit
   `CORS_ORIGINS` in the Render dashboard if your frontend origin differs.
   Credentialed requests are never allowed against an unrestricted wildcard.
5. Note the API URL, for example `https://newtonite-ops-api.onrender.com`.

> Free Render web services sleep after inactivity, so the first request after a
> nap takes a few seconds. The free database plan expires after 90 days.

### Frontend (Vercel)

1. Import the repository in Vercel.
2. Set **Root Directory** to `frontend`. The `vercel.json` SPA rewrite is
   already included.
3. Add the environment variable `VITE_API_BASE_URL` pointing at the Render API
   URL, for example `https://newtonite-ops-api.onrender.com`.
4. Deploy, then copy the deployed URL back into Render's `CORS_ORIGINS`.

### Frontend (Netlify, alternative)

`frontend/netlify.toml` has the equivalent build settings and SPA redirect. Set
the base directory to `frontend`, add `VITE_API_BASE_URL`, and deploy.

### Continuous integration

`.github/workflows/ci.yml` runs the backend test suite against a PostgreSQL 16
service container and builds the frontend on every push and pull request.
