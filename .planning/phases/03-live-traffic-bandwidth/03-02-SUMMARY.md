---
phase: 03-live-traffic-bandwidth
plan: 02
subsystem: capture
tags: [dpkt, raw-socket, capture, dns-cache, wan-filter]
dependency_graph:
  requires:
    - capture/capture.py (existing stop_event, SIGTERM handling, httpx.post pattern)
  provides:
    - capture/traffic_sniff.py (dpkt-based WAN traffic sniff loop, 5-tuple aggregation, passive DNS cache)
    - fourth capture thread (traffic-sniff) in capture.py's main()
  affects:
    - capture/capture.py (added traffic_thread alongside arp/dhcp/mdns threads)
tech_stack:
  added:
    - dpkt==1.9.8
  patterns:
    - Aggregated capture loop (no per-packet POST) — RESEARCH.md Pattern 1
    - Passive DNS sniffing for IP-to-hostname cache — RESEARCH.md Pattern 2
key_files:
  created:
    - capture/traffic_sniff.py
  modified:
    - capture/capture.py
    - capture/requirements.txt
decisions:
  - "dpkt==1.9.8 pinned, confirmed current via pip index versions at implementation time"
  - "FLUSH_INTERVAL=7 seconds, midpoint of locked 5-10s range per D-01/D-11"
  - "_iso8601() helper converts time.monotonic() readings to wall-clock ISO8601 strings for the interval_start/interval_end payload fields, since the flow loop tracks elapsed time via monotonic() but the payload contract requires wall-clock timestamps"
metrics:
  duration: ~20min
  completed: 2026-06-19
---

# Phase 3 Plan 2: Traffic-Sniff Capture Loop Summary

Added the second sniffing capability to the existing capture container: a dpkt-based raw-socket loop that observes WAN-bound packets only, aggregates bytes by 5-tuple over a 7-second window, builds a passive DNS-sniffed IP-to-hostname cache, and POSTs one rollup batch per window to the API (the ingest route itself does not exist until Plan 03 lands — POST failures against the missing route are expected at this stage).

## What Was Built

**Task 0 (checkpoint, resolved before this agent started):** Package-legitimacy checkpoint for `dpkt` was approved by the user after reviewing https://pypi.org/project/dpkt/ and github.com/kbandla/dpkt's commit history.

**Task 1 — `capture/traffic_sniff.py`:**
- `_is_wan_bound(src_ip, dst_ip)`: classifies both IPs via `ipaddress.ip_address(...).is_private` and returns `True` only when exactly one side is private — implements D-03's WAN-only scope, dropping LAN-to-LAN frames.
- `run_traffic_sniff(stop_event)`: opens a raw `AF_PACKET`/`SOCK_RAW` socket (`ETH_P_ALL`), loops with a 1.0s socket timeout so `stop_event` is re-checked even with no traffic, parses each frame with `dpkt.ethernet.Ethernet`, skips non-IP frames, applies `_is_wan_bound`, and for UDP port-53 traffic attempts `dpkt.dns.DNS` parsing (wrapped in `try/except dpkt.dpkt.UnpackError`) to populate `dns_cache` from A-records — DNS traffic is excluded from flow accounting (it is metadata, not user bandwidth). All other WAN-bound frames are aggregated into `flows: dict[5-tuple, bytes]` keyed by `(src_mac, dst_ip, dst_port, protocol)`.
- Every `FLUSH_INTERVAL` (7s) seconds, `_flush_and_post` builds the rollup payload (`interval_start`/`interval_end`/`flows` list, each flow entry including `dst_hostname` resolved from `dns_cache` when present) and POSTs via `httpx.post(f"{API_URL}/api/capture/traffic", ...)`, wrapped in the same `try/except Exception` swallow-and-continue style as `capture.py`'s existing handlers. `flows` is cleared after each flush; `dns_cache` persists across flushes as a slowly-growing lookup table.
- The entire per-packet parse body is wrapped in a broad `except Exception` so a single malformed frame cannot crash the sniff thread.
- `dpkt==1.9.8` added to `capture/requirements.txt` (confirmed current via `pip index versions dpkt`).

**Task 2 — `capture/capture.py` wiring:**
- Added `from traffic_sniff import run_traffic_sniff` (plain sibling-module import, matching the flat `capture/` directory layout with no `__init__.py`).
- Added `traffic_thread = threading.Thread(target=run_traffic_sniff, args=(stop_event,), name="traffic-sniff")` to `main()`, started alongside the existing arp/dhcp/mdns threads and joined alongside them — sharing the single module-level `stop_event` so SIGTERM propagates to all four threads.

## Verification

- `python3 -c "import ast; ast.parse(open('traffic_sniff.py').read())"` — syntax valid
- `grep -q "def run_traffic_sniff" traffic_sniff.py && grep -q "_is_wan_bound" traffic_sniff.py` — both present
- `grep -q "run_traffic_sniff" capture/capture.py` and `traffic_thread.join()` present — wiring confirmed
- `grep -c "httpx.post" capture/traffic_sniff.py` → 1 (single POST call site, confirming aggregation-only, never per-packet POST)
- Manual end-to-end verification (real WAN traffic + `docker compose up` + observing `[capture]` log lines for traffic POSTs) is deferred to integration once Plan 03's ingest route exists, per this plan's own scope boundary — POST attempts against the not-yet-existing `/api/capture/traffic` route will fail with connection-refused/404 in the interim, which is expected and does not block this plan's verification.

## Deviations from Plan

None — plan executed exactly as written. The only implementation detail not explicitly spelled out in the plan's `<action>` block was how to convert the loop's `time.monotonic()`-based interval tracking into the wall-clock ISO8601 `interval_start`/`interval_end` strings the payload contract requires; resolved with a small `_iso8601()` helper that combines the monotonic delta with the current wall clock at flush time (Rule 2 — minor missing detail needed for correctness, not an architectural decision).

## Threat Flags

None — this plan's threat model (T-03-04 DoS via unbounded flows dict, T-03-05 DNS cache poisoning, T-03-06 information disclosure via raw capture, T-03-SC dpkt supply-chain) already covers all new surface introduced by `traffic_sniff.py` and the capture.py thread wiring, with explicit dispositions (mitigate/accept) already assigned. No new surface beyond what was modeled.

## Self-Check: PASSED

- FOUND: capture/traffic_sniff.py
- FOUND: capture/capture.py (modified)
- FOUND: capture/requirements.txt (modified)
- FOUND commit b5619d9 (Task 1)
- FOUND commit 4ad61fc (Task 2)
