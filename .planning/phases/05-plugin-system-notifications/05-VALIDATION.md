---
phase: 5
slug: plugin-system-notifications
status: final
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-20
updated: 2026-06-21
---

> **SUPERSEDED 2026-06-21** — built against the retired bolt-on plugin contract. See `docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md` and the new Phase 5 (Module Platform Foundation) in ROADMAP.md. Kept for history only; do not use as input to planning or execution.


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
| 05-01 Task 1 | 05-01 | 1 | PLUG-01 | — | Plugin manifest loads and validates against documented schema; malformed manifest rejected | unit | `pytest tests/test_plugin_manifest.py -x` | ✅ | ✅ done |
| 05-01 Task 2 | 05-01 | 1 | PLUG-03 | — | Publishing an event invokes subscribed handlers; unsubscribed event types no-op; slow/raising handler never blocks publisher | unit | `pytest tests/test_event_bus.py -x` | ✅ | ✅ done |
| 05-01 Task 3 | 05-01 | 1 | PLUG-05 | — | Directory-scan loader discovers a plugin without package install; a registered collector loop ticks, writes data, and publishes an event each tick | unit + integration | `pytest tests/test_plugin_loader.py tests/test_plugin_collector.py -x` | ✅ | ✅ done |
| 05-02 Task 1 | 05-02 | 2 | PLUG-02, PLUG-04 | T-05-05, T-05-06, T-05-07 | `GET /api/plugins`, enable/disable/config/page routes round-trip; disabled plugin routes 404 via require_plugin_enabled; secrets masked; generic collector start/stop hook fires on enable/disable | integration | `pytest tests/test_plugins_routes.py -x` | ✅ | ✅ done |
| 05-02 Task 2 | 05-02 | 2 | PLUG-03 | T-05-09 | new_device/traffic_spike publish alongside existing SecurityAlert writes with no duplication; device_lost fires once per loss and re-arms on device return | integration | `pytest tests/test_event_wiring.py tests/test_device_lost_detector.py -x` | ✅ | ✅ done |
| 05-03 Task 1 | 05-03 | 2 | PLUG-01, PLUG-03, FPLG-04 | T-05-02 | Notification plugin manifest discoverable without loader changes; sends via ntfy.sh/Pushover given valid config; send failure never raises out of the event handler; explicit httpx timeout on every outbound call; test-send route gated by require_plugin_enabled | unit | `pytest tests/test_notification_plugin.py -x` | ✅ | ✅ done |
| 05-04 Task 1 | 05-04 | 3 | PLUG-02 | — | api.ts exposes plugin client functions; Switch component installed via official shadcn-svelte registry | static (svelte-check) | `cd frontend && npx svelte-check` | ✅ | ✅ done |
| 05-04 Task 2 | 05-04 | 3 | PLUG-02, PLUG-04 | — | `/settings/plugins` list page renders Enabled/Disabled/Not-configured status + working enable/disable Switch; dashboard renders a dynamic per-plugin nav entry for every enabled plugin with ui_page=true (PLUG-04's literal nav-entry clause) | static + manual (Task 4 fixture step) | `cd frontend && npx svelte-check` | ✅ | ✅ done |
| 05-04 Task 3 | 05-04 | 3 | PLUG-04 | T-05-14, T-05-15 | Schema-driven config dialog with masked-secret/replace-token interaction and test-send; generic `/plugins/[slug]` page renders all four documented states with zero `{@html}` usage | static + manual | `cd frontend && grep -c '{@html}' "src/routes/plugins/[slug]/+page.svelte" \| grep -qx 0 && npx svelte-check` | ✅ | ✅ done |
| 05-04 Task 4 | 05-04 | 3 | PLUG-02, PLUG-04 | T-05-16 | Human-verify checkpoint: full enable → configure → test-send → save → masked-display → generic-page-states flow, plus the ui_page=true fixture step proving the dashboard's dynamic nav entry appears/disappears correctly | manual | (checkpoint, no automated command) | ✅ | ✅ done |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 1 Test Scaffolding (Plan 05-01, no dependencies)

- [x] `tests/test_plugin_manifest.py` — covers PLUG-01 (Plan 05-01 Task 1)
- [x] `tests/test_event_bus.py` — covers PLUG-03 (Plan 05-01 Task 2)
- [x] `tests/test_plugin_loader.py`, `tests/test_plugin_collector.py` — covers PLUG-05 (Plan 05-01 Task 3)
- [x] No new framework install needed — pytest/pytest-asyncio/aiosqlite already present

## Wave 2 Test Scaffolding (Plans 05-02, 05-03 — depend on 05-01)

- [x] `tests/test_plugins_routes.py` — covers PLUG-02, PLUG-04 backend half, generic collector lifecycle hook (Plan 05-02 Task 1)
- [x] `tests/test_event_wiring.py`, `tests/test_device_lost_detector.py` — covers PLUG-03's real publish sites (Plan 05-02 Task 2)
- [x] `tests/test_notification_plugin.py` — covers FPLG-04 (Plan 05-03 Task 1; httpx mocked via hand-rolled monkeypatch fixture per project's existing minimal-deps convention — no `respx` dependency added)

## Wave 3 Verification (Plan 05-04 — depends on 05-02, 05-03; frontend has no automated test runner)

- [x] `cd frontend && npx svelte-check` — static verification for all three auto tasks
- [x] Human-verify checkpoint (Task 4) — full interactive flow plus the ui_page=true fixture step proving PLUG-04's dashboard nav-entry clause

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Enabled plugin with a UI page appears at `/plugins/[plugin-name]` with no core rebuild, AND surfaces as its own dashboard navigation entry | PLUG-04 | Frontend uses `adapter-static` SPA — no SvelteKit server runtime in production; route rendering is a generic data-driven page, not unit-testable; no first-party plugin this phase declares ui_page=true, so the nav-entry clause requires a manifest fixture toggle to observe | Enable a plugin via dashboard settings, navigate to `/plugins/{slug}`, confirm descriptor-driven UI renders without a frontend rebuild/redeploy; additionally, temporarily flip the notification plugin's manifest `ui_page` to `true` (Plan 05-04 Task 4, step 10) and confirm a dynamic dashboard nav entry appears/disappears correctly with enabled state, then revert |
| User receives a push alert on their phone when an unknown device joins | FPLG-04 | Requires a real ntfy.sh/Pushover endpoint and a physical device receiving the push — not mockable end-to-end | Configure notification plugin with real ntfy/Pushover topic, trigger a `new_device` event (connect an unrecognized device), confirm push arrives on phone |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 1 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 1 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
