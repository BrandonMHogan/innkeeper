---
phase: 05-plugin-system-notifications
plan: 03
subsystem: api
tags: [module-host, device-identity, alembic-branch, schema-isolation, retrofit, capability-protocol]

# Dependency graph
requires:
  - phase: 05-plugin-system-notifications
    plan: 01
    provides: "host/{protocols,manifest,registry,loader,event_bus,dependencies}.py module-host contract, require_module_enabled, schema_translate_map PASS verdict"
provides:
  - "backend/src/modules/device_identity/ — support module owning Device/DiscoveredIdentity/DeviceMacHistory in its own device_identity Postgres schema, record_observation/upsert logic, DeviceLookupInterface Protocol"
  - "backend/src/modules/devices/ — thin feature module, zero direct canonical-data queries, mounted via ModuleLoader at /api/modules/devices/"
  - "DeviceLookupInterface contract (lookup(identifier) -> DeviceInfo | None) — documented contract Plans 04/05 build their Traffic/Security retrofits against"
  - "device_identity Alembic branch (device_identity_0001, branch_labels=(\"device_identity\",)) — live ALTER TABLE SET SCHEMA pattern for Plans 04/05's own schema migrations"
affects: [05-04-traffic-retrofit, 05-05-security-retrofit]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level EventBus singleton (event_bus_singleton.py) shared between capture.py's hot-path caller (outside the ModuleLoader graph) and the ModuleLoader-instantiated DeviceIdentityModule"
    - "Devices routes.py module-level set_device_identity()/get_device_identity() accessor pair — lets DevicesModule's constructor inject the ModuleLoader-resolved DeviceLookupInterface instance into route handlers without re-threading FastAPI Depends() per-request"
    - "Alembic multi-branch version_locations using os.pathsep-separated paths (version_path_separator = os requires ':'-joined paths, not space-joined, in version_locations)"
    - "schema_translate_map applied at create_async_engine() execution_options for in-memory SQLite test fixtures to support schema-qualified ORM models without a real Postgres schema"

key-files:
  created:
    - backend/src/modules/device_identity/__init__.py
    - backend/src/modules/device_identity/manifest.py
    - backend/src/modules/device_identity/interfaces.py
    - backend/src/modules/device_identity/models.py
    - backend/src/modules/device_identity/service.py
    - backend/src/modules/device_identity/module.py
    - backend/src/modules/device_identity/identity_resolver.py
    - backend/src/modules/device_identity/identity_inference.py
    - backend/src/modules/device_identity/event_bus_singleton.py
    - backend/src/modules/device_identity/migrations/0001_initial.py
    - backend/src/modules/devices/__init__.py
    - backend/src/modules/devices/manifest.py
    - backend/src/modules/devices/module.py
    - backend/src/modules/devices/routes.py
    - backend/tests/test_device_identity_lookup.py
    - backend/tests/test_devices_module_boot.py
  modified:
    - backend/alembic.ini
    - backend/src/data/vendor_catalog.py
    - backend/src/models/__init__.py
    - backend/src/models/pending_scan_request.py
    - backend/src/models/port_scan_result.py
    - backend/src/models/security_alert.py
    - backend/src/routes/capture.py
    - backend/src/routes/security.py
    - backend/src/routes/traffic.py
    - backend/src/services/port_rules.py
    - backend/src/services/traffic_broadcaster.py
    - backend/src/main.py
    - backend/tests/conftest.py
    - backend/tests/test_devices.py
    - backend/tests/test_bandwidth_anomaly.py
    - backend/tests/test_capture.py
    - backend/tests/test_discovery.py
    - backend/tests/test_identity_inference.py
    - backend/tests/test_identity_resolver.py
    - backend/tests/test_mac_history.py
    - backend/tests/test_port_rules.py
    - backend/tests/test_security_alerts.py
    - backend/tests/test_security_scan.py
    - backend/tests/test_traffic_stream.py
    - frontend/src/lib/api.ts
  deleted:
    - backend/src/models/device.py
    - backend/src/models/discovered_identity.py
    - backend/src/models/device_mac_history.py
    - backend/src/services/discovery.py
    - backend/src/services/identity_inference.py
    - backend/src/services/identity_resolver.py
    - backend/src/routes/devices.py

key-decisions:
  - "EventBus singleton: a bare module-level instance in event_bus_singleton.py, shared between capture.py's hot ingest path (outside the ModuleLoader graph entirely) and DeviceIdentityModule's own construction — avoids fragmenting publish/subscribe into two disconnected buses, since capture.py is not itself a module in this phase's scope."
  - "DeviceLookupInterface contract: lookup(identifier) accepts a MAC or an identity_key string, returns DeviceInfo | None — None (not a raised exception) is the documented 'not found' signal, matching the pre-retrofit routes' scalar_one_or_none() convention. macs field is the MAC-rotation-aware union (current last_known_mac + full DeviceMacHistory), moved here from routes/traffic.py::_resolve_device_macs per RESEARCH.md Pattern 6 — Plans 04/05 must consume this field instead of re-implementing the union."
  - "Devices' write paths (register/merge) implemented as DeviceIdentityModule methods, not on the DeviceLookupInterface Protocol itself — the Protocol only carries the read contract (lookup); writes are accessed via a module-level set_device_identity()/get_device_identity() accessor pair in devices/routes.py, injected once by DevicesModule's constructor at ModuleLoader wiring time."
  - "/api/modules/devices/ is the new canonical mount prefix (D-09), replacing /api/devices/ — main.py derives the prefix from the manifest id (device_id.replace('_','-')), frontend api.ts and test_devices.py updated to match."

patterns-established:
  - "Pattern: Alembic version_locations with multiple paths must be os.pathsep-joined (':' on macOS/Linux), not space-joined, when version_path_separator = os is set — space-joining silently collapses to a single malformed path and alembic heads/history return empty with no error."
  - "Pattern: when a model's schema-qualifying retrofit deletes the old unqualified model file, every other model with a ForeignKey pointing at the relocated table's unqualified name must be updated to the schema-qualified target in the same task — these are blocking issues (Rule 3), not deferred work, since the app cannot import/migrate without them."

requirements-completed: [MOD-02, MOD-04, MOD-05, MOD-07]

# Metrics
duration: 70min
completed: 2026-06-21
---

# Phase 5 Plan 03: Module Platform Foundation — DeviceIdentity/Devices Retrofit Summary

**Retrofitted today's device discovery/registry logic into a real DeviceIdentity support module (own Postgres schema, DeviceLookupInterface, record_observation's hot-path contract frozen byte-for-byte) and a thin Devices feature module mounted through Plan 01's ModuleLoader at /api/modules/devices/ — zero regressions across two bisection-sequenced full-suite runs.**

## Performance

- **Duration:** 70 min
- **Started:** 2026-06-21T18:05:00Z
- **Completed:** 2026-06-21T19:15:00Z
- **Tasks:** 2 completed
- **Files modified:** 47 (16 created, 24 modified, 7 deleted)

## Accomplishments

- **Task 1 (DeviceIdentity extraction):** Moved `Device`/`DiscoveredIdentity`/`DeviceMacHistory` into `modules/device_identity/models.py`, each gaining `__table_args__ = {"schema": "device_identity"}`; moved `record_observation`/`upsert_discovered_identity`/`upsert_device_mac_history` verbatim into `service.py`, adding exactly one `event_bus.publish("new_device", ...)` call inside the new-identity branch — signature, return type, and commit timing are byte-identical to the pre-retrofit `discovery.py` (verified by re-running every pre-existing discovery/mac-history/security-alert test unmodified except import paths). New `DeviceLookupInterface` Protocol + `DeviceInfo` dataclass carry the MAC-rotation-aware union logic moved out of `routes/traffic.py::_resolve_device_macs`. New Alembic branch (`device_identity_0001`, `branch_labels=("device_identity",)`) does a live `ALTER TABLE ... SET SCHEMA` move of the three tables into a new `device_identity` Postgres schema.
- **Task 2 (Devices retrofit + main.py wiring):** Moved `routes/devices.py` into `modules/devices/routes.py`, replacing every direct `select(Device)`/`select(DiscoveredIdentity)` with calls through the constructor-injected `DeviceIdentityModule` instance's `list_all()`/`register()`/`merge()`. Every route stacks `Depends(require_module_enabled("devices"))`. `main.py` now boots `device_identity`/`devices` through Plan 01's `ModuleLoader`, mounting at `/api/modules/devices/` (D-09's canonical prefix); `auth`/`capture`/`security`/`traffic` stay hardcoded per this plan's explicit boundary.
- **Isolated-bisection sequencing honored exactly as the Risk Summary specified:** Task 1 was committed and its full acceptance criteria (including the full backend suite, not just `test_devices.py`) verified green *before* Task 2 began — full suite was 131/132 passing (1 pre-existing unrelated failure) after Task 1 alone, then 134/135 after Task 1+2.
- **Behavior-parity proven, not assumed:** `test_devices.py`'s pre-existing assertions are unchanged (only the request path moved from `/api/devices/` to `/api/modules/devices/`); the entire pre-existing `test_capture.py`/`test_discovery.py`/`test_mac_history.py`/`test_security_alerts.py` suite re-ran unmodified (except import paths) and stayed green throughout both tasks, proving the capture container's ARP/DHCP/mDNS ingest contract is identical pre/post retrofit.

## Task Commits

Each task was committed atomically:

1. **Task 1: DeviceIdentity support module — models, service, DeviceLookupInterface, migration** - `31fabea` (feat)
2. **Task 2: Devices feature module retrofit + ModuleLoader wiring in main.py + capture.py/traffic.py/security.py import cutover** - `23667ce` (feat)

Both tasks were `tdd="true"`; tests and implementation are co-located in the same commit per this codebase's established Phase 1-4/Plan 01 practice (the `<behavior>` blocks define test cases written alongside their implementation, not as a separate pre-existing-failing-test commit step).

## Files Created/Modified

**Created:**
- `backend/src/modules/device_identity/{models,service,interfaces,module,manifest,identity_resolver,identity_inference,event_bus_singleton}.py` — the full DeviceIdentity support module package
- `backend/src/modules/device_identity/migrations/0001_initial.py` — new Alembic branch, live schema-move migration
- `backend/src/modules/devices/{routes,module,manifest}.py` — the full Devices feature module package
- `backend/tests/test_device_identity_lookup.py` — `DeviceLookupInterface` contract tests (MAC lookup, identity_key lookup, not-found, MAC-history union)
- `backend/tests/test_devices_module_boot.py` — zero-module-configs boot proof, disabled-module 404 proof, grep-verified zero-direct-query proof

**Modified (transitional shims required for the app to boot once old model files were deleted, Rule 3):**
- `backend/src/routes/capture.py` — `record_observation`/`Observation`/`MDNS_PLACEHOLDER_MAC` import paths only, no other line changed
- `backend/src/routes/traffic.py`, `backend/src/routes/security.py` — `Device`/`DeviceMacHistory` import paths only; full Protocol-boundary retrofit of their query logic is Plans 04/05's scope (documented as `accept`-disposition T-05-10 in the threat model)
- `backend/src/data/vendor_catalog.py`, `backend/src/services/port_rules.py`, `backend/src/services/traffic_broadcaster.py` — `DeviceType`/`Device` import paths only
- `backend/src/models/{security_alert,pending_scan_request,port_scan_result}.py` — `ForeignKey` targets re-pointed to `device_identity.devices.id` since the referenced table moved schemas
- `backend/src/main.py` — `ModuleLoader`-driven mounting for `device_identity`/`devices`
- `backend/alembic.ini` — `version_locations` (multi-branch, `os.pathsep`-joined)
- `backend/tests/conftest.py` — `schema_translate_map` execution option on the test engine
- `frontend/src/lib/api.ts` — `/api/devices/` → `/api/modules/devices/`
- All pre-existing test files importing the relocated models/services — import paths only, zero assertion changes

**Deleted:**
- `backend/src/models/{device,discovered_identity,device_mac_history}.py`, `backend/src/services/{discovery,identity_inference,identity_resolver}.py`, `backend/src/routes/devices.py` — fully relocated into `backend/src/modules/device_identity/` and `backend/src/modules/devices/`

## Decisions Made

- **DeviceLookupInterface contract (documented for Plans 04/05):** `lookup(identifier: str) -> DeviceInfo | None`. `identifier` may be a MAC address or an `identity_key`. Returns `None` (never raises) when no registered `Device` matches — this mirrors every pre-retrofit route's `scalar_one_or_none()` convention. `DeviceInfo.macs` is the union of the device's current `last_known_mac` plus every historical MAC from `DeviceMacHistory` — Plans 04/05 must consume this field directly rather than re-implementing the union logic that `routes/traffic.py::_resolve_device_macs` used to do inline.
- **EventBus singleton location:** a bare module-level `EventBus()` instance in `device_identity/event_bus_singleton.py`, imported by both `service.py` (the publisher, called from `capture.py`'s hot path, which sits outside the ModuleLoader's constructor-injection graph entirely) and available for `module.py`/future subscribers. This was necessary because `record_observation()` is invoked directly from `routes/capture.py`, not through a module instance the loader constructed — a loader-scoped `EventBus` instance would never see capture.py's publishes.
- **Devices write-path access pattern:** `devices/routes.py` uses a module-level `set_device_identity()`/`get_device_identity()` accessor pair rather than FastAPI `Depends()`-based injection for the `DeviceIdentityModule` instance, since that instance is resolved once at `ModuleLoader.load()` time (startup), not per-request — `DevicesModule.__init__` calls `set_device_identity()` exactly once when the loader instantiates it.
- **Canonical mount prefix derivation:** `main.py`'s `_load_native_modules()` derives each module's URL prefix from its manifest `id` (`module_id.replace('_', '-')`), so `devices` → `/api/modules/devices/` and `device_identity` (which provides no `HasAPIRoutes` capability, so is never mounted as a router) is a no-op in the router-mounting loop.

## Issues Encountered

- **Alembic `version_locations` with multiple paths must be `os.pathsep`-joined, not space-joined**, despite `version_path_separator = os` being set. The first attempt (`%(here)s/src/modules/device_identity/migrations %(here)s/alembic/versions`, space-separated) silently collapsed into a single malformed `PosixPath` containing a literal space — `alembic heads`/`history` then returned completely empty with no error, including for the pre-existing 0001-0006 chain. Diagnosed by directly inspecting `ScriptDirectory.from_config(cfg)._version_locations` in a Python shell. Fixed by joining with `:` (the macOS/Linux `os.pathsep`). This is now documented as a reusable pattern for Plans 04/05 if they ever need their own migration branch directory.
- **Three models outside the plan's explicit Task 1 `files_modified` list** (`security_alert.py`, `pending_scan_request.py`, `port_scan_result.py`) had `ForeignKey("devices.id")` pointing at the table being moved to the `device_identity` schema — left unqualified, these FKs would either fail to resolve at migration time (Postgres) or silently point at a non-existent table. Fixed (Rule 3 — blocking issue) by re-pointing all three to `device_identity.devices.id` in the same Task 1 commit, since the app cannot boot/migrate correctly without this fix and it was directly caused by Task 1's schema-relocation.
- **A docstring literal collision with the acceptance-criteria grep pattern**, the same class of issue Plan 01 documented for "networkx": `devices/routes.py`'s module docstring initially used the literal string `select(Device)/select(DiscoveredIdentity)` in prose explaining the module's design intent, which itself matched the `grep -c "select(Device)\|select(DiscoveredIdentity)"` acceptance criterion (count was 1, not 0). Reworded the docstring to describe the same constraint without the literal pattern, then added a dedicated pytest test (`test_devices_routes_contains_no_direct_canonical_data_query`) that re-greps the file at test time so this constraint is continuously enforced, not just satisfied once at commit time.
- **Unused import** (`create as create_device_identity_module` in `devices/routes.py`, left over from an earlier draft) — removed before commit (Rule 1).

## User Setup Required

None — no external service configuration required. The `device_identity` Alembic migration (`ALTER TABLE ... SET SCHEMA`) is Postgres-specific SQL and was verified by direct SQL inspection plus a successful `alembic heads`/`history` resolution against the full migration chain; it was not executed against a live Postgres instance in this sandboxed worktree (no Docker Postgres container was available), consistent with every other migration in this codebase being verified by inspection + the SQLite-fixture test suite rather than a live Postgres run during plan execution. The plan's `<verification>` block's "confirm via the Lima VM/docker-compose live stack" step is a manual, human-run verification step outside this executor's scope — flagging it here so the orchestrator/user can run it before this schema-move migration is applied to any real environment with live data.

## Next Phase Readiness

- `DeviceIdentity`/`Devices` are real modules, proven to boot through `ModuleLoader`, with `DeviceLookupInterface`'s contract documented exactly as Plans 04/05 will need to consume it.
- `traffic.py`/`security.py` still import successfully via the transitional shim (import-path-only fix); their own `select(Device)` query logic is unchanged and will be retrofitted onto `DeviceLookupInterface` in Plans 04/05 per the threat model's `accept`-disposition T-05-10.
- The `device_identity` Alembic branch pattern (live `ALTER TABLE ... SET SCHEMA`, `branch_labels`, `os.pathsep`-joined `version_locations`) is now a proven, reusable template for Plans 04/05's own schema migrations (Traffic/Security modules), including the documented gotcha about path-joining.
- No blockers identified for downstream plans. The capture container's hot ingest path (`/api/capture/{arp,dhcp,mdns}`) is confirmed behavior-identical pre/post retrofit at the test level; live-stack verification against a real Postgres + Lima VM is recommended before this migration is applied outside a test environment, per the plan's own `<verification>` block.

## Known Stubs

None — every artifact this plan produces is wired to real data sources; no hardcoded empty/placeholder values were introduced.

## Threat Flags

None — every new surface this plan introduces was already covered by the plan's own `<threat_model>` (T-05-07, T-05-08, T-05-09, T-05-10), and no additional security-relevant surface (new endpoints, auth paths, file access, schema changes at trust boundaries) was introduced beyond what that threat model already accounts for.

---
*Phase: 05-plugin-system-notifications (directory name predates the module-platform pivot; phase content is "Module Platform Foundation" per ROADMAP.md)*
*Completed: 2026-06-21*
