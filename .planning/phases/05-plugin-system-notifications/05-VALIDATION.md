---
phase: 05
slug: plugin-system-notifications
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-21
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (`asyncio_mode = "auto"`), already configured in `backend/pyproject.toml` |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `/tmp/innkeeper-venv313/bin/python -m pytest backend/tests/test_<module>.py -x` |
| **Full suite command** | `cd backend && /tmp/innkeeper-venv313/bin/python -m pytest` |
| **Estimated runtime** | ~30-60 seconds (109 pre-existing tests, growing with this phase's Wave 0 additions) |

---

## Sampling Rate

- **After every task commit:** Run the targeted module test file (`pytest tests/test_<changed_module>.py -x`)
- **After every plan wave:** Run the full suite (`cd backend && /tmp/innkeeper-venv313/bin/python -m pytest`)
- **Before `/gsd-verify-work`:** Full suite must be green, plus a live Lima VM docker-compose smoke check of the capture container's ingest path (mirrors the Phase 3 P04 precedent)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-NN | 01 | 1 | MOD-01 | — | ModuleLoader topo-sorts manifests, fails fast on unsatisfied `requires`/conflicting `provides` | unit | `pytest tests/test_module_loader.py -x` | ❌ W0 | ⬜ pending |
| 05-01-NN | 01 | 1 | MOD-02 | — | Toggling a module's enabled flag immediately blocks/unblocks its routes without restart | integration | `pytest tests/test_module_registry_toggle.py -x` | ❌ W0 | ⬜ pending |
| 05-01-NN | 01 | 1 | MOD-03 | — | Publishing an event invokes subscribed handlers; unsubscribed event types are a no-op | unit | `pytest tests/test_event_bus.py -x` | ❌ W0 | ⬜ pending |
| 05-01-NN | 01 | 1 | MOD-04 | — | Enabled `HasUIPage` module produces a discoverable nav entry; core app boots with zero modules enabled | integration | `pytest tests/test_module_loader.py::test_ui_page_registration -x` | ❌ W0 | ⬜ pending |
| 05-01-NN | 01 | 1 | MOD-05 | — | A `HasCollector` module's background loop starts at startup, stops cleanly on shutdown | integration | `pytest tests/test_module_loader.py::test_collector_lifecycle -x` | ❌ W0 | ⬜ pending |
| 05-01-NN | 01 | 1 | MOD-06 | — | Two modules declaring the same `provides` type fails loader startup with a clear error | unit | `pytest tests/test_module_loader.py::test_provides_conflict_fails_fast -x` | ❌ W0 | ⬜ pending |
| 05-0N-NN | TBD | 2-4 | MOD-07 | T-disabled-route-reachable | Retrofitted Devices/Traffic/Security endpoints return identical response shapes to pre-retrofit versions (behavior parity); disabled-module routes return 404 | integration | `pytest tests/test_devices.py tests/test_traffic_destinations.py tests/test_security_alerts.py -x` | ✅ existing | ⬜ pending |
| 05-01-NN | 01 | 1 | MOD-08 | — | `LinkedModuleManifest` round-trips through dashboard "Linked Apps" section; empty-state when zero entries | unit + integration | `pytest tests/test_linked_apps.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Exact task IDs (`05-0N-NN`) are assigned by the planner once plans/waves are finalized — this map will be refined to reference real task IDs during/after planning.*

---

## Wave 0 Requirements

- [ ] `tests/test_module_loader.py` — stubs for MOD-01, MOD-04, MOD-05, MOD-06
- [ ] `tests/test_module_registry_toggle.py` — stubs for MOD-02
- [ ] `tests/test_event_bus.py` — stubs for MOD-03 (same gap identified by the superseded 05-RESEARCH.md, never closed — close it this phase)
- [ ] `tests/test_linked_apps.py` — stubs for MOD-08
- [ ] A schema-portability spike script (not a permanent test file) resolving Open Question 1 (SQLite-vs-Postgres per-module schema test strategy, e.g. `schema_translate_map`) before any module's `migrations/` directory is written

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Capture container ingest path stays correct end-to-end through the DeviceIdentity retrofit | MOD-07 | Requires a live Lima VM docker-compose environment (per Pitfall 3 / Phase 3 P04 precedent) — not reproducible in the pytest-only CI loop | Run `docker compose up` in the project's Lima VM, trigger an ARP/DHCP/mDNS observation, confirm it lands correctly in the new `device_identity.*` schema with no regression in `/api/capture/*` response contract |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (test_module_loader.py, test_module_registry_toggle.py, test_event_bus.py, test_linked_apps.py)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
