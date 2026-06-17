# Phase 1: Foundation + Capture Feasibility - Research

**Researched:** 2026-06-17
**Domain:** Full-stack Docker Compose deployment — FastAPI + SQLAlchemy async + TimescaleDB + SvelteKit static + Scapy ARP capture + cookie auth
**Confidence:** MEDIUM (all packages verified on registries; patterns verified via official docs and authoritative community sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Target is a Linux machine (bare metal or VM) — NOT macOS with Docker Desktop. The macOS Docker host-networking constraint does not apply.
- **D-02:** PLAT-03 "native macOS agent fallback" is NOT needed. Linux host networking is the baseline — no alternative topology research required.
- **D-03:** Capture runs as a Docker container with `network_mode: host` + `CAP_NET_RAW` + `CAP_NET_ADMIN` capabilities. Never `--privileged`.
- **D-04:** Phase 1 capture service is proof-of-concept only — captures ARP packets and POSTs them to the FastAPI API (which writes to PostgreSQL).
- **D-05:** Spike success criteria: capture one real ARP packet from the LAN, POST it to the API, confirm one row written to PostgreSQL.
- **D-06:** Capture service data flows via POST to the FastAPI API (not direct DB writes). The API is the single point of truth for all data writes.
- **D-07:** Session persistence: httpOnly signed session cookie. No JWT in localStorage.
- **D-08:** First-run flow: all routes redirect to `/setup` if no password has been configured. User sets password → redirected to `/login` → enters dashboard.
- **D-09:** Password policy: any non-empty string. No minimum length or complexity rules.
- **D-10:** Sessions never expire automatically. A session is invalidated only when the user changes their password.
- **D-11:** 4 services from day 1: `api` (FastAPI), `frontend` (SvelteKit static), `db` (PostgreSQL + TimescaleDB), `capture` (host-networked capture service). Final topology.
- **D-12:** Dashboard accessible at port **9999** (HTTP, no TLS). Frontend container on :9999.
- **D-13:** Browser fetches API at the host's IP on its own port (e.g., :8000 or as configured). Frontend calls API via the host's network address, not Docker-internal DNS.
- **D-14:** Config via `.env` file at repo root. Committed `.env.example` documents required variables.
- **D-15:** Alembic migrations run automatically on API container startup (`alembic upgrade head` before Uvicorn starts).
- **D-16:** TimescaleDB hypertable created in a Phase 1 Alembic migration — even though traffic data doesn't land until Phase 3.
- **D-17:** Frontend: SvelteKit built with `adapter-static`, served from a lightweight nginx container on port 9999.
- **D-18:** Development workflow: `docker compose up` for everything. Source directories mounted as volumes so code changes reflect without full rebuilds.
- **D-19:** Phase 1 dashboard shell contains only: `/setup`, `/login`, and a protected empty `/dashboard`. No nav structure, no device list, no additional routes.

### Claude's Discretion

- API port selection (internal to Docker Compose) — any available port is fine
- Health check configuration for each service — standard patterns acceptable
- Docker Compose network name and internal DNS names for services
- Session cookie signing implementation details (e.g., itsdangerous, PyJWT in cookie mode)
- Specific nginx config for the frontend container

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within Phase 1 scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLAT-01 | User accesses Innkeeper via a web dashboard from any device on the home network without installing anything on that device | D-12 (port 9999), D-17 (nginx serves static SPA), D-13 (API via host IP) — standard browser access |
| PLAT-02 | The full Innkeeper stack (API, frontend, database, capture engine) is deployable via a single `docker compose up` command on any Docker-capable machine | D-11 (4 services), D-14 (.env config), D-15 (migrations auto-run) — standard Docker Compose patterns documented below |
| PLAT-03 | The capture engine runs as a separate, isolated Docker service with only `CAP_NET_RAW` and `CAP_NET_ADMIN` capabilities — never `--privileged` | D-03, Scapy ARP sniffing pattern documented below; Linux network_mode:host confirmed working |
| AUTH-01 | A first-run setup wizard prompts the user to set a dashboard password before the UI is accessible | D-08, first-run redirect logic documented; Starlette SessionMiddleware pattern |
| AUTH-02 | User must authenticate with the dashboard password to access any page of the Innkeeper UI | D-07, FastAPI auth dependency + SvelteKit route guard documented |
| AUTH-03 | User session persists across browser refresh (JWT or session cookie) | D-07 (httpOnly signed cookie), D-10 (no expiry), Starlette SessionMiddleware with itsdangerous |
</phase_requirements>

---

## Summary

Phase 1 establishes the full walking skeleton: four Docker Compose services (API, frontend, DB, capture), session-based authentication with a first-run password flow, and a proof-of-concept ARP capture pipeline. Every downstream phase builds on this topology — nothing here is throwaway.

The research confirms all locked stack choices are current and compatible. The highest-risk area is the TimescaleDB hypertable integration with Alembic autogenerate — a known issue where Alembic tries to drop the auto-created time column index on every autogenerated migration. The workaround is an `include_name` filter in `env.py`, documented below. The second area to watch is the SvelteKit SPA cookie auth pattern: because the frontend is a static SPA calling a separate API origin (by host IP), cookies must have `SameSite=lax` and `Secure=false` for local HTTP, and the API's CORS configuration must allow credentials from the frontend origin.

The capture topology — Linux `network_mode: host` + `CAP_NET_RAW` + `CAP_NET_ADMIN` — is confirmed working. Scapy requires running as root inside the container (capabilities are granted at the container level, not the file level; Python interpreters cannot receive file-level capabilities). The capture container must therefore run as root with the listed capabilities — no other approach works for raw socket access in Python.

**Primary recommendation:** Build bottom-up — DB → API (auth + migration) → Capture PoC → Frontend SPA — with integration test coverage at each step before advancing.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Password storage + verification | API (FastAPI) | DB (PostgreSQL) | Passwords are hashed and stored in DB; API owns the hashing and comparison logic |
| Session management | API (FastAPI/Starlette) | Browser (cookie) | Starlette SessionMiddleware signs and sets the httpOnly cookie; browser auto-sends it |
| First-run redirect guard | API (FastAPI dependency) | Frontend (SvelteKit guard) | API rejects unauthenticated requests 401; frontend redirects to /setup or /login |
| ARP packet capture | Capture service | — | Isolated container with host networking; never touches DB directly |
| ARP data ingest | API (FastAPI) | DB (PostgreSQL) | Capture POSTs to API; API validates and writes to PostgreSQL |
| Static UI serving | Frontend (nginx) | — | SvelteKit builds to static files; nginx serves from /usr/share/nginx/html |
| API routing | API (FastAPI) | — | FastAPI owns all /api/* endpoints; browser fetches by host IP |
| DB schema lifecycle | DB (Alembic migration on startup) | — | `alembic upgrade head` in API container startup command |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.13.x | Backend runtime | Required by aiounifi v91; best async story for 2026 |
| FastAPI | 0.137.1 | HTTP API, OpenAPI, dependency injection | Latest stable Jun 15 2026; async-native; CLAUDE.md says 0.136+ series |
| Pydantic | 2.13.4 | Validation / settings / serialization | Latest stable; FastAPI default; Rust-core 5–50x faster than v1 |
| pydantic-settings | 2.11.0 | .env loading into typed Settings class | Standard 12-factor companion; reads .env automatically |
| Uvicorn | 0.39.0 | ASGI server | Standard FastAPI server; latest stable Jun 3 2026 |
| SQLAlchemy | 2.0.51 | ORM + async query layer | Latest stable Jun 15 2026; 2.0 async mode is the modern standard |
| asyncpg | 0.31.0 | Async PostgreSQL driver | Fastest async driver; SQLAlchemy async uses it |
| Alembic | 1.16.5 | Schema migrations | Latest stable; standard with SQLAlchemy |
| itsdangerous | 2.2.0 | Cookie signing (used by Starlette SessionMiddleware) | Starlette ships with it as a dependency |
| Starlette SessionMiddleware | bundled with FastAPI/Starlette | httpOnly signed session cookie | No separate install; add_middleware call only |
| Scapy | 2.7.0 | ARP sniffing for capture PoC | Latest stable Dec 2025; standard for raw packet work |
| Svelte | 5.56.3 | UI framework | Latest stable Jun 7 2026 |
| @sveltejs/kit | 2.65.2 | App framework, routing, build | Latest stable Jun 16 2026 |
| @sveltejs/adapter-static | 3.0.10 | Build static files for nginx | Standard; produces /build dir for nginx to serve |
| Vite | 8.0.16 | Build tool (bundled with SvelteKit) | SvelteKit 2 uses Vite 6+ internally |
| tailwindcss | 4.3.1 | Utility CSS | Latest stable; used for design system tokens |
| @lucide/svelte | 1.20.0 | Icon library | Replacement for deprecated lucide-svelte; Svelte 5 compatible |
| bits-ui | 2.18.1 | Headless UI primitives (shadcn-svelte uses) | Svelte 5 compatible; 755k weekly downloads |
| @fontsource/inter | 5.2.8 | Self-hosted Inter font | No CDN calls; loads in app |
| shadcn-svelte | 1.3.0 | Component library (Card, Input, Button, Alert) | UI-SPEC mandates this; initialized with npx shadcn-svelte@next init |

[VERIFIED: npm registry] - svelte 5.56.3, @sveltejs/kit 2.65.2, @sveltejs/adapter-static 3.0.10, vite 8.0.16, tailwindcss 4.3.1, @lucide/svelte 1.20.0, bits-ui 2.18.1, @fontsource/inter 5.2.8, shadcn-svelte 1.3.0 — verified via `npm view` June 2026

[VERIFIED: PyPI] - fastapi 0.137.1, pydantic 2.13.4, pydantic-settings 2.11.0, uvicorn 0.39.0, sqlalchemy 2.0.51, alembic 1.16.5, asyncpg 0.31.0, scapy 2.7.0, itsdangerous 2.2.0 — verified via `pip3 index versions` June 2026

**Note on FastAPI version:** CLAUDE.md documents 0.136.x which was accurate when written (April 2026). The current latest is 0.137.1 (Jun 15 2026). Pin to `fastapi>=0.136,<0.138` or `fastapi==0.137.1` in requirements. Either is acceptable.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uvloop | latest | Event loop accelerator | Drop-in asyncio speedup on Linux containers |
| httpx | latest | Async HTTP client | For capture service to POST to API |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Starlette SessionMiddleware | Custom session table + token | Middleware is simpler for single-user; custom gives server-side invalidation but requires a sessions table |
| nginx (standard) | nginxinc/nginx-unprivileged | Unprivileged variant runs as non-root on port 8080; standard variant needs port 80 or root; for port 9999 either works, standard is simpler |
| Starlette SessionMiddleware | PyJWT + manual cookie setting | JWT approach requires managing expiry; Starlette middleware handles signing automatically |
| timescale/timescaledb:latest-pg17 | timescale/timescaledb-ha:pg17-ts2.27 | -ha image includes PostGIS, Patroni, toolkit — overkill for self-hosted single node; standard image is smaller and simpler |

**Installation (backend):**
```bash
pip install fastapi==0.137.1 "uvicorn[standard]==0.39.0" pydantic==2.13.4 pydantic-settings==2.11.0 sqlalchemy==2.0.51 asyncpg==0.31.0 alembic==1.16.5 itsdangerous==2.2.0 scapy==2.7.0 httpx uvloop
```

**Installation (frontend):**
```bash
npm create svelte@latest frontend
# select: SvelteKit, TypeScript, no linting/testing
cd frontend
npm install
npm install -D tailwindcss @sveltejs/adapter-static
npm install @lucide/svelte @fontsource/inter bits-ui
npx shadcn-svelte@next init
```

---

## Package Legitimacy Audit

> Package legitimacy gate run via `gsd-tools query package-legitimacy check` on June 17 2026.

**Note on `SUS` verdicts:** The legitimacy checker flags packages as `SUS` for two reasons here:
1. `too-new` — the package's *latest version* was published within the last 30 days. For all flagged packages, this is because they are **actively maintained major packages** with frequent releases, not new/unknown packages.
2. `unknown-downloads` — PyPI does not expose weekly download stats in the same format as npm; the checker cannot verify PyPI download volume.

Every flagged package below is confirmed from official project repositories and has been verified via `pip3 index versions` or `npm view`.

| Package | Registry | Ecosystem Origin | Source Repo | Verdict | Disposition |
|---------|----------|-----------------|-------------|---------|-------------|
| fastapi 0.137.1 | PyPI | github.com/fastapi/fastapi | github.com/fastapi/fastapi | SUS/too-new | Approved — official repo, verified on archlinux.org |
| pydantic 2.13.4 | PyPI | github.com/pydantic/pydantic | github.com/pydantic/pydantic | SUS/unknown-downloads | Approved — official; FastAPI dependency |
| pydantic-settings 2.11.0 | PyPI | github.com/pydantic/pydantic-settings | github.com/pydantic/pydantic-settings | SUS/unknown-downloads | Approved — official Pydantic companion |
| uvicorn 0.39.0 | PyPI | github.com/Kludex/uvicorn | github.com/encode/uvicorn | SUS/too-new | Approved — standard FastAPI server |
| sqlalchemy 2.0.51 | PyPI | sqlalchemy.org | sqlalchemy.org | SUS/too-new | Approved — well-established ORM |
| alembic 1.16.5 | PyPI | github.com/sqlalchemy/alembic | github.com/sqlalchemy/alembic | SUS/unknown-downloads | Approved — standard SQLAlchemy migrations |
| asyncpg 0.31.0 | PyPI | MagicStack | github.com/MagicStack/asyncpg | SUS/no-repo | Approved — canonical async PG driver; PyPI repo URL missing is a metadata issue |
| scapy 2.7.0 | PyPI | scapy.net | github.com/secdev/scapy | SUS/unknown-downloads | Approved — standard packet library |
| itsdangerous 2.2.0 | PyPI | github.com/pallets/itsdangerous | github.com/pallets/itsdangerous | SUS/unknown-downloads | Approved — Pallets project; bundled Starlette dependency |
| svelte 5.56.3 | npm | github.com/sveltejs/svelte | github.com/sveltejs/svelte | SUS/too-new | Approved — official Svelte org |
| @sveltejs/kit 2.65.2 | npm | github.com/sveltejs/kit | github.com/sveltejs/kit | SUS/too-new | Approved — official Svelte org |
| @sveltejs/adapter-static 3.0.10 | npm | github.com/sveltejs/kit | github.com/sveltejs/kit | OK | Approved |
| vite 8.0.16 | npm | github.com/vitejs/vite | github.com/vitejs/vite | SUS/too-new | Approved — official Vite project |
| tailwindcss 4.3.1 | npm | github.com/tailwindlabs/tailwindcss | github.com/tailwindlabs/tailwindcss | SUS/too-new | Approved — official Tailwind project |
| lucide-svelte 1.0.1 | npm | github.com/lucide-icons/lucide | github.com/lucide-icons/lucide | SUS/deprecated | **REMOVED** — use `@lucide/svelte` instead |
| @lucide/svelte 1.20.0 | npm | github.com/lucide-icons/lucide | github.com/lucide-icons/lucide | SUS/too-new | Approved — official Lucide replacement for lucide-svelte |
| bits-ui 2.18.1 | npm | github.com/huntabyte/bits-ui | github.com/huntabyte/bits-ui | OK | Approved |
| @fontsource/inter 5.2.8 | npm | github.com/fontsource/font-files | github.com/fontsource/font-files | OK | Approved |
| shadcn-svelte 1.3.0 | npm | shadcn-svelte.com | github.com/huntabyte/shadcn-svelte | OK | Approved |

**Packages removed due to SLOP/deprecated verdict:** `lucide-svelte` — deprecated; official replacement is `@lucide/svelte`

**UI-SPEC impact:** The UI-SPEC references `lucide-svelte`. The planner must update all icon imports to use `@lucide/svelte` instead. The import pattern changes from `import { Eye } from 'lucide-svelte'` to `import { Eye } from '@lucide/svelte'`. API surface is identical.

**Packages flagged as suspicious [SUS]:** All the above are false positives from PyPI download-count limitations and active-release timing. All are confirmed from official repositories.

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (any device on LAN)
  │
  │ HTTP :9999
  ▼
┌─────────────────────────────────────────────────────────────────┐
│  frontend  (nginx container)                                    │
│  Serves static HTML/JS/CSS built by SvelteKit adapter-static   │
│  Route guard: /setup /login /dashboard — client-side SPA       │
└─────────────────────────────────────────────────────────────────┘
  │
  │ fetch(import.meta.env.PUBLIC_API_URL + '/api/...')
  │ HTTP :8000  (by host IP)
  ▼
┌─────────────────────────────────────────────────────────────────┐
│  api  (FastAPI + Uvicorn container)                             │
│  POST /api/auth/setup  — first-run password set                 │
│  POST /api/auth/login  — authenticate, set session cookie       │
│  GET  /api/auth/me     — check session (dependency)             │
│  POST /api/capture/arp — capture service posts ARP events here  │
│  Alembic upgrade head runs before Uvicorn starts                │
│  Starlette SessionMiddleware: httpOnly signed session cookie     │
└─────────────────────────────────────────────────────────────────┘
  │                            ▲
  │ asyncpg                    │ httpx POST /api/capture/arp
  ▼                            │
┌───────────────────────┐   ┌─────────────────────────────────────┐
│  db  (TimescaleDB)    │   │  capture  (Scapy container)          │
│  PostgreSQL 17        │   │  network_mode: host                  │
│  settings table       │   │  CAP_NET_RAW + CAP_NET_ADMIN         │
│  bandwidth_metrics    │   │  Runs as root (required for Scapy)   │
│  (hypertable)         │   │  sniff(filter='arp', prn=on_packet)  │
└───────────────────────┘   └─────────────────────────────────────┘
```

### Recommended Project Structure

```
innkeeper/
├── docker-compose.yml
├── .env                        ← gitignored; created from .env.example
├── .env.example                ← committed; documents all vars
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial.py ← creates settings + bandwidth_metrics hypertable
│   └── src/
│       ├── main.py             ← FastAPI app, lifespan, middleware
│       ├── settings.py         ← pydantic-settings BaseSettings
│       ├── database.py         ← engine, async_session_maker, get_db
│       ├── models/
│       │   ├── __init__.py
│       │   ├── base.py         ← DeclarativeBase with AsyncAttrs
│       │   ├── settings.py     ← AppSettings ORM model (stores dashboard password)
│       │   └── bandwidth.py    ← BandwidthMetric ORM model (hypertable)
│       └── routes/
│           ├── auth.py         ← /api/auth/setup, /api/auth/login, /api/auth/me, /api/auth/logout
│           └── capture.py      ← /api/capture/arp
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── svelte.config.js        ← adapter-static, fallback: '200.html'
│   ├── vite.config.ts
│   └── src/
│       ├── lib/
│       │   ├── styles/
│       │   │   └── theme.css   ← UI-SPEC color tokens (from 01-UI-SPEC.md)
│       │   └── api.ts          ← fetch wrapper using PUBLIC_API_URL
│       └── routes/
│           ├── +layout.svelte  ← root layout, theme import
│           ├── +layout.ts      ← export const ssr = false
│           ├── setup/
│           │   └── +page.svelte
│           ├── login/
│           │   └── +page.svelte
│           └── dashboard/
│               └── +page.svelte ← protected; redirects to /login if no session
└── capture/
    ├── Dockerfile
    └── capture.py              ← Scapy sniff + httpx POST loop
```

### Pattern 1: Docker Compose — Mixed Networking

One critical constraint: when a service uses `network_mode: host`, it **cannot** be on the default bridge network. The other services cannot reach the capture container by DNS name, and the capture container reaches the API by the host's IP address.

```yaml
# docker-compose.yml
# Source: [ASSUMED] — standard Docker Compose patterns
services:
  db:
    image: timescale/timescaledb:latest-pg17
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10
    ports:
      - "5432:5432"

  api:
    build: ./backend
    command: bash -c "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      SESSION_SECRET: ${SESSION_SECRET}
    env_file: .env
    ports:
      - "${API_PORT:-8000}:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app   # dev: source mount for hot reload

  frontend:
    build: ./frontend
    ports:
      - "9999:9999"
    depends_on:
      - api

  capture:
    build: ./capture
    network_mode: host   # required for ARP sniffing — no port mappings allowed
    cap_add:
      - NET_RAW
      - NET_ADMIN
    # cap_drop ALL is intentionally NOT done — Scapy needs root inside the container
    environment:
      API_URL: http://127.0.0.1:${API_PORT:-8000}
    depends_on:
      - api
    # volumes for dev:
    volumes:
      - ./capture:/app

volumes:
  pgdata:
```

**Key constraint:** `network_mode: host` is mutually exclusive with `networks`. The capture service cannot be on the bridge network. It reaches the API via `127.0.0.1:8000` (the host loopback — since all services share the host's network namespace).

### Pattern 2: FastAPI Lifespan + Starlette SessionMiddleware

```python
# Source: [CITED: fastapi.tiangolo.com/advanced/events]
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from src.settings import get_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — engine is initialized before this via module import
    yield
    # Shutdown — close engine connections
    from src.database import engine
    await engine.dispose()

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Innkeeper API", lifespan=lifespan)
    
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="innkeeper_session",
        same_site="lax",    # default; protects CSRF without requiring HTTPS
        https_only=False,   # HTTP is acceptable for local LAN use
        # httponly=True is the default — cannot be disabled
    )
    
    from src.routes import auth, capture
    app.include_router(auth.router, prefix="/api/auth")
    app.include_router(capture.router, prefix="/api/capture")
    
    return app

app = create_app()
```

### Pattern 3: pydantic-settings .env Loading

```python
# src/settings.py
# Source: [CITED: docs.pydantic.dev/latest/concepts/pydantic_settings]
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    database_url: str
    session_secret: str
    api_port: int = 8000

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Pattern 4: SQLAlchemy 2.0 Async Engine

```python
# src/database.py
# Source: [CITED: docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from typing import AsyncGenerator

from src.settings import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,  # postgresql+asyncpg://user:pass@db:5432/innkeeper
    echo=False,
    pool_size=10,
    max_overflow=5,
)

async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,  # required for async — objects detach from session after commit
    class_=AsyncSession,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
```

### Pattern 5: SQLAlchemy Models (Mapped style)

```python
# src/models/settings.py
# Source: [CITED: docs.sqlalchemy.org/en/20/orm/declarative_tables.html]
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from src.models.base import Base

class AppSettings(Base):
    """Single-row table for application configuration (password hash, setup state)."""
    __tablename__ = "app_settings"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    setup_complete: Mapped[bool] = mapped_column(default=False)
```

```python
# src/models/bandwidth.py — hypertable target (populated in Phase 3)
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float, func
from src.models.base import Base

class BandwidthMetric(Base):
    """Time-series table (TimescaleDB hypertable) for per-device bandwidth."""
    __tablename__ = "bandwidth_metrics"
    
    time: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        primary_key=True,   # composite PK with device_mac for TimescaleDB
    )
    device_mac: Mapped[str] = mapped_column(String(17), nullable=False, primary_key=True)
    bytes_rx: Mapped[float] = mapped_column(Float, default=0.0)
    bytes_tx: Mapped[float] = mapped_column(Float, default=0.0)
```

### Pattern 6: Alembic Async Migration with TimescaleDB Hypertable

The Alembic init must use the async template: `alembic init -t async alembic`

```python
# alembic/versions/0001_initial.py
# Source: [CITED: alembic.sqlalchemy.org/en/latest/ops.html]
from alembic import op

def upgrade() -> None:
    # 1. Create regular tables
    op.create_table(
        "app_settings",
        op.Column("id", sa.Integer(), nullable=False),
        op.Column("password_hash", sa.String(256), nullable=True),
        op.Column("setup_complete", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # 2. Create the table that will become a hypertable
    op.create_table(
        "bandwidth_metrics",
        op.Column("time", sa.TIMESTAMP(timezone=True), nullable=False),
        op.Column("device_mac", sa.String(17), nullable=False),
        op.Column("bytes_rx", sa.Float(), nullable=False, server_default="0"),
        op.Column("bytes_tx", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("time", "device_mac"),
    )
    
    # 3. Convert to TimescaleDB hypertable
    # Use the new by_range() API (TimescaleDB 2.13+)
    op.execute(
        "SELECT create_hypertable('bandwidth_metrics', by_range('time', INTERVAL '1 week'))"
    )
    
    # 4. Add explicit index so Alembic doesn't try to drop the auto-created one
    # TimescaleDB auto-creates an index on the time column; we must declare it
    # so autogenerate doesn't try to drop it on subsequent migrations
    op.create_index(
        "bandwidth_metrics_time_idx",
        "bandwidth_metrics",
        ["time"],
        unique=False,
    )

def downgrade() -> None:
    op.drop_table("bandwidth_metrics")
    op.drop_table("app_settings")
```

**Critical: Alembic env.py must exclude TimescaleDB internal indexes:**

```python
# alembic/env.py — add this to prevent autogenerate from dropping TimescaleDB indexes
def include_name(name, type_, parent_names):
    """Exclude TimescaleDB auto-created internal indexes from autogenerate."""
    if type_ == "index" and name and name.startswith("_hyper_"):
        return False
    return True

# Pass to context.configure():
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    include_name=include_name,
)
```

[CITED: github.com/sqlalchemy/alembic/discussions/1465] — confirmed workaround for TimescaleDB index autogenerate issue.

### Pattern 7: Session-based Auth — FastAPI Side

```python
# src/routes/auth.py
# Source: [ASSUMED] — standard Starlette session pattern
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
import hashlib
import secrets

router = APIRouter()

class PasswordPayload(BaseModel):
    password: str

async def require_auth(request: Request):
    """FastAPI dependency — raises 401 if not authenticated."""
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")

async def require_setup_complete(request: Request):
    """Redirect-safe check: returns setup_complete state from DB."""
    # Load from AppSettings table
    pass

@router.post("/setup")
async def setup(payload: PasswordPayload, request: Request, db=Depends(get_db)):
    """First-run: set dashboard password. Raises 409 if already set."""
    if not payload.password:
        raise HTTPException(status_code=422, detail="Password cannot be empty")
    # Hash and store; mark setup_complete = True
    # On success: return 200 (frontend redirects to /login)

@router.post("/login")
async def login(payload: PasswordPayload, request: Request, db=Depends(get_db)):
    """Authenticate. Sets session cookie on success."""
    # Compare hash; on match: request.session["authenticated"] = True
    # On failure: raise 401

@router.get("/me")
async def me(request: Request, _=Depends(require_auth)):
    """Returns 200 if authenticated, 401 if not. Frontend uses this to check session."""
    return {"authenticated": True}

@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}
```

**Password hashing:** Use `hashlib.scrypt` (stdlib, no extra dependency) or `passlib[bcrypt]` (if bcrypt is preferred). For a single-user self-hosted tool, `hashlib.scrypt` with a random salt is sufficient. [ASSUMED]

### Pattern 8: Scapy ARP Capture PoC

```python
# capture/capture.py
# Source: [CITED: scapy.net/doc/usage.html] + [ASSUMED: httpx pattern]
import os
import httpx
from scapy.all import sniff, ARP

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

def on_arp_packet(pkt):
    """Called for each captured ARP packet."""
    if ARP in pkt and pkt[ARP].op == 1:  # ARP request (who-has)
        payload = {
            "src_mac": pkt[ARP].hwsrc,
            "src_ip": pkt[ARP].psrc,
            "dst_ip": pkt[ARP].pdst,
        }
        try:
            # Synchronous httpx for simplicity in Phase 1
            httpx.post(f"{API_URL}/api/capture/arp", json=payload, timeout=5.0)
        except Exception as e:
            print(f"[capture] POST failed: {e}")

if __name__ == "__main__":
    print("[capture] Starting ARP sniff on all interfaces...")
    # Must run as root inside container for raw socket access
    # filter='arp' reduces CPU load vs capturing all packets
    sniff(filter="arp", prn=on_arp_packet, store=False)
```

**Why root is required:** Docker grants `CAP_NET_RAW` at the container level. Python cannot receive file-level capabilities, so the Python interpreter must run as root to use raw sockets. This is a Python interpreter constraint, not a Docker limitation. [CITED: py4u.org/blog/python-scapy-sniff-without-root] [ASSUMED for the Python-interpreter specifics]

### Pattern 9: SvelteKit SPA + adapter-static Configuration

```javascript
// svelte.config.js
// Source: [CITED: svelte.dev/docs/kit/single-page-apps]
import adapter from '@sveltejs/adapter-static';

const config = {
  kit: {
    adapter: adapter({
      fallback: '200.html',  // enables SPA client-side routing for all routes
      precompress: true,
    }),
  },
};

export default config;
```

```javascript
// src/routes/+layout.ts — disables SSR globally (SPA mode)
// Source: [CITED: svelte.dev/docs/kit/single-page-apps]
export const ssr = false;
```

```typescript
// src/lib/api.ts — call FastAPI by host IP
// PUBLIC_ prefix is required for browser-accessible env vars in SvelteKit
const API_BASE = import.meta.env.PUBLIC_API_URL ?? 'http://localhost:8000';

export async function apiPost(path: string, body: unknown) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',  // sends the httpOnly session cookie cross-origin
  });
  return res;
}

export async function apiGet(path: string) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
  });
  return res;
}
```

**CRITICAL — SvelteKit env vars:** SvelteKit uses `$env/static/public` for browser-accessible vars in SSR mode, but in adapter-static / SPA mode, Vite's `import.meta.env` is the correct approach. Variables must be prefixed with `PUBLIC_` (SvelteKit convention) or `VITE_` (raw Vite convention). Use `PUBLIC_API_URL` built into the image at build time via `--build-arg`. [CITED: dev.to/hideckies/environment-variables-in-sveltekit-and-vercel-52jc] [ASSUMED for the adapter-static specifics]

### Pattern 10: nginx Config for SvelteKit Static

```nginx
# frontend/nginx.conf
# Source: [CITED: hugosum.com/blog/dockerize-sveltekit-with-adaptor-static-and-nginx]
server {
    listen 9999;
    root /usr/share/nginx/html;
    server_name _;

    location / {
        try_files $uri $uri.html $uri/ /200.html =404;
    }

    error_page 404 /200.html;  # SPA: let client-side router handle 404s

    gzip_static on;
    include /etc/nginx/mime.types;
    
    # Cache static assets aggressively; do not cache the fallback HTML
    location ~* \.(js|css|woff2|png|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location = /200.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
}
```

### Pattern 11: Frontend Dockerfile (multi-stage)

```dockerfile
# frontend/Dockerfile
# Source: [CITED: hugosum.com/blog/dockerize-sveltekit-with-adaptor-static-and-nginx]
FROM node:22-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
ARG PUBLIC_API_URL=http://localhost:8000
ENV PUBLIC_API_URL=$PUBLIC_API_URL
RUN npm run build

FROM nginx:alpine AS release
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 9999
CMD ["nginx", "-g", "daemon off;"]
```

**Note on CORS:** Because the browser fetches `http://<host-ip>:8000` from a page loaded at `http://<host-ip>:9999`, the API and frontend are on **different ports** = **different origins**. FastAPI must include CORS middleware allowing the frontend origin and `credentials: true`. [ASSUMED]

```python
# Add to main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:9999", f"http://{HOST_IP}:9999"],
    allow_credentials=True,  # required for cookies to work cross-origin
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**CORS + cookie constraint:** `credentials: 'include'` in the browser fetch + `allow_credentials=True` in CORS requires `allow_origins` to list explicit origins (not `*`). The `API_URL` env var and the frontend origin must be known at build/startup time. [ASSUMED: this constraint is well-known but the exact env var plumbing is implementation-specific]

### Anti-Patterns to Avoid

- **Putting the capture service on the bridge network:** When `network_mode: host` is set, Docker ignores any `networks:` config on that service. The capture container cannot be in the named network — it uses the host's namespace.
- **Using `docker compose --privileged` instead of cap_add:** `--privileged` grants ALL capabilities and disables seccomp. PLAT-03 explicitly forbids this.
- **Using `@app.on_event("startup")` for lifespan:** Deprecated in FastAPI 0.103+. Use the `@asynccontextmanager lifespan` pattern.
- **Using `sessionmaker` (sync) with async SQLAlchemy:** Always use `async_sessionmaker`. Using sync `sessionmaker` with an async engine produces cryptic errors at query time.
- **Setting `expire_on_commit=True` with async sessions:** Accessing lazy-loaded relationships after `session.commit()` will fail in async mode because the session is already detached. Always set `expire_on_commit=False`.
- **Running `alembic autogenerate` after creating the hypertable without the `include_name` filter:** Autogenerate will see the TimescaleDB-created index and emit a `drop_index` operation on every subsequent migration.
- **Serving SvelteKit SPA without `try_files ... /200.html`:** Without this, refreshing `/dashboard` returns nginx 404.
- **Using `lucide-svelte` instead of `@lucide/svelte`:** `lucide-svelte` is deprecated; `@lucide/svelte` is the replacement.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cookie signing/verification | Custom HMAC signing + base64 | Starlette `SessionMiddleware` (uses itsdangerous) | Timing attack vulnerabilities in naive HMAC comparison; itsdangerous uses constant-time comparison |
| ARP packet parsing | Manually parse Ethernet/ARP bytes | Scapy `ARP` layer | ARP has many edge cases (RARP, Probe, Announcement); Scapy normalizes all variants |
| DB migration runner | `CREATE TABLE` in startup code | Alembic | Alembic handles idempotency, versioning, and rollback; hand-rolled startup DDL is brittle |
| PostgreSQL time-series chunking | Manual table partitioning | TimescaleDB `create_hypertable` | Automatic chunk management, compression, retention, and continuous aggregates |
| Static file serving | Python `FileResponse` per file | nginx | Python serving static files blocks async workers; nginx is 10–100x faster for static assets |
| CSS theming | Inline `style=` on every element | CSS custom properties in `theme.css` | UI-SPEC contract: all tokens in `src/lib/styles/theme.css`, components reference `var(--color-*)` |

**Key insight:** In network infrastructure tooling, the hardest bugs are in protocol parsing and concurrency edge cases. Scapy, Starlette, and TimescaleDB each encapsulate years of hardened knowledge in their respective domains.

---

## Common Pitfalls

### Pitfall 1: CORS blocks cookies from the SPA

**What goes wrong:** Browser sends `fetch` to `http://192.168.1.10:8000/api/auth/login` from `http://192.168.1.10:9999`. Session cookie is set but browser refuses to send it on subsequent requests. Login appears to work but every page then redirects back to `/login`.

**Why it happens:** `credentials: 'include'` requires the API to respond with `Access-Control-Allow-Credentials: true` AND `Access-Control-Allow-Origin` must be the exact requesting origin (not `*`). If `allow_origins=["*"]` is set in the CORSMiddleware, credentials are blocked by the browser.

**How to avoid:** Configure `CORSMiddleware` with `allow_credentials=True` and an explicit list of allowed origins. Read the frontend origin from a `FRONTEND_URL` env var so it works on any machine.

**Warning signs:** Browser console shows "CORS policy: The 'Access-Control-Allow-Credentials' header cannot be set to 'true' when 'Access-Control-Allow-Origin' is '*'".

### Pitfall 2: Alembic autogenerate drops TimescaleDB hypertable indexes

**What goes wrong:** After creating the hypertable migration, developer runs `alembic revision --autogenerate -m "next"`. The generated migration contains `op.drop_index("bandwidth_metrics_time_idx")` or similar. Running this drops a required index.

**Why it happens:** TimescaleDB auto-creates a time column index after `create_hypertable()`. Alembic doesn't know this index exists in the model metadata, so it thinks it should be dropped.

**How to avoid:** (1) Add the explicit `op.create_index("bandwidth_metrics_time_idx", ...)` in the initial migration so Alembic knows about it. (2) Add the `include_name` filter in `alembic/env.py` to exclude `_hyper_*` internal indexes.

**Warning signs:** Generated migration contains `op.drop_index` for the time column index.

### Pitfall 3: `network_mode: host` captures service cannot reach other services by DNS name

**What goes wrong:** Capture service tries to POST to `http://api:8000/api/capture/arp` and gets `Name or service not known`.

**Why it happens:** When `network_mode: host` is set, the container does not join the Docker bridge network. Docker Compose's internal DNS (which resolves service names like `api`) only works within the bridge network. The host-networked container cannot use internal DNS.

**How to avoid:** Configure the capture service to POST to `http://127.0.0.1:${API_PORT}` (host loopback). Since the capture container shares the host's network namespace, `127.0.0.1` reaches all host-bound ports including the `api` container's mapped port.

**Warning signs:** `httpx.ConnectError: [Errno -2] Name or service not known` in capture logs.

### Pitfall 4: Alembic cannot connect during async migration with `run_sync`

**What goes wrong:** `alembic upgrade head` hangs or throws `context has no attribute 'configure'` when using an async engine in `env.py`.

**Why it happens:** Alembic's async template requires `run_async_migrations()` with `async_engine_from_config` and `run_sync`. The default (sync) `env.py` template does not work with an async engine URL.

**How to avoid:** Use `alembic init -t async alembic` to generate the async template. Never use `create_async_engine` in the sync migration path. The Alembic async env.py pattern uses `connectable.connect()` in an async context.

**Warning signs:** Alembic hangs indefinitely or throws `greenlet_spawn has not been called`.

### Pitfall 5: SvelteKit public env var not available at runtime

**What goes wrong:** `import.meta.env.PUBLIC_API_URL` is `undefined` in the built SPA. The fetch goes to `undefined/api/auth/login`.

**Why it happens:** Vite bakes env vars into the JS bundle at build time. If `PUBLIC_API_URL` is not set during `npm run build`, it is not embedded.

**How to avoid:** Pass it as a Docker build arg: `docker build --build-arg PUBLIC_API_URL=http://192.168.1.10:8000`. Or provide a runtime-config endpoint that the SPA fetches on startup to get the API URL. The simplest approach for Phase 1: use a `vite.config.ts` that reads `process.env.PUBLIC_API_URL` with a sensible default.

**Warning signs:** Network requests in browser to `undefinedundefined/api/...`.

### Pitfall 6: Scapy sniff blocks the container — no graceful shutdown

**What goes wrong:** `docker compose down` hangs waiting for the capture container to stop. The Scapy `sniff()` call blocks the main thread forever.

**Why it happens:** `sniff()` with no `timeout` or `count` argument runs indefinitely. Docker sends SIGTERM, but the blocked Python process does not respond.

**How to avoid:** Use `sniff(..., stop_filter=lambda x: should_stop)` or run sniff in a thread with a stop event, handling SIGTERM:

```python
import signal, threading

stop_event = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
sniff(filter="arp", prn=on_arp_packet, store=False,
      stop_filter=lambda _: stop_event.is_set())
```

**Warning signs:** `docker compose down` hangs for 10 seconds before force-killing the capture container.

---

## Code Examples

### Verified patterns from official sources

#### Starlette SessionMiddleware defaults (httpOnly is always true)

```python
# Source: [CITED: starlette.dev/middleware/#sessionmiddleware]
# The httponly flag on the session cookie is ALWAYS True — it cannot be disabled.
# This is hardcoded in Starlette's SessionMiddleware implementation.
# Configuration:
app.add_middleware(
    SessionMiddleware,
    secret_key="your-32-char-secret",
    session_cookie="innkeeper_session",  # default: "session"
    same_site="lax",    # "lax" | "strict" | "none"
    https_only=False,   # adds Secure flag if True — set False for local HTTP
    max_age=None,       # None = session cookie (browser tab lifetime)
)
# Session data is stored client-side, signed with itsdangerous.
# request.session is a dict that's deserialized from the cookie on each request.
```

#### TimescaleDB docker-compose service

```yaml
# Source: [CITED: docs.timescale.com / hub.docker.com/r/timescale/timescaledb]
db:
  image: timescale/timescaledb:latest-pg17
  environment:
    POSTGRES_DB: innkeeper
    POSTGRES_USER: innkeeper
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  volumes:
    - pgdata:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U innkeeper -d innkeeper"]
    interval: 5s
    timeout: 5s
    retries: 10
```

Note: `timescale/timescaledb:latest-pg17` is the standard lightweight image (Alpine-based). The `-ha` variant adds PostGIS, Patroni, and Toolkit — unnecessary for this project. [ASSUMED: recommendation based on image size reasoning; planner should verify final image choice]

#### create_hypertable with new API

```sql
-- TimescaleDB 2.13+ uses by_range() instead of positional column argument
-- Source: [CITED: oneuptime.com/blog/post/2026-01-26-timescaledb-hypertables/view]
SELECT create_hypertable('bandwidth_metrics', by_range('time', INTERVAL '1 week'));

-- For phase 1, 1-week chunks are appropriate:
-- Expected ingest: <1M rows/day (only ARP events in phase 1, traffic metrics in phase 3)
-- 1-week chunk fits easily in memory for a home server
```

#### SvelteKit auth guard pattern

```typescript
// src/routes/dashboard/+page.svelte
// Source: [ASSUMED] — standard SvelteKit pattern for client-side auth guard
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiGet } from '$lib/api';
  
  let loading = $state(true);
  
  onMount(async () => {
    const res = await apiGet('/api/auth/me');
    if (!res.ok) {
      await goto('/login');
    }
    loading = false;
  });
</script>

{#if !loading}
  <main style="padding: 24px">
    <h1>Dashboard</h1>
    <p>Your network monitoring dashboard. Device discovery and traffic monitoring coming in Phase 2.</p>
  </main>
{/if}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` in FastAPI | `@asynccontextmanager lifespan` function | FastAPI 0.93 (2023) | Old decorators deprecated — use lifespan |
| `sessionmaker` (sync) for all SQLAlchemy | `async_sessionmaker` for async | SQLAlchemy 2.0 (2023) | Sync sessionmaker produces runtime errors with async engines |
| `create_hypertable('table', 'time_col')` positional | `create_hypertable('table', by_range('col'))` | TimescaleDB 2.13 (2024) | Old positional API still works but deprecated; new API is explicit |
| `lucide-svelte` | `@lucide/svelte` | Lucide 1.0 (2025) | Old package deprecated; same API, new package name |
| `VITE_` prefix for public env vars | `PUBLIC_` prefix (SvelteKit convention) | SvelteKit 1.0 (2023) | Both work with adapter-static; SvelteKit recommends `PUBLIC_` for env module system |
| `adapter-node` for all SvelteKit apps | `adapter-static` for pure SPA | — | For dashboards without SSR, static adapter + nginx is simpler and lighter |

**Deprecated/outdated:**
- `lucide-svelte`: deprecated; use `@lucide/svelte`
- FastAPI `@app.on_event`: deprecated; use lifespan context manager
- Alembic sync `env.py` template with async engine: use `alembic init -t async`

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Password hashing uses `hashlib.scrypt` (stdlib) | Pattern 7 | If scrypt is too slow on target hardware, switch to passlib/bcrypt; single-user impact is minimal |
| A2 | CORS middleware needs explicit origin list from env var | Pattern 11 / Pitfall 1 | If wrong, cookies won't work cross-origin; but the CORS requirement itself is certain |
| A3 | Capture service reaches API via `127.0.0.1:${API_PORT}` using host loopback | Pattern 1 / Pitfall 3 | Confirmed by Docker network_mode:host semantics; should be reliable on Linux |
| A4 | `timescale/timescaledb:latest-pg17` (standard Alpine image) is preferred over `-ha` image | Standard Stack | `-ha` also works; just larger image; functionally equivalent for this use case |
| A5 | Python interpreter root requirement for Scapy raw sockets cannot be worked around | Pattern 8 / Architecture | This is a documented Python interpreter constraint; alternatives (libpcap with setuid binary) would be significant extra complexity |
| A6 | `PUBLIC_API_URL` baked at frontend build time (Docker `--build-arg`) | Pattern 9 | If the API URL changes post-deploy, the frontend image must be rebuilt; could also use runtime config endpoint as alternative |
| A7 | `SameSite=lax` cookie works for the cross-port same-host scenario | Pitfall 1 | Same-site means same host regardless of port; lax should work; strict could also work |
| A8 | Scapy's synchronous `sniff()` is acceptable for Phase 1 PoC | Pattern 8 | For Phase 2+, async or threaded sniff may be needed; PoC only needs to capture one packet |

---

## Open Questions

1. **API URL configuration mechanism**
   - What we know: `PUBLIC_API_URL` must be baked into the frontend Docker image at build time for adapter-static builds.
   - What's unclear: Should the user supply this as a build-arg in docker-compose.yml, or should there be a runtime mechanism (e.g., the frontend fetches `/api/config` before initializing)?
   - Recommendation: For Phase 1 simplicity, bake it at build time via `args:` in docker-compose.yml. Document in `.env.example`. Revisit if live-reconfiguration is needed.

2. **Which TimescaleDB Docker image variant**
   - What we know: `timescale/timescaledb:latest-pg17` (Alpine-based, ~50MB compressed) vs `timescale/timescaledb-ha:pg17` (Ubuntu-based, ~300MB+ compressed, includes PostGIS/Patroni/Toolkit).
   - What's unclear: Does `-ha` provide any Phase 1 benefit? (Probably not — no PostGIS, no HA needed.)
   - Recommendation: Use `timescale/timescaledb:latest-pg17` for Phase 1. Pin to `2.27.0-pg17` for reproducibility.

3. **Frontend `+page.svelte` auth guard: `onMount` vs `load` function**
   - What we know: In SPA mode (ssr=false), `+page.ts load` functions run client-side. Either approach works.
   - What's unclear: Which is more idiomatic for SvelteKit 2 + Svelte 5 runes?
   - Recommendation: Use `onMount` for Phase 1 simplicity; the load function approach is cleaner long-term but more complex.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | All services | Yes | 29.1.3 | — |
| Docker Compose v2 | All services | Yes | 2.40.3 | — |
| Node.js | Frontend build | Yes (dev machine) | 26.0.0 | — |
| npm | Frontend packages | Yes | 11.12.1 | — |
| Python 3.13 | Backend (runtime) | No (host: 3.9.6) | 3.9.6 (dev machine) | Use Docker container — host Python not needed |
| nmap (Linux target) | Not Phase 1 | n/a | — | — |

**Note:** Python 3.13 is required in the backend Docker container, not on the developer's machine. The dev machine runs `docker compose up`; Python 3.9.6 on the host is irrelevant since the API runs inside the container.

**Missing dependencies with no fallback:** None — all runtime dependencies are containerized.

**Missing dependencies with fallback:** Host Python 3.9.6 (only matters if running backend directly; Docker resolves this).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio + httpx (AsyncClient) |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest backend/tests/ -x -q` |
| Full suite command | `pytest backend/tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | GET /dashboard redirects to /setup when no password set | Integration | `pytest tests/test_auth.py::test_setup_redirect -x` | Wave 0 |
| AUTH-01 | POST /api/auth/setup stores hashed password | Integration | `pytest tests/test_auth.py::test_setup_stores_password -x` | Wave 0 |
| AUTH-02 | GET /api/auth/me returns 401 when not authenticated | Integration | `pytest tests/test_auth.py::test_me_unauthenticated -x` | Wave 0 |
| AUTH-02 | POST /api/auth/login returns session cookie on valid password | Integration | `pytest tests/test_auth.py::test_login_sets_cookie -x` | Wave 0 |
| AUTH-02 | POST /api/auth/login returns 401 on wrong password | Integration | `pytest tests/test_auth.py::test_login_wrong_password -x` | Wave 0 |
| AUTH-03 | GET /api/auth/me returns 200 with valid session cookie | Integration | `pytest tests/test_auth.py::test_session_persists -x` | Wave 0 |
| PLAT-01 | Dashboard reachable on port 9999 from any browser | Smoke (manual) | manual — open browser on different device | — |
| PLAT-02 | `docker compose up` brings all 4 services healthy | Integration (Docker) | `pytest tests/test_compose.py::test_all_services_healthy -x` | Wave 0 |
| PLAT-03 | Capture container starts, sniffs ARP, POSTs to API | Spike (manual) | manual — check logs + DB row | — |
| D-05 | ARP packet captured → POST to API → row in PostgreSQL | Spike gate | `pytest tests/test_capture.py::test_arp_ingest -x` (mocked capture) | Wave 0 |

### Integration Test Pattern — TestClient with SQLite override

```python
# backend/tests/conftest.py
# Source: [CITED: testdriven.io/blog/fastapi-crud] + [ASSUMED: pattern composition]
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

@pytest.fixture
async def test_db():
    """In-memory SQLite for tests — no Docker needed."""
    # NOTE: TimescaleDB-specific SQL (create_hypertable) must be skipped in tests
    # Use a test migration env that mocks TimescaleDB calls
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def client(test_db):
    """FastAPI TestClient with DB override."""
    from src.main import app
    from src.database import get_db
    
    async def override_get_db():
        async with async_sessionmaker(test_db)() as session:
            yield session
    
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

**SQLite for tests:** TimescaleDB-specific SQL (`create_hypertable`) will fail on SQLite. The test migration environment must mock or skip the `create_hypertable` call. Options: (1) conditional in migration based on DB dialect, (2) separate test migration that creates a plain table, (3) mock at the `op.execute` level. [ASSUMED: option 2 is simplest for Phase 1]

### Sampling Rate

- **Per task commit:** `pytest backend/tests/ -x -q --tb=short`
- **Per wave merge:** `pytest backend/tests/ -v` + manual smoke test of `docker compose up`
- **Phase gate:** Full suite green + manual D-05 spike verification (one ARP row in PostgreSQL)

### Wave 0 Gaps

- [ ] `backend/tests/__init__.py` — empty file
- [ ] `backend/tests/conftest.py` — DB + TestClient fixtures
- [ ] `backend/tests/test_auth.py` — AUTH-01/02/03 tests
- [ ] `backend/tests/test_capture.py` — mocked ARP ingest test
- [ ] `backend/tests/test_compose.py` — Docker Compose healthcheck test (or mark manual)
- [ ] `backend/pyproject.toml` — pytest config + pytest-asyncio + httpx + aiosqlite devDeps

---

## Security Domain

> `security_enforcement: true` in config.json, ASVS level 1.

### Applicable ASVS Categories (Level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes — password auth for single user | Password hashing (scrypt/bcrypt), no plaintext storage |
| V3 Session Management | Yes — httpOnly signed cookie | Starlette SessionMiddleware with itsdangerous; session cleared on password change |
| V4 Access Control | Yes — all routes except /setup and /login require auth | FastAPI `require_auth` dependency on all protected routes |
| V5 Input Validation | Yes — password and ARP event inputs | Pydantic models on all request bodies |
| V6 Cryptography | Partial — cookie signing, password hashing | itsdangerous (HMAC-SHA1 by default); use scrypt for password hashing |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Session cookie theft via JS | Information Disclosure | httpOnly=True (Starlette default — not configurable off) |
| CSRF on state-changing endpoints | Tampering | SameSite=lax prevents cross-site form submission; sufficient for local-only LAN tool |
| Password stored in plaintext | Information Disclosure | Hash with scrypt before storing; never store raw password |
| Capture service escaping container | Elevation of Privilege | cap_add NET_RAW + NET_ADMIN only; no other capabilities; never --privileged |
| Unauthenticated ARP ingest | Tampering | /api/capture/arp should require an internal service token or restrict to loopback-only requests (127.0.0.1 source IP check) |
| SQL injection via ARP payload | Tampering | SQLAlchemy ORM parameterizes all queries; no raw SQL for data writes |
| Session fixation | Elevation of Privilege | Regenerate session on login (call `request.session.clear()` before setting `authenticated=True`) |

**ASVS L1 scope note:** This is a self-hosted, single-user, LAN-only tool. CSRF tokens are not required when `SameSite=lax` is set — the cookie will not be sent cross-site. No HTTPS is required for local LAN use (D-12). Password complexity rules are explicitly out of scope (D-09). [ASSUMED: this ASVS-L1 assessment is appropriate for a self-hosted single-user dashboard; a public web app would require stricter controls]

---

## Sources

### Primary (MEDIUM confidence — verified via official package registries and docs)

- [PyPI: fastapi](https://pypi.org/project/fastapi/) — verified 0.137.1 current as of Jun 2026
- [Arch Linux: python-fastapi 0.136.3-1](https://archlinux.org/packages/extra/any/python-fastapi/) — confirmed 0.136.x series real
- [PyPI: sqlalchemy 2.0.51](https://pypi.org/project/sqlalchemy/) — verified via pip3 index versions
- [PyPI: alembic 1.16.5](https://pypi.org/project/alembic/) — verified via pip3 index versions
- [PyPI: scapy 2.7.0](https://pypi.org/project/scapy/) — verified via pip3 index versions
- [npm: svelte 5.56.3](https://www.npmjs.com/package/svelte) — verified via npm view
- [npm: @sveltejs/kit 2.65.2](https://www.npmjs.com/package/@sveltejs/kit) — verified via npm view
- [npm: @lucide/svelte 1.20.0](https://www.npmjs.com/package/@lucide/svelte) — verified; confirmed as replacement for deprecated lucide-svelte
- [hub.docker.com/r/timescale/timescaledb-ha/tags](https://hub.docker.com/r/timescale/timescaledb-ha/tags) — confirmed pg17-ts2.27 tags exist
- [SvelteKit single-page apps docs](https://svelte.dev/docs/kit/single-page-apps) — fallback: '200.html', ssr=false pattern
- [Starlette SessionMiddleware docs](https://starlette.dev/middleware/) — httpOnly default behavior confirmed
- [Alembic Discussion #1465](https://github.com/sqlalchemy/alembic/discussions/1465) — TimescaleDB index autogenerate workaround
- [TimescaleDB hypertable design guide](https://oneuptime.com/blog/post/2026-01-26-timescaledb-hypertables/view) — create_hypertable by_range() API, chunk sizing
- [Dockerize SvelteKit adapter-static + nginx](https://hugosum.com/blog/dockerize-sveltekit-with-adaptor-static-and-nginx) — multi-stage Dockerfile, nginx.conf
- [FastAPI + Async SQLAlchemy 2 + Alembic setup](https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/) — project structure, async engine, Alembic async template

### Secondary (LOW confidence — verified via web search, not official docs)

- [Docker Compose healthcheck patterns](https://eastondev.com/blog/en/posts/dev/20251217-docker-compose-healthcheck/) — depends_on service_healthy pattern
- [Scapy without root](https://www.py4u.org/blog/python-scapy-sniff-without-root/) — confirmed Python interpreter root requirement

---

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM — all packages verified on npm/PyPI; patterns from official docs or authoritative community sources
- Architecture: MEDIUM — topology decisions are locked; patterns verified; CORS+cookie interaction in cross-port same-host scenario has some nuance
- Pitfalls: MEDIUM — TimescaleDB/Alembic pitfall confirmed in official tracker; others are standard Docker/FastAPI patterns

**Research date:** 2026-06-17
**Valid until:** 2026-07-17 (stable ecosystem; packages release frequently but APIs are stable)
