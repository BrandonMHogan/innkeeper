---
phase: 4
slug: security
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-20
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (asyncio_mode=auto), in-memory SQLite via `test_db`/`client` fixtures |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `cd backend && python -m pytest tests/test_security_<area>.py -x` |
| **Full suite command** | `cd backend && python -m pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_<new_file>.py -x`
- **After every plan wave:** Run `cd backend && python -m pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-XX-XX | TBD | 0 | SEC-01 | — | `evaluate_open_ports()` risky/unexpected classification (pure function) | unit | `pytest tests/test_port_rules.py -x` | ❌ W0 | ⬜ pending |
| 04-XX-XX | TBD | TBD | SEC-01 | T-04-01 | On-demand scan trigger + result ingest + unexpected-port flagging | integration | `pytest tests/test_security_scan.py -x` | ❌ W0 | ⬜ pending |
| 04-XX-XX | TBD | TBD | SEC-02 | — | Unregistered device join writes `security_alerts` row (type=unknown_device) | integration | `pytest tests/test_security_alerts.py -x` | ❌ W0 | ⬜ pending |
| 04-XX-XX | TBD | TBD | SEC-03 | T-04-02 | Malicious-IP match on traffic ingest writes alert + flips status to critical | integration | `pytest tests/test_threat_intel.py -x` | ❌ W0 | ⬜ pending |
| 04-XX-XX | TBD | TBD | SEC-03 | — | Bandwidth-spike anomaly check (warning-level) | unit + integration | `pytest tests/test_bandwidth_anomaly.py -x` | ❌ W0 | ⬜ pending |
| 04-XX-XX | TBD | 0 | SEC-04 | — | `derive_status()` good/warning/critical table-driven logic (pure function) | unit | `pytest tests/test_security_status.py -x` | ❌ W0 | ⬜ pending |
| 04-XX-XX | TBD | TBD | SEC-04 | — | `/api/devices` response includes `security_status` field | integration | `pytest tests/test_devices.py -x` (extend existing file) | ✅ existing, new cases | ⬜ pending |
| 04-XX-XX | TBD | TBD | (capture-side) | T-04-03 | Trust-boundary rejection on `/api/capture/scan` for non-loopback callers | integration | `pytest tests/test_capture.py -x` (extend existing file, reuse `ASGITransport(client=...)`) | ✅ existing, new cases | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_port_rules.py` — covers SEC-01 (pure-function table-driven port classification, no DB fixture, follows `test_domain_grouping.py`'s fixture-free style)
- [ ] `backend/tests/test_security_status.py` — covers SEC-04 (pure-function status derivation, no DB fixture needed)
- [ ] `backend/tests/test_security_scan.py` — covers SEC-01 end-to-end ingest, reuses `client`/`test_db` fixtures from `conftest.py`
- [ ] `backend/tests/test_security_alerts.py` — covers SEC-02 (extend `test_discovery.py`'s unknown-device-join test path to also assert a `security_alerts` row is written)
- [ ] `backend/tests/test_threat_intel.py` — covers SEC-03 malicious-IP path, needs a small fixture blocklist (not the full vendored file) for deterministic test IPs
- [ ] `backend/tests/test_bandwidth_anomaly.py` — covers SEC-03 anomaly path, reuses `seeded_traffic_db`-style fixture pattern from `conftest.py`
- [ ] No new framework/config install needed — existing pytest + SQLite-fixture infrastructure fully covers all phase requirements structurally; only new test *files* are needed, matching every prior phase's pattern

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification per the test map above.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
