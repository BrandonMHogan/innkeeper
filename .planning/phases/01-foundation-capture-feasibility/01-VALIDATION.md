---
phase: 1
slug: foundation-capture-feasibility
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-17
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio + httpx (AsyncClient) + aiosqlite |
| **Config file** | `backend/pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `pytest backend/tests/ -x -q --tb=short` |
| **Full suite command** | `pytest backend/tests/ -v --tb=short` |
| **Estimated runtime** | ~10 seconds (SQLite in-memory; no Docker required) |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/ -x -q --tb=short`
- **After every plan wave:** Run `pytest backend/tests/ -v` + manual smoke test of `docker compose up`
- **Before `/gsd-verify-work`:** Full suite must be green + manual D-05 spike verification (one ARP row in PostgreSQL)
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-auth-setup | TBD | 1 | AUTH-01 | T-session-fixation | Hashes password before storing; never stores plaintext | integration | `pytest tests/test_auth.py::test_setup_stores_password -x` | Wave 0 | ⬜ pending |
| 01-auth-redirect | TBD | 1 | AUTH-01 | — | N/A | integration | `pytest tests/test_auth.py::test_setup_redirect -x` | Wave 0 | ⬜ pending |
| 01-auth-login | TBD | 1 | AUTH-02 | T-session-fixation | Clears session before setting authenticated=True | integration | `pytest tests/test_auth.py::test_login_sets_cookie -x` | Wave 0 | ⬜ pending |
| 01-auth-wrong-pw | TBD | 1 | AUTH-02 | — | Returns 401 on wrong password | integration | `pytest tests/test_auth.py::test_login_wrong_password -x` | Wave 0 | ⬜ pending |
| 01-auth-me-unauth | TBD | 1 | AUTH-02 | — | Returns 401 when not authenticated | integration | `pytest tests/test_auth.py::test_me_unauthenticated -x` | Wave 0 | ⬜ pending |
| 01-auth-session | TBD | 1 | AUTH-03 | — | Session persists across requests | integration | `pytest tests/test_auth.py::test_session_persists -x` | Wave 0 | ⬜ pending |
| 01-capture-ingest | TBD | 2 | PLAT-03 | T-arp-ingest | Rejects ARP events from non-loopback IP | integration | `pytest tests/test_capture.py::test_arp_ingest -x` | Wave 0 | ⬜ pending |
| 01-compose-healthy | TBD | 2 | PLAT-02 | — | N/A | integration | `pytest tests/test_compose.py::test_all_services_healthy -x` | Wave 0 | ⬜ pending |
| 01-lan-access | TBD | 2 | PLAT-01 | — | N/A | smoke (manual) | manual — open browser on different LAN device, navigate to http://host-ip:9999 | — | ⬜ pending |
| 01-arp-spike | TBD | 2 | PLAT-03/D-05 | — | N/A | spike (manual) | manual — check capture logs + SELECT * FROM arp_events LIMIT 1 | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/__init__.py` — empty file
- [ ] `backend/tests/conftest.py` — async SQLite in-memory DB + FastAPI AsyncClient fixtures; must mock/skip `create_hypertable` TimescaleDB call (SQLite incompatible)
- [ ] `backend/tests/test_auth.py` — stubs for AUTH-01/02/03 tests
- [ ] `backend/tests/test_capture.py` — mocked ARP ingest test (POST to /api/capture/arp, verify DB row written)
- [ ] `backend/tests/test_compose.py` — Docker Compose healthcheck test (or marked manual if compose is unavailable in CI)
- [ ] `backend/pyproject.toml` — pytest config + dev deps: pytest, pytest-asyncio, httpx, aiosqlite

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard reachable on :9999 from a different device | PLAT-01 | Requires a second physical device on the LAN; cannot be automated | 1. Run `docker compose up`. 2. From a second device, open browser to `http://<host-ip>:9999`. 3. Confirm /setup page loads. |
| ARP packet captured → POST to API → row in PostgreSQL | PLAT-03 / D-05 | Requires host networking on Linux; cannot be automated in CI | 1. Run `docker compose up` on Linux host. 2. Wait 10s for capture container to start. 3. Run `docker compose exec db psql -U innkeeper -d innkeeper -c "SELECT * FROM arp_events LIMIT 1;"`. 4. Confirm at least one row returned. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
