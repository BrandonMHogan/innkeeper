---
phase: 1
slug: foundation-capture-feasibility
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-17
revised: 2026-06-17
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
| 01-auth-setup | 01-01 (Task 2) | 1 | AUTH-01 | T-01-03 | Hashes password before storing; never stores plaintext | integration | `pytest backend/tests/test_auth.py::test_setup_stores_password -x` | Wave 0 | ⬜ pending |
| 01-auth-redirect | 01-01 (Task 2) | 1 | AUTH-01 | — | GET /api/auth/me before setup returns 401 | integration | `pytest backend/tests/test_auth.py::test_setup_redirect -x` | Wave 0 | ⬜ pending |
| 01-auth-login | 01-01 (Task 2) | 1 | AUTH-02 | T-01-04 | Clears session before setting authenticated=True | integration | `pytest backend/tests/test_auth.py::test_login_sets_cookie -x` | Wave 0 | ⬜ pending |
| 01-auth-wrong-pw | 01-01 (Task 2) | 1 | AUTH-02 | — | Returns 401 on wrong password | integration | `pytest backend/tests/test_auth.py::test_login_wrong_password -x` | Wave 0 | ⬜ pending |
| 01-auth-me-unauth | 01-01 (Task 2) | 1 | AUTH-02 | — | Returns 401 when not authenticated | integration | `pytest backend/tests/test_auth.py::test_me_unauthenticated -x` | Wave 0 | ⬜ pending |
| 01-auth-session | 01-01 (Task 2) | 1 | AUTH-03 | — | Session persists across requests | integration | `pytest backend/tests/test_auth.py::test_session_persists -x` | Wave 0 | ⬜ pending |
| 01-capture-ingest | 01-01 (Task 2) | 1 | PLAT-03 | T-01-05 | Rejects ARP events from non-loopback IP | integration | `pytest backend/tests/test_capture.py::test_arp_ingest -x` | Wave 0 | ⬜ pending |
| 01-compose-healthy | 01-02 (Task 1) | 2 | PLAT-02 | — | Full 4-service stack reaches healthy/running state | integration (Docker — executes, not skipped; Docker 29.1.3 confirmed present) | `pytest backend/tests/test_compose.py::test_all_services_healthy -x` | Wave 0 | ⬜ pending |
| 01-lan-access | 01-02 (Task 2) | 2 | PLAT-01 | — | N/A | smoke (manual) | manual — open browser on different LAN device, navigate to http://host-ip:9999 | — | ⬜ pending |
| 01-arp-spike | 01-02 (Task 2) | 2 | PLAT-03/D-05 | — | N/A | spike (manual) | manual — check capture logs + SELECT * FROM arp_events LIMIT 1 | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 scaffolding is satisfied by Plan 01-01 Task 1 and Plan 01-02 Task 1 (no separate pre-task is needed — the plans create these artifacts directly as their first deliverables):

- [x] `backend/tests/__init__.py` — empty file (01-01 Task 1)
- [x] `backend/tests/conftest.py` — async SQLite in-memory DB + FastAPI AsyncClient fixtures; `create_hypertable` is never invoked outside Alembic migrations, so no SQLite mocking is needed (01-01 Task 1)
- [x] `backend/tests/test_auth.py` — full AUTH-01/02/03 test implementations, not stubs (01-01 Task 2)
- [x] `backend/tests/test_capture.py` — real ARP ingest test (POST to /api/capture/arp, verify DB row written) (01-01 Task 2)
- [x] `backend/tests/test_compose.py` — Docker Compose healthcheck test that executes for real (Docker 29.1.3 confirmed present) (01-02 Task 1)
- [x] `backend/pyproject.toml` — pytest config + dev deps: pytest, pytest-asyncio, httpx, aiosqlite (01-01 Task 1)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard reachable on :9999 from a different device | PLAT-01 | Requires a second physical device on the LAN; cannot be automated | 1. Run `docker compose up`. 2. From a second device, open browser to `http://<host-ip>:9999`. 3. Confirm /setup page loads. |
| ARP packet captured → POST to API → row in PostgreSQL | PLAT-03 / D-05 | Requires host networking on Linux; cannot be automated in CI | 1. Run `docker compose up` on Linux host. 2. Wait 10s for capture container to start. 3. Run `docker compose exec db psql -U innkeeper -d innkeeper -c "SELECT * FROM arp_events LIMIT 1;"`. 4. Confirm at least one row returned. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — every task in 01-01-PLAN.md, 01-02-PLAN.md, and 01-03-PLAN.md now has a `<verify><automated>` element with an exact, runnable command (pytest node IDs matching this file's Per-Task Verification Map for backend plans; `npm run build` + grep checks for the frontend plan); the single `checkpoint:human-verify` task in 01-02 is exempt by design (human-verify tasks use manual confirmation, not automated verify)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — all 5 non-checkpoint tasks across the 3 plans have automated verify
- [x] Wave 0 covers all MISSING references — see Wave 0 Requirements section above, all satisfied by 01-01 Task 1/Task 2 and 01-02 Task 1
- [x] No watch-mode flags — all commands are one-shot (`-x -q`, `--wait`, `npm run build`)
- [x] Feedback latency < 30s — pytest suite ~10s; `docker compose up -d --wait` budgeted up to 60s timeout for the compose healthcheck test, acceptable for an integration-tier (not unit-tier) check
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved — revision closes the BLOCKER (missing `<verify><automated>` elements added to all 3 plans) and the compose-test WARNING (test now executes against confirmed Docker 29.1.3 instead of skip-gating).
