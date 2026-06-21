---
phase: 5
slug: plugin-system-notifications
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-20
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x + pytest-asyncio (asyncio_mode = "auto"), aiosqlite in-memory DB fixture |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/test_<module>.py -x` (run from `backend/`) |
| **Full suite command** | `pytest` (backend/, 108+ tests as of Phase 4 completion) |
| **Estimated runtime** | ~30 seconds (full suite, per Phase 4 baseline) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_<new_file>.py -x`
- **After every plan wave:** Run `pytest` (full backend suite)
- **Before `/gsd-verify-work`:** Full suite must be green; frontend has no automated test runner in this project (svelte-check + manual verification, consistent with Phases 1-4)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01 | TBD | 0 | PLUG-01 | — | Plugin manifest loads and validates against documented schema | unit | `pytest tests/test_plugin_manifest.py -x` | ❌ W0 | ⬜ pending |
| 05-02 | TBD | 0 | PLUG-02 | T-05-01 | `GET /api/plugins`, enable/disable/config routes round-trip; disabled plugin routes unreachable | integration | `pytest tests/test_plugins_routes.py -x` | ❌ W0 | ⬜ pending |
| 05-03 | TBD | 0 | PLUG-03 | — | Publishing an event invokes subscribed handlers; unsubscribed event types no-op | unit | `pytest tests/test_event_bus.py -x` | ❌ W0 | ⬜ pending |
| 05-04 | TBD | 0 | PLUG-04 | — | Enabling a plugin with a UI page causes `/api/plugins/{slug}/page` to return a descriptor (frontend manual-verify) | integration + manual | `pytest tests/test_plugins_routes.py -x` | ❌ W0 | ⬜ pending |
| 05-05 | TBD | 0 | PLUG-05 | — | A registered collector loop writes data and publishes an event on tick | integration | `pytest tests/test_plugin_collector.py -x` | ❌ W0 | ⬜ pending |
| 05-06 | TBD | 0 | FPLG-04 | T-05-02 | Notification plugin sends via ntfy.sh/Pushover given valid config; no-ops gracefully on send failure (httpx mocked) | unit | `pytest tests/test_notification_plugin.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_plugin_manifest.py` — covers PLUG-01
- [ ] `tests/test_plugins_routes.py` — covers PLUG-02, PLUG-04 (backend half)
- [ ] `tests/test_event_bus.py` — covers PLUG-03
- [ ] `tests/test_plugin_collector.py` — covers PLUG-05
- [ ] `tests/test_notification_plugin.py` — covers FPLG-04 (requires mocking httpx — no `respx` dependency exists yet; add as dev dependency or hand-roll a monkeypatch fixture per project's existing minimal-deps convention)
- [ ] No new framework install needed — pytest/pytest-asyncio/aiosqlite already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Enabled plugin with a UI page appears at `/plugins/[plugin-name]` with no core rebuild | PLUG-04 | Frontend uses `adapter-static` SPA — no SvelteKit server runtime in production; route rendering is a generic data-driven page, not unit-testable | Enable a plugin via dashboard settings, navigate to `/plugins/{slug}`, confirm descriptor-driven UI renders without a frontend rebuild/redeploy |
| User receives a push alert on their phone when an unknown device joins | FPLG-04 | Requires a real ntfy.sh/Pushover endpoint and a physical device receiving the push — not mockable end-to-end | Configure notification plugin with real ntfy/Pushover topic, trigger a `new_device` event (connect an unrecognized device), confirm push arrives on phone |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
