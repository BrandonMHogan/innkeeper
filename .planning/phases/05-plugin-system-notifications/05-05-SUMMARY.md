---
phase: 05-plugin-system-notifications
plan: 05
subsystem: api
tags: [module-host, security, device-identity, alembic-branch, schema-isolation, retrofit, capability-protocol]

# Dependency graph
requires:
  - phase: 05-plugin-system-notifications
    plan: 03
    provides: "DeviceLookupInterface contract (lookup(identifier) -> DeviceInfo | None), device_identity Alembic branch pattern"
  - phase: 05-plugin-system-notifications
    plan: 04
    provides: "Traffic feature-module retrofit pattern (own Postgres schema, ModuleLoader wiring, module-level set_device_lookup()/get_device_lookup() accessor pair), DeviceLookupInterface numeric-device_id lookup extension, traffic Alembic branch (traffic_0001) to chain after"
provides:
  - "backend/src/modules/security/ — Security feature module owning its own security Postgres schema, mounted via ModuleLoader at /api/modules/security/"
  - "security Alembic branch (security_0001, branch_labels=(\"security\",), chained after traffic_0001) — live ALTER TABLE SET SCHEMA pattern for port_scan_results/security_alerts/pending_scan_requests"
  - "backend/src/modules/linked_apps/module.py — minimal HasAPIRoutes factory (zero requires/provides) letting linked_apps join the single ModuleLoader call"
  - "main.py's _load_native_modules() now wires all five native+linked modules (device_identity, devices, traffic, security, linked_apps) through one ModuleLoader call — zero hardcoded app.include_router calls remain for any retrofitted module; only auth+capture stay hardcoded as host-level concerns"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Final retrofit closes the loop on Plan 03/04's pattern: a feature module with requires=[DeviceLookupInterface] and db_schema=\"<name>\" mirrors TrafficModule's module-level set_device_lookup()/get_device_lookup() accessor pair exactly — list_alerts's per-alert device-name lookup (called once per unacknowledged alert in a loop) and trigger_scan/get_scan_result's device-existence checks all go through this same accessor, not a freshly constructed lookup per route."
    - "A module with zero requires/provides (linked_apps) still needs a minimal module.py factory (`create(deps) -> Instance` returning an instance whose get_router() satisfies HasAPIRoutes) to join the ModuleLoader call — it cannot just keep its router as a bare module-level APIRouter mounted directly in create_app(), since the success criterion is zero per-module app.include_router calls outside the loader's own mounting loop."

key-files:
  created:
    - backend/src/modules/security/__init__.py
    - backend/src/modules/security/manifest.py
    - backend/src/modules/security/module.py
    - backend/src/modules/security/routes.py
    - backend/src/modules/security/models.py
    - backend/src/modules/security/migrations/0001_initial.py
    - backend/src/modules/linked_apps/module.py
  modified:
    - backend/alembic.ini
    - backend/src/main.py
    - backend/src/models/__init__.py
    - backend/src/modules/device_identity/service.py
    - backend/src/routes/capture.py
    - backend/tests/conftest.py
    - backend/tests/test_capture.py
    - backend/tests/test_security_alerts.py
    - backend/tests/test_security_scan.py
    - frontend/src/lib/api.ts
  deleted:
    - backend/src/models/pending_scan_request.py
    - backend/src/models/port_scan_result.py
    - backend/src/models/security_alert.py
    - backend/src/routes/security.py

key-decisions:
  - "list_alerts's device-name resolution is per-alert, not a single batched join: for each unacknowledged SecurityAlert with a non-null device_id, the handler calls await get_device_lookup().lookup(str(alert.device_id)) individually inside the serialization loop, mirroring the documented None-is-not-found convention exactly as the pre-retrofit outerjoin would have produced (alert.device_id is None alerts keep device_name=None without any lookup call). This trades one N+1-shaped query pattern for the same DeviceLookupInterface boundary every other retrofitted route uses — acceptable per the threat model's accept-disposition T-05-16, since alert volume in a single-household deployment is small and DeviceLookupInterface's own implementation is already audited in device_identity (Plan 03)."
  - "linked_apps needed a new module.py factory (LinkedAppsModule, zero requires/provides) it did not have before this plan — it was previously mounted via a bare `app.include_router(linked_apps_routes.router, ...)` call directly in create_app(), bypassing the ModuleLoader entirely. This plan's success criterion (zero hardcoded app.include_router calls for any of the five native+linked modules) required wiring it through the loader too, even though linked_apps itself was out of scope for the Security retrofit narrowly defined by the plan's <files> list — added as a Rule 2 (missing critical functionality for this plan's own stated success criterion) rather than skipped."

patterns-established:
  - "Pattern: a feature module's create() factory and its routes.py's accessor pair (set_device_lookup/get_device_lookup) is now a three-time-proven template (devices/Plan03, traffic/Plan04, security/Plan05) for any future module retrofitted onto DeviceLookupInterface — copy module.py/manifest.py's shape verbatim, swap the relocated models/router contents."

requirements-completed: [MOD-07]

# Metrics
duration: 55min
completed: 2026-06-21
---

# Phase 5 Plan 05: Module Platform Foundation — Security Retrofit Summary

**Retrofitted Security (on-demand port scan trigger/read, alert listing/ack) into a real feature module owning its own `security` Postgres schema, with every `outerjoin(Device, ...)`/direct `Device` existence-check call site replaced by `DeviceLookupInterface.lookup()` — main.py now boots all five native+linked modules through a single `ModuleLoader` call with zero hardcoded per-module `app.include_router` calls remaining, closing out MOD-07's full three-module retrofit scope.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-06-21T19:05:00Z
- **Completed:** 2026-06-21T20:00:00Z
- **Tasks:** 1 completed (single `tdd="true"` task per plan)
- **Files modified:** 21 (7 created, 10 modified, 4 deleted)

## Accomplishments

- **Security feature module package** (`backend/src/modules/security/`): `models.py` relocates `PortScanResult`/`SecurityAlert`/`SecurityAlertType`/`PendingScanRequest` with `__table_args__ = {"schema": "security"}` and `ForeignKey` targets re-pointed at `device_identity.devices.id`; `routes.py` relocates the scan/alert router, deleting the `select(SecurityAlert, Device.name).outerjoin(Device, ...)` query and both `select(Device).where(Device.id == device_id)` existence checks — every device-name/device-existence resolution call site now calls `get_device_lookup().lookup(str(device_id))` through a module-level accessor pair (`set_device_lookup`/`get_device_lookup`), mirroring Plan 04's `traffic/routes.py` pattern exactly; `module.py`/`manifest.py` provide the `create(deps)` factory (`requires=[DeviceLookupInterface]`, `db_schema="security"`).
- **New Alembic branch** (`security_0001`, chained after `traffic_0001`): `CREATE SCHEMA IF NOT EXISTS security` plus a live `ALTER TABLE ... SET SCHEMA` move of `port_scan_results`/`security_alerts`/`pending_scan_requests` into the new schema — no continuous aggregates or hypertables involved (these are plain relational tables per the original 0005 migration's own note), so the migration is simpler than Plan 04's traffic equivalent.
- **main.py's ModuleLoader call extended to all five modules**: `security` and `linked_apps` manifests/factories added alongside `device_identity`/`devices`/`traffic`; the last two hardcoded router mounts (`security.router` at `/api/security`, `linked_apps_routes.router` at `/api/modules/linked-apps`) removed from `create_app()`. `linked_apps` needed a brand-new `module.py` factory (`LinkedAppsModule`, zero `requires`/`provides`) since it had no factory at all before this plan — only a bare module-level `APIRouter` mounted directly. After this plan, `main.py` mounts only `auth.router`/`capture.router` as hardcoded routers; every other module (`device_identity`, `devices`, `traffic`, `security`, `linked_apps`) goes through the single `ModuleLoader.load()` call.
- **Transitive consumer updates**: `capture.py`/`device_identity/service.py`/`models/__init__.py` import `PortScanResult`/`SecurityAlert`/`SecurityAlertType`/`PendingScanRequest` from `modules.security.models`; the full security/alerts/scan test suite and `frontend/src/lib/api.ts` move to the `/api/modules/security/` prefix.

## Task Commits

Single `tdd="true"` task, committed as one atomic commit (tests and implementation co-located per this codebase's established practice — the `<behavior>` block's test cases were the existing `test_security_alerts.py`/`test_security_scan.py`/`test_capture.py` suite re-run unmodified except import/path updates, plus the grep-verified main.py consolidation criterion):

1. **Security feature module package + main.py ModuleLoader consolidation + transitive import/path updates** - `fb97e2c` (feat)

## Files Created/Modified

**Created:**
- `backend/src/modules/security/{models,routes,module,manifest}.py` — the full Security feature module package
- `backend/src/modules/security/migrations/0001_initial.py` — new Alembic branch, live schema-move migration
- `backend/src/modules/linked_apps/module.py` — new `HasAPIRoutes`-satisfying factory letting `linked_apps` join the `ModuleLoader` call (it previously had none)

**Modified:**
- `backend/src/main.py` — `security`/`linked_apps` added to the `ModuleLoader` manifest/factory list; old hardcoded `security.router`/`linked_apps_routes.router` `app.include_router` calls removed; only `auth`/`capture` remain hardcoded
- `backend/alembic.ini` — `version_locations` gains `src/modules/security/migrations`
- `backend/src/models/__init__.py`, `backend/src/routes/capture.py`, `backend/src/modules/device_identity/service.py` — `PortScanResult`/`SecurityAlert`/`SecurityAlertType`/`PendingScanRequest` import paths only (Rule 3 — blocking, since the old `src/models/{port_scan_result,security_alert,pending_scan_request}.py` files were deleted in this same commit)
- `backend/tests/conftest.py` — `schema_translate_map` gains `"security": None`; model-import block drops the three deleted `src.models.*` imports in favor of `src.modules.security.models`
- `backend/tests/{test_capture,test_security_alerts,test_security_scan}.py` — import paths + `/api/security/` → `/api/modules/security/` path updates
- `frontend/src/lib/api.ts` — `triggerScan()`/`listAlerts()`/`ackAlert()`/`ackAllAlerts()`/`getScanResult()` updated to `/api/modules/security/...`

**Deleted:**
- `backend/src/models/{port_scan_result,security_alert,pending_scan_request}.py`, `backend/src/routes/security.py` — fully relocated into `backend/src/modules/security/`

## Decisions Made

See `key-decisions` in frontmatter for full rationale on: `list_alerts`'s per-alert (not batched) `DeviceLookupInterface.lookup()` resolution pattern, and the addition of a `linked_apps/module.py` factory that was not explicitly listed in the plan's `<files>` block but was required to satisfy the plan's own "zero hardcoded `app.include_router` calls" success criterion.

## Issues Encountered

- **Circular-import risk avoided by design, not by accident**: `device_identity/service.py` needed to import `SecurityAlert`/`SecurityAlertType` from the new `modules.security.models` (to keep firing the `UNKNOWN_DEVICE` alert from `record_observation`'s new-identity branch), while `security/manifest.py` imports `device_identity.interfaces`. Verified before committing that `device_identity/interfaces.py` has zero internal imports and `device_identity/module.py` never imports `device_identity/service.py`, so no cycle exists — `security.models` → (nothing in `device_identity`) and `device_identity.service` → `security.models` is a one-directional edge.
- **Acceptance criterion's literal `app.include_router` grep count (expected 2) undercounts by construction**: the criterion's intent is "zero hardcoded per-module include calls outside the loader's own mounting loop," but the loader's own `app.include_router(router, prefix=...)` line inside `_load_native_modules()`'s `for module_id, router in result.routers:` loop also matches the same literal grep pattern, making the raw count 3 (loop line + auth + capture), not 2. Verified the *true* intent — zero hardcoded calls naming `security`/`traffic`/`devices`/`linked_apps_routes` specifically — holds via a more targeted grep (`app\.include_router\((auth|capture|security|linked_apps_routes|traffic|devices)\.`), which returns exactly the 2 expected hardcoded lines (`auth.router`, `capture.router`). Documented here rather than silently treated as a criterion failure, since the criterion's plain-text grep command as literally written in the plan would never have returned 2 in any state of this codebase once the loader's mounting loop itself exists (true since Plan 03).
- **Docstring literal-pattern collision** (same class of issue Plan 03/04 already documented for `select(Device)`/`networkx`): `security/routes.py`'s initial module docstring used the literal text `outerjoin(Device, ...)` to describe what was removed, which itself matched the `grep -c "outerjoin(Device" backend/src/modules/security/routes.py` acceptance criterion (count was 1, not 0). Reworded the docstring to describe the same removed pattern without the literal substring (Rule 1 — directly caused by this task's own acceptance-criteria wording).
- **`device_identity/service.py`'s import reordering**: removing the now-stale `from src.models.security_alert import ...` line at its original position (alphabetically before `device_identity` imports) and re-adding it after the `device_identity.models` import (to keep import-sort order matching the rest of the file's existing convention) — purely cosmetic, no behavior change.

## User Setup Required

None — no external service configuration required. As with Plans 03/04, the new `security_0001` Alembic migration's live `ALTER TABLE ... SET SCHEMA` is Postgres-specific SQL, verified by inspection and a successful `alembic heads`/`history` resolution against the full migration chain (single head: `security_0001`), not executed against a live Postgres instance in this sandboxed worktree (no Docker Postgres container available). The plan's `<verification>` block's "confirm via the Lima VM/docker-compose live stack" step — live port scans and malicious-IP alerts both still populating `security.port_scan_results`/`security.security_alerts`, and the dashboard's SecurityAlertsBanner/ScanResultDialog still rendering real data — is a manual, human-run verification step outside this executor's scope, flagged here for the orchestrator/user to run before this migration is applied to any real environment with live data.

## Next Phase Readiness

- All three originally-bolt-on feature areas (DeviceIdentity/Devices, Traffic, Security) are now real modules, proven to boot through `ModuleLoader`, each consuming `DeviceLookupInterface` instead of querying `Device`/`DeviceMacHistory` directly — MOD-07's full retrofit scope is closed.
- `main.py` boots `device_identity`, `devices`, `traffic`, `security`, and `linked_apps` through a single `ModuleLoader` call; only `auth` and `capture` remain hardcoded as explicit host-level (non-module) concerns, exactly as this plan's success criteria specified.
- The `security` Alembic branch pattern (live `ALTER TABLE ... SET SCHEMA`, chained after `traffic_0001`) is a third proven, reusable template for any future module needing its own schema migration.
- No blockers identified for downstream phases. The capture container's port-scan/malicious-IP/bandwidth-anomaly alert-writing paths (`/api/capture/scan`, `/pending-scans`, `/queue-daily-scans`) are confirmed behavior-identical pre/post retrofit at the test level (all `test_capture.py`/`test_security_alerts.py`/`test_security_scan.py` assertions unchanged except import/path updates); live-stack verification against a real Postgres + Lima VM is recommended before this migration is applied outside a test environment, per the plan's own `<verification>` block.

## Known Stubs

None — every artifact this plan produces is wired to real data sources; no hardcoded empty/placeholder values were introduced.

## Threat Flags

None — every new surface this plan introduces was already covered by the plan's own `<threat_model>` (T-05-14, T-05-15, T-05-16), and no additional security-relevant surface (new endpoints, auth paths, file access, schema changes at trust boundaries) was introduced beyond what that threat model already accounts for.

## Self-Check: PASSED

All created artifacts (`backend/src/modules/security/{__init__,manifest,module,routes,models}.py`, `backend/src/modules/security/migrations/0001_initial.py`, `backend/src/modules/linked_apps/module.py`, this SUMMARY.md) verified present on disk. The single commit (`fb97e2c`) verified present in `git log`. Full backend suite (134/134, excluding one pre-existing environment-only `test_compose.py::test_all_services_healthy` failure caused by a missing `.env` file in this worktree, unrelated to this plan's changes) confirmed green by direct pytest run.

---
*Phase: 05-plugin-system-notifications (directory name predates the module-platform pivot; phase content is "Module Platform Foundation" per ROADMAP.md)*
*Completed: 2026-06-21*
