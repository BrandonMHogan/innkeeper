---
phase: 02-device-registry-discovery
plan: 04
subsystem: api
tags: [fastapi, sqlalchemy, identity-resolution, svelte, gap-closure]

# Dependency graph
requires:
  - phase: 02-device-registry-discovery
    provides: discovery/capture/devices routes, identity_resolver, frontend api.ts client built in plans 01-03
provides:
  - Hostname-less mDNS observations no longer over-fuse into a shared placeholder-MAC identity
  - Named _MDNS_PLACEHOLDER_MAC constant replacing the inline magic string
  - Frontend listDevices()/registerDevice() now target the canonical /api/devices/ backend path (no redirect hop)
  - Regression tests locking both fixes in place
affects: [03, verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Skip-on-no-signal guard: when an observation carries no usable identity signal (hostname absent for mDNS), skip record_observation entirely rather than fabricating a shared/placeholder identity key"
    - "Frontend API client literals must match the backend's canonical (trailing-slash) mount point exactly to avoid relying on FastAPI's redirect_slashes for POST requests"

key-files:
  created: []
  modified:
    - backend/src/routes/capture.py
    - backend/tests/test_capture.py
    - frontend/src/lib/api.ts
    - backend/tests/test_devices.py

key-decisions:
  - "Guard clause in ingest_mdns checks only payload.hostname presence (not MAC), since mDNS observations always carry the same placeholder MAC today — a hostname-only check is currently equivalent to a combined MAC+hostname check per 02-REVIEW.md's CR-01 fix direction"
  - "mergeDevice() left unchanged — its path already has a trailing path segment after /api/devices/{id}/merge and is not subject to FastAPI's redirect_slashes behavior"

patterns-established:
  - "Regression tests for path-mismatch bugs use a raw httpx.AsyncClient with follow_redirects=False against ASGITransport to assert exact redirect Location headers, not just status codes"

requirements-completed: [DISC-01, DISC-02, DISC-04]

# Metrics
duration: 18min
completed: 2026-06-18
---

# Phase 02 Plan 04: mDNS Over-Fusion and Frontend Path Mismatch Gap Closure Summary

**Guard clause skips mDNS identity resolution when no hostname is present (closing the placeholder-MAC over-fusion bug), and frontend api.ts now calls the canonical trailing-slash /api/devices/ path, closing both critical gaps from 02-VERIFICATION.md.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-06-18T20:22:00Z
- **Completed:** 2026-06-18T20:40:22Z
- **Tasks:** 2 completed
- **Files modified:** 4

## Accomplishments
- Fixed CR-01: hostname-less mDNS observations no longer collapse into a single shared placeholder-MAC `DiscoveredIdentity` row; `ingest_mdns` now returns `{"ok": true, "skipped": "no identity signal"}` and skips `record_observation` when `payload.hostname` is absent or blank
- Extracted the magic placeholder-MAC literal `"00:00:00:00:00:00"` into a named `_MDNS_PLACEHOLDER_MAC` module constant (closes IN-02)
- Fixed CR-02: `listDevices()` and `registerDevice()` in `frontend/src/lib/api.ts` now call `/api/devices/` (trailing slash) instead of the non-canonical `/api/devices`, eliminating the 307-redirect hop on every list/register call
- Added 3 new regression tests (2 in `test_capture.py`, 1 in `test_devices.py`) proving both fixes and locking the backend's canonical-path contract against future regression

## Task Commits

Each task was committed atomically (TDD: test then implementation):

1. **Task 1 test: mDNS over-fusion regression tests** - `5bf256b` (test)
2. **Task 1 fix: mDNS placeholder-MAC over-fusion guard** - `2c8bab8` (fix)
3. **Task 2 test: canonical /api/devices/ path regression test** - `7c340fd` (test)
4. **Task 2 fix: frontend trailing-slash path correction** - `9db55df` (fix)

**Plan metadata:** (pending — final commit below)

## Files Created/Modified
- `backend/src/routes/capture.py` - Added `_MDNS_PLACEHOLDER_MAC` constant; `ingest_mdns` now guards on `payload.hostname` and skips `record_observation` when absent
- `backend/tests/test_capture.py` - Added `test_mdns_ingest_without_hostname_does_not_collide` and `test_mdns_ingest_with_hostname_still_resolves_identity`
- `frontend/src/lib/api.ts` - `listDevices()` and `registerDevice()` now call `/api/devices/` (trailing slash)
- `backend/tests/test_devices.py` - Added `test_list_devices_canonical_path_no_redirect`

## Decisions Made
- Guard clause checks `payload.hostname` presence only (not a combined MAC+hostname check), since mDNS observations always carry the same placeholder MAC today, making the two checks currently equivalent — consistent with 02-REVIEW.md's CR-01 suggested fix
- Left `mergeDevice()` untouched since its URL path already has a segment after the `/api/devices/{id}/merge` prefix and isn't subject to FastAPI's `redirect_slashes`

## Deviations from Plan

None - plan executed exactly as written. Both tasks followed the plan's action steps precisely; all acceptance-criteria greps and test assertions passed without needing additional fixes.

## Issues Encountered

None. The `test_list_devices_canonical_path_no_redirect` test passed immediately upon being written (before the frontend fix) since it only exercises already-correct backend routing behavior — this is expected per the plan's design: the test locks the backend contract that the frontend client (a TypeScript file, not separately unit-tested in this repo) must match.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DISC-01 (multi-source fusion correctness), DISC-02 (register flow reachability), and DISC-04 (unknown-device list reachability) requirements are now expected to move from PARTIAL to SATISFIED on the next verification pass
- Full backend suite: 31 passed (28 baseline + 3 new), 0 failed, no regressions
- CR-03 (TOCTOU race) and CR-04 (gateway trust spoofing), plus all WR-*/IN-* items besides IN-02, remain explicitly out of scope per this plan's success criteria and are tracked in 02-REVIEW.md for future consideration

## Self-Check: PASSED

---
*Phase: 02-device-registry-discovery*
*Completed: 2026-06-18*
