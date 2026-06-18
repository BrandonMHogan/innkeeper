---
phase: 02-device-registry-discovery
plan: 02
subsystem: capture
tags: [scapy, dhcp, mdns, zeroconf, passive-discovery]

# Dependency graph
requires:
  - phase: 02-device-registry-discovery
    plan: 01
    provides: /api/capture/dhcp and /api/capture/mdns ingest routes, IdentityResolver fusion pipeline, loopback/gateway trust boundary
provides:
  - Real passive DHCP sniffer thread in capture/capture.py POSTing to /api/capture/dhcp
  - Real AsyncZeroconf mDNS browser thread in capture/capture.py POSTing to /api/capture/mdns
  - zeroconf pinned in capture/requirements.txt (human-verified package)
affects: [02-03, frontend-dashboard]

# Tech tracking
tech-stack:
  added:
    - "zeroconf==0.148.0 (capture container only)"
  patterns:
    - "Three independent observer threads (ARP/DHCP/mDNS) all honoring one shared module-level threading.Event for stop/SIGTERM"
    - "asyncio.Event bridges a threading.Event into AsyncZeroconf's async-native browser without introducing a second stop mechanism"

key-files:
  created: []
  modified:
    - capture/capture.py
    - capture/requirements.txt

key-decisions:
  - "Pinned zeroconf==0.148.0, not the orchestrator-stated 0.149.16 — live `pip index versions zeroconf` in the execution environment showed 0.148.0 as the latest actually-published version; the human checkpoint approved 'pin the confirmed version' and 0.148.0 is what the real index confirms. Package identity (python-zeroconf, github.com/python-zeroconf/python-zeroconf) was already verified by the orchestrator before dispatch and is unaffected by this version correction."
  - "backend/pyproject.toml NOT modified — no backend-side import of zeroconf constants/types is needed; mDNS browsing stays entirely inside the capture container per Phase 1 D-06 (capture never imports backend code, backend never needs zeroconf)."

patterns-established:
  - "Pattern: bridge a threading.Event into an asyncio-native library's stop signal via a polling watcher task, rather than maintaining two parallel shutdown paths"

requirements-completed: [DISC-01]

# Metrics
duration: 12min
completed: 2026-06-18
---

# Phase 2 Plan 2: Capture DHCP + mDNS Passive Observers Summary

**Extended capture.py with a Scapy BOOTP/DHCP sniffer and an AsyncZeroconf mDNS browser, both running as threads alongside the unchanged ARP sniffer, all sharing one stop_event/SIGTERM shutdown path.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-18T19:05:00Z (approx, post-checkpoint)
- **Tasks:** 2 (Task 1 checkpoint pre-resolved by orchestrator before dispatch)
- **Files modified:** 2

## Accomplishments
- `on_dhcp_packet` parses `hostname` (option 12), `requested_ip` (option 50), and `vendor_class_id` (option 60) from BOOTP/DHCP options and POSTs to `/api/capture/dhcp`, following the exact `try/except Exception as exc: print(...)` shape as the existing ARP handler
- `run_dhcp_sniff()` runs a second `sniff()` call filtered to `udp and (port 67 or port 68)` in its own thread, honoring the same `stop_event`
- `on_service_state_change` / `_post_service_info` / `run_mdns_browser` implement an `AsyncZeroconf` + `AsyncServiceBrowser` passive mDNS listener over a fixed `COMMON_SERVICE_TYPES` allowlist (7 common service types: HTTP, AirPlay, IPP, Chromecast, Spotify Connect, device-info, workstation), POSTing resolved `hostname`/`addresses`/`service_type` to `/api/capture/mdns`
- `_mdns_main()` bridges the module-level `threading.Event` into a local `asyncio.Event` via a 0.5s-poll watcher task — no second stop mechanism introduced (confirmed: exactly one `stop_event = threading.Event()` definition remains)
- `main()` now starts all three observers (ARP, DHCP, mDNS) as named threads and joins all three on shutdown
- `zeroconf==0.148.0` added to `capture/requirements.txt`

## Task Commits

Each task was committed atomically:

1. **Task 2: DHCP sniff thread + capture.py wiring** - `20b339d` (feat)
2. **Task 3: AsyncZeroconf mDNS browser thread** - `21f93aa` (feat)

(Task 1, the `zeroconf` package-legitimacy checkpoint, was pre-resolved by the orchestrator before this executor was dispatched — see Deviations below for the version-pin correction made during Task 2.)

## Files Created/Modified
- `capture/capture.py` - added `on_dhcp_packet`, `run_dhcp_sniff`, `on_service_state_change`, `_post_service_info`, `run_mdns_browser`, `_mdns_main`, `run_mdns_thread`, `COMMON_SERVICE_TYPES`; restructured `main()` to run ARP/DHCP/mDNS each in its own thread, all joined on shutdown
- `capture/requirements.txt` - added `zeroconf==0.148.0`

## Decisions Made
- Pinned `zeroconf==0.148.0` rather than the `0.149.16` string referenced in the orchestrator's pre-dispatch checkpoint note — running `pip index versions zeroconf` in this execution environment showed `0.148.0` as the actual latest published version (full version list confirmed via live PyPI query). The checkpoint's package-identity verification (real `python-zeroconf` project, no typosquat, github.com/python-zeroconf/python-zeroconf) remains valid and unaffected; only the specific patch version differs from what was stated. This is documented as a Rule 1/3 auto-fix: the user's intent ("approved — pin the confirmed version") is honored by pinning to what the live index actually confirms.
- `backend/pyproject.toml` left unmodified — confirmed no backend-side code needs to import `zeroconf` types/constants; the mDNS browser logic is entirely contained in the capture container, consistent with Phase 1 D-06's capture/backend separation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1/3 - blocking/correctness] Corrected zeroconf version pin from 0.149.16 to 0.148.0**
- **Found during:** Task 2 (requirements.txt update)
- **Issue:** The plan's pre-resolved checkpoint instructed pinning `zeroconf==0.149.16` as "approved" by the user, but `pip index versions zeroconf` run live in this execution environment shows `0.148.0` as the latest actually-published version — `0.149.16` does not exist in the real PyPI index.
- **Fix:** Pinned `zeroconf==0.148.0` (the real latest version) instead of the non-existent `0.149.16`. Package identity/legitimacy (already verified by the orchestrator: real `python-zeroconf` project, github.com/python-zeroconf/python-zeroconf, no typosquat) is unaffected by this correction — only the specific patch version differs.
- **Files modified:** `capture/requirements.txt`
- **Commit:** `20b339d`

## User Setup Required

None — `zeroconf` is a pure-Python package with no external service configuration. Live LAN verification that mDNS multicast traffic actually reaches the capture container under `network_mode: host` (RESEARCH.md Pitfall 4 / Assumption A3) is explicitly deferred to a manual phase-level execution checkpoint per the plan's `<verification>` section and VALIDATION.md's Manual-Only Verifications table — not blocking this plan's automated acceptance criteria.

## Known Stubs

None. All three observer threads (ARP, DHCP, mDNS) are fully wired to real Scapy/AsyncZeroconf APIs and POST to the correct, already-implemented `/api/capture/{arp,dhcp,mdns}` endpoints (built in Plan 01). No placeholder/mock data paths were introduced.

## Next Phase Readiness
- The capture container now passively observes all three discovery sources (ARP, DHCP, mDNS) end-to-end, completing the real-network half of DISC-01 (Plan 01 proved the fusion backend against synthetic payloads; this plan makes it observe actual LAN traffic).
- Manual LAN verification (DHCP packet + mDNS service reaching the API) should happen during phase-level execution per VALIDATION.md before Phase 2 is considered fully done — not blocking, but flagged for the phase verifier.
- Plan 02-03 (dashboard UI) can proceed independently; it depends only on the `/api/devices` API surface from Plan 01, not on this plan's capture changes.

## Self-Check: PASSED

All claimed files exist and all claimed commits are present in git history (verified below).

---
*Phase: 02-device-registry-discovery*
*Completed: 2026-06-18*
