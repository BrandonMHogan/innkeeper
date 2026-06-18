---
phase: 02-device-registry-discovery
plan: 05
subsystem: discovery
tags: [identity-resolution, mdns, sqlalchemy, regression-fix, security]

# Dependency graph
requires:
  - phase: 02-device-registry-discovery
    provides: identity_resolver.py, discovery.py record_observation, devices.py register_device/merge_device (built in 02-01..02-04)
provides:
  - "Shared MDNS_PLACEHOLDER_MAC sentinel constant as single source of truth"
  - "record_observation Device-branch lookup excludes the placeholder MAC entirely"
  - "register_device/merge_device refuse to persist the placeholder into Device.last_known_mac"
  - "Device.last_known_mac column made nullable to support the None-on-placeholder write"
affects: [verification, code-review]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared sentinel constants live in the lowest-level module (identity_resolver.py) and are imported by every consumer, not redefined locally"
    - "Defense-in-depth: placeholder-MAC exclusion applied both at the matching site (discovery.py) and the write site (devices.py) independently"

key-files:
  created: []
  modified:
    - backend/src/services/identity_resolver.py
    - backend/src/services/discovery.py
    - backend/src/routes/capture.py
    - backend/src/routes/devices.py
    - backend/src/models/device.py
    - backend/alembic/versions/0002_device_registry_discovery.py
    - backend/tests/test_discovery.py
    - backend/tests/test_devices.py

key-decisions:
  - "MDNS_PLACEHOLDER_MAC hoisted to identity_resolver.py as single source of truth; capture.py's local _MDNS_PLACEHOLDER_MAC duplicate removed"
  - "record_observation skips the Device-branch select() entirely for placeholder-MAC observations rather than filtering results post-query, eliminating the hijack vector at the query level"
  - "register_device/merge_device independently guard against persisting the placeholder (defense-in-depth) even though discovery.py's fix alone would prevent new hijacks"
  - "Device.last_known_mac made nullable (model + migration 0002 edited in place, not superseded) because migration 0002 was introduced earlier in this same in-progress phase and has not shipped outside this branch"

requirements-completed: [DISC-01, DISC-02, DISC-04]

duration: 25min
completed: 2026-06-18
---

# Phase 02 Plan 05: Close CR-05 mDNS Placeholder-MAC Device Hijack Summary

**Closed a device-hijacking bug where any mDNS observation for ANY device could silently overwrite a registered device's identity_key/last_known_mac because all hostname-bearing mDNS observations share one placeholder MAC.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-06-18T23:30:00Z
- **Completed:** 2026-06-18T23:55:39Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Hoisted `MDNS_PLACEHOLDER_MAC` to `identity_resolver.py` as the single shared sentinel, removing the duplicate local definition in `capture.py`
- `record_observation`'s Device-branch lookup now unconditionally skips the placeholder MAC, falling through to the hostname-keyed `DiscoveredIdentity` upsert instead of risking a cross-device match
- `register_device`/`merge_device` independently refuse to write the placeholder into `Device.last_known_mac` (defense-in-depth at the write site)
- `Device.last_known_mac` made nullable to support the `None` write on placeholder-sourced registrations
- Four new regression tests prove the exact CR-05 hijack scenario is closed, with no regression to existing non-placeholder matching behavior

## Task Commits

Each task was committed atomically (TDD red/green per task):

1. **Task 1: Hoist shared placeholder-MAC constant and exclude it from Device-branch matching**
   - `03f508f` (test) — add failing regression tests for placeholder-MAC device hijack
   - `a80df66` (fix) — hoist `MDNS_PLACEHOLDER_MAC`, exclude it from Device-branch matching in `record_observation`
2. **Task 2: Refuse to persist the placeholder MAC into Device.last_known_mac on register/merge**
   - `d21c238` (test) — add failing tests for placeholder-MAC persistence guard
   - `35e9ea6` (fix) — guard `register_device`/`merge_device`, make `Device.last_known_mac` nullable

**Plan metadata:** (this commit, following SUMMARY.md)

## Files Created/Modified
- `backend/src/services/identity_resolver.py` - added `MDNS_PLACEHOLDER_MAC` module-level constant (single source of truth)
- `backend/src/services/discovery.py` - `record_observation` now skips the Device-branch `select()` entirely when `observation.mac == MDNS_PLACEHOLDER_MAC`, falling through to `upsert_discovered_identity`
- `backend/src/routes/capture.py` - removed local `_MDNS_PLACEHOLDER_MAC`; imports the shared constant instead
- `backend/src/routes/devices.py` - `register_device` writes `None` instead of the placeholder; `merge_device` leaves `last_known_mac` unchanged when the source identity carries the placeholder
- `backend/src/models/device.py` - `last_known_mac` column changed to `Mapped[str | None]` / `nullable=True`
- `backend/alembic/versions/0002_device_registry_discovery.py` - `last_known_mac` column changed to `nullable=True` (edited in place; this migration is part of this same in-progress phase and has not shipped elsewhere)
- `backend/tests/test_discovery.py` - 2 new regression tests for the discovery-path hijack scenario
- `backend/tests/test_devices.py` - 2 new regression tests for the register/merge write-path guard

## Decisions Made
- Edited migration `0002` in place to make `last_known_mac` nullable, rather than adding a new migration `0003`, because `0002` was introduced earlier in this same in-progress phase 02 and has not been released or applied outside this development branch — no production schema depends on its original `nullable=False` shape.
- Applied the placeholder-MAC guard at both the read/match site (`discovery.py`) and the write site (`devices.py`) independently per the plan's threat model (T-02-05-01, T-02-05-02), so the corrupting value cannot reach the `Device` table from either code path even if one guard were later removed by mistake.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Made Device.last_known_mac nullable to support the planned None write**
- **Found during:** Task 2 (register_device placeholder guard)
- **Issue:** The plan's action item required `register_device` to set `last_known_mac=None` when the source identity carries the placeholder MAC, but `Device.last_known_mac` was defined `nullable=False` in both the SQLAlchemy model and migration `0002`. Running the new test against the unmodified schema raised `sqlalchemy.exc.IntegrityError: NOT NULL constraint failed: devices.last_known_mac` — the planned behavior was impossible without a schema change.
- **Fix:** Changed `Device.last_known_mac` to `Mapped[str | None]` / `nullable=True` in `src/models/device.py`, and updated the corresponding column definition in `alembic/versions/0002_device_registry_discovery.py` (edited in place rather than superseded by a new migration, since `0002` has not shipped outside this branch).
- **Files modified:** backend/src/models/device.py, backend/alembic/versions/0002_device_registry_discovery.py
- **Verification:** `cd backend && python -m pytest tests/ -q --ignore=tests/test_compose.py` — 35 passed, 0 failed
- **Committed in:** 35e9ea6 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to fulfill the plan's own explicit requirement (`last_known_mac is None`) for `register_device`. No scope creep — schema change confined to the single column the plan already targeted.

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CR-05 closed; DISC-01, DISC-02, DISC-04 requirements move back from PARTIAL to SATISFIED pending re-verification.
- Full backend suite (35 tests) passes with no regressions.
- No scope creep into CR-03, CR-04, WR-08, WR-09 — all remain explicitly out of scope per this plan's success criteria.

---
*Phase: 02-device-registry-discovery*
*Completed: 2026-06-18*

## Self-Check: PASSED

All claimed files verified present; all four task commits (03f508f, a80df66, d21c238, 35e9ea6) verified present in git log.
