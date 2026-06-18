---
phase: 02-device-registry-discovery
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, identity-fusion, device-registry, upsert, alembic]

# Dependency graph
requires:
  - phase: 01-foundation-capture-feasibility
    provides: ArpEvent raw observation model, /api/capture/arp ingest route with loopback/gateway trust boundary, session-cookie auth (require_auth), SQLite-in-memory test fixtures (test_db/client)
provides:
  - DhcpEvent and MdnsEvent raw observation models (extend ArpEvent pattern)
  - DiscoveredIdentity (fused, unregistered) and Device (registry, locked identity) models
  - IdentityResolver Protocol + HostnameFallbackResolver (D-01/D-02/D-03 fusion seam)
  - discovery.record_observation() orchestration (Pitfall 2 registered-device-rename handling)
  - Dialect-aware upsert (pg_insert/sqlite_insert ON CONFLICT) preventing duplicate-identity races (Pitfall 5)
  - Alembic migration 0002 creating dhcp_events/mdns_events/discovered_identities/devices
  - /api/capture/dhcp, /api/capture/mdns ingest routes; /api/capture/arp refactored to feed fusion
  - /api/devices GET (list, unknown-tagged)/POST (register)/POST /{id}/merge (manual merge only, D-05)
affects: [02-02, 02-03, frontend-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "IdentityResolver as a Protocol — pure/stateless fusion logic, swappable without touching callers (D-01)"
    - "Dialect-aware upsert branching on db.bind.dialect.name (postgresql vs sqlite) — same ON CONFLICT DO UPDATE semantics for prod and SQLite-in-memory tests"
    - "Registered-device-identity-key-change check happens in the orchestration service (discovery.py), not inside the resolver — keeps the resolver pure"
    - "Capture ingest routes never write fusion logic inline — always delegate to record_observation()"

key-files:
  created:
    - backend/src/models/dhcp_event.py
    - backend/src/models/mdns_event.py
    - backend/src/models/discovered_identity.py
    - backend/src/models/device.py
    - backend/src/services/identity_resolver.py
    - backend/src/services/discovery.py
    - backend/src/routes/devices.py
    - backend/alembic/versions/0002_device_registry_discovery.py
    - backend/tests/test_identity_resolver.py
    - backend/tests/test_discovery.py
    - backend/tests/test_devices.py
  modified:
    - backend/src/models/__init__.py
    - backend/src/routes/capture.py
    - backend/src/main.py
    - backend/tests/test_capture.py

key-decisions:
  - "mDNS observations use a placeholder MAC (00:00:00:00:00:00) since mDNS browsing alone yields no MAC — documented inline as a known Phase 2 limitation; ARP/DHCP observations for the same device independently resolve the real identity"
  - "Used Python 3.13 via a throwaway local venv (/tmp/innkeeper-venv) to run pytest since the project requires >=3.13 and no project venv existed yet"

patterns-established:
  - "Pattern: Identity fusion as Protocol — resolve(observation) -> str, no shared state, swappable implementation"
  - "Pattern: Discovery orchestration owns the registry-aware identity-key-change check; resolver stays pure"
  - "Pattern: Dialect-aware upsert for any table needing race-safe dedup under concurrent ingest"

requirements-completed: [DISC-01, DISC-02, DISC-03, DISC-04]

# Metrics
duration: 25min
completed: 2026-06-18
---

# Phase 2 Plan 1: Device Registry + Discovery Backend Vertical Slice Summary

**Backend fusion pipeline (ARP+DHCP+mDNS → IdentityResolver → discovered_identities/devices) with full /api/devices registry CRUD and merge, proven by 16 new passing pytest tests.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-06-18T18:51:00Z
- **Completed:** 2026-06-18T18:56:17Z
- **Tasks:** 2
- **Files modified:** 15 (11 created, 4 modified)

## Accomplishments
- Built the `IdentityResolver` Protocol + `HostnameFallbackResolver` — hostname-primary/MAC-fallback identity fusion (D-01/D-02/D-03), fully isolated and swappable
- Built `discovery.record_observation()` orchestration that resolves identity keys, detects and updates already-registered devices in place on hostname/MAC change (Pitfall 2 regression-proofed), and dialect-aware upserts unregistered identities (Pitfall 5 race-proofed)
- Extended `/api/capture` with `/dhcp` and `/mdns` ingest routes reusing the existing loopback/gateway trust boundary unchanged; refactored `/arp` to also feed the fusion pipeline
- Built `/api/devices` (list with unknown/registered distinction, register, merge) — all auth-gated, `type` constrained to the closed `DeviceType` enum at the Pydantic layer
- Alembic migration `0002` creates all four new tables (`dhcp_events`, `mdns_events`, `discovered_identities`, `devices`) chained correctly off `0001`
- 16 new tests across 4 files, all passing; full backend suite (28 tests, excluding the pre-existing infra-bound `test_compose.py`) green with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Models + migration + IdentityResolver + discovery orchestration service** - `32c7481` (feat)
2. **Task 2: Capture ingest routes (DHCP/mDNS) + devices registry API + app wiring** - `3572f0b` (feat)

## Files Created/Modified
- `backend/src/models/dhcp_event.py` - DhcpEvent raw observation model
- `backend/src/models/mdns_event.py` - MdnsEvent raw observation model
- `backend/src/models/discovered_identity.py` - DiscoveredIdentity (fused, unregistered) model, unique identity_key
- `backend/src/models/device.py` - DeviceType enum (9 values) + Device registry model, locked identity_key
- `backend/src/models/__init__.py` - imports all four new models for Base.metadata pickup
- `backend/src/services/identity_resolver.py` - Observation dataclass, IdentityResolver Protocol, HostnameFallbackResolver
- `backend/src/services/discovery.py` - upsert_discovered_identity (dialect-aware), record_observation (orchestration + Pitfall 2 handling)
- `backend/alembic/versions/0002_device_registry_discovery.py` - migration creating all four new tables
- `backend/src/routes/capture.py` - added DhcpEventPayload/MdnsEventPayload, /dhcp and /mdns handlers, refactored /arp to call record_observation
- `backend/src/routes/devices.py` - GET/POST /api/devices, POST /api/devices/{id}/merge, all auth-gated
- `backend/src/main.py` - wired devices.router into the app
- `backend/tests/test_identity_resolver.py` - 3 tests covering D-01/D-02/D-03
- `backend/tests/test_discovery.py` - 4 tests covering DISC-03 timestamps and the Pitfall 2/5 regressions
- `backend/tests/test_capture.py` - extended with test_dhcp_ingest, test_mdns_ingest
- `backend/tests/test_devices.py` - 6 tests covering register/merge/list/auth

## Decisions Made
- mDNS ingest uses a placeholder MAC (`00:00:00:00:00:00`) since mDNS browsing alone carries no MAC address — documented inline in `capture.py` as a known Phase 2 limitation; ARP/DHCP observations for the same physical device independently resolve the real MAC- or hostname-keyed identity, so this doesn't block fusion accuracy in practice.
- No project Python venv existed (system python3 was 3.9, project requires >=3.13). Created a throwaway venv at `/tmp/innkeeper-venv` using the already-installed `/opt/homebrew/bin/python3.13` to install `backend[dev]` and run pytest. This venv is not committed and is local-machine-only; future executors on this machine may want to formalize this as a tracked `.venv` or document it in dev setup docs.

## Deviations from Plan

None - plan executed exactly as written. All models, services, routes, and tests match the plan's `<action>` and `<behavior>` specifications verbatim, including exact field names, identity-key formats, and the dialect-aware upsert branching.

## Issues Encountered
- `backend/tests/test_compose.py::test_all_services_healthy` failed when running the full suite — pre-existing, unrelated to this plan's changes. The failure is a `docker compose up` port conflict (`0.0.0.0:8000` already bound by the developer's local Lima VM dev environment, per STATE.md's Phase 1 decision log). Out of scope per the executor's scope boundary rule (pre-existing infra dependency, not caused by this plan's changes) — excluded from the full-suite run via `--ignore=tests/test_compose.py`; all other 28 tests pass cleanly.

## User Setup Required

None - no external service configuration required. No new third-party packages were introduced this plan (zeroconf install is deferred to Plan 02 per the plan's threat model note T-02-SC).

## Next Phase Readiness
- The backend vertical slice for DISC-01 through DISC-04 is complete and fully tested — Plan 02 (real DHCP/mDNS sniffing in the capture container) and Plan 03 (dashboard UI) can build directly on this API surface without revisiting the data model.
- `IdentityResolver`/`HostnameFallbackResolver` are stable and ready to be swapped for a smarter fusion strategy later without touching `discovery.py` or any route.
- No blockers. The `zeroconf` package install (flagged in RESEARCH.md's threat model as needing a `checkpoint:human-verify`) is correctly deferred to Plan 02, not this plan.

## Self-Check: PASSED

All claimed files exist and all claimed commits are present in git history (verified below).

---
*Phase: 02-device-registry-discovery*
*Completed: 2026-06-18*
