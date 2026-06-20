---
phase: 04-security
plan: 02
status: complete
---

# Plan 04-02 Summary: Backend Request/Response and Event-Driven Surfaces

## What Was Built

Phase 4's backend API surface on top of Plan 04-01's schema and pure-function
services: a new `/api/security/*` route file, extensions to `/api/capture/*`,
the SEC-02 unknown-device alert hook in `discovery.py`, and the
`devices.py` serializer extension.

### Task 1 — security.py route + bandwidth_anomaly.py service
- `backend/src/services/bandwidth_anomaly.py` — `check_bandwidth_anomaly()`
  (D-09), a read-only query comparing a device's most-recent day of traffic
  against its own 14-day rolling average (`ROLLING_WINDOW_DAYS=14`,
  `ANOMALY_THRESHOLD_MULTIPLIER=3.0`, `MIN_SAMPLE_DAYS=7`), reusing
  `traffic.py`'s `_resolve_device_macs()` directly. This file was left
  uncommitted by a prior interrupted execution attempt; verified against
  the plan spec and reused as-is (no changes needed).
- `backend/src/routes/security.py` — `POST /scan/{device_id}` (queues a
  `PendingScanRequest`), `GET /scan/{device_id}` (latest scan's per-port
  risky/unexpected/expected classification via `evaluate_open_ports()`, or
  `{"scanned_at": None, "ports": []}` if never scanned), `GET /alerts`
  (unacknowledged only), `POST /alerts/{id}/ack`, `POST /alerts/ack-all`.
  All routes gated behind `Depends(require_auth)`.
- `backend/src/main.py` — registered `security.router` under `/api/security`.
- `backend/tests/test_security_scan.py`, `test_bandwidth_anomaly.py` — 14
  new tests, all passing.

### Task 2 — capture.py extensions, devices.py serializer, discovery.py SEC-02 hook
- `backend/src/routes/capture.py`:
  - `POST /scan` — scan-result ingest (loopback-only, `_MAX_OPEN_PORTS=1000`
    bound, 413 on overflow); persists `PortScanResult`, recomputes
    `Device.security_status` via `derive_status()`, checking for existing
    unacknowledged `MALICIOUS_IP`/`SUSPICIOUS_TRAFFIC` alerts so a clean scan
    never silently clears an independent prior signal; inserts an
    `UNEXPECTED_PORT` alert when applicable.
  - `GET /pending-scans` — claim-on-read poll target; only returns
    `PendingScanRequest` rows whose `Device.last_known_ip` is non-null,
    leaving IP-less devices unclaimed for retry.
  - `POST /queue-daily-scans` — queues one `PendingScanRequest` per
    registered `Device` (skips devices with an existing unclaimed request);
    independently calls `check_bandwidth_anomaly()` per device and, on
    `True` with no existing unacknowledged `SUSPICIOUS_TRAFFIC` alert,
    writes the alert and recomputes/persists `Device.security_status` —
    closing the gap where D-09's signal was previously only unit-tested in
    isolation.
  - `ingest_arp` — now persists `Device.last_known_ip` from the payload's
    `src_ip` for any registered device matched by `src_mac`.
  - `ingest_traffic` — checks every flow's `dst_ip` against
    `get_default_threat_intel_source().is_malicious()`; on a hit, resolves
    the `Device` by `src_mac`, inserts a `MALICIOUS_IP` alert, flips
    `security_status` to `critical`, deduped per device+ip within the call.
- `backend/src/routes/devices.py` — `_serialize_device()` gained
  `security_status`/`last_scanned_at` keys.
- `backend/src/services/discovery.py` — `upsert_discovered_identity()` now
  pre-checks whether `identity_key` already exists before the dialect-aware
  upsert; on a genuinely new identity, fires exactly one `UNKNOWN_DEVICE`
  `SecurityAlert` (`device_id=None`) after the upsert commits. Updates to
  an existing identity never re-fire the alert.
- `backend/tests/test_capture.py` (extended), `test_security_alerts.py`
  (new), `test_devices.py` (extended) — 17 new/changed tests, all passing.

## Verification

- `pytest tests/test_security_scan.py tests/test_bandwidth_anomaly.py -x -v`
  — 14/14 passed.
- `pytest tests/test_capture.py tests/test_security_alerts.py tests/test_devices.py -x -v`
  — 31/31 passed.
- Full suite (`pytest`) — 108/108 passed, no regressions.
- Ran via `/tmp/innkeeper-venv313` (Python 3.13 venv), consistent with
  Plan 04-01's environment.

## Deviations From Plan

None. `bandwidth_anomaly.py` (left over from an interrupted prior attempt)
matched the plan's specified shape, constants, and guard logic exactly and
was reused without modification.

## Key Decisions / Notes for Downstream Plans

- `POST /api/capture/scan`'s independent-signal-contribution logic (re-deriving
  `has_malicious_ip_match`/`has_bandwidth_anomaly` from existing unacknowledged
  alerts before calling `derive_status()`) is duplicated in `queue-daily-scans`'
  bandwidth-anomaly branch — both follow the same pattern per the plan's
  action text; no shared helper was extracted since the plan specified the
  logic inline in both places.
- `GET /pending-scans` and `POST /queue-daily-scans` both reuse the file's
  existing `_TRUSTED_HOSTS` check verbatim — no second trust-boundary
  implementation introduced.
- Plan 04-03 (capture container) and Plan 04-04 (frontend) can now build
  against a stable, fully-tested `/api/security/*` and extended
  `/api/capture/*` contract.
