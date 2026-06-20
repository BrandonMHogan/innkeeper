---
phase: 04-security
plan: 01
status: complete
---

# Plan 04-01 Summary: Security Data Layer Foundation

## What Was Built

Phase 4's foundational data layer: three framework-free pure-function/Protocol
services and four new/modified database tables that every later Phase 4 plan
(routes, capture-container scan loop) depends on.

### Task 1 — Pure-function services
- `backend/src/services/port_rules.py` — `RISKY_PORTS` frozenset (universal
  unauthenticated/legacy-remote-access ports), `EXPECTED_PORTS` dict keyed by
  `DeviceType`, `evaluate_open_ports()` returning `(risky_open, unexpected_open)`.
  Zero sqlalchemy/DB imports — verified by grep.
- `backend/src/services/security_status.py` — `SecurityStatus` enum
  (GOOD/WARNING/CRITICAL) and `derive_status()` implementing D-06's exact
  precedence (critical > warning > good), with never-scanned correctly
  defaulting to GOOD (Pitfall 3). Zero sqlalchemy/DB imports.
- `backend/src/services/threat_intel_source.py` — `ThreatIntelSource` Protocol
  + `StaticBlocklistSource` concrete implementation, mirroring
  `bandwidth_source.py`'s swappable-source shape exactly, including a
  docstring naming the future opt-in `RemoteFeedSource` (D-10). Lazy singleton
  via `get_default_threat_intel_source()`.
- `backend/src/data/firehol_level1.netset` — vendored FireHOL Level 1
  blocklist (dshield/feodo/fullbogons/spamhaus_drop), fetched verbatim with
  original header comments intact (`# Source File Date: Sat Jun 20 05:59:39
  UTC 2026`), 4558 CIDR entries.
- Three new pytest files (`test_port_rules.py`, `test_security_status.py`,
  `test_threat_intel.py`), all fixture-free pure-function/unit style matching
  `test_domain_grouping.py`'s convention. All 11 specified behavior cases pass.

### Task 2 — Schema
- `backend/src/models/device.py` — added `security_status` (SAEnum, defaults
  to `"good"`), `last_scanned_at` (nullable timestamp), `last_known_ip`
  (nullable, 45-char) columns to the existing `Device` class, in place,
  preserving every existing column.
- `backend/src/models/port_scan_result.py` — new `PortScanResult` history
  table (`id`, `device_id` FK, `scanned_at`, `open_ports` as portable JSON
  column).
- `backend/src/models/security_alert.py` — new `SecurityAlert` model +
  `SecurityAlertType` enum (UNKNOWN_DEVICE/MALICIOUS_IP/SUSPICIOUS_TRAFFIC/
  UNEXPECTED_PORT), reusing `SecurityStatus` as the severity enum per D-11
  (no parallel severity enum introduced).
- `backend/src/models/pending_scan_request.py` — new `PendingScanRequest`
  DB-backed queue table (`id`, `device_id` FK, `requested_at`, `claimed_at`).
- `backend/alembic/versions/0005_security.py` — migration `revision="0005"`,
  `down_revision="0004"`, adding the three `devices` columns and creating all
  three new tables as plain relational tables (no `create_hypertable` calls).
- `backend/tests/conftest.py` — added `pending_scan_request`, `port_scan_result`,
  `security_alert` to the explicit model-import list so `Base.metadata.create_all`
  picks up the new tables in the in-memory SQLite test fixture.

## Verification

- `pytest tests/test_port_rules.py tests/test_security_status.py
  tests/test_threat_intel.py -x -v` — 11/11 passed.
- `pytest tests/test_devices.py -x -v` — 9/9 passed, no regression from the
  in-place `Device` extension.
- Full suite (`pytest`) — 80/80 passed.
- `grep -n "^import\|^from" src/services/port_rules.py
  src/services/security_status.py` confirms zero sqlalchemy/`src.database`
  imports in either pure-function file.
- Migration file structurally validated (module imports cleanly, `revision`/
  `down_revision`/`upgrade`/`downgrade` all present and correctly wired) — full
  `alembic upgrade head` against a live Postgres was not run in this dev
  environment (no Postgres instance available here), consistent with the
  plan's stated success criteria.

## Deviations From Plan

None. All files matched the plan's specified shapes, column types, and
function signatures exactly.

## Key Decisions / Notes for Downstream Plans

- Used `/tmp/innkeeper-venv313` (an existing Python 3.13 venv already present
  on this dev machine from prior phase work) to run pytest, since no
  project-local venv exists yet and the project requires Python >=3.13.
- The vendored blocklist snapshot date (`Source File Date: Sat Jun 20
  05:59:39 UTC 2026`) is preserved in the file header per Pitfall 4 — a
  future release-cadence reminder to refresh it lives in CONTEXT.md/RESEARCH.md,
  not repeated here.
- `Device.last_known_ip` is schema-only in this plan — wiring
  `discovery.py`'s `record_observation()` to actually populate it from ARP's
  `src_ip` is explicitly deferred to Plan 04-02 per the plan's task 2 action
  text.
- This plan ships no routes and no capture-container code by design — it is
  purely the schema + business-logic substrate for later Phase 4 waves.
