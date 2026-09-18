# VIRĀM API (apps/api)

FastAPI + SQLAlchemy (async) + Alembic foundation — Phase 2 baseline.
Design source of truth: [`docs/DATABASE_DESIGN.md`](../../docs/DATABASE_DESIGN.md).

## Setup

```bash
cd apps/api
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash)
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements/dev.txt

cp .env.example .env            # then edit values (generate a real JWT secret)
```

## Database (Docker)

```bash
docker compose up -d db          # from repo root
cd apps/api
alembic upgrade head             # applies baseline revision 0001
```

Single source of truth for the connection string is `VIRAM_DATABASE_URL`
(in `apps/api/.env`), read by both the app and Alembic.

## Run

```bash
uvicorn app.main:app --reload    # from apps/api
```

- API:    http://localhost:8000/api/v1/health
- Docs:   http://localhost:8000/docs

## Test

```bash
pytest            # from apps/api — no database required for current tests
```

## Layout

```
app/
  main.py               # app factory, lifespan, CORS, error handlers
  api/v1/               # routers (health now; auth, trips, ... next)
  core/
    config.py           # pydantic-settings (VIRAM_ prefix)
    database.py         # async engine, session, DeclarativeBase
    errors.py           # unified error envelope + handlers
    logging.py          # logging config (no sensitive fields)
migrations/             # Alembic (async engine, autogenerate-ready)
tests/                  # pytest suite
requirements/           # base.txt / dev.txt (pinned)
```
