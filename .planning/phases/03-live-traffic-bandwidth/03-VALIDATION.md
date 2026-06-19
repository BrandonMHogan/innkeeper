---
phase: 3
slug: live-traffic-bandwidth
status: draft
nyquist_compliant: false
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
| 03-TBD | TBD | 0 | TRAF-01 | T-03-01 | Ingest route rejects non-loopback/gateway sources | integration | `pytest tests/test_traffic_stream.py -x` | ❌ W0 | ⬜ pending |
| 03-TBD | TBD | 0 | TRAF-02 | — | N/A | unit + integration | `pytest tests/test_bandwidth_query.py -x` | ❌ W0 | ⬜ pending |
| 03-TBD | TBD | 0 | TRAF-03 | — | N/A | unit + integration | `pytest tests/test_domain_grouping.py -x`, `pytest tests/test_traffic_destinations.py -x` | ❌ W0 | ⬜ pending |
| 03-TBD | TBD | 0 | TRAF-04 | — | N/A | integration | `pytest tests/test_bandwidth_aggregates.py -x` | ❌ W0 | ⬜ pending |

*Planner fills in exact Task IDs/Plan/Wave once PLAN.md files exist. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_traffic_stream.py` — covers TRAF-01 (SSE endpoint snapshot emission, disconnect handling)
- [ ] `backend/tests/test_bandwidth_query.py` — covers TRAF-02 (arbitrary time-range query, confirms no default retention policy drops data)
- [ ] `backend/tests/test_domain_grouping.py` — covers TRAF-03 (tldextract-based registered-domain grouping logic, offline-mode verification)
- [ ] `backend/tests/test_traffic_destinations.py` — covers TRAF-03 (per-device destination breakdown API endpoint)
- [ ] `backend/tests/test_bandwidth_aggregates.py` — covers TRAF-04 (continuous aggregate daily/weekly/monthly correctness against seeded raw rows)
- [ ] `backend/tests/conftest.py` fixtures — extend existing `test_db`/`client` fixtures with a fixture seeding `traffic_flows`/`bandwidth_metrics` rows across a synthetic time range for aggregate tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live feed visually updates without page refresh | TRAF-01 | No frontend test framework exists yet (consistent with Phase 1/2 posture) | Open dashboard, generate traffic on a test device, confirm live feed/top-talkers update every ~5-10s without manual refresh |
| Chart rendering correctness (daily/weekly/monthly views) | TRAF-04 | No frontend test framework exists yet | Open network-wide bandwidth chart, switch between daily/weekly/monthly views, confirm totals match backend query results |
| EventSource reconnect behavior on dropped connection | TRAF-01 | No frontend test framework exists yet | Kill backend mid-session, confirm browser EventSource auto-reconnects and live feed resumes without a manual page refresh |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
