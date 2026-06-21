---
phase: 05-plugin-system-notifications
plan: 04
subsystem: api
tags: [module-host, traffic, device-identity, alembic-branch, schema-isolation, retrofit, capability-protocol, timescaledb]

# Dependency graph
requires:
  - phase: 05-plugin-system-notifications
    plan: 03
    provides: "DeviceLookupInterface contract (lookup(identifier) -> DeviceInfo | None, DeviceInfo.macs MAC-rotation-aware union), device_identity Alembic branch pattern"
provides:
  - "backend/src/modules/traffic/ — Traffic feature module owning its own traffic Postgres schema, mounted via ModuleLoader at /api/modules/traffic/"
  - "HasCollector-wired broadcaster loop (run_collector) — first concrete proof of MOD-05's collector capability, started/stopped by ModuleLoader instead of main.py's hardcoded lifespan block"
  - "DeviceLookupInterface numeric-device_id lookup support (Rule 1 extension to Plan 03's contract) — Plan 05 (Security retrofit) can rely on this same extended contract"
  - "main.py's split module-loading pattern (sync router-mounting at create_app() time + async HasCollector-task wiring at lifespan startup) — reusable template for any future module with a HasCollector capability"
affects: [05-05-security-retrofit]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazily-resolved session factory (_live_session_factory, re-imports src.database fresh on every call) for any module factory's create() that constructs its own DB session outside per-request FastAPI dependency injection — required because _load_native_modules() runs at create_app()/module-import time, before any per-test monkeypatch of src.database.engine can take effect."
    - "Module loading split into two phases: a synchronous create_app()-time phase (router mounting only — httpx's ASGITransport never runs FastAPI lifespan events, so routes must be mounted eagerly for tests to see them) and an async lifespan-startup-time phase (HasCollector task creation — asyncio.create_task() requires a running event loop, which only exists once lifespan() executes)."
    - "Continuous aggregates dropped and recreated schema-qualified after a hypertable's ALTER TABLE...SET SCHEMA move, rather than relying on search_path — the materialized view's query string references the base table by name at creation time and is not automatically rewritten by a later base-table schema move."

key-files:
  created:
    - backend/src/modules/traffic/__init__.py
    - backend/src/modules/traffic/manifest.py
    - backend/src/modules/traffic/module.py
    - backend/src/modules/traffic/routes.py
    - backend/src/modules/traffic/models.py
    - backend/src/modules/traffic/broadcaster.py
    - backend/src/modules/traffic/migrations/0001_initial.py
  modified:
    - backend/alembic.ini
    - backend/src/main.py
    - backend/src/models/__init__.py
    - backend/src/modules/device_identity/interfaces.py
    - backend/src/modules/device_identity/module.py
    - backend/src/routes/capture.py
    - backend/src/services/bandwidth_anomaly.py
    - backend/src/services/bandwidth_source.py
    - backend/tests/conftest.py
    - backend/tests/test_bandwidth_aggregates.py
    - backend/tests/test_bandwidth_anomaly.py
    - backend/tests/test_bandwidth_query.py
    - backend/tests/test_capture.py
    - backend/tests/test_models_scaffold.py
    - backend/tests/test_traffic_destinations.py
    - backend/tests/test_traffic_stream.py
    - frontend/src/lib/api.ts
  deleted:
    - backend/src/routes/traffic.py
    - backend/src/services/traffic_broadcaster.py
    - backend/src/models/traffic_flow.py
    - backend/src/models/bandwidth.py

key-decisions:
  - "DeviceLookupInterface extended to resolve numeric-string identifiers against Device.id first (before MAC/identity_key) — Plan 03's documented contract only covered MAC/identity_key lookups, but Traffic's pre-retrofit routes are keyed by the integer device_id path param. This is a backward-compatible extension (MAC/identity_key lookups are unaffected since real MACs/identity_keys are never all-digit strings in this codebase), not a breaking change to Plan 03's contract — Plan 05 (Security retrofit) can rely on the same extended lookup() for its own device_id-keyed routes."
  - "Lazy session-factory resolution (_live_session_factory) in both device_identity/module.py and traffic/module.py's create() — replaces binding a session factory to a literal `engine` object captured once at create()-time. _load_native_modules() runs once at create_app()/module-import time (before pytest's per-test monkeypatch of src.database.engine takes effect), so a factory that captures `engine` immediately would permanently miss the test fixture's migrated, schema-translated database. Re-resolving src.database.engine fresh on every lookup()/run_collector() tick lets the per-test monkeypatch (added to tests/conftest.py's client fixture this plan) take effect."
  - "main.py's module loading split into two phases instead of one: _load_native_modules() runs synchronously inside create_app() (mounts routers — required since httpx's ASGITransport, used by every test fixture, never runs FastAPI lifespan events) and a new _start_collectors() runs inside lifespan()'s startup phase (creates the actual asyncio.Task for any HasCollector-satisfying module instance — required since asyncio.create_task() raises RuntimeError without a running event loop, which create_app() never has). The loader's existing per-capability try/except (D-03) already silently skips collector_tasks when called with no running loop, so this split required no change to host/loader.py itself."
  - "bandwidth_anomaly.py's check_bandwidth_anomaly() keeps an inline same-session Device/DeviceMacHistory query instead of routing through DeviceLookupInterface — it's called from capture.py's queue_daily_scans mid-transaction with an already-open db session; DeviceLookupInterface's lookup() uses its own independently-constructed session (via the lazy session factory), which would not see uncommitted state from the caller's open transaction. This is a deliberate, documented exception to T-05-11's general retrofit rule, scoped to same-transaction callers only — routes.py's per-request consumers (device_bandwidth, device_destinations) go through DeviceLookupInterface.lookup() exactly as the threat model specifies."
  - "Continuous aggregates (bandwidth_hourly/daily/weekly/monthly) are dropped before the ALTER TABLE...SET SCHEMA move and recreated schema-qualified afterward, rather than relying on TimescaleDB resolving the unqualified materialized-view query string via search_path post-move — documented in migrations/0001_initial.py's module docstring as the defensive choice against T-05-13 (continuous-aggregate staleness)."

patterns-established:
  - "Pattern: any module factory's create() that constructs its own DB session outside FastAPI's per-request Depends(get_db) injection (i.e. anything called from ModuleLoader.load() or a background collector loop) must resolve src.database.engine lazily on every call, not capture it once at create()-time — otherwise it permanently misses any later monkeypatch of the engine (e.g. tests/conftest.py's client fixture), since _load_native_modules() runs at create_app()/module-import time, before fixtures apply."
  - "Pattern: a HasCollector-satisfying module's task creation must happen in lifespan()'s startup phase, never in create_app() — asyncio.create_task() requires a running event loop that create_app() (called once at plain Python import time) never has. Router mounting (HasAPIRoutes) stays in create_app() since httpx's ASGITransport test fixture never runs lifespan events."

requirements-completed: [MOD-05, MOD-07]

# Metrics
duration: 95min
completed: 2026-06-21
---

# Phase 5 Plan 04: Module Platform Foundation — Traffic Retrofit Summary

**Retrofitted Traffic (SSE live feed, bandwidth/destinations queries, the snapshot broadcaster) into a real feature module owning its own `traffic` Postgres schema, with `_resolve_device_macs` deleted entirely in favor of `DeviceLookupInterface.lookup()` and the broadcaster loop now a `HasCollector` capability started by `ModuleLoader` — full 134/134 backend suite green.**

## Performance

- **Duration:** 95 min
- **Started:** 2026-06-21T21:48:00Z
- **Completed:** 2026-06-21T23:23:00Z
- **Tasks:** 1 completed (single tdd="true" task per plan)
- **Files modified:** 24 (7 created, 17 modified, 4 deleted)

## Accomplishments

- **Traffic feature module package** (`backend/src/modules/traffic/`): `models.py` relocates `TrafficFlow`/`BandwidthMetric` with `__table_args__ = {"schema": "traffic"}`; `broadcaster.py` relocates `update_snapshot_loop`/`_compute_snapshot`/`get_latest_snapshot` verbatim, adding a `run_collector(stop_event, session_factory)` thin wrapper satisfying `HasCollector`; `routes.py` relocates the SSE/bandwidth/destinations router, deleting `_resolve_device_macs` entirely — every MAC-resolution call site now calls `get_device_lookup().lookup(str(device_id))` directly (module-level accessor pair `set_device_lookup`/`get_device_lookup`, mirroring Plan 03's `devices/routes.py` pattern) and reads `.macs` off the returned `DeviceInfo`; `module.py`/`manifest.py` provide the `create(deps)` factory (`requires=[DeviceLookupInterface]`, `db_schema="traffic"`).
- **New Alembic branch** (`traffic_0001`, chained after `device_identity_0001`): `CREATE SCHEMA IF NOT EXISTS traffic`, live `ALTER TABLE traffic_flows/bandwidth_metrics SET SCHEMA traffic`, and the four continuous aggregates (`bandwidth_hourly/daily/weekly/monthly`) dropped and recreated schema-qualified against `traffic.bandwidth_metrics`/`traffic.bandwidth_hourly` etc. — documented in the migration's docstring as the defensive choice against continuous-aggregate staleness (T-05-13), since a materialized view's query string is not automatically rewritten by a later base-table schema move.
- **main.py's module loading split into two phases** (Rule 1 fix, required for Traffic's `HasCollector` capability to work at all): `_load_native_modules()` still runs synchronously inside `create_app()` (mounts routers — httpx's `ASGITransport`, used by every test fixture, never runs FastAPI lifespan events, so routes must be mounted eagerly); a new `_start_collectors()` runs inside `lifespan()`'s startup phase and creates the actual `asyncio.Task` for any `HasCollector`-satisfying module instance, since `asyncio.create_task()` raises `RuntimeError` without a running event loop (which `create_app()` never has). The loader's existing per-capability try/except (D-03) already silently swallows that `RuntimeError` at `create_app()` time and skips `collector_tasks` — no change to `host/loader.py` itself was needed.
- **DeviceLookupInterface extended** (Rule 1 fix): `_find_device()` now matches numeric-string identifiers against `Device.id` first, before falling back to MAC/identity_key — Plan 03's documented contract only covered MAC/identity_key lookups, but Traffic's pre-retrofit routes are keyed by the integer `device_id` path param. Backward-compatible (real MACs/identity_keys are never all-digit strings in this codebase).
- **Lazy session-factory resolution** (Rule 1 fix, both `device_identity/module.py` and `traffic/module.py`): `create()` now passes a `_live_session_factory` callable that re-imports `src.database` and constructs a fresh `async_sessionmaker` on every invocation, instead of capturing the literal `engine` object once at `create()`-time. `_load_native_modules()` runs once at `create_app()`/module-import time, before pytest's per-test `monkeypatch.setattr(database_module, "engine", test_db)` (added to `tests/conftest.py`'s `client` fixture this plan) can take effect — a factory binding `engine` immediately would permanently miss the test fixture's migrated, schema-translated database.
- **Transitive consumer updates**: `capture.py`/`bandwidth_source.py`/`models/__init__.py` import `TrafficFlow`/`BandwidthMetric` from `modules.traffic.models`; `bandwidth_anomaly.py` keeps an inline same-session `Device`/`DeviceMacHistory` query (documented exception to T-05-11, since it shares a transaction with `capture.py`'s `queue_daily_scans` and would not see uncommitted state through the lookup interface's independently-constructed session); the full traffic/bandwidth test suite and `frontend/src/lib/api.ts` move to the `/api/modules/traffic/` prefix.

## Task Commits

Single `tdd="true"` task, committed across two atomic commits (tests and implementation co-located per this codebase's established practice; split into two commits only due to an initial staging-path mistake, not a TDD red/green split):

1. **New traffic module package** (models, broadcaster, routes, module, manifest, migration) - `3e53104` (feat)
2. **Wiring into main.py + transitive consumer updates** (alembic.ini, capture.py, bandwidth_anomaly.py, bandwidth_source.py, models/__init__.py, device_identity's lookup extension, full test suite, frontend api.ts) - `c42b69e` (feat)

## Files Created/Modified

**Created:**
- `backend/src/modules/traffic/{models,broadcaster,routes,module,manifest}.py` — the full Traffic feature module package
- `backend/src/modules/traffic/migrations/0001_initial.py` — new Alembic branch, live schema-move + continuous-aggregate recreation migration

**Modified:**
- `backend/src/main.py` — module loading split into sync (router mounting) + async (HasCollector task creation) phases; `traffic` added to the `ModuleLoader` manifest/factory list; old `traffic.router`/`update_snapshot_loop`/hardcoded `broadcaster_stop_event`/`broadcaster_task` lifespan block removed
- `backend/alembic.ini` — `version_locations` gains `src/modules/traffic/migrations`
- `backend/src/models/__init__.py`, `backend/src/routes/capture.py`, `backend/src/services/{bandwidth_anomaly,bandwidth_source}.py` — `TrafficFlow`/`BandwidthMetric` import paths only (`bandwidth_anomaly.py` also gained an inline same-session MAC-resolution helper, replacing its import of the deleted `routes/traffic.py::_resolve_device_macs`)
- `backend/src/modules/device_identity/{interfaces,module}.py` — `DeviceLookupInterface`/`_find_device()` extended for numeric-device_id lookups; `create()` switched to lazy session-factory resolution
- `backend/tests/conftest.py` — `schema_translate_map` gains `"traffic": None`; `client` fixture monkeypatches `src.database.engine` to `test_db`
- `backend/tests/{test_bandwidth_aggregates,test_bandwidth_anomaly,test_bandwidth_query,test_capture,test_models_scaffold,test_traffic_destinations,test_traffic_stream}.py` — import paths + `/api/traffic/` → `/api/modules/traffic/` path updates; `test_models_scaffold.py`'s `test_metadata_create_all` updated for `bandwidth_metrics`'s new schema-qualified table-metadata key
- `frontend/src/lib/api.ts` — `openTrafficStream()`/`getDeviceBandwidth()`/`getNetworkBandwidth()`/`getDeviceDestinations()` updated to `/api/modules/traffic/...`

**Deleted:**
- `backend/src/routes/traffic.py`, `backend/src/services/traffic_broadcaster.py`, `backend/src/models/traffic_flow.py`, `backend/src/models/bandwidth.py` — fully relocated into `backend/src/modules/traffic/`

## Decisions Made

See `key-decisions` in frontmatter for full rationale on: the `DeviceLookupInterface` numeric-device_id extension, the lazy session-factory pattern, the two-phase module-loading split, `bandwidth_anomaly.py`'s same-session exception to the DeviceLookupInterface retrofit rule, and the continuous-aggregate drop/recreate migration choice.

## Issues Encountered

- **`DeviceLookupInterface.lookup()` never actually worked through the production-wired `ModuleLoader.load()` path in tests before this plan** — Plan 03's own unit test (`test_device_identity_lookup.py`) constructs `DeviceIdentityModule` directly with the test's `session_maker`, bypassing `create()`'s production engine entirely, and Plan 03's `devices` routes only ever call `list_all(db)`/`register(db, ...)`/`merge(db, ...)`, which take the per-request `db` session as an explicit argument and never exercise `lookup()`'s internal session factory. Plan 04 is the first plan to actually call `lookup()` through the real `ModuleLoader`-constructed instance from an HTTP route, surfacing a latent "no such table" failure (the module-level `src.database.engine` is a separate, unmigrated in-memory SQLite DB from the `test_db` fixture's engine). Fixed via the lazy session-factory pattern (see Decisions) plus a `client` fixture monkeypatch — both documented as reusable patterns for Plan 05.
- **`asyncio.create_task()` for the `HasCollector` capability would have crashed `create_app()` at plain Python import time** (no running event loop exists there) had the loader's existing per-capability try/except (D-03, Plan 01) not already caught and logged the `RuntimeError`. Confirmed this safety net works as designed, then added the lifespan-startup-time `_start_collectors()` retry so the broadcaster loop actually starts in production (where `create_app()` never has a loop, but `lifespan()` always does).
- **A stale pre-existing test** (`test_models_scaffold.py::test_metadata_create_all`) asserted the literal unqualified table name `"bandwidth_metrics"` in `Base.metadata.tables.keys()` — broken by this plan's schema-qualification (the key becomes `"traffic.bandwidth_metrics"`), exactly the same class of issue Plan 03 noted for `device_identity`-qualified tables but never circled back to fix for this specific assertion. Fixed (Rule 1, directly caused by this plan's schema move) by splitting the assertion into unqualified-tables and the schema-qualified `bandwidth_metrics` key separately.
- **Initial commit staging mistake** (non-functional): the first `git add` invocation listed `backend/src/models/bandwidth.py` (a path being deleted) without realizing git's rename-detection needed the new `modules/traffic/` directory staged in the same operation to pair renames correctly; split into two commits as a result. No functional impact — both commits are part of the same single `tdd="true"` task's atomic unit of work.

## User Setup Required

None — no external service configuration required. As with Plan 03, the new `traffic_0001` Alembic migration's live `ALTER TABLE ... SET SCHEMA` + continuous-aggregate drop/recreate is Postgres/TimescaleDB-specific SQL, verified by inspection and a successful `alembic heads`/`history` resolution against the full migration chain (single head: `traffic_0001`), not executed against a live Postgres instance in this sandboxed worktree (no Docker Postgres container available). The plan's `<verification>` block's "confirm via the Lima VM/docker-compose live stack" step — live traffic ingest populating `traffic.traffic_flows`/`traffic.bandwidth_metrics` post-migration, SSE feed and bandwidth charts rendering with real data — is a manual, human-run verification step outside this executor's scope, flagged here for the orchestrator/user to run before this migration is applied to any real environment with live data.

## Next Phase Readiness

- Traffic is a real feature module, proven to boot through `ModuleLoader` with its `HasCollector` capability actually starting in `lifespan()`, and its `DeviceLookupInterface` consumption documented exactly as Plan 05 (Security retrofit) will need to consume the same (now numeric-device_id-extended) contract.
- The `traffic` Alembic branch pattern (live `ALTER TABLE ... SET SCHEMA` + continuous-aggregate drop/recreate, chained after `device_identity_0001`) is now a second proven, reusable template for Plan 05's own Security schema migration.
- The lazy session-factory pattern and the two-phase module-loading split (sync router-mounting + async collector-task creation) are both documented, reusable fixes any future `HasCollector`-satisfying module (including Plan 05's Security module, if it ever needs a background loop) should follow from the start, rather than rediscovering the same `asyncio.create_task()`/test-monkeypatch gaps this plan hit.
- No blockers identified for downstream plans. The capture container's traffic-ingest path (`/api/capture/traffic`) is confirmed behavior-identical pre/post retrofit at the test level (all `test_traffic_stream.py`/`test_capture.py` assertions unchanged except import paths); live-stack verification against a real Postgres + Lima VM is recommended before this migration is applied outside a test environment, per the plan's own `<verification>` block.

## Known Stubs

None — every artifact this plan produces is wired to real data sources; no hardcoded empty/placeholder values were introduced.

## Threat Flags

None — every new surface this plan introduces was already covered by the plan's own `<threat_model>` (T-05-11, T-05-12, T-05-13), and no additional security-relevant surface (new endpoints, auth paths, file access, schema changes at trust boundaries) was introduced beyond what that threat model already accounts for. The `DeviceLookupInterface` numeric-device_id extension is a backward-compatible read-path addition to an existing in-process Protocol boundary, not a new trust boundary.

---
*Phase: 05-plugin-system-notifications (directory name predates the module-platform pivot; phase content is "Module Platform Foundation" per ROADMAP.md)*
*Completed: 2026-06-21*
