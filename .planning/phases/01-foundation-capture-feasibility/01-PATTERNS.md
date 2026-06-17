# Phase 1: Foundation + Capture Feasibility - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 31
**Analogs found:** 0 / 31

## Greenfield Notice

This is Phase 1 of a brand-new project. The repository currently contains only planning docs (`.planning/`), an empty OpenSpec scaffold (`openspec/specs/.gitkeep`, `openspec/changes/`), `CLAUDE.md`, and `.env`/`.env.example`. **There is no existing application source code anywhere in the repo** — no `backend/`, `frontend/`, or `capture/` directories exist yet. A full Glob/Grep search for controllers, services, models, routes, and components confirmed zero matches.

Consequently, **every file in this phase has no in-repo analog.** This PATTERNS.md instead maps each new file to the verified pattern from `01-RESEARCH.md` that the planner/implementor should follow, since RESEARCH.md is the canonical source of pattern truth for Phase 1. All patterns below are copied verbatim from RESEARCH.md (with citations preserved) rather than extracted from codebase analogs.

**Important for future phases:** Once Phase 1 lands, Phase 2+ pattern-mapping runs should treat the files created here (`backend/src/routes/auth.py`, `backend/src/models/*.py`, `frontend/src/routes/*/+page.svelte`, etc.) as the first real in-repo analogs.

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|-----------------|----------------|
| `docker-compose.yml` | config | batch (orchestration) | none | no-analog |
| `.env.example` | config | — | `.env.example` (exists, empty/minimal) | partial (file exists but not yet populated per D-14) |
| `backend/Dockerfile` | config | file-I/O (build) | none | no-analog |
| `backend/pyproject.toml` | config | — | none | no-analog |
| `backend/alembic.ini` | config | — | none | no-analog |
| `backend/alembic/env.py` | migration | batch | none | no-analog |
| `backend/alembic/versions/0001_initial.py` | migration | batch | none | no-analog |
| `backend/src/main.py` | config/provider | request-response | none | no-analog |
| `backend/src/settings.py` | config | — | none | no-analog |
| `backend/src/database.py` | service | CRUD (connection mgmt) | none | no-analog |
| `backend/src/models/base.py` | model | — | none | no-analog |
| `backend/src/models/settings.py` | model | CRUD | none | no-analog |
| `backend/src/models/bandwidth.py` | model | CRUD/streaming (time-series) | none | no-analog |
| `backend/src/routes/auth.py` | controller/route | request-response | none | no-analog |
| `backend/src/routes/capture.py` | controller/route | event-driven (ingest) | none | no-analog |
| `backend/tests/__init__.py` | test | — | none | no-analog |
| `backend/tests/conftest.py` | test | — | none | no-analog |
| `backend/tests/test_auth.py` | test | request-response | none | no-analog |
| `backend/tests/test_capture.py` | test | event-driven | none | no-analog |
| `backend/tests/test_compose.py` | test | batch (infra) | none | no-analog |
| `capture/Dockerfile` | config | file-I/O (build) | none | no-analog |
| `capture/capture.py` | service | streaming/event-driven | none | no-analog |
| `frontend/Dockerfile` | config | file-I/O (build) | none | no-analog |
| `frontend/nginx.conf` | config | request-response (static serve) | none | no-analog |
| `frontend/package.json` | config | — | none | no-analog |
| `frontend/svelte.config.js` | config | — | none | no-analog |
| `frontend/vite.config.ts` | config | — | none | no-analog |
| `frontend/src/lib/styles/theme.css` | utility | — | `.planning/phases/01-foundation-capture-feasibility/01-UI-SPEC.md` (design tokens defined there, not code) | partial (spec exists, no CSS file yet) |
| `frontend/src/lib/api.ts` | service/utility | request-response | none | no-analog |
| `frontend/src/routes/+layout.svelte` | component | — | none | no-analog |
| `frontend/src/routes/+layout.ts` | config | — | none | no-analog |
| `frontend/src/routes/setup/+page.svelte` | component | request-response | none | no-analog |
| `frontend/src/routes/login/+page.svelte` | component | request-response | none | no-analog |
| `frontend/src/routes/dashboard/+page.svelte` | component | request-response (guarded) | none | no-analog |

## Pattern Assignments

Since no codebase analogs exist, each assignment below references the verified RESEARCH.md pattern number and reproduces the exact excerpt the planner should hand to implementors.

### `backend/src/main.py` (config/provider, request-response)

**Source:** RESEARCH.md Pattern 2 (FastAPI Lifespan + SessionMiddleware), Pattern 11 CORS addendum

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

from src.settings import get_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from src.database import engine
    await engine.dispose()

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Innkeeper API", lifespan=lifespan)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="innkeeper_session",
        same_site="lax",
        https_only=False,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[...],  # explicit frontend origin(s); never "*" with credentials
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from src.routes import auth, capture
    app.include_router(auth.router, prefix="/api/auth")
    app.include_router(capture.router, prefix="/api/capture")

    return app

app = create_app()
```

**Anti-pattern to avoid:** `@app.on_event("startup")` is deprecated (FastAPI 0.103+) — always use the `lifespan` context manager (RESEARCH.md "State of the Art" table).

---

### `backend/src/settings.py` (config)

**Source:** RESEARCH.md Pattern 3 (pydantic-settings .env loading)

```python
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

---

### `backend/src/database.py` (service, CRUD/connection management)

**Source:** RESEARCH.md Pattern 4 (SQLAlchemy 2.0 Async Engine)

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator
from src.settings import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False, pool_size=10, max_overflow=5)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
```

**Critical anti-pattern:** Never use sync `sessionmaker` with an async engine, and never set `expire_on_commit=True` in async mode (RESEARCH.md "Anti-Patterns to Avoid").

---

### `backend/src/models/base.py`, `backend/src/models/settings.py`, `backend/src/models/bandwidth.py` (model, CRUD)

**Source:** RESEARCH.md Pattern 5 (SQLAlchemy Mapped-style models)

```python
# settings.py
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from src.models.base import Base

class AppSettings(Base):
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    setup_complete: Mapped[bool] = mapped_column(default=False)
```

```python
# bandwidth.py — hypertable target (populated Phase 3, schema locked now per D-16)
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float, func
from src.models.base import Base

class BandwidthMetric(Base):
    __tablename__ = "bandwidth_metrics"
    time: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), primary_key=True)
    device_mac: Mapped[str] = mapped_column(String(17), nullable=False, primary_key=True)
    bytes_rx: Mapped[float] = mapped_column(Float, default=0.0)
    bytes_tx: Mapped[float] = mapped_column(Float, default=0.0)
```

---

### `backend/alembic/versions/0001_initial.py` + `backend/alembic/env.py` (migration, batch)

**Source:** RESEARCH.md Pattern 6 (Alembic Async Migration with TimescaleDB Hypertable)

```python
def upgrade() -> None:
    op.create_table("app_settings", ...)
    op.create_table("bandwidth_metrics", ...)
    op.execute("SELECT create_hypertable('bandwidth_metrics', by_range('time', INTERVAL '1 week'))")
    op.create_index("bandwidth_metrics_time_idx", "bandwidth_metrics", ["time"], unique=False)

def downgrade() -> None:
    op.drop_table("bandwidth_metrics")
    op.drop_table("app_settings")
```

```python
# env.py — REQUIRED to avoid autogenerate dropping TimescaleDB internal indexes
def include_name(name, type_, parent_names):
    if type_ == "index" and name and name.startswith("_hyper_"):
        return False
    return True

context.configure(connection=connection, target_metadata=target_metadata, include_name=include_name)
```

**Critical pitfall (RESEARCH.md Pitfall 2):** Without `include_name`, every subsequent `alembic revision --autogenerate` emits a `drop_index` against the TimescaleDB-managed index. Must use `alembic init -t async alembic` for the async template (Pitfall 4) — the default sync template breaks with an async engine URL.

---

### `backend/src/routes/auth.py` (controller/route, request-response)

**Source:** RESEARCH.md Pattern 7 (Session-based Auth)

```python
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter()

class PasswordPayload(BaseModel):
    password: str

async def require_auth(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")

@router.post("/setup")
async def setup(payload: PasswordPayload, request: Request, db=Depends(get_db)):
    if not payload.password:
        raise HTTPException(status_code=422, detail="Password cannot be empty")
    # hash (hashlib.scrypt), store, mark setup_complete=True

@router.post("/login")
async def login(payload: PasswordPayload, request: Request, db=Depends(get_db)):
    # compare hash; on match: request.session["authenticated"] = True
    # on failure: raise 401

@router.get("/me")
async def me(request: Request, _=Depends(require_auth)):
    return {"authenticated": True}

@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}
```

**Security note (ASVS V3, Security Domain section):** call `request.session.clear()` before setting `authenticated=True` on login to prevent session fixation. Hash with `hashlib.scrypt` (stdlib) — never store plaintext passwords.

---

### `backend/src/routes/capture.py` (controller/route, event-driven ingest)

**No direct RESEARCH.md code example provided** — derive from Pattern 7's router structure, validate with a Pydantic model matching the capture payload shape from Pattern 8 (`src_mac`, `src_ip`, `dst_ip`), and apply the security control from the Security Domain table: *"Unauthenticated ARP ingest... restrict to loopback-only requests (127.0.0.1 source IP check)"* since the capture container POSTs via `127.0.0.1` per Pitfall 3 / Pattern 1.

---

### `capture/capture.py` (service, streaming/event-driven)

**Source:** RESEARCH.md Pattern 8 (Scapy ARP Capture PoC) + Pitfall 6 (graceful shutdown)

```python
import os, httpx
from scapy.all import sniff, ARP

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

def on_arp_packet(pkt):
    if ARP in pkt and pkt[ARP].op == 1:
        payload = {"src_mac": pkt[ARP].hwsrc, "src_ip": pkt[ARP].psrc, "dst_ip": pkt[ARP].pdst}
        try:
            httpx.post(f"{API_URL}/api/capture/arp", json=payload, timeout=5.0)
        except Exception as e:
            print(f"[capture] POST failed: {e}")

if __name__ == "__main__":
    sniff(filter="arp", prn=on_arp_packet, store=False)
```

**Required addition (Pitfall 6 — graceful shutdown, otherwise `docker compose down` hangs):**

```python
import signal, threading
stop_event = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
sniff(filter="arp", prn=on_arp_packet, store=False, stop_filter=lambda _: stop_event.is_set())
```

**Must run as root inside the container** (CAP_NET_RAW at container level, not file level — Python interpreter constraint per Pattern 8 note).

---

### `frontend/src/lib/api.ts` (service/utility, request-response)

**Source:** RESEARCH.md Pattern 9 (SvelteKit SPA fetch wrapper)

```typescript
const API_BASE = import.meta.env.PUBLIC_API_URL ?? 'http://localhost:8000';

export async function apiPost(path: string, body: unknown) {
  return fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  });
}

export async function apiGet(path: string) {
  return fetch(`${API_BASE}${path}`, { credentials: 'include' });
}
```

**Pitfall 5 warning:** `PUBLIC_API_URL` must be baked in at Docker build time via `--build-arg`; if unset, requests silently go to `undefined/api/...`.

---

### `frontend/src/routes/dashboard/+page.svelte` (component, guarded request-response)

**Source:** RESEARCH.md "SvelteKit auth guard pattern" code example

```svelte
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
  <main>
    <h1>Dashboard</h1>
    <p>Your network monitoring dashboard. Device discovery and traffic monitoring coming in Phase 2.</p>
  </main>
{/if}
```

`frontend/src/routes/setup/+page.svelte` and `login/+page.svelte` follow the same component shape, calling `apiPost('/api/auth/setup', ...)` / `apiPost('/api/auth/login', ...)` respectively, then `goto()` on success per D-08's first-run flow.

---

### `frontend/svelte.config.js`, `frontend/src/routes/+layout.ts` (config)

**Source:** RESEARCH.md Pattern 9

```javascript
// svelte.config.js
import adapter from '@sveltejs/adapter-static';
const config = {
  kit: { adapter: adapter({ fallback: '200.html', precompress: true }) },
};
export default config;
```

```typescript
// +layout.ts
export const ssr = false;
```

---

### `frontend/nginx.conf` (config, request-response static serve)

**Source:** RESEARCH.md Pattern 10

```nginx
server {
    listen 9999;
    root /usr/share/nginx/html;
    location / { try_files $uri $uri.html $uri/ /200.html =404; }
    error_page 404 /200.html;
    gzip_static on;
    include /etc/nginx/mime.types;
}
```

**Anti-pattern:** Omitting `try_files ... /200.html` breaks client-side routing on refresh (404 on `/dashboard`).

---

### `docker-compose.yml` (config, orchestration)

**Source:** RESEARCH.md Pattern 1 (Docker Compose — Mixed Networking)

Key structural rules to copy verbatim:
- `capture` service: `network_mode: host`, `cap_add: [NET_RAW, NET_ADMIN]`, no `ports:`, no `networks:` (mutually exclusive with host mode)
- `capture` reaches API via `API_URL: http://127.0.0.1:${API_PORT:-8000}` — never the `api` Docker DNS name (Pitfall 3)
- `api` command: `bash -c "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000"` (D-15)
- `db` healthcheck: `pg_isready` with `depends_on: condition: service_healthy` gating `api`
- Source dirs mounted as volumes for dev hot-reload (D-18): `./backend:/app`, `./capture:/app`

---

## Shared Patterns

### Session Auth Dependency
**Source:** RESEARCH.md Pattern 7 — `require_auth` FastAPI dependency
**Apply to:** All protected routes except `/api/auth/setup` and `/api/auth/login`
```python
async def require_auth(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")
```

### CORS + Credentialed Cookies
**Source:** RESEARCH.md Pattern 11 / Pitfall 1
**Apply to:** `backend/src/main.py` and every frontend fetch in `api.ts`
- `allow_origins` must be an explicit list (never `"*"`) when `allow_credentials=True`
- Every frontend fetch call must include `credentials: 'include'`

### Async SQLAlchemy Session Discipline
**Source:** RESEARCH.md Pattern 4 / Anti-Patterns
**Apply to:** `database.py`, all route handlers using `Depends(get_db)`
- `async_sessionmaker` only, `expire_on_commit=False` always

### TimescaleDB-safe Alembic Migrations
**Source:** RESEARCH.md Pattern 6 / Pitfall 2
**Apply to:** `alembic/env.py`, every future migration touching `bandwidth_metrics`
- `include_name` filter excluding `_hyper_*` indexes; explicit `op.create_index` for the time column

### Capture Container Security Posture
**Source:** RESEARCH.md D-03 / Security Domain table
**Apply to:** `capture/Dockerfile`, `docker-compose.yml` capture service
- `cap_add: [NET_RAW, NET_ADMIN]` only; never `--privileged`; container runs as root (required by Python raw-socket constraint) but capability set stays minimal

## No Analog Found

All 31 files in this phase have no in-repo analog — this is the first phase of a greenfield project. Use the RESEARCH.md-sourced patterns above instead of searching for codebase precedent.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (all 31 files listed in File Classification above) | various | various | No application source code exists in the repository yet; only planning docs, empty `openspec/` scaffold, and `.env`/`.env.example` are present |

## Metadata

**Analog search scope:** Repository root (excluding `.git/`, `.planning/`); confirmed via `find` listing and `Glob`/`Grep` patterns for controllers, services, routes, models, components
**Files scanned:** 0 application source files found (repo is pre-code)
**Pattern extraction date:** 2026-06-16
