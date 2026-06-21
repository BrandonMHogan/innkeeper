# Phase 5: Plugin System + Notifications - Pattern Map

> **SUPERSEDED 2026-06-21** — built against the retired bolt-on plugin contract. See `docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md` and the new Phase 5 (Module Platform Foundation) in ROADMAP.md. Kept for history only; do not use as input to planning or execution.


**Mapped:** 2026-06-21
**Files analyzed:** 18 (backend: 11, frontend: 4, tests: 5 representative + 1 migration)
**Analogs found:** 16 / 18

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `backend/src/services/bandwidth_source.py` (model for) `backend/src/plugins/contract.py` | service (Protocol contract) | transform | `backend/src/services/bandwidth_source.py` | exact |
| `backend/src/plugins/manifest.py` | model/utility (Pydantic schema) | transform | `backend/src/models/security_alert.py` (Pydantic-adjacent SAEnum + field shape conventions) + RESEARCH.md Pattern 2 | role-match |
| `backend/src/plugins/loader.py` | service (directory-scan + lifecycle) | event-driven / batch | `backend/src/services/traffic_broadcaster.py` (`update_snapshot_loop`'s stop_event loop) for collector bookkeeping; `backend/src/main.py` lifespan for startup-scan wiring | role-match |
| `backend/src/plugins/event_bus.py` | service (pub/sub) | event-driven | No direct analog (net-new per RESEARCH.md Pattern 3) — closest precedent is `traffic_broadcaster.py`'s async-loop/exception-swallow idiom | partial (see No Analog Found) |
| `backend/src/plugins/events.py` (typed Pydantic event payload models) | model (DTO) | event-driven | `backend/src/routes/capture.py`'s `ArpEventPayload`/`DhcpEventPayload` Pydantic request models | role-match |
| `backend/src/models/plugin_config.py` | model (single/multi-row config + secrets) | CRUD | `backend/src/models/app_settings.py` (single-row config pattern) + `backend/src/models/security_alert.py` (enum/typed-column conventions) | exact (combined) |
| `backend/src/routes/plugins.py` | route/controller | request-response (CRUD: list/enable/config) | `backend/src/routes/devices.py` (CRUD list/register/merge under `require_auth`) | exact |
| `backend/src/plugins/require_plugin_enabled.py` (or inline in `routes/plugins.py`) | middleware (dependency) | request-response | `backend/src/auth.py`'s `require_auth` FastAPI dependency | exact |
| `plugins/notification/manifest.json` | config | n/a (static) | RESEARCH.md Pattern 2 (no in-repo analog — net new) | no analog |
| `plugins/notification/plugin.py` | service (event subscriber) | event-driven | `backend/src/services/discovery.py`'s `upsert_discovered_identity` (publish-at-occurrence trigger site) for wiring; itself is the first plugin module, no prior analog | partial |
| `plugins/notification/senders/ntfy.py` | service (outbound HTTP client) | request-response (external) | No analog — net new; uses RESEARCH.md's cited httpx pattern | no analog |
| `plugins/notification/senders/pushover.py` | service (outbound HTTP client) | request-response (external) | Same as `ntfy.py` | no analog |
| `backend/src/services/device_lost_detector.py` | service (periodic detector loop) | event-driven / batch | `backend/src/services/traffic_broadcaster.py`'s `update_snapshot_loop` (stop_event + asyncio.wait_for cadence) | exact |
| `backend/src/services/bandwidth_anomaly.py` (modify: add `event_bus.publish`) | service (detector, modified) | event-driven | itself (modification, not new file) — wiring follows `discovery.py`'s publish-alongside-alert-write idiom | exact (self) |
| `backend/src/services/discovery.py` (modify: add `event_bus.publish("new_device", ...)`) | service (modified) | event-driven | itself — RESEARCH.md Code Examples section shows exact insertion point | exact (self) |
| `backend/src/main.py` (modify: plugin loader startup, EventBus singleton, device_lost_detector task) | config/bootstrap | event-driven | itself (modification) — same lifespan pattern already used for `update_snapshot_loop` | exact (self) |
| `backend/alembic/versions/000X_plugin_configs.py` | migration | batch | `backend/alembic/versions/0005_security.py` (most recent prior migration, security_alerts table) | role-match |
| `frontend/src/routes/settings/plugins/+page.svelte` | route/page (list+toggle+config) | request-response | `frontend/src/routes/setup/+page.svelte` (form/loading/error state pattern) + dashboard page for list rendering | role-match |
| `frontend/src/routes/plugins/[slug]/+page.svelte` | route/page (generic data-driven) | request-response | `frontend/src/routes/setup/+page.svelte` (script/style structure); no generic-schema-driven analog exists | partial |
| `frontend/src/lib/api.ts` (modify: add plugin API functions) | utility (API client) | request-response | itself — exact existing function shapes (`listDevices`, `apiPost`/`apiGet`) to copy from directly | exact (self) |

## Pattern Assignments

### `backend/src/plugins/contract.py` (Plugin Protocol)

**Analog:** `backend/src/services/bandwidth_source.py`

**Protocol pattern** (lines 1-26, full file):
```python
from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bandwidth import BandwidthMetric


class BandwidthSource(Protocol):
    """D-07: swappable bandwidth-writing interface.
    ...
    """

    async def write_rollup(
        self,
        db: AsyncSession,
        device_mac: str,
        bytes_rx: float,
        bytes_tx: float,
        observed_at: datetime,
    ) -> None: ...
```
**Apply this exact idiom**: `Plugin` as a `typing.Protocol` with typed method signatures, loader introspects rather than requires inheritance (per RESEARCH.md Pattern 1). Concrete plugin modules expose a module-level `PLUGIN` object satisfying the Protocol, mirroring how `PassiveCaptureBandwidthSource` is the one concrete implementation today.

---

### `backend/src/plugins/loader.py` (directory scan + per-plugin task lifecycle)

**Analog (loop/stop-event half):** `backend/src/services/traffic_broadcaster.py`

**Stop-event + wait_for pattern** (lines 94-114):
```python
async def update_snapshot_loop(stop_event: asyncio.Event, session_factory) -> None:
    global _latest_snapshot
    while not stop_event.is_set():
        try:
            async with session_factory() as db:
                _latest_snapshot = await _compute_snapshot(db)
        except Exception as exc:  # noqa: BLE001 - must never crash this loop
            print(f"[traffic_broadcaster] snapshot computation failed: {exc}")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=7)
        except asyncio.TimeoutError:
            pass
```
**Apply exactly per D-03**: one `asyncio.Event` *per plugin_id* (not shared global), stored in a `dict[plugin_id, asyncio.Event]` + `dict[plugin_id, asyncio.Task]` in the loader (per RESEARCH.md Open Question 1 recommendation, locked by D-03's discretion note). Wrap every collector invocation in the loader's own try/except — never trust plugin code to handle its own exceptions (Pitfall 3).

**Analog (startup wiring half):** `backend/src/main.py`
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.database import engine
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    broadcaster_stop_event = asyncio.Event()
    broadcaster_task = asyncio.create_task(update_snapshot_loop(broadcaster_stop_event, session_factory))
    yield
    broadcaster_stop_event.set()
    broadcaster_task.cancel()
    try:
        await broadcaster_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()
```
**Apply this idiom**: plugin directory scan + per-enabled-plugin task creation happens inside this same `lifespan` function, alongside the existing `broadcaster_task` creation — not a separate startup hook.

---

### `backend/src/plugins/event_bus.py` (EventBus — no existing analog, net new)

No in-repo precedent for pub/sub exists. Use RESEARCH.md Pattern 3 verbatim as the canonical reference implementation (already vetted against this codebase's conventions: fire-and-forget `asyncio.create_task`, `except Exception` swallow-and-log matching `traffic_broadcaster`'s defensive style):
```python
import asyncio
from collections import defaultdict

class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: callable) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, payload: dict) -> None:
        for handler in self._subscribers.get(event_type, []):
            asyncio.create_task(self._safe_call(handler, payload))

    @staticmethod
    async def _safe_call(handler, payload):
        try:
            await handler(payload)
        except Exception as exc:  # noqa: BLE001
            print(f"[event_bus] handler {handler} failed: {exc}")
```
**Critical constraint (Pitfall 4):** `publish()` must never `await handler(payload)` directly — always via `asyncio.create_task`, so a slow ntfy.sh call never blocks `discovery.py`'s commit path on the capture-ingest hot path.

---

### `backend/src/plugins/events.py` (typed event payload models)

**Analog:** `backend/src/routes/capture.py`'s payload models (lines 75-122)
```python
class ArpEventPayload(BaseModel):
    src_mac: str
    src_ip: IPvAnyAddress
    dst_ip: IPvAnyAddress

class DhcpEventPayload(BaseModel):
    src_mac: str
    hostname: str | None = None
    requested_ip: str | None = None
    vendor_class_id: str | None = None
```
**Apply this exact convention** for `NewDeviceEvent`, `DeviceLostEvent`, `SecurityAlertEvent`, `TrafficSpikeEvent`, `ModeChangeEvent` — plain `BaseModel` subclasses, `| None = None` for optional fields, no custom validators unless needed. This directly addresses Pitfall 2 (payload schema drift) per D-04's "all five typed this phase" decision.

---

### `backend/src/models/plugin_config.py` (plugin_configs table)

**Analog (single-row/simple-flag half):** `backend/src/models/app_settings.py` (full file, lines 1-15)
```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base

class AppSettings(Base):
    """Single-row table for application configuration (password hash, setup state)."""
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    setup_complete: Mapped[bool] = mapped_column(default=False)
```
**Analog (enum + typed-column half):** `backend/src/models/security_alert.py` (lines 1-44) — copy the `SAEnum(..., values_callable=lambda enum_cls: [e.value for e in enum_cls])` convention if `plugin_configs` needs an enum column (e.g. a `provider` enum for ntfy vs pushover), and the `Boolean`/`String`/`DateTime(timezone=True)` column-type conventions plus `server_default=func.now()` for timestamps.

**Apply:** one row per plugin (`plugin_id` unique key, not a true single-row table like `AppSettings`), `enabled: Mapped[bool]`, `config_json`/`secrets_json` columns (JSON type), per D-01 stored as plaintext — no encryption layer, consistent with `AppSettings.password_hash` already being the only "secret-like" column in the codebase (itself a hash, not reversible — `plugin_config`'s tokens are reversible plaintext, a deliberate difference to flag in the model's docstring).

---

### `backend/src/routes/plugins.py` (plugin management routes)

**Analog:** `backend/src/routes/devices.py` (full file)

**Imports + router pattern** (lines 1-13):
```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_auth
from src.database import get_db
from src.models.device import Device, DeviceType
...
router = APIRouter()
```

**Auth pattern** (line 68, repeated per route):
```python
@router.get("/")
async def list_devices(_: None = Depends(require_auth), db: AsyncSession = Depends(get_db)):
```

**CRUD/serialize pattern** (lines 28-42, 67-98):
```python
def _serialize_device(device: Device) -> dict:
    return {"id": device.id, "identity_key": device.identity_key, ...}

@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_device(payload: DeviceRegisterPayload, _: None = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DiscoveredIdentity).where(DiscoveredIdentity.id == payload.identity_id))
    identity = result.scalar_one_or_none()
    if identity is None:
        raise HTTPException(status_code=404, detail="Discovered identity not found")
    ...
    db.add(device)
    await db.commit()
    return _serialize_device(device)
```
**Apply directly** for `GET /api/plugins`, `POST /api/plugins/{id}/enable`, `POST /api/plugins/{id}/config`: same `Depends(require_auth)` + `Depends(get_db)` signature, same `_serialize_*` private helper convention, same 404-on-missing-row + `HTTPException` idiom. For secret masking on GET responses, write a `_serialize_plugin_config` that returns `"••••" + value[-4:]` instead of the raw secret column value (per D-01 / Pitfall security note — never echo plaintext back).

---

### `require_plugin_enabled` dependency (Pitfall 1 mitigation)

**Analog:** `backend/src/auth.py`'s `require_auth` (full file, lines 45-48)
```python
async def require_auth(request: Request) -> None:
    """FastAPI dependency — raises 401 if the session is not authenticated."""
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")
```
**Apply exactly this shape** for `require_plugin_enabled(plugin_id: str)`: a dependency factory returning a callable that queries `plugin_configs.enabled` for `plugin_id` and raises `HTTPException(404)` (per RESEARCH.md Pitfall 1's recommendation (a) — register all plugin routers at startup, gate per-request via dependency rather than attempting `app.router.routes` removal). Combine with `Depends(require_auth)` on the same route, same calling convention as `devices.py`.

---

### `plugins/notification/plugin.py` + senders (ntfy/pushover)

**Analog (trigger/wiring site):** `backend/src/services/discovery.py`'s `upsert_discovered_identity` (lines 21-106), specifically the alert-write block (lines 97-106):
```python
if is_new_identity:
    db.add(
        SecurityAlert(
            device_id=None,
            type=SecurityAlertType.UNKNOWN_DEVICE,
            severity=SecurityStatus.WARNING,
            message="Unknown device joined the network",
        )
    )
    await db.commit()
```
**Apply per RESEARCH.md Code Examples**: insert `await event_bus.publish("new_device", {...})` immediately after this existing `db.commit()` — do not replace the `SecurityAlert` write, add alongside it (durable row stays the record of truth; the event is the immediate-delivery side channel).

**Outbound HTTP pattern** (no in-repo analog — use RESEARCH.md's cited, externally-sourced code verbatim):
```python
# ntfy.sh — Source: https://docs.ntfy.sh/publish/
import httpx

async def send_ntfy(topic: str, message: str, title: str | None = None, token: str | None = None) -> bool:
    headers = {}
    if title:
        headers["X-Title"] = title
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"https://ntfy.sh/{topic}", content=message.encode("utf-8"), headers=headers)
        return resp.status_code == 200
```
```python
# Pushover — Source: https://pushover.net/api
import httpx

async def send_pushover(api_token: str, user_key: str, message: str, title: str | None = None) -> bool:
    data = {"token": api_token, "user": user_key, "message": message}
    if title:
        data["title"] = title
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post("https://api.pushover.net/1/messages.json", data=data)
        return resp.status_code == 200 and resp.json().get("status") == 1
```
**Apply with `httpx.AsyncClient(timeout=10.0)`** matching the existing `Don't Hand-Roll`/Pitfall 4 guidance — never an unbounded-timeout client. Treat non-2xx/429 as non-fatal: log and drop (Pitfall 5), never retry-loop.

---

### `backend/src/services/device_lost_detector.py`

**Analog:** `backend/src/services/traffic_broadcaster.py`'s `update_snapshot_loop` (same lines as above, 94-114) — copy the exact `while not stop_event.is_set(): try/except Exception ... asyncio.wait_for(stop_event.wait(), timeout=N)` skeleton. Query target is `Device.last_seen` (see `backend/src/models/device.py` line 42, `last_seen: Mapped[datetime]`) compared against a threshold (D-05: tune during implementation), firing `event_bus.publish("device_lost", {...})` per device that crosses the threshold (debounce/track already-fired state to avoid re-firing every tick — not explicitly covered by D-05, flag for planner discretion).

---

### `backend/src/services/bandwidth_anomaly.py` (modify — add publish call)

**Analog:** itself, `check_bandwidth_anomaly()` (full file, lines 16-86) is a pure read+compute function with **no side effects today** ("Pure read+compute query, no side effects (no alert insert, no status write) — callers act on the returned bool", line 19-20). The actual `SecurityAlert` write + `event_bus.publish("traffic_spike", ...)` call per D-06 belongs in the **caller** (`backend/src/routes/capture.py`'s `queue_daily_scans`, lines 425-513, specifically the existing `SecurityAlert(type=SecurityAlertType.SUSPICIOUS_TRAFFIC, ...)` write at lines 472-479) — add `await event_bus.publish("traffic_spike", {...})` immediately after that existing `db.add(SecurityAlert(...))` block, mirroring discovery.py's alongside-not-instead-of pattern.

---

## Shared Patterns

### Authentication
**Source:** `backend/src/auth.py` lines 45-48 (`require_auth`)
**Apply to:** every route in `backend/src/routes/plugins.py` (management routes), same `Depends(require_auth)` signature as `devices.py`/`security.py`/`traffic.py`. Plugin-registered routes (PLUG-01 optional API routes) additionally need `Depends(require_plugin_enabled(plugin_id))`.

### Error Handling
**Source:** `backend/src/routes/devices.py` lines 80-83 (404-on-missing pattern), `backend/src/services/traffic_broadcaster.py` lines 108-109 (`except Exception as exc: print(...)` loop-survival pattern)
**Apply to:** all plugin route handlers (404 via `HTTPException`) and all background loops (`device_lost_detector`, plugin collectors, `event_bus._safe_call`) — never let an exception kill a long-running async loop or block a publishing caller.

### Dialect-aware DB writes
**Source:** `backend/src/services/discovery.py` lines 30-95 (`pg_insert`/`sqlite_insert` upsert pattern)
**Apply to:** only if `plugin_configs` needs an upsert-on-toggle path (e.g. `POST /api/plugins/{id}/enable` creating-or-updating a row) — otherwise a simple `select` + `if None: db.add() else: update-in-place` (per `devices.py`'s simpler CRUD style) is sufficient and preferred, since `plugin_configs` rows are seeded once per discovered plugin, not concurrently raced like capture ingest.

### Frontend API client functions
**Source:** `frontend/src/lib/api.ts` lines 20-37, 72-84 (`listDevices`, `ackAlert` shapes)
**Apply to:** new `listPlugins()`, `enablePlugin(id, enabled)`, `savePluginConfig(id, config)`, `getPluginPage(slug)` functions — same `apiGet`/`apiPost` wrapper calls, same `if (!res.ok) throw new Error(...)` guard, same `Promise<unknown>`/typed-payload return shape.

### Frontend page structure (forms, loading/error state)
**Source:** `frontend/src/routes/setup/+page.svelte` (full file)
**Apply to:** `/settings/plugins/+page.svelte` and `/plugins/[slug]/+page.svelte` — `$state()` runes for `loading`/`errorMessage`, `async function handleSubmit` with `event.preventDefault()`, inline `style=` attributes using the existing `var(--color-*)` CSS variable tokens (no separate CSS framework in use), `role="alert"` error block convention.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/src/plugins/event_bus.py` | service | event-driven | No pub/sub exists anywhere in the codebase yet (Phases 1-4 use poll-and-broadcast or durable-row patterns only) — RESEARCH.md Pattern 3's synthesized code is the canonical reference, not a real-codebase analog |
| `plugins/notification/manifest.json` | config | n/a | First manifest file of its kind — no JSON config files precedent in-repo beyond `docker-compose.yml`/`pyproject.toml`; follow RESEARCH.md Pattern 2's documented shape |
| `plugins/notification/senders/ntfy.py` | service | request-response (external) | First outbound-to-third-party-service client in the codebase (all existing httpx-adjacent code is inbound capture ingest); use RESEARCH.md's cited official-docs code verbatim |
| `plugins/notification/senders/pushover.py` | service | request-response (external) | Same as above |
| `frontend/src/routes/plugins/[slug]/+page.svelte` | route/page | request-response | No generic/schema-driven page exists; every existing frontend page (`dashboard`, `setup`, `login`) is hand-coded for one fixed purpose — the planner should treat `05-UI-SPEC.md` as primary source for this file's structure, with `setup/+page.svelte` only as a baseline for state-management idiom |

## Metadata

**Analog search scope:** `backend/src/{models,routes,services}/`, `backend/src/{auth,main}.py`, `backend/alembic/versions/`, `frontend/src/{routes,lib}/`
**Files scanned:** 11 backend services/models, 4 backend routes, `auth.py`, `main.py`, 3 frontend files, 1 migration listing
**Pattern extraction date:** 2026-06-21
