---
phase: 01-foundation-capture-feasibility
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, alembic, timescaledb, scrypt, session-auth, pytest]

requires: []
provides:
  - Settings/get_db/require_auth patterns every later phase's API additions build on
  - Base declarative model + AppSettings/BandwidthMetric/ArpEvent ORM models
  - Initial Alembic migration creating the TimescaleDB hypertable schema
  - Full /api/auth/* and /api/capture/arp route surface with pytest coverage
affects: [01-02-capture-compose, 01-03-frontend, phase-2-device-registry, phase-3-traffic-bandwidth]

tech-stack:
  added: [fastapi==0.137.1, sqlalchemy==2.0.51, alembic==1.16.5, asyncpg==0.31.0, pydantic-settings==2.11.0, itsdangerous==2.2.0, greenlet, pytest, pytest-asyncio, aiosqlite]
  patterns:
    - "Async SQLAlchemy 2.0: async_sessionmaker + expire_on_commit=False + get_db generator dependency"
    - "Session auth via Starlette SessionMiddleware (httpOnly hardcoded, max_age=None per D-10)"
    - "Password hashing via stdlib hashlib.scrypt, salt$hash hex string, hmac.compare_digest comparison"
    - "Capture ingest security control: loopback-only check (127.0.0.1/::1) on request.client.host, 403 otherwise"
    - "Alembic async env.py with include_name filter excluding TimescaleDB _hyper_* internal indexes"
    - "Test DB override: in-memory SQLite + app.dependency_overrides[get_db], no Docker/Postgres needed for unit tests"

key-files:
  created:
    - backend/pyproject.toml
    - backend/Dockerfile
    - backend/alembic.ini
    - backend/alembic/env.py
    - backend/alembic/versions/0001_initial.py
    - backend/src/settings.py
    - backend/src/database.py
    - backend/src/models/base.py
    - backend/src/models/app_settings.py
    - backend/src/models/bandwidth.py
    - backend/src/models/arp_event.py
    - backend/src/auth.py
    - backend/src/routes/auth.py
    - backend/src/routes/capture.py
    - backend/src/main.py
    - backend/tests/conftest.py
    - backend/tests/test_models_scaffold.py
    - backend/tests/test_auth.py
    - backend/tests/test_capture.py
  modified:
    - .env.example

key-decisions:
  - "database.py only passes pool_size/max_overflow (QueuePool-only kwargs) when the URL is not sqlite, so the same engine factory works for both production Postgres and the in-memory SQLite test fixture"
  - "greenlet added as an explicit dependency — SQLAlchemy's async extension requires it at runtime but does not declare it as a hard dependency, so pip would not have installed it transitively"
  - "Settings.model_config uses env_file=None — config is injected entirely via Docker Compose's env_file: directive since the container's CWD (/app) never resolves a relative .env path to the repo root"

patterns-established:
  - "ORM models live under src/models/, one file per table, importing Base from src/models/base.py"
  - "Routes are FastAPI APIRouter instances under src/routes/, included in main.py with explicit prefixes"
  - "Security-sensitive checks (loopback-only, session-fixation) are implemented inline in the route handler with a code comment citing the threat ID (e.g. T-01-05) for traceability"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, PLAT-03]

duration: 35min
completed: 2026-06-17
---

# Phase 1 Plan 01: Backend Foundation Summary

**FastAPI backend with async SQLAlchemy/TimescaleDB schema, scrypt-based session auth, and a loopback-only ARP capture ingest route — all 12 pytest cases green.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-06-17T20:51:00Z
- **Completed:** 2026-06-17T20:56:05Z
- **Tasks:** 2 completed
- **Files modified:** 19 created, 1 modified (.env.example)

## Accomplishments

- Stood up the full backend scaffold: pydantic-settings config, async SQLAlchemy engine/session wiring, and the three ORM models (`AppSettings`, `BandwidthMetric`, `ArpEvent`) that every later phase's schema extends
- Wrote the initial Alembic migration creating all three tables and converting `bandwidth_metrics` to a TimescaleDB hypertable via `create_hypertable`, with the `include_name` filter in `env.py` protecting TimescaleDB's auto-created internal indexes from future autogenerate runs
- Implemented the complete `/api/auth/*` route surface (setup/login/me/logout) with `hashlib.scrypt` password hashing, session-fixation mitigation (`session.clear()` before granting `authenticated=True`), and a one-time setup gate (409 on re-call)
- Implemented `/api/capture/arp` with the loopback-only security control (403 for any non-127.0.0.1/::1 source), satisfying PLAT-03's "capture never writes directly to the DB" requirement
- Full automated pytest coverage: 12/12 tests passing, covering AUTH-01/02/03 and the capture ingest security control, using in-memory SQLite — no Docker/Postgres required for the test suite

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend scaffold — settings, database, models, Alembic migration** - `a1d2c7d` (feat)
2. **Task 2: Auth routes + capture ingest route + FastAPI app wiring** - `ba09de1` (feat)

_Note: Both tasks were marked `tdd="true"` in the plan; tests were written alongside implementation in the same commit per task rather than as separate RED/GREEN commits, since the plan's `<behavior>` blocks described route-level tests that depend on routes not yet existing in Task 1 (the plan itself documents this RED/GREEN relationship spanning the two tasks rather than within a single task)._

## Files Created/Modified

- `backend/pyproject.toml` - Project deps pinned per RESEARCH.md Standard Stack; pytest config (asyncio_mode=auto)
- `backend/Dockerfile` - python:3.13-slim + nmap, installs `.[dev]`
- `backend/alembic.ini` / `backend/alembic/env.py` - Async Alembic env with `include_name` TimescaleDB index filter
- `backend/alembic/versions/0001_initial.py` - Creates app_settings/bandwidth_metrics/arp_events, converts bandwidth_metrics to hypertable
- `backend/src/settings.py` - `Settings(BaseSettings)`, `get_settings()` lru_cache factory
- `backend/src/database.py` - async engine/session factory, `get_db()` dependency, dialect-conditional pool kwargs
- `backend/src/models/{base,app_settings,bandwidth,arp_event}.py` - Declarative ORM models
- `backend/src/auth.py` - `hash_password`, `verify_password` (scrypt), `require_auth` dependency
- `backend/src/routes/auth.py` - `/setup`, `/login`, `/me`, `/logout`
- `backend/src/routes/capture.py` - `/arp` loopback-only ingest
- `backend/src/main.py` - `create_app()`, lifespan, SessionMiddleware, CORSMiddleware, router wiring
- `backend/tests/conftest.py` - `test_db` and `client` fixtures (in-memory SQLite + dependency override)
- `backend/tests/test_models_scaffold.py`, `test_auth.py`, `test_capture.py` - Full behavioral coverage
- `.env.example` - Rewritten with Phase 1's actual required vars (POSTGRES_*, DATABASE_URL, SESSION_SECRET, API_PORT, PUBLIC_API_URL), removing unrelated leftover content

## Decisions Made

- **Dialect-conditional engine kwargs:** `pool_size`/`max_overflow` are QueuePool-specific and break SQLite's StaticPool used in tests; `database.py` now only applies them when `database_url` doesn't start with `sqlite`. This keeps one engine factory function working correctly for both production (Postgres) and tests (SQLite) without duplicating `database.py` per environment.
- **Explicit `greenlet` dependency:** SQLAlchemy's async mode requires `greenlet` at runtime, but SQLAlchemy doesn't declare it as a mandatory dependency (it's pulled in via the optional `sqlalchemy[asyncio]` extra, which the plan's exact pin `sqlalchemy==2.0.51` without the extra does not request). Added explicitly to `pyproject.toml` so a fresh `pip install` always succeeds, locally and in the Docker build.
- **Local test toolchain on Python 3.13:** Host machine had only Python 3.9.6, which cannot install fastapi>=0.136 (requires >=3.10) or satisfy the project's `requires-python >= 3.13`. Installed `python@3.13` via Homebrew and ran the full pytest suite against a dedicated 3.13 venv to validate against the actual pinned dependency versions, matching what the Docker image will use.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Missing `greenlet` dependency**
- **Found during:** Task 1 verification (`pytest backend/tests/test_models_scaffold.py -x -q`)
- **Issue:** `ValueError: the greenlet library is required to use this function. No module named 'greenlet'` — SQLAlchemy's async engine needs greenlet at runtime but it wasn't installed since the plan's pin list didn't include it and SQLAlchemy doesn't declare it as a mandatory dependency.
- **Fix:** Added `"greenlet"` to `backend/pyproject.toml` dependencies.
- **Files modified:** `backend/pyproject.toml`
- **Verification:** `pytest backend/tests/test_models_scaffold.py -x -q` passed after the fix.
- **Committed in:** `a1d2c7d` (part of Task 1 commit)

**2. [Rule 1 - Bug] `database.py` engine kwargs incompatible with SQLite test fixture**
- **Found during:** Task 2 verification (`pytest backend/tests/ -x -q`)
- **Issue:** `TypeError: Invalid argument(s) 'pool_size','max_overflow' sent to create_engine() ... SQLiteDialect_aiosqlite/StaticPool/Engine`. The module-level `engine` in `database.py` always passed `pool_size`/`max_overflow`, which only `QueuePool` (used by Postgres/asyncpg) accepts; SQLite's default `StaticPool` rejects them, breaking every test that imports `src.main` (which imports `src.database`).
- **Fix:** Made `pool_size`/`max_overflow` conditional on `database_url` not starting with `sqlite`.
- **Files modified:** `backend/src/database.py`
- **Verification:** `pytest backend/tests/ -x -q --tb=short` — all 12 tests passed after the fix; `expire_on_commit=False` literal string (required by acceptance criteria) remains present and unaffected.
- **Committed in:** `ba09de1` (part of Task 2 commit)

## Threat Flags

None — all threat register items (T-01-01 through T-01-07) were implemented exactly as specified in the plan's `<threat_model>` (httpOnly cookie, scrypt hashing, session-fixation mitigation, loopback-only capture ingest, ORM-parameterized queries, 409 setup re-invocation guard). No new security-relevant surface was introduced beyond what the plan's threat model already covers.

## Known Stubs

None. Every artifact listed in the plan's `must_haves.artifacts` was implemented with real logic (no hardcoded empty returns or placeholder text) and is exercised by an automated test.

## Self-Check

See below.
