# Phase 5: Module Platform Foundation - Pattern Map

**Mapped:** 2026-06-21
**Files analyzed:** 28 (net-new host infra + retrofit targets)
**Analogs found:** 24 / 28

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `backend/src/host/protocols.py` | utility (Protocol defs) | event-driven | none in current codebase (net-new pattern) | no-analog (verbatim from design doc per CONTEXT.md specifics) |
| `backend/src/host/manifest.py` | model (Pydantic config) | request-response | `backend/src/settings.py` (Pydantic settings/config model) | role-match |
| `backend/src/host/registry.py` | service (singleton map) | request-response | `backend/src/services/identity_resolver.py` (stateless service class with simple API) | partial-match |
| `backend/src/host/loader.py` | service (startup orchestrator) | event-driven | `backend/src/main.py::create_app`/`lifespan` (startup wiring, router mounting, background task spawn) | role-match |
| `backend/src/host/event_bus.py` | service (pub/sub) | event-driven | `_superseded-bolt-on-plugin-model/05-RESEARCH.md` EventBus (carried over verbatim per D-10) | exact (carried over) |
| `backend/src/modules/device_identity/manifest.py` | config | request-response | `backend/src/host/manifest.py` (ModuleManifest itself, once written) | exact |
| `backend/src/modules/device_identity/module.py` | service (factory) | event-driven | `backend/src/main.py::create_app` (construction/wiring pattern, scaled down to one module) | role-match |
| `backend/src/modules/device_identity/interfaces.py` | utility (Protocol) | request-response | none (net-new Protocol pattern, mirrors `host/protocols.py`) | role-match (sibling file) |
| `backend/src/modules/device_identity/models.py` | model | CRUD | `backend/src/models/device.py`, `backend/src/models/discovered_identity.py`, `backend/src/models/device_mac_history.py` (moved verbatim, add `schema="device_identity"`) | exact |
| `backend/src/modules/device_identity/service.py` | service | CRUD + event-driven | `backend/src/services/discovery.py`, `backend/src/services/identity_inference.py` (moved, add EventBus.publish calls) | exact |
| `backend/src/modules/device_identity/migrations/0001_initial.py` | migration | batch | `backend/alembic/versions/0002_device_registry_discovery.py` (table creation in a migration) | role-match |
| `backend/src/modules/devices/manifest.py` | config | request-response | `backend/src/host/manifest.py` | exact |
| `backend/src/modules/devices/module.py` | service (factory) | event-driven | `backend/src/modules/device_identity/module.py` (sibling factory) | exact |
| `backend/src/modules/devices/routes.py` | route/controller | CRUD | `backend/src/routes/devices.py` (moved, swap direct `Device`/`DiscoveredIdentity` queries for `DeviceLookupInterface` calls) | exact |
| `backend/src/modules/devices/models.py` | model | CRUD | `backend/src/models/device.py` (style only — new file is UI-owned columns, not canonical fields) | partial-match |
| `backend/src/modules/devices/migrations/0001_initial.py` | migration | batch | `backend/alembic/versions/0001_initial.py` (simple `create_table`) | role-match |
| `backend/src/modules/traffic/manifest.py` | config | request-response | `backend/src/host/manifest.py` | exact |
| `backend/src/modules/traffic/module.py` | service (factory) | event-driven | `backend/src/modules/device_identity/module.py` | exact |
| `backend/src/modules/traffic/routes.py` | route/controller | streaming + request-response | `backend/src/routes/traffic.py` (moved, SSE stream + historical queries; swap `_resolve_device_macs`' direct `Device`/`DeviceMacHistory` joins for `DeviceLookupInterface.lookup()`) | exact |
| `backend/src/modules/traffic/models.py` | model | CRUD + streaming | `backend/src/models/traffic_flow.py`, `backend/src/models/bandwidth.py` (moved, add `schema="traffic"`) | exact |
| `backend/src/modules/traffic/broadcaster.py` | service (background loop) | streaming | `backend/src/services/traffic_broadcaster.py` (moved, wrapped to satisfy `HasCollector.run_collector(stop_event)`) | exact |
| `backend/src/modules/traffic/migrations/0001_initial.py` | migration | batch | `backend/alembic/versions/0004_traffic_flows.py` (hypertable + continuous aggregates + compression, now schema-qualified per D-14) | exact |
| `backend/src/modules/security/manifest.py` | config | request-response | `backend/src/host/manifest.py` | exact |
| `backend/src/modules/security/module.py` | service (factory) | event-driven | `backend/src/modules/device_identity/module.py` | exact |
| `backend/src/modules/security/routes.py` | route/controller | CRUD | `backend/src/routes/security.py` (moved, same `DeviceLookupInterface` swap pattern as traffic) | exact |
| `backend/src/modules/security/models.py` | model | CRUD | `backend/src/models/security_alert.py`, `backend/src/models/port_scan_result.py` (moved, add `schema="security"`) | exact |
| `backend/src/modules/security/migrations/0001_initial.py` | migration | batch | `backend/alembic/versions/0005_security.py` | exact |
| `backend/src/modules/linked_apps/manifest.py` | config | request-response | `backend/src/host/manifest.py` | role-match |
| `backend/src/modules/linked_apps/linked_manifest.py` | model | request-response | `backend/src/models/app_settings.py` (simple Pydantic/ORM data-holder model) | partial-match |
| `backend/src/main.py` (modified) | config/wiring | event-driven | itself, current version (this session, before/after diff) | exact (modify in place) |
| `backend/alembic/env.py` (modified) | config | batch | itself, current version + `branches.html` `version_locations` pattern | exact (modify in place) |
| `backend/tests/test_module_loader.py` | test | unit | `backend/tests/conftest.py` + existing `test_devices.py`-style fixture usage | role-match |
| `backend/tests/test_event_bus.py` | test | unit | same | role-match |
| `backend/tests/test_module_registry_toggle.py` | test | integration | `backend/tests/conftest.py`'s `client`/`_login` fixtures | role-match |
| `backend/tests/test_linked_apps.py` | test | integration | same | role-match |
| `frontend/src/lib/components/ui/*` (no new primitives expected; reuse) | component | request-response | `frontend/src/lib/components/ui/{alert,alert-dialog,tooltip}/*` (already-built shadcn-svelte primitives from Phase 4) | exact (reuse, no new file) |
| `frontend/src/app.css` (modified — verify token completeness) | config | request-response | itself, current version | exact (modify in place) |

## Pattern Assignments

### `backend/src/host/manifest.py` (config, request-response)

**Analog:** `backend/src/settings.py` (read fully — not shown above but already in project; follows pydantic-settings BaseSettings convention) and the design doc's verbatim `ModuleManifest` stub from CONTEXT.md's `<specifics>` section.

**Core pattern — reproduce exactly (per CONTEXT.md "Claude's Discretion" note: NOT to be reinvented):**
```python
from typing import Literal
from pydantic import BaseModel

class ModuleManifest(BaseModel):
    id: str
    display_name: str
    version: str
    kind: Literal["feature", "support"]
    provides: list[type]      # Protocol types this module satisfies
    requires: list[type]      # Protocol types this module needs from others
    db_schema: str | None
```
**Note:** Pydantic validates `list[type]` permissively (any `type` passes) — the real safety net is `ModuleLoader`'s fail-fast `provides`/`requires` matching, not field validation. Do not add custom Pydantic validators here trying to enforce "this type must be a Protocol" — out of scope.

---

### `backend/src/host/protocols.py` (utility/Protocol defs, event-driven)

**Analog:** none existing in codebase — this is the first `typing.Protocol` usage in the project. Reproduce the design doc's verbatim stub (CONTEXT.md `<specifics>`):
```python
from typing import Protocol, runtime_checkable, Callable
import asyncio
from fastapi import APIRouter

@runtime_checkable
class HasAPIRoutes(Protocol):
    def get_router(self) -> APIRouter: ...

@runtime_checkable
class HasUIPage(Protocol):
    def get_ui_route(self) -> str: ...

@runtime_checkable
class HasEventSubscriptions(Protocol):
    def get_subscriptions(self) -> dict[str, Callable]: ...

@runtime_checkable
class HasCollector(Protocol):
    async def run_collector(self, stop_event: asyncio.Event) -> None: ...
```
**Gotcha:** `@runtime_checkable` is mandatory on every Protocol used with `isinstance()`. `isinstance()` checks existence only, not signature — wrap every capability-wiring call in `loader.py` in its own try/except (see Pitfall 2 in RESEARCH.md) so one bad-signature module doesn't crash startup ambiguously.

---

### `backend/src/host/registry.py` (service, request-response)

**Analog:** synthesized in RESEARCH.md Pattern 3 (no direct codebase precedent for a type→instance map; closest *style* precedent is `backend/src/services/identity_resolver.py`'s small, dependency-free service class). Reproduce exactly:
```python
class ModuleRegistry:
    def __init__(self) -> None:
        self._providers: dict[type, object] = {}

    def register(self, protocol_type: type, instance: object) -> None:
        if protocol_type in self._providers:
            raise RuntimeError(
                f"Provider conflict: {protocol_type} already provided by "
                f"{self._providers[protocol_type]!r}, cannot also register {instance!r}"
            )
        self._providers[protocol_type] = instance

    def resolve(self, protocol_type: type) -> object:
        try:
            return self._providers[protocol_type]
        except KeyError:
            raise RuntimeError(f"No provider registered for {protocol_type}") from None
```

---

### `backend/src/host/loader.py` (service, event-driven)

**Analog:** `backend/src/main.py` lines 14-61 — the existing `lifespan` context manager + `create_app()` is the direct precedent for "startup wiring": creating a background task with its own `asyncio.Event`/cancel-on-shutdown (lines 18-29), and `app.include_router(..., prefix=...)` (lines 55-59) is the precedent for the loader's `HasAPIRoutes` mount-under-`/api/modules/<id>/` step.

**Startup background-task pattern to copy** (`backend/src/main.py` lines 14-31):
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
This is the exact shape `loader.py` must generalize for every `HasCollector` module: one `asyncio.Event` + `asyncio.create_task` per collector, cancelled and awaited on shutdown.

**Router-mount pattern to copy** (`backend/src/main.py` lines 55-59):
```python
app.include_router(auth.router, prefix="/api/auth")
app.include_router(capture.router, prefix="/api/capture")
app.include_router(devices.router, prefix="/api/devices")
```
Generalize to `app.include_router(instance.get_router(), prefix=f"/api/modules/{manifest.id}")` for every `isinstance(instance, HasAPIRoutes)` module, called from the loader instead of hardcoded in `main.py`.

**Topo-sort pattern (use stdlib, not hand-rolled) — RESEARCH.md Pattern 4, verified against `docs.python.org/3/library/graphlib.html`:**
```python
from graphlib import TopologicalSorter, CycleError

def build_load_order(manifests: list[ModuleManifest]) -> list[str]:
    provides_index: dict[type, str] = {}
    for m in manifests:
        for protocol_type in m.provides:
            if protocol_type in provides_index:
                raise RuntimeError(
                    f"provides conflict: {protocol_type} declared by both "
                    f"{provides_index[protocol_type]} and {m.id}"
                )
            provides_index[protocol_type] = m.id

    graph: dict[str, set[str]] = {m.id: set() for m in manifests}
    for m in manifests:
        for required_type in m.requires:
            provider_id = provides_index.get(required_type)
            if provider_id is None:
                raise RuntimeError(f"{m.id} requires {required_type}, no module provides it")
            graph[m.id].add(provider_id)

    try:
        return list(TopologicalSorter(graph).static_order())
    except CycleError as exc:
        raise RuntimeError(f"Module dependency cycle detected: {exc}") from exc
```

**Error handling pattern:** fail loudly at startup (`RuntimeError`), never swallow a missing/conflicting dependency — mirrors the project's existing convention of raising `HTTPException` for client-facing errors (`backend/src/routes/devices.py` lines 82-83, 110-111, 115-116) but at startup time instead of request time, per D-08.

---

### `backend/src/host/event_bus.py` (service, event-driven)

**Analog:** `_superseded-bolt-on-plugin-model/05-RESEARCH.md` — carried over **verbatim** per D-10. Do not modify the pub/sub mechanics.
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
        except Exception as exc:  # noqa: BLE001 — one module must never crash the bus
            print(f"[event_bus] handler {handler} failed: {exc}")
```
**Error handling pattern:** the `_safe_call` broad-except-and-log mirrors `backend/src/services/traffic_broadcaster.py`'s `update_snapshot_loop` (lines 104-109) — "a single transient failure must not kill the long-running loop/bus for the process lifetime."

---

### `backend/src/modules/device_identity/service.py` (service, CRUD + event-driven)

**Analog:** `backend/src/services/discovery.py` — moved wholesale (`upsert_discovered_identity`, `upsert_device_mac_history`, `record_observation`), with one addition: `record_observation` must call `event_bus.publish("new_device", ...)` synchronously at the point of the DB write (RESEARCH.md Anti-Patterns: "publish synchronously at the point of occurrence ... never reconstruct events by polling").

**Dialect-aware upsert pattern to preserve exactly** (`backend/src/services/discovery.py` lines 21-95):
```python
dialect_name = db.bind.dialect.name if db.bind is not None else db.get_bind().dialect.name

if dialect_name == "postgresql":
    stmt = (
        pg_insert(DiscoveredIdentity)
        .values(...)
        .on_conflict_do_update(index_elements=[DiscoveredIdentity.identity_key], set_={...})
    )
else:
    stmt = (
        sqlite_insert(DiscoveredIdentity)
        .values(...)
        .on_conflict_do_update(index_elements=["identity_key"], set_={...})
    )
```
**Critical retrofit note (Pitfall 3):** `record_observation()`'s signature, return type, and commit timing must not change at all during the move — the capture container calls `POST /api/capture/arp` → this function on every observation. Write/confirm integration test coverage of the full path before refactoring internals (RESEARCH.md Pitfall 3).

---

### `backend/src/modules/device_identity/models.py` (model, CRUD)

**Analog:** `backend/src/models/device.py` (full file shown above) — move verbatim, only change: add `__table_args__ = {"schema": "device_identity"}` (or equivalent declarative schema arg) to each model class. Same for `discovered_identity.py` and `device_mac_history.py`.

**Pattern to preserve** (`backend/src/models/device.py` lines 26-58): declarative `Mapped[...]`/`mapped_column` style, `server_default=func.now()` for timestamps, `SAEnum(..., values_callable=lambda enum_cls: [e.value for e in enum_cls])` for string-backed enums — this exact enum convention must be replicated for any new enum columns in any retrofitted module.

---

### `backend/src/modules/devices/routes.py` (route/controller, CRUD)

**Analog:** `backend/src/routes/devices.py` (full file shown above) — move wholesale, then swap every direct `select(Device)`/`select(DiscoveredIdentity)` query for a call through the constructor-injected `DeviceLookupInterface` (or DeviceIdentity's write methods for register/merge).

**Imports pattern to preserve** (lines 1-11):
```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_auth
from src.database import get_db
```
**Auth pattern** (every route handler): `_: None = Depends(require_auth)` as a parameter — this convention is universal across every existing route file (`devices.py`, `traffic.py`, presumably `security.py`) and must be preserved unchanged on every retrofitted + every new module route per RESEARCH.md's ASVS V4 note ("must keep `Depends(require_auth)` exactly as today").

**Error handling pattern** (lines 82-83, 110-111, 115-116):
```python
if identity is None:
    raise HTTPException(status_code=404, detail="Discovered identity not found")
```
Plain `HTTPException` with explicit status/detail — no custom exception hierarchy exists in this codebase; do not introduce one for module routes.

**New addition for this phase:** every module-mounted route must also get `Depends(require_module_enabled(module_id))` (RESEARCH.md Pattern 9) stacked alongside `Depends(require_auth)` — this is the new access-control mechanism replacing FastAPI's inability to un-mount a router at runtime:
```python
def require_module_enabled(module_id: str):
    async def _check(db: AsyncSession = Depends(get_db)) -> None:
        if not await is_module_enabled(db, module_id):
            raise HTTPException(status_code=404, detail="Module disabled")
    return _check
```

---

### `backend/src/modules/traffic/routes.py` (route/controller, streaming + request-response)

**Analog:** `backend/src/routes/traffic.py` (full file shown above) — move wholesale. Key retrofit: `_resolve_device_macs` (lines 46-67) currently does `select(Device)` + `select(DeviceMacHistory)` directly; this entire function's logic moves into `DeviceIdentity`'s `lookup()` implementation, and the call site becomes `await self._device_lookup.lookup(device_id)` instead.

**SSE pattern to preserve unchanged** (lines 70-88) — this is the canonical SSE precedent for any future module needing live streaming:
```python
@router.get("/stream")
async def traffic_stream(request: Request, _: None = Depends(require_auth)):
    async def event_generator():
        last_sent = None
        while True:
            if await request.is_disconnected():
                break
            snapshot = get_latest_snapshot()
            if snapshot != last_sent:
                yield {"event": "snapshot", "data": json.dumps(snapshot)}
                last_sent = dict(snapshot)
            await asyncio.sleep(1)
    return EventSourceResponse(event_generator(), ping=15)
```
**Dialect-fallback pattern to preserve** (lines 109-142) — Postgres reads from a continuous-aggregate view; SQLite (tests) falls back to a portable Python GROUP BY. This same fork must be applied wherever a retrofitted module's queries depend on Postgres/TimescaleDB-only features.

---

### `backend/src/modules/traffic/broadcaster.py` (service/background loop, streaming)

**Analog:** `backend/src/services/traffic_broadcaster.py` (full file shown above) — move wholesale, then wrap to satisfy `HasCollector`:

**Existing loop pattern to preserve exactly** (lines 94-114):
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
This `stop_event`/`asyncio.wait_for(..., timeout=...)` shape is the canonical, CONTEXT.md-cited precedent for every `HasCollector.run_collector(stop_event)` implementation across all modules — wrap this exact function as the module's `run_collector` method rather than rewriting the loop mechanics.

---

### `backend/src/modules/traffic/migrations/0001_initial.py` (migration, batch)

**Analog:** `backend/alembic/versions/0004_traffic_flows.py` (full file shown above) — same hypertable/continuous-aggregate/compression-policy structure, but every table/view name becomes schema-qualified per D-14 (RESEARCH.md Pattern 8):

```sql
CREATE SCHEMA IF NOT EXISTS traffic;
CREATE TABLE traffic.traffic_flows (...);
SELECT create_hypertable('traffic.traffic_flows', by_range('time', INTERVAL '1 week'));
```
The schema-qualified name is passed as a single quoted string — no new function signature for `create_hypertable`/`add_compression_policy`/`add_continuous_aggregate_policy`. Existing data migration step (RESEARCH.md Runtime State Inventory) must add `op.execute("ALTER TABLE traffic_flows SET SCHEMA traffic")` for any pre-existing `public.traffic_flows` rows before this migration's `create_table` runs against a fresh schema — sequence this as its own migration step, not folded silently into the `CREATE TABLE`.

**Alembic branch-label setup** (RESEARCH.md Pattern 7, cited from `alembic.sqlalchemy.org/en/latest/branches.html`):
```ini
[alembic]
version_locations =
    %(here)s/src/modules/device_identity/migrations
    %(here)s/src/modules/devices/migrations
    %(here)s/src/modules/traffic/migrations
    %(here)s/src/modules/security/migrations
    %(here)s/alembic/versions
path_separator = os
```
```bash
alembic revision -m "traffic initial schema" --head=base --branch-label=traffic \
  --version-path=src/modules/traffic/migrations
```
**Gotcha:** `--version-path` is required only on a branch's *first* revision — verify with `git status` that the generated file lands in `src/modules/traffic/migrations/`, not `alembic/versions/`, immediately after running this command (Pitfall 5).

---

### `backend/tests/test_module_loader.py` / `test_event_bus.py` / `test_module_registry_toggle.py` / `test_linked_apps.py` (test, unit/integration)

**Analog:** `backend/tests/conftest.py` — reuse the existing `test_db`/`client`/`_login` fixtures verbatim; no new fixture infrastructure needed for unit tests of `ModuleLoader`/`EventBus`/`ModuleRegistry` (these are pure in-process Python, no DB).

**Integration test pattern to copy** (`conftest.py` lines 48-69 — `client` fixture + `_login` helper):
```python
@pytest.fixture
async def client(test_db):
    from src.database import get_db
    from src.main import app
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async def override_get_db():
        async with session_maker() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

async def _login(client):
    await client.post("/api/auth/setup", json={"password": "correct-password"})
    login_response = await client.post("/api/auth/login", json={"password": "correct-password"})
    assert login_response.status_code == 200
```
Use this exact `client`/`_login` combo for `test_module_registry_toggle.py`'s disabled-module-404 assertion and `test_linked_apps.py`'s manifest-round-trip test.

**Critical unresolved item before writing any retrofit migration:** RESEARCH.md Open Question 1 — spike `schema_translate_map` against this exact `test_db` fixture (lines 33-45) with two throwaway models in two different declared schemas before trusting it across all four real module schemas. Do this as a standalone script, not as a permanent test file, per RESEARCH.md's Wave 0 Gaps.

---

## Shared Patterns

### Authentication
**Source:** `backend/src/auth.py` lines 45-48
**Apply to:** Every route in every module (`devices/routes.py`, `traffic/routes.py`, `security/routes.py`), unchanged.
```python
async def require_auth(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")
```
Used as `_: None = Depends(require_auth)` in every existing route handler — do not introduce a different auth dependency style for module routes.

### Module-Enabled Gate (new this phase, layered alongside auth)
**Source:** RESEARCH.md Pattern 9 (synthesized, carried over from superseded research's Pitfall 1 fix)
**Apply to:** Every module-mounted route, stacked with `require_auth`.
```python
def require_module_enabled(module_id: str):
    async def _check(db: AsyncSession = Depends(get_db)) -> None:
        if not await is_module_enabled(db, module_id):
            raise HTTPException(status_code=404, detail="Module disabled")
    return _check
```

### Database Session Injection
**Source:** `backend/src/database.py` lines 30-32
**Apply to:** Every service/route function needing DB access, across every module.
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
```
Used as `db: AsyncSession = Depends(get_db)` — unchanged convention for all module routes.

### Error Handling (HTTP layer)
**Source:** `backend/src/routes/devices.py` lines 82-83, 110-111, 115-116
**Apply to:** All route files across all modules.
```python
if identity is None:
    raise HTTPException(status_code=404, detail="Discovered identity not found")
```
No custom exception hierarchy exists or should be introduced — plain `HTTPException(status_code=..., detail=...)`.

### Error Handling (background loop layer)
**Source:** `backend/src/services/traffic_broadcaster.py` lines 104-109 and `event_bus.py`'s `_safe_call`
**Apply to:** Every `HasCollector` implementation and every `EventBus` subscriber handler.
```python
try:
    ...
except Exception as exc:  # noqa: BLE001 - must never crash this loop
    print(f"[<module>] <operation> failed: {exc}")
```
Broad-except-and-log — a single module's collector/handler failure must never kill the host process or the bus.

### Dialect-Aware Upsert / Query Fork (Postgres vs SQLite test fixture)
**Source:** `backend/src/services/discovery.py` lines 41-92, `backend/src/routes/traffic.py` lines 109-142
**Apply to:** Any module service/route doing an upsert or relying on Postgres/TimescaleDB-only features (continuous aggregates, schema-qualified hypertables).
```python
dialect_name = db.bind.dialect.name if db.bind is not None else db.get_bind().dialect.name
if dialect_name == "postgresql":
    ...
else:
    ...  # SQLite test-fixture fallback
```

### Enum Column Convention
**Source:** `backend/src/models/device.py` lines 35-38, 47-51
**Apply to:** Any new enum-backed column in any module's models.
```python
type: Mapped[DeviceType] = mapped_column(
    SAEnum(DeviceType, name="devicetype", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
    nullable=False,
)
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/src/host/protocols.py` | utility (Protocol) | event-driven | First `typing.Protocol` usage in this codebase — no prior structural-typing pattern exists; reproduce design doc's verbatim stub, see RESEARCH.md Pattern 1 |
| `backend/src/modules/linked_apps/linked_manifest.py` | model | request-response | No prior "manifest-only, no-code" data shape exists; closest stylistic precedent (`app_settings.py`) is a real ORM-backed settings row, not a static manifest list — use RESEARCH.md's `LinkedModuleManifest` description (`id`, `name`, `icon_url`, `target_url`) as the spec, no codebase analog to copy structure from |
| `backend/src/host/loader.py`'s topo-sort internals | service (algorithm) | batch | No graph algorithm exists anywhere in this codebase today; use stdlib `graphlib.TopologicalSorter` per RESEARCH.md Pattern 4, not a hand-rolled analog |
| Frontend `/settings/modules` page + `/modules/[slug]` route | component/page | CRUD | Phase 4's settings/UI work didn't include a modules list page yet — no direct frontend analog found in repo at time of this mapping; planner should treat this as net-new Svelte work following D-18/D-19's existing token/component conventions (`frontend/src/app.css`, `frontend/src/lib/components/ui/`), not copy from an equivalent existing page |

## Metadata

**Analog search scope:** `backend/src/{main.py,auth.py,database.py,settings.py,models/*,routes/*,services/*}`, `backend/alembic/versions/*`, `backend/tests/conftest.py`, `_superseded-bolt-on-plugin-model/05-RESEARCH.md`, `frontend/src/app.css`, `frontend/src/lib/components/ui/*`
**Files scanned:** ~30 backend files, 5 alembic migrations, 1 conftest, 1 superseded research doc, frontend token/component directories
**Pattern extraction date:** 2026-06-21
</content>
