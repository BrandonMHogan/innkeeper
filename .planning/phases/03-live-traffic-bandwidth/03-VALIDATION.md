---
phase: 3
slug: live-traffic-bandwidth
status: active
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-19
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (backend, established Phase 1/2 pattern); no frontend test framework exists yet |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) |
| **Quick run command** | `cd backend && pytest tests/test_<module>.py -x` |
| **Full suite command** | `cd backend && pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_<module>.py -x`
- **After every plan wave:** Run `cd backend && pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-T1 | 03-01 | 1 | TRAF-02, TRAF-04 | T-03-01 | Migration 0004 creates traffic_flows/device_mac_history with zero retention-policy calls (D-06) | unit + integration | `pytest tests/test_mac_history.py -x` | ✅ planned | ⬜ pending |
| 03-01-T2 | 03-01 | 1 | TRAF-03 | T-03-SC | registered_domain() runs fully offline (no outbound network calls) | unit | `pytest tests/test_domain_grouping.py tests/test_mac_history.py -x` | ✅ planned | ⬜ pending |
| 03-02-T1 | 03-02 | 1 | TRAF-01, TRAF-02, TRAF-03 | T-03-04 | WAN-only filter excludes LAN-to-LAN frames; no per-packet POST | static (syntax/grep) | `python -c "import ast; ast.parse(open('traffic_sniff.py').read())"` | ✅ planned | ⬜ pending |
| 03-02-T2 | 03-02 | 1 | TRAF-01 | — | Fourth capture thread shares the existing stop_event (clean SIGTERM propagation) | static (syntax/grep) | `python -c "..."` (see 03-02-PLAN.md Task 2 verify) | ✅ planned | ⬜ pending |
| 03-03-T1 | 03-03 | 2 | TRAF-01, TRAF-02 | T-03-07, T-03-08 | Ingest route rejects non-loopback/gateway sources | integration | `pytest tests/test_traffic_stream.py -x` | ✅ planned | ⬜ pending |
| 03-03-T2 | 03-03 | 2 | TRAF-01 | T-03-09 | SSE stream gated behind require_auth; rolling 5-min window excludes stale rows | unit + integration | `pytest tests/test_traffic_stream.py -x` | ✅ planned | ⬜ pending |
| 03-03-T3 | 03-03 | 2 | TRAF-02, TRAF-03, TRAF-04 | T-03-10 | Historical/destinations/network routes gated behind require_auth; full MAC-history join, not just last_known_mac | unit + integration | `pytest tests/test_bandwidth_query.py tests/test_traffic_destinations.py tests/test_bandwidth_aggregates.py -x` | ✅ planned | ⬜ pending |
| 03-04-T1 | 03-04 | 3 | TRAF-01 | T-03-11 | LiveTrafficFeed aria-live region; EventSource auto-reconnect/error states | static (svelte-check) + manual | `npx svelte-check --tsconfig ./tsconfig.json` (filtered to LiveTrafficFeed) | ✅ planned | ⬜ pending |
| 03-04-T2 | 03-04 | 3 | TRAF-02, TRAF-03 | — | All byte values rendered via formatBytes (no raw integers) | static (svelte-check) | `npx svelte-check --tsconfig ./tsconfig.json` (filtered to BandwidthHistoryChart/DestinationsBreakdown) | ✅ planned | ⬜ pending |
| 03-04-T3 | 03-04 | 3 | TRAF-01, TRAF-04 | T-03-12 | LiveTrafficFeed lifecycle independent of device-picker/tab navigation | static (svelte-check) + manual (see 03-04-PLAN.md `<verification>`) | `npx svelte-check --tsconfig ./tsconfig.json` (filtered to NetworkBandwidthChart/dashboard) | ✅ planned | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_traffic_stream.py` — covers TRAF-01 (SSE endpoint snapshot emission, disconnect handling); created in 03-03-PLAN.md Task 1, extended in Task 2
- [ ] `backend/tests/test_bandwidth_query.py` — covers TRAF-02 (arbitrary time-range query, confirms no default retention policy drops data); created in 03-03-PLAN.md Task 3
- [ ] `backend/tests/test_domain_grouping.py` — covers TRAF-03 (tldextract-based registered-domain grouping logic, offline-mode verification); created in 03-01-PLAN.md Task 2
- [ ] `backend/tests/test_traffic_destinations.py` — covers TRAF-03 (per-device destination breakdown API endpoint); created in 03-03-PLAN.md Task 3
- [ ] `backend/tests/test_bandwidth_aggregates.py` — covers TRAF-04 (continuous aggregate daily/weekly/monthly correctness against seeded raw rows); created in 03-03-PLAN.md Task 3
- [ ] `backend/tests/test_mac_history.py` — covers MAC-rotation reconciliation (device_mac_history CRUD); created in 03-01-PLAN.md Task 1
- [ ] `backend/tests/conftest.py` fixtures — extend existing `test_db`/`client` fixtures with a `seeded_traffic_db`-style fixture seeding `traffic_flows`/`bandwidth_metrics`/`device_mac_history`/`device` rows across a synthetic time range for aggregate tests; added in 03-03-PLAN.md Task 3

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|--------------------|
| Live feed visually updates without page refresh | TRAF-01 | No frontend test framework exists yet (consistent with Phase 1/2 posture) | Open dashboard, generate traffic on a test device, confirm live feed/top-talkers update every ~5-10s without manual refresh |
| Chart rendering correctness (daily/weekly/monthly views) | TRAF-04 | No frontend test framework exists yet | Open network-wide bandwidth chart, switch between daily/weekly/monthly views, confirm totals match backend query results |
| EventSource reconnect behavior on dropped connection | TRAF-01 | No frontend test framework exists yet | Kill backend mid-session, confirm browser EventSource auto-reconnects and live feed resumes without a manual page refresh |
| Live feed survives device-picker/tab navigation | TRAF-01, TRAF-04 | No frontend test framework exists yet; svelte-check alone cannot prove runtime lifecycle independence (see 03-04-PLAN.md Task 3 `<done>` cross-reference) | Switch device picker and confirm bandwidth chart/destinations re-query without disrupting the live feed; switch Daily/Weekly/Monthly tabs and confirm the network chart re-renders without affecting the live feed |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
