---
phase: 03-live-traffic-bandwidth
plan: 01
subsystem: backend-storage
tags: [timescaledb, sqlalchemy, alembic, tldextract, mac-rotation]
dependency_graph:
  requires: []
  provides:
    - traffic_flows hypertable + TrafficFlow model
    - device_mac_history table + DeviceMacHistory model
    - BandwidthSource Protocol + PassiveCaptureBandwidthSource
    - registered_domain() grouping function
  affects:
    - backend/src/services/discovery.py (record_observation)
tech_stack:
  added:
    - tldextract==5.3.0
  patterns:
    - Protocol + single concrete class (BandwidthSource, mirrors IdentityResolver)
    - dialect-aware pg_insert/sqlite_insert upsert (mirrors upsert_discovered_identity)
key_files:
  created:
    - backend/src/models/traffic_flow.py
    - backend/src/models/device_mac_history.py
    - backend/alembic/versions/0004_traffic_flows.py
    - backend/src/services/bandwidth_source.py
    - backend/src/services/domain_grouping.py
    - backend/tests/test_mac_history.py
    - backend/tests/test_domain_grouping.py
  modified:
    - backend/src/services/discovery.py
    - backend/pyproject.toml
decisions:
  - "Added upsert_device_mac_history() to discovery.py as a new dialect-aware upsert helper, reusing the exact pg_insert/sqlite_insert .on_conflict_do_update() shape already established by upsert_discovered_identity — no third upsert style introduced"
  - "tldextract pinned at 5.3.0, confirmed current via pip index versions at implementation time"
metrics:
  duration: ~25min
  completed: 2026-06-19
---

# Phase 3 Plan 1: Traffic/Bandwidth Storage Foundation Summary

Built the TimescaleDB schema, MAC-rotation-aware history table, swappable bandwidth-source interface, and registered-domain grouping service that every other Phase 3 plan (capture sniffer, ingest route, SSE/query routes, frontend) depends on.

## What Was Built

**Task 1 — Schema (traffic_flows + device_mac_history):**
- `TrafficFlow` model: composite PK `(time, device_mac, dst_ip, dst_port, protocol)`, `bytes` float column, nullable `dst_hostname` (always raw, never grouped — D-10 grouping happens at query time only)
- `DeviceMacHistory` model: composite PK `(device_id, mac)`, `first_seen`/`last_seen` timestamps — closes the MAC-rotation blind spot identified in 03-RESEARCH.md Pitfall 1 / Open Question 1
- Migration `0004_traffic_flows.py`: creates both tables (traffic_flows as a hypertable via `create_hypertable`, device_mac_history as a plain table), 4 hierarchical continuous aggregates (`bandwidth_hourly` → `bandwidth_daily` → `bandwidth_weekly`/`bandwidth_monthly`) with scaled refresh policies, and compression policies on both `bandwidth_metrics` and `traffic_flows` — zero `add_retention_policy` calls anywhere (D-06 compliance verified via grep)

**Task 2 — Wiring (MAC history, bandwidth source, domain grouping):**
- `domain_grouping.py`: module-level `tldextract.TLDExtract(suffix_list_urls=())` offline extractor + `registered_domain()` pure function — groups subdomains under their registered domain (including multi-part PSL suffixes like `github.io`), passes bare IPs through unchanged
- `bandwidth_source.py`: `BandwidthSource` Protocol + `PassiveCaptureBandwidthSource` concrete implementation, mirroring `identity_resolver.py`'s Protocol+concrete-class shape exactly — ready for Plan 03's ingest route and a future Phase 7 UniFi adapter
- `discovery.py`: added `upsert_device_mac_history()` (same dialect-branching upsert pattern as `upsert_discovered_identity`) and wired it into `record_observation`'s Device-branch fast path — every `last_known_mac` update now also upserts a `DeviceMacHistory` row

## Verification

- `pytest tests/test_mac_history.py tests/test_domain_grouping.py -x` — 7 passed
- `pytest` (full suite) — 52 passed, no regressions
- `grep -c "add_retention_policy" backend/alembic/versions/0004_traffic_flows.py` confirmed the only match is the explanatory comment ("Deliberately NOT calling add_retention_policy()"), not an actual call — D-06 compliance verified

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLite drops tzinfo on round-trip, test assertion needed adjustment**
- **Found during:** Task 1, writing `test_upsert_same_device_mac_pair_no_integrity_error`
- **Issue:** SQLite (the in-memory test fixture dialect) stores `DateTime(timezone=True)` columns without preserving tzinfo on read-back, so a naive `==` comparison between an aware and naive datetime failed even though the upsert logic itself was correct
- **Fix:** Compare with `.replace(tzinfo=timezone.utc)` on the read-back value before asserting equality — a test-only adjustment, not a model/migration change
- **Files modified:** backend/tests/test_mac_history.py
- **Commit:** d2de5cd

**2. [Rule 2 - Missing functionality] Added an explicit integration test for record_observation's MAC-history wiring**
- **Found during:** Task 2
- **Issue:** The plan's behavior tests for Task 2 only covered `registered_domain()`; the Device-branch wiring itself (the actual closing of the MAC-rotation blind spot) had no direct test
- **Fix:** Added `test_record_observation_writes_mac_history_for_registered_device` to test_mac_history.py, exercising the full `record_observation` → `upsert_device_mac_history` path against a registered Device
- **Files modified:** backend/tests/test_mac_history.py
- **Commit:** 379562d

## Threat Flags

None — this plan's threat model already covers all new surface (Alembic migration trust, device_mac_history information disclosure, continuous aggregate refresh DoS, tldextract supply-chain) with explicit dispositions in 03-01-PLAN.md's threat_model section; no new surface was introduced beyond what was already modeled.

## Self-Check: PASSED

- FOUND: backend/src/models/traffic_flow.py
- FOUND: backend/src/models/device_mac_history.py
- FOUND: backend/alembic/versions/0004_traffic_flows.py
- FOUND: backend/src/services/bandwidth_source.py
- FOUND: backend/src/services/domain_grouping.py
- FOUND: backend/tests/test_mac_history.py
- FOUND: backend/tests/test_domain_grouping.py
- FOUND commit d2de5cd
- FOUND commit 379562d
