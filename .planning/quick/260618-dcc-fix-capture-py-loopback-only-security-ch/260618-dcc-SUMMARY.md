---
phase: quick
plan: 260618-dcc
subsystem: backend/capture-ingest
tags: [security, docker, networking, tdd]
dependency-graph:
  requires: []
  provides:
    - "Runtime default-gateway detection trusted alongside loopback for /api/capture/arp"
  affects:
    - backend/src/routes/capture.py
tech-stack:
  added: []
  patterns:
    - "Module-load-time runtime detection with injectable path constant for testability (_PROC_NET_ROUTE_PATH)"
key-files:
  created: []
  modified:
    - backend/src/routes/capture.py
    - backend/tests/test_capture.py
decisions:
  - "Gateway IP is never hardcoded — always parsed live from /proc/net/route at module import, with broad try/except returning None on any failure (fail-safe to loopback-only)"
metrics:
  duration: "~15 min"
  completed: "2026-06-18"
---

# Quick Task 260618-dcc: Fix capture.py loopback-only security check Summary

Added runtime default-gateway detection (`_detect_default_gateway()`, parsing `/proc/net/route`) merged into a computed `_TRUSTED_HOSTS` frozenset alongside loopback, so Docker hairpin-NATed capture-container traffic is trusted while genuinely external LAN clients remain rejected with 403.

## Task 1: COMPLETE (committed)

**Commit:** `8054f07` — fix(quick-260618-dcc): trust runtime-detected default gateway for capture ingest

Implemented exactly per plan:
- `backend/src/routes/capture.py`: added `_PROC_NET_ROUTE_PATH` module constant (injectable for tests), `_detect_default_gateway() -> str | None` (reads `/proc/net/route`, finds the `00000000` destination row, decodes the little-endian hex gateway field via `socket.inet_ntoa`, wrapped in broad `try/except (OSError, ValueError, IndexError)` returning `None` on any failure). Replaced the static `_LOOPBACK_HOSTS` tuple with a computed `_TRUSTED_HOSTS` frozenset built once at module load (`{"127.0.0.1", "::1"}` plus the detected gateway if found). `ingest_arp` now checks `client_host not in _TRUSTED_HOSTS`. No hardcoded gateway literal anywhere (verified via `grep -n "172\." backend/src/routes/capture.py` — no matches).
- `backend/tests/test_capture.py`: added `test_arp_ingest_accepts_detected_gateway` (monkeypatches `capture_module._TRUSTED_HOSTS` to include a fake gateway IP `10.99.0.1`, proves a request from that exact peer is accepted with 201) and `test_detect_default_gateway_fails_safe_on_bad_path` (monkeypatches `_PROC_NET_ROUTE_PATH` to a nonexistent path, asserts `_detect_default_gateway()` returns `None` without raising).

**Test results:** All 4 tests in `tests/test_capture.py` pass (ran via a Python 3.13.13 venv at `/tmp/innkeeper-venv-dcc`, since system Python was too old):

```
tests/test_capture.py::test_arp_ingest PASSED
tests/test_capture.py::test_arp_ingest_rejects_non_loopback PASSED
tests/test_capture.py::test_arp_ingest_accepts_detected_gateway PASSED
tests/test_capture.py::test_detect_default_gateway_fails_safe_on_bad_path PASSED
```

Full backend suite also run for regression check: 14 passed, 1 pre-existing unrelated failure (`tests/test_compose.py::test_all_services_healthy` — fails identically on `main` with no changes applied, due to local port 8000 already in use / docker-compose environment conflict; confirmed via `git stash` before/after comparison). This failure is out of scope (Rule: scope boundary — pre-existing, unrelated to this task's files) and not caused by this change.

## Task 2: Live verification — PASSED (performed by orchestrator)

Rebuilt and restarted `api` in the running Lima VM (`limactl shell innkeeper`, `docker compose up -d --build api`). POSTed a test ARP payload from inside the `capture` container to `http://127.0.0.1:8000/api/capture/arp` (same path capture.py itself uses) — got `201 {"ok":true}` (previously `403 Forbidden`), confirming the api container now trusts its own Docker bridge gateway (`172.18.0.1`) for hairpin-NATed loopback traffic.

**D-05 go/no-go gate: PASS.** Forced a real ARP request (`ip neigh del` + `ping -I lima0`) and confirmed via `docker compose exec db psql ... SELECT * FROM arp_events` that the genuine LAN-captured packet (`src_mac 52:55:55:ba:0d:04`, the VM's own MAC, `who-has 10.0.0.1` from `10.0.0.161`) landed in the table — proving the full pipeline: real LAN ARP traffic → Scapy capture (network_mode: host) → httpx POST → FastAPI ingest → PostgreSQL/TimescaleDB.

## Deviations from Plan

None — plan executed exactly as written for Task 1.

## Self-Check

- `backend/src/routes/capture.py` modified: FOUND
- `backend/tests/test_capture.py` modified: FOUND
- Commit `8054f07`: FOUND (`git log --oneline | grep 8054f07` matches)
- `grep -n "172\." backend/src/routes/capture.py`: no matches (no hardcoded gateway literal)

## Self-Check: PASSED
