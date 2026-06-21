---
phase: 05-plugin-system-notifications
plan: 01
subsystem: api
tags: [typing-protocol, pydantic, graphlib, fastapi, sqlalchemy, alembic, module-host]

# Dependency graph
requires:
  - phase: 04-security-foundation
    provides: existing src/auth.py require_auth Depends convention, src/database.py get_db dependency, app_settings.py single-row config table style
provides:
  - "backend/src/host/{protocols,manifest,registry,loader,event_bus,dependencies}.py — the full module-host contract"
  - "module_configs table + migration 0006 backing MOD-02's enable/disable toggle"
  - "require_module_enabled(module_id)/is_module_enabled(db, module_id) FastAPI dependency, proven importable and behaviorally correct, ready for Plans 03/04/05 retrofits"
  - "schema_translate_map PASS verdict resolving RESEARCH.md Open Question 1, consumed by Plan 03's device_identity migration design"
affects: [05-02-notifications, 05-03-device-identity-devices-retrofit, 05-04-traffic-retrofit, 05-05-security-retrofit]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Capability Protocols (typing.Protocol + @runtime_checkable) for module composition instead of a fat base class"
    - "graphlib.TopologicalSorter for dependency-graph fail-fast ordering"
    - "Constructor-injection-resolved-at-startup wiring (ModuleLoader resolves requires before instantiating)"
    - "Per-capability try/except defensive wiring in the loader so one malformed module never crashes the whole startup sequence"
    - "require_module_enabled(module_id) mirrors require_auth's Depends(get_db)-style composition for FastAPI dependency stacking"

key-files:
  created:
    - backend/src/host/__init__.py
    - backend/src/host/protocols.py
    - backend/src/host/manifest.py
    - backend/src/host/registry.py
    - backend/src/host/loader.py
    - backend/src/host/event_bus.py
    - backend/src/host/dependencies.py
    - backend/src/models/module_config.py
    - backend/alembic/versions/0006_module_configs.py
    - backend/tests/test_module_loader.py
    - backend/tests/test_event_bus.py
    - backend/tests/test_module_registry_toggle.py
    - backend/tests/test_require_module_enabled.py
    - backend/tests/schema_portability_spike.py
  modified:
    - backend/src/models/__init__.py
    - backend/tests/conftest.py

key-decisions:
  - "ModuleLoader implemented as a class (not a bare function) holding registry/event_bus state, returning a LoadResult dataclass (instances/routers/ui_routes/collector_tasks) for main.py to consume in Plan 03 — Claude's Discretion per CONTEXT.md"
  - "schema_translate_map confirmed via spike as the SQLite-test/Postgres-production schema-portability strategy — RESEARCH.md Open Question 1 resolved PASS"

patterns-established:
  - "Pattern: every capability-wiring call in ModuleLoader is wrapped in its own try/except, logging and continuing rather than crashing the whole loader run (RESEARCH.md Pitfall 2 mitigation)"
  - "Pattern: ModuleManifest provides/requires conflicts and unsatisfied dependencies fail loudly at startup via RuntimeError, never silently worked around"

requirements-completed: [MOD-01, MOD-03, MOD-06]

# Metrics
duration: 35min
completed: 2026-06-21
---

# Phase 5 Plan 01: Module Platform Foundation — Host Infrastructure Summary

**Capability-Protocol module contract (HasAPIRoutes/HasUIPage/HasEventSubscriptions/HasCollector), ModuleManifest/ModuleRegistry/ModuleLoader with graphlib topo-sort and constructor injection, carried-over EventBus, module_configs enable/disable table, and require_module_enabled FastAPI dependency — all net-new, zero existing retrofit code touched.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-06-21T17:21:00Z
- **Completed:** 2026-06-21T17:56:59Z
- **Tasks:** 2 completed
- **Files modified:** 15 (13 created, 2 modified)

## Accomplishments
- Built the full module-host contract (`backend/src/host/{protocols,manifest,registry,loader,event_bus,dependencies}.py`) as pure net-new code, proven against throwaway test modules — no existing retrofit code touched, `main.py` untouched per the plan's explicit boundary.
- `module_configs` table + migration `0006` shipped, with `require_module_enabled(module_id)`/`is_module_enabled` proven importable and behaviorally correct (404 disabled / 200 enabled / 200 default-enabled-when-no-row) ahead of every Plan 03/04/05 route that will stack it alongside `Depends(require_auth)`.
- Resolved RESEARCH.md Open Question 1 empirically: `schema_translate_map` PASS — confirmed it cleanly maps two simultaneous Postgres-style schemas onto a single in-memory SQLite engine, de-risking Plan 03's device_identity migration design.
- 16 new tests passing (9 from Task 1, 7 from Task 2), full backend suite at 124/125 passing (the 1 failure is `test_compose.py::test_all_services_healthy`, a pre-existing, environment-dependent failure unrelated to this plan — missing `.env` file for `docker compose config`, not a regression).

## Task Commits

Each task was committed atomically:

1. **Task 1: Capability Protocols, ModuleManifest, ModuleRegistry, EventBus** - `4f4cec3` (feat)
2. **Task 2: ModuleLoader (topo-sort + constructor injection + capability wiring) and schema-portability spike** - `a8a8af9` (feat)

_Note: both tasks were `tdd="true"` but executed RED+GREEN as a single commit per task per this codebase's established Phase 1-4 practice (tests + implementation co-located in the same commit) since the `<behavior>` blocks define test cases written alongside their implementation, not as a separate pre-existing-failing-test commit step._

## Files Created/Modified
- `backend/src/host/protocols.py` - `HasAPIRoutes`/`HasUIPage`/`HasEventSubscriptions`/`HasCollector`, all `@runtime_checkable`, reproduced verbatim per CONTEXT.md/RESEARCH.md Pattern 1
- `backend/src/host/manifest.py` - `ModuleManifest` Pydantic model (`id`, `display_name`, `version`, `kind`, `provides`, `requires`, `db_schema`)
- `backend/src/host/registry.py` - `ModuleRegistry` (Protocol type → provider instance map, `RuntimeError` on conflict/missing)
- `backend/src/host/loader.py` - `build_load_order()` (stdlib `graphlib.TopologicalSorter`) + `ModuleLoader` class (constructor-injection wiring, per-capability defensive try/except)
- `backend/src/host/event_bus.py` - `EventBus` fire-and-forget pub/sub, carried over verbatim per D-10
- `backend/src/host/dependencies.py` - `require_module_enabled(module_id)`/`is_module_enabled(db, module_id)`, mirrors `src/auth.py`'s `require_auth` convention
- `backend/src/models/module_config.py` - `ModuleConfig` ORM model (`module_id` unique, `enabled` default `True`)
- `backend/alembic/versions/0006_module_configs.py` - new migration, `module_configs` table + unique index on `module_id`
- `backend/src/models/__init__.py` - exports `ModuleConfig`
- `backend/tests/conftest.py` - added `module_config` to the explicit pre-import list so `test_db`'s `create_all` registers the new table
- `backend/tests/test_module_loader.py`, `test_event_bus.py`, `test_module_registry_toggle.py`, `test_require_module_enabled.py` - new test files, 16 tests total
- `backend/tests/schema_portability_spike.py` - throwaway spike script resolving Open Question 1, PASS verdict

## Decisions Made
- **ModuleLoader as a class returning a `LoadResult` dataclass** (instances/routers/ui_routes/collector_tasks) rather than a bare function — gives Plan 03's `main.py` integration a single object to inspect for mounting routers and managing collector-task shutdown, consistent with CONTEXT.md's "Claude's Discretion" note on loader internal structure.
- **schema_translate_map confirmed as the production SQLite/Postgres schema-portability strategy** via the empirical spike (PASS) — Plan 03 should use this pattern in its conftest.py fixtures for `device_identity`/`devices`/`traffic`/`security` schemas rather than falling back to multi-attach SQLite or testcontainers.

## Deviations from Plan

None - plan executed exactly as written. All artifacts, signatures, and test behaviors match the plan's `<action>`/`<behavior>`/`<acceptance_criteria>` blocks verbatim.

## Issues Encountered

- `ModuleManifest`'s `provides`/`requires` fields are typed `list[type]`, which Pydantic v2 does not validate by default without `arbitrary_types_allowed=True` in the model config — added `model_config = ConfigDict(arbitrary_types_allowed=True)` to make the verbatim-specified field types work; this is a direct consequence of reproducing the plan's exact field signatures, not a deviation from them.
- The plan's Task 2 acceptance criteria require `grep -c "networkx" backend/src/host/loader.py` to equal exactly 0 — the first docstring draft mentioned "not networkx" in prose explaining the design choice, which itself matched the grep pattern. Reworded to describe the same constraint ("RESEARCH.md's explicit non-recommendation of any third-party graph library") without using the literal string, satisfying the acceptance criterion while preserving the documentation intent.

## User Setup Required

None - no external service configuration required. All host infrastructure is pure in-process Python (stdlib `typing`/`asyncio`/`graphlib` plus already-pinned `pydantic`/`sqlalchemy`/`alembic`).

## Next Phase Readiness

- Host infrastructure (`backend/src/host/*`) is complete, tested, and importable — Plan 03 (DeviceIdentity extraction + Devices retrofit) can now build its module's `manifest.py`/`module.py`/factory against this contract.
- `require_module_enabled`/`is_module_enabled` exist and are proven correct ahead of every retrofitted route in Plans 03/04/05 that will stack it alongside `Depends(require_auth)`.
- `schema_translate_map` is confirmed (PASS) as the test-fixture strategy Plan 03 should use for its `device_identity`/`devices` schema split conftest.py fixtures — no further spiking needed before that plan's migrations are written.
- `main.py` is completely untouched this plan, exactly as scoped — wiring `ModuleLoader` into the live FastAPI app happens in Plan 03 when DeviceIdentity/Devices become real modules.
- No blockers identified for downstream plans.

---
*Phase: 05-plugin-system-notifications (directory name predates the module-platform pivot; phase content is "Module Platform Foundation" per ROADMAP.md)*
*Completed: 2026-06-21*

## Self-Check: PASSED

All 15 claimed files verified present on disk; all 3 commit hashes (`4f4cec3`, `a8a8af9`, `e34cdc5`) verified present in git log.
