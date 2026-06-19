---
phase: 03-live-traffic-bandwidth
plan: 03
subsystem: backend-api
tags: [sse-starlette, fastapi, timescaledb, sqlalchemy, mac-rotation, sse]
dependency_graph:
  requires:
    - backend/src/models/traffic_flow.py (Plan 01)
    - backend/src/models/device_mac_history.py (Plan 01)
    - backend/src/services/bandwidth_source.py (Plan 01)
    - backend/src/services/domain_grouping.py (Plan 01)
    - capture/traffic_sniff.py (Plan 02, POST payload contract)
  provides:
    - POST /api/capture/traffic ingest route
    - GET /api/traffic/stream (SSE live feed)
    - GET /api/traffic/bandwidth/{device_id}
    - GET /api/traffic/bandwidth/network
    - GET /api/traffic/devices/{device_id}/destinations
    - traffic_broadcaster background snapshot-refresh task
  affects:
    - backend/src/main.py (lifespan, router registration)
    - backend/tests/conftest.py (model imports, seeded_traffic_db fixture)
tech_stack:
  added:
    - sse-starlette==3.4.4
  patterns:
    - Single global SSE broadcaster (D-13) — one background task computes a
      shared snapshot, all clients fan out from shared state
    - Shared _resolve_device_macs() helper for MAC-rotation-aware queries
      (DeviceMacHistory union Device.last_known_mac)
    - Dialect-branching query (Postgres continuous aggregate vs portable
      SQLite GROUP BY fallback) for network_bandwidth
key_files:
  created:
    - backend/src/routes/traffic.py
    - backend/src/services/traffic_broadcaster.py
    - backend/tests/test_traffic_stream.py
    - backend/tests/test_bandwidth_query.py
    - backend/tests/test_traffic_destinations.py
    - backend/tests/test_bandwidth_aggregates.py
  modified:
    - backend/src/routes/capture.py
    - backend/src/main.py
    - backend/pyproject.toml
    - backend/tests/conftest.py
decisions:
  - "sse-starlette pinned at 3.4.4 (Task 0 checkpoint approved by user after independent PyPI verification matching 03-RESEARCH.md's verdict)"
  - "GET /bandwidth/network registered before GET /bandwidth/{device_id} — FastAPI route matching is declaration-order-sensitive; the literal 'network' segment was being captured by the path-parameter route and failing int parsing before reordering"
  - "conftest.py now explicitly imports every model module before Base.metadata.create_all — previously only models reachable via an indirect import chain (e.g. through src.main) got registered, which silently dropped device_mac_history from any test using test_db without first importing src.main"
metrics:
  duration: ~45min
  completed: 2026-06-19
---

# Phase 3 Plan 3: Traffic/Bandwidth API Routes Summary

Built the API-side half of the traffic/bandwidth pipeline: the trusted ingest route consuming Plan 02's capture rollups, the D-13 single-global-SSE-channel live feed, and the MAC-rotation-aware historical query routes (per-device bandwidth, network-wide daily/weekly/monthly, per-device destinations) — the seam connecting Plan 01's storage layer, Plan 02's data producer, and Plan 04's frontend consumer.

## What Was Built

**Task 0 (checkpoint, resolved before this agent started):** Package-legitimacy checkpoint for `sse-starlette` was approved by the user ("approved — pin sse-starlette==3.4.4") after independently confirming via `pip index versions sse-starlette` that 3.4.4 is the current latest release, resolving the version discrepancy flagged in 03-RESEARCH.md.

**Task 1 — `POST /api/capture/traffic` ingest route:**
- `TrafficFlowPayload`/`TrafficRollupPayload` Pydantic models matching Plan 02's exact `traffic_sniff.py` POST shape (`interval_start`, `interval_end`, `flows[]`)
- `ingest_traffic` reuses the existing `_TRUSTED_HOSTS` loopback/gateway trust check verbatim (no second trust-boundary implementation)
- Writes one `TrafficFlow` row per 5-tuple flow entry, groups by `src_mac`, sums bytes, and calls `PassiveCaptureBandwidthSource.write_rollup()` once per distinct device_mac
- `bytes_rx` hardcoded to `0.0` (documented known v1 limitation — single-vantage-point passive capture cannot observe inbound return traffic with 5-tuple fidelity; `bytes_tx` is real captured data, satisfying TRAF-02)
- T-03-08 mitigation: rejects rollups with more than 5000 distinct flow entries (413) to bound worst-case write volume from a misbehaving/compromised capture process

**Task 2 — SSE broadcaster + live stream route:**
- `traffic_broadcaster.py`: `_compute_snapshot()` queries `TrafficFlow` rows within a 5-minute rolling window (D-12), resolves device names via `Device.last_known_mac` (acceptable for the live snapshot since the window is far shorter than any realistic MAC-rotation interval), ranks `top_talkers` descending by summed bytes, and caps `active_connections` at 100 most-recent rows
- `update_snapshot_loop()` recomputes the snapshot every 7 seconds (D-11, matching Plan 02's `FLUSH_INTERVAL`), using `asyncio.wait_for(stop_event.wait(), timeout=7)` so shutdown is responsive rather than blocking a full sleep cycle
- `GET /api/traffic/stream`: `EventSourceResponse`-based SSE endpoint behind `require_auth`, polling the shared snapshot every 1s and yielding only on change (D-13's single global channel)
- `main.py`'s `lifespan` now starts `update_snapshot_loop` as a background `asyncio.Task` before `yield`, and cancels/awaits it during shutdown before `engine.dispose()`

**Task 3 — Historical bandwidth, network aggregates, and destinations routes:**
- `_resolve_device_macs()` shared helper: unions `DeviceMacHistory` rows with the device's current `last_known_mac`, 404s if the device doesn't exist — used by both `device_bandwidth` and `device_destinations` so the MAC-rotation fix (Pitfall 1/Open Question 1) is implemented exactly once
- `GET /api/traffic/bandwidth/{device_id}`: queries raw `BandwidthMetric` rows filtered by the resolved MAC set and an arbitrary `start`/`end` range — proven to support "any time range" (TRAF-02) with no implicit truncation
- `GET /api/traffic/bandwidth/network`: dialect-branches on `db.bind.dialect.name` — reads the Postgres continuous aggregate (`bandwidth_daily`/`weekly`/`monthly`, hardcoded literal table names selected only via a `Literal["daily","weekly","monthly"]`-typed parameter, T-03-10 mitigation) on Postgres, falls back to a portable Python `GROUP BY`-equivalent bucketing over raw rows on any other dialect (the SQLite test fixture)
- `GET /api/traffic/devices/{device_id}/destinations`: groups raw `TrafficFlow` rows by `registered_domain(dst_hostname)` (D-10) with raw-IP fallback when no hostname was ever resolved (D-09), sorted descending by bytes

## Verification

- `pytest tests/test_traffic_stream.py tests/test_bandwidth_query.py tests/test_traffic_destinations.py tests/test_bandwidth_aggregates.py -x` — 15 passed
- `pytest` (full suite) — 67 passed, no regressions
- `grep -c "Depends(require_auth)" backend/src/routes/traffic.py` → 5 (every new GET route gated, exceeds the required minimum of 4)
- Manual lifespan smoke test (`create_app()` + `lifespan_context`) confirms the background snapshot-refresh task starts and stops cleanly without hanging shutdown

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FastAPI route declaration order caused /bandwidth/network to be captured by /bandwidth/{device_id}**
- **Found during:** Task 3, running `test_bandwidth_aggregates.py`
- **Issue:** `GET /bandwidth/{device_id}` was declared before `GET /bandwidth/network` in the plan's literal task order; FastAPI matches routes in declaration order, so a request to `/bandwidth/network` matched the path-parameter route first, with `"network"` failing `int` parsing for `device_id` (422)
- **Fix:** Reordered the route definitions so `network_bandwidth` (the literal-path route) is declared before `device_bandwidth` (the path-parameter route)
- **Files modified:** backend/src/routes/traffic.py
- **Commit:** c812384

**2. [Rule 1 - Bug] conftest.py's test_db fixture silently dropped device_mac_history (and any model not reachable via an indirect import) from Base.metadata**
- **Found during:** Task 3, writing `seeded_traffic_db` — `INSERT INTO device_mac_history` failed with `no such table: device_mac_history` even though the model and migration both exist
- **Issue:** SQLAlchemy only registers a model's table on `Base.metadata` once its module is imported somewhere in the process. `test_db`'s `Base.metadata.create_all` only "worked" for prior tests because `client` (which imports `src.main`) was always used first in the same test, pulling in the full import chain incidentally. A test using `test_db` directly (no `client`) hit the gap.
- **Fix:** conftest.py now explicitly imports every model module (`app_settings`, `arp_event`, `bandwidth`, `device`, `device_mac_history`, `dhcp_event`, `discovered_identity`, `mdns_event`, `traffic_flow`) before any fixture runs, making `test_db` self-sufficient regardless of which other fixtures a test does or doesn't use
- **Files modified:** backend/tests/conftest.py
- **Commit:** c812384

**3. [Rule 2 - Missing functionality] Test client fixtures needed an authenticated-session helper for the new auth-gated routes**
- **Found during:** Task 3, first run of `test_bandwidth_query.py` returned 401 instead of 200
- **Issue:** The plan's `<action>` blocks describe the routes but the existing `client`/`test_db` fixtures don't pre-authenticate a session; `test_devices.py` already established a `_login()` helper pattern for exactly this need, but the new test files needed their own way to reach it for device-scoped query routes
- **Fix:** Added a shared `_login()` helper to conftest.py (matching `test_devices.py`'s existing pattern) and wired `seeded_traffic_db` to depend on the `client` fixture, log in once, and yield `(client, device_id)` so all three new test files get a ready-to-use authenticated client
- **Files modified:** backend/tests/conftest.py, backend/tests/test_bandwidth_query.py, backend/tests/test_traffic_destinations.py, backend/tests/test_bandwidth_aggregates.py
- **Commit:** c812384

## Threat Flags

None — this plan's threat model (T-03-07 spoofed ingest, T-03-08 oversized rollup DoS, T-03-09 SSE information disclosure, T-03-10 dialect-branching SQL tampering, T-03-SC sse-starlette supply-chain) already covers all new surface introduced by `routes/traffic.py`, `routes/capture.py`'s new endpoint, and `traffic_broadcaster.py`, with explicit dispositions (mitigate/accept) already assigned in 03-03-PLAN.md. No new surface was introduced beyond what was already modeled.

## Self-Check: PASSED

- FOUND: backend/src/routes/traffic.py
- FOUND: backend/src/services/traffic_broadcaster.py
- FOUND: backend/tests/test_traffic_stream.py
- FOUND: backend/tests/test_bandwidth_query.py
- FOUND: backend/tests/test_traffic_destinations.py
- FOUND: backend/tests/test_bandwidth_aggregates.py
- FOUND commit cf3a9c3 (Task 1)
- FOUND commit 8730e19 (Task 2)
- FOUND commit c812384 (Task 3)
