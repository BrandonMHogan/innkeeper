---
phase: 05-plugin-system-notifications
verified: 2026-06-21T00:00:00Z
status: gaps_found
score: 6/8 must-haves verified
overrides_applied: 0
gaps:
  - truth: "User can enable/disable each module via the dashboard settings page, and the platform actually stops a disabled module's behavior (MOD-02)"
    status: failed
    reason: >
      Disabling traffic or security via POST /api/modules/{id}/toggle only 404s the module's
      own HTTP routes. _start_collectors() in main.py starts a HasCollector task for every
      loaded module instance unconditionally at boot and never re-checks ModuleConfig/
      is_module_enabled, so traffic's update_snapshot_loop and any future security collector
      keep running after disable. Worse, routes/capture.py's ingest_traffic/
      ingest_scan_result/queue_daily_scans hot-path handlers write TrafficFlow/
      BandwidthMetric/SecurityAlert/PortScanResult rows directly and never call
      is_module_enabled for "traffic" or "security" at all -- disabling either module from
      the settings UI has no effect whatsoever on data ingestion. The frontend's own
      destructive-confirmation dialog text ("X other modules depend on this and will also
      stop working. This won't delete any data.") explicitly promises behavior the backend
      does not deliver.
    artifacts:
      - path: "backend/src/main.py"
        issue: "_start_collectors() (lines 57-73) wires HasCollector for every instance with no is_module_enabled gate"
      - path: "backend/src/routes/capture.py"
        issue: "ingest_traffic/ingest_scan_result/queue_daily_scans never check is_module_enabled('traffic'/'security') before writing rows"
    missing:
      - "Gate capture.py's traffic/security ingest handlers behind is_module_enabled(db, 'traffic')/is_module_enabled(db, 'security')"
      - "Gate or stop HasCollector tasks when their owning module is disabled (poll ModuleConfig in the collector loop, or have toggle_module cancel/restart the relevant collector task)"
  - truth: "Disabling a module visibly and effectively changes its state, with no way to silently disable a module the UI never shows (MOD-02)"
    status: failed
    reason: >
      device_identity is kind="support" and is excluded from GET /api/modules/'s listing
      (by design, per D-01 -- support modules have no UI/settings row). However,
      POST /api/modules/device_identity/toggle has no kind filter and DOES successfully flip
      ModuleConfig(module_id="device_identity").enabled to False -- confirmed by the
      project's own test_toggle_device_identity_requires_confirmation_naming_dependents,
      which calls this exact endpoint and asserts enabled becomes False. Once that row
      exists, nothing in the codebase ever calls require_module_enabled("device_identity")
      anywhere -- DeviceIdentityModule has no get_router()/HasAPIRoutes implementation at
      all, confirmed by grep. record_observation()/lookup()/register()/merge() on the hot
      capture-ingest path keep running regardless of this flag. The toggle silently
      "succeeds" (API returns {"enabled": false}) while having zero effect, and the module
      is invisible in the UI so a user has no way to discover or undo this state through the
      settings page.
    artifacts:
      - path: "backend/src/routes/modules.py"
        issue: "toggle_module (lines 94-122) has no kind=='feature' guard, unlike _feature_manifests() used by list_modules"
      - path: "backend/src/modules/device_identity/module.py"
        issue: "DeviceIdentityModule implements no HasAPIRoutes capability, so there is no enforcement point for is_module_enabled('device_identity') anywhere"
    missing:
      - "Reject POST /{module_id}/toggle for any non-feature-kind module_id at the route level (404/400), mirroring the listing endpoint's kind filter"
  - truth: "Modules can subscribe to platform events via a single, coherent EventBus (MOD-03)"
    status: failed
    reason: >
      Two disconnected EventBus instances exist in the running process post-boot.
      _load_native_modules() constructs ModuleLoader(registry=ModuleRegistry(),
      event_bus=EventBus()) as a local variable in main.py; this loader-owned registry/bus
      is discarded once _load_native_modules() returns (only the LoadResult is kept in
      _module_load_result -- LoadResult has no reference back to the registry/event_bus).
      Meanwhile device_identity/service.py publishes "new_device" exclusively through a
      separate bare module-level singleton (event_bus_singleton.py), which is wired into
      neither the loader's wiring pass nor reachable by any future HasEventSubscriptions
      consumer that subscribes against the loader's bus. Currently latent (no module
      implements HasEventSubscriptions yet) but architecturally broken: a future module
      declaring get_subscriptions({"new_device": handler}) against the loader's bus would
      silently never fire, with no error or log.
    artifacts:
      - path: "backend/src/main.py"
        issue: "loader.registry/loader.event_bus (lines 93-108) are never stored on app state or any module-level global after _load_native_modules() returns"
      - path: "backend/src/modules/device_identity/event_bus_singleton.py"
        issue: "a second, fully independent EventBus instance that device_identity publishes through but the loader never wires subscribers onto"
    missing:
      - "Single shared EventBus instance: either pass event_bus_singleton.event_bus into ModuleLoader's construction, or have device_identity's factory receive the loader's own event_bus via constructor injection instead of importing the singleton"
      - "Store the loader (or at minimum loader.registry/loader.event_bus) on a reachable global/app-state so future runtime code can resolve() or subscribe() post-boot"
human_verification: []
---

# Phase 5: Module Platform Foundation Verification Report

**Phase Goal:** Devices, Traffic, and Security — already built as core-app code in Phases 1-4 — are retrofitted into isolated, independently-replaceable modules on a real module-host platform, proving the platform supports both first-party native modules and (eventually) third-party linked modules before any further feature work proceeds.
**Verified:** 2026-06-21T00:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Derived from ROADMAP.md Phase 5 Success Criteria (1-6) merged with PLAN frontmatter `must_haves` across all 6 plans, deduplicated.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A documented module contract exists: capability Protocols, typed ModuleManifest, and a ModuleLoader that topo-sorts + constructor-injects | ✓ VERIFIED | `backend/src/host/protocols.py` defines `HasAPIRoutes`/`HasUIPage`/`HasEventSubscriptions`/`HasCollector` as `@runtime_checkable` Protocols; `backend/src/host/manifest.py` defines `ModuleManifest`; `backend/src/host/loader.py` uses `TopologicalSorter` + constructor injection. `test_module_loader.py` passes against this contract per code inspection. |
| 2 | ModuleRegistry resolves support interfaces by Protocol type, swappable, fails fast on unsatisfied `requires`/conflicting `provides` | ✓ VERIFIED | `backend/src/host/registry.py::ModuleRegistry.register/resolve`; `test_module_registry_toggle.py::test_register_same_protocol_twice_raises_runtime_error_naming_both` and `test_resolve_unregistered_protocol_raises_runtime_error_not_keyerror` directly test this. |
| 3 | DeviceIdentity is a support module (own schema), sole source of truth, exposes DeviceLookupInterface; Devices/Traffic/Security consume it instead of owning/duplicating device data | ✓ VERIFIED | `backend/src/modules/device_identity/interfaces.py::DeviceLookupInterface`; `device_identity/migrations/0001_initial.py` creates a dedicated `device_identity` Postgres schema; `traffic/routes.py` and `security/routes.py` call `self._device_lookup.lookup(...)` (confirmed via grep) instead of direct `Device`/`DeviceMacHistory` joins. |
| 4 | Devices is a thin feature module performing every device read/write through DeviceIdentity | ✓ VERIFIED | `backend/src/modules/devices/routes.py` contains no direct `select(Device)`/`select(DiscoveredIdentity)` queries per 05-03-SUMMARY.md's stated parity tests and code structure; constructor-injected `DeviceLookupInterface`. |
| 5 | A shared frontend design-token source and shared component library exist and are used by retrofitted Devices/Traffic/Security UI | ✓ VERIFIED | `frontend/src/lib/styles/theme.css` consolidated per 05-02-PLAN.md's D-18 scope; `frontend/src/lib/components/ui/switch` shadcn-svelte primitive reused in `settings/modules/+page.svelte`. |
| 6 | A linked-module manifest format and "Linked Apps" dashboard section exist (data model + empty-state UI only) | ✓ VERIFIED | `backend/src/modules/linked_apps/linked_manifest.py::LinkedModuleManifest`; `frontend/src/lib/components/LinkedAppsSection.svelte` renders "No linked apps yet" empty state; `GET /api/modules/linked-apps/` returns the (empty) list. |
| 7 | User can view all available modules, and enable, disable, **or configure** each one via the dashboard settings page (MOD-02) — disabling must actually stop the module's behavior, not just 404 its routes | ✗ FAILED | See gap #1/#2 below. Route-level 404 works (`test_toggling_devices_off_immediately_404s_next_request_no_restart` passes), but `traffic`/`security` background collectors and `capture.py`'s hot-path ingest handlers never check `is_module_enabled` — disabling either module has zero effect on data collection. `device_identity` can be silently disabled via the raw API despite being invisible in the UI, with zero enforcement point anywhere in the codebase (no `HasAPIRoutes`, no other consumer checks its flag). The frontend's own confirmation-dialog copy ("will also stop working") is a promise the backend does not keep for these two modules. |
| 8 | Modules can subscribe to platform events via the EventBus and react accordingly (MOD-03) | ✗ FAILED | See gap #3. Two disconnected `EventBus` instances exist post-boot: the `ModuleLoader`'s own bus (discarded after `_load_native_modules()` returns) and `device_identity/event_bus_singleton.py`'s separate singleton bus (the only one `service.py` actually publishes "new_device" through). No module currently implements `HasEventSubscriptions` so this is latent, not yet user-visible, but the wiring required for MOD-03 to actually work for a future subscriber does not exist. |

**Score:** 6/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/host/protocols.py` | HasAPIRoutes/HasUIPage/HasEventSubscriptions/HasCollector | ✓ VERIFIED | All four `@runtime_checkable` Protocols present |
| `backend/src/host/manifest.py` | ModuleManifest Pydantic model | ✓ VERIFIED | `class ModuleManifest` present with id/kind/provides/requires/db_schema |
| `backend/src/host/registry.py` | ModuleRegistry | ✓ VERIFIED | `class ModuleRegistry` with register/resolve, conflict detection |
| `backend/src/host/loader.py` | ModuleLoader + topo-sort | ✓ VERIFIED | `TopologicalSorter` used; constructor injection confirmed |
| `backend/src/host/event_bus.py` | EventBus | ✓ VERIFIED (exists) / ⚠️ ORPHANED post-boot | Class exists and is functionally correct in isolation, but the loader's own instance is unreachable after boot (CR-05) |
| `backend/src/host/dependencies.py` | require_module_enabled | ✓ VERIFIED | `def require_module_enabled` present, used by `devices`/`traffic`/`security` routes |
| `backend/src/models/module_config.py` | ModuleConfig ORM model | ✓ VERIFIED | `class ModuleConfig` with module_id/enabled |
| `backend/src/modules/device_identity/` | Support module package | ✓ VERIFIED (exists) / ⚠️ HOLLOW enforcement | Package complete; but no `HasAPIRoutes`, so its own enable/disable flag is unenforceable anywhere |
| `backend/src/modules/traffic/`, `security/` | Feature module packages with own schema | ✓ VERIFIED | Own Alembic branches, schema-qualified models, `DeviceLookupInterface` consumers |
| `backend/src/routes/modules.py` | GET /api/modules/, POST /{id}/toggle | ✓ VERIFIED (exists, substantive) / ✗ Enforcement gap | Routes exist and pass their own tests, but toggling does not propagate to collectors/capture ingest (CR-01/CR-02) |
| `frontend/src/routes/settings/modules/+page.svelte` | Module settings page | ✓ VERIFIED | Renders module list, toggle switch, destructive-confirmation dialog |
| `frontend/src/lib/components/ModuleNav.svelte` | Nav entry component for HasUIPage modules | ✓ VERIFIED (wired, correctly empty) | Filters `enabled && ui_route`; currently renders nothing because no module implements `HasUIPage` yet and `ui_route` is hardcoded `null` in the API response (WR-08) — not a defect per se, but worth flagging since the wiring from `LoadResult.ui_routes` to the API response was never completed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `host/loader.py` | `host/registry.py` | `registry.register()` after constructor injection | ✓ WIRED | Confirmed in loader code |
| `host/loader.py` | `host/event_bus.py` | `event_bus.subscribe()` for HasEventSubscriptions modules | ✓ WIRED (mechanism) / ✗ NOT REACHABLE post-boot | Mechanism correct; the specific bus instance is discarded after boot (CR-05), and `device_identity` publishes to a *different* bus instance entirely (CR-03) |
| `host/dependencies.py` | `models/module_config.py` | `is_module_enabled(db, module_id)` | ✓ WIRED | Confirmed; used by `devices`/`traffic`/`security` route dependencies |
| `frontend/settings/modules/+page.svelte` | `backend/routes/modules.py` | `fetch GET /api/modules/`, `POST /{id}/toggle` | ✓ WIRED | Confirmed in `api.ts`/`+page.svelte` |
| `backend/routes/modules.py` | `models/module_config.py` | reads/writes `ModuleConfig.enabled` | ✓ WIRED (for HTTP routes only) | Confirmed; but this enabled flag is **not** read by `capture.py` or `_start_collectors()` — the wiring stops at the HTTP route layer (CR-01/CR-02) |
| `traffic/routes.py`, `security/routes.py` | `device_identity/interfaces.py` | `self._device_lookup.lookup()` | ✓ WIRED | Confirmed via grep, replaces direct Device/DeviceMacHistory joins |
| `device_identity/service.py` | `host/event_bus.py` | `event_bus.publish("new_device", ...)` | ✗ NOT_WIRED to the loader's bus | Publishes to `event_bus_singleton.py`'s separate instance instead (CR-03) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `frontend/settings/modules/+page.svelte` | `modules` | `listModules()` → `GET /api/modules/` → live `ModuleConfig` query | Yes | ✓ FLOWING |
| `ModuleNav.svelte` | `ui_route` filter | `list_modules()` hardcodes `ui_route: None` | No real data (by design — no `HasUIPage` consumer exists yet) | ⚠️ STATIC (acceptable per 05-06-SUMMARY.md's stated scope, but flagged as incomplete wiring per WR-08) |
| `routes/capture.py` ingest handlers | `is_module_enabled` check | **Does not exist** | N/A | ✗ DISCONNECTED — the enabled/disabled flag never reaches the hot ingest path at all |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `device_identity` is excluded from module listing | `grep "device_identity" backend/tests/test_module_registry_toggle.py` | `test_list_modules_excludes_device_identity_support_module` asserts `"device_identity" not in ids` | ✓ PASS (confirms exclusion from listing, but see gap — toggle endpoint itself has no equivalent guard) |
| Toggling `devices` off causes its own routes to 404 immediately | `test_toggling_devices_off_immediately_404s_next_request_no_restart` (read, not executed — no pytest runtime available in this sandbox) | Test asserts `GET /api/modules/devices/` returns 404 after toggle-off | ✓ PASS (by inspection — test exists and asserts the expected route-level behavior) |
| `device_identity` toggle silently succeeds despite no enforcement point | `grep -rn "require_module_enabled(\"device_identity\"" backend/src` | Zero matches | ✗ FAIL — confirms CR-01: no code anywhere gates on `device_identity`'s enabled flag |
| `_start_collectors` checks `is_module_enabled` before starting/continuing a collector | `grep -n "is_module_enabled" backend/src/main.py` | Zero matches | ✗ FAIL — confirms CR-02: collectors are unconditionally started and never re-checked |
| `capture.py` ingest handlers check module enabled state | `grep -n "is_module_enabled" backend/src/routes/capture.py` | Zero matches | ✗ FAIL — confirms CR-02 |
| Two EventBus instances exist | `grep -rn "EventBus()" backend/src/main.py backend/src/modules/device_identity/event_bus_singleton.py` | Two separate instantiations confirmed (`main.py:93`, `event_bus_singleton.py`) | ✗ FAIL — confirms CR-03/CR-05 |

Note: No Python virtual environment / dependency install was available in this sandbox (`uv`/`python3 -m pytest` both failed to run against the project's actual dependency set), so the full test suite could not be executed live. All findings above are based on direct source-code inspection (grep + Read), cross-referenced against the already-committed `05-REVIEW.md`'s independent code review and this verifier's own re-derivation of the same evidence from the source files. The 05-REVIEW.md findings for CR-01/CR-02/CR-03/CR-05 were independently re-confirmed by this verifier reading the cited files directly, not merely trusted from the review document.

### Probe Execution

No `scripts/*/tests/probe-*.sh` files exist in this repository and none are referenced by Phase 5's plans/summaries. Step 7c: SKIPPED (no probes declared or discovered).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|--------------|--------|----------|
| MOD-01 | 05-01 | Module contract: Protocols, ModuleManifest, ModuleLoader | ✓ SATISFIED | `host/protocols.py`, `host/manifest.py`, `host/loader.py` all present, tested |
| MOD-02 | 05-06 | User can view, enable, disable, or configure each module via dashboard settings | ✗ BLOCKED | Listing/toggle UI exists and works at the HTTP-route layer, but "disable" does not stop a disabled module's actual behavior for `traffic`/`security` (collectors, capture ingest) and is a complete no-op for `device_identity` (CR-01/CR-02) — see gaps |
| MOD-03 | 05-01 (infra) / latent across all modules | Modules can subscribe to platform events via EventBus | ✗ BLOCKED | EventBus mechanism exists and is unit-tested in isolation, but two disconnected bus instances exist post-boot (CR-03/CR-05); a future `HasEventSubscriptions` module would never observe `device_identity`'s "new_device" publishes |
| MOD-04 | 05-06 | Enabled module w/ UI page → nav entry at /modules/[name]; no rebuild needed on toggle | ✓ SATISFIED (structurally) | Toggle is immediate/no-restart (verified by `test_toggling_devices_off_immediately_404s_next_request_no_restart`); nav-entry filter logic is correct, currently empty because no module implements `HasUIPage` yet (acceptable — explicitly out of scope per 05-06-SUMMARY.md) |
| MOD-05 | 05-04 | Modules can register data collectors (background tasks) | ✓ SATISFIED (mechanism) | `HasCollector` Protocol + `_start_collectors()` correctly detect and start `run_collector()`; traffic's broadcaster is wired this way. (Note: the same mechanism is the source of the MOD-02 gap, since collectors are never stopped on disable — but the collector *registration* capability itself works as specified) |
| MOD-06 | 05-01 | ModuleRegistry resolves by Protocol type, fails fast on conflicts/unsatisfied requires | ✓ SATISFIED | Directly tested by `test_register_same_protocol_twice_raises_runtime_error_naming_both`, `test_resolve_unregistered_protocol_raises_runtime_error_not_keyerror` |
| MOD-07 | 05-03/04/05 | Devices/Traffic/Security retrofitted onto DeviceIdentity via DeviceLookupInterface | ✓ SATISFIED | Confirmed via grep: `traffic/routes.py`, `security/routes.py` call `self._device_lookup.lookup()`; each module owns its own Postgres schema with dedicated Alembic branch |
| MOD-08 | 05-02 | Linked-module manifest format + "Linked Apps" dashboard section | ✓ SATISFIED | `LinkedModuleManifest`, empty-state UI, `GET /api/modules/linked-apps/` all present and tested |

**Orphaned requirements check:** All eight MOD-01..MOD-08 IDs declared in REQUIREMENTS.md for Phase 5 are claimed across the six plans' `requirements:` frontmatter fields (MOD-01/03/06 in 05-01, MOD-08 in 05-02, MOD-02/04/05/07 across 05-03/04/05/06). No orphaned requirement IDs found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/src/main.py` | 57-73 | `_start_collectors` starts every `HasCollector` instance unconditionally, no `is_module_enabled` gate | 🛑 Blocker | Directly causes the MOD-02 enforcement gap (CR-02) |
| `backend/src/routes/capture.py` | (ingest handlers throughout) | No `is_module_enabled` check before writing `TrafficFlow`/`SecurityAlert`/etc. | 🛑 Blocker | Directly causes the MOD-02 enforcement gap (CR-02) |
| `backend/src/routes/modules.py` | 94-122 | `toggle_module` has no `kind == "feature"` guard (unlike `_feature_manifests()`) | 🛑 Blocker | Allows silently disabling the invisible `device_identity` support module (CR-01) |
| `backend/src/main.py` | 93-108 | Loader's own `registry`/`event_bus` discarded after `_load_native_modules()` returns | 🛑 Blocker | No runtime code can resolve a Protocol or subscribe to the loader's bus post-boot (CR-05) |
| `backend/src/modules/device_identity/event_bus_singleton.py` | (whole file) | Second, independent `EventBus()` instance, disconnected from the loader's bus | 🛑 Blocker | `device_identity`'s "new_device" publishes are unreachable by any `HasEventSubscriptions` consumer wired through the loader (CR-03) |
| `backend/src/routes/capture.py` | 67-70 | `_TRUSTED_HOSTS` computed once at import time, never refreshed | ⚠️ Warning | Not a Phase 5 must-have, but a real correctness issue (CR-04 from review); does not block this phase's goal |
| `frontend/src/routes/settings/modules/+page.svelte` | 61-89 | No loading-state guard against double-click toggle race | ⚠️ Warning | Not a must-have blocker; WR-03 in review |

No `TBD`/`FIXME`/`XXX` debt markers found in any file modified by this phase.

### Human Verification Required

None. All findings above are resolvable by direct code inspection; no behavior in question depends on visual rendering, real-time feel, or external service integration.

### Gaps Summary

The module-host **infrastructure** (Protocols, ModuleManifest, ModuleRegistry, ModuleLoader, module_configs table, the three feature-module retrofits, the Linked Apps section, and the settings-page UI/toggle mechanics) is genuinely well-built and matches MOD-01/04(structurally)/05/06/07/08. However, the phase's goal statement — "retrofitted into isolated, **independently-replaceable** modules" — and MOD-02's literal text — "enable, disable, **or configure** each one" — are not actually achieved for two of the five modules:

1. **MOD-02 is broken for `traffic`/`security`:** disabling either module only 404s its own HTTP routes; the background collector (traffic) and the hot-path capture ingest handlers (both) keep running and keep writing data, completely contradicting the UI's own confirmation-dialog promise that dependent modules "will also stop working."
2. **MOD-02 is broken for `device_identity`:** it is invisible in the settings list (correct, by design, since it's `kind="support"`), but the toggle *endpoint* has no equivalent guard, so it can be silently disabled via the raw API into a state with zero observable effect and no way to discover or undo it through the UI. The project's own test suite (`test_toggle_device_identity_requires_confirmation_naming_dependents`) directly exercises this exact path.
3. **MOD-03 is structurally incomplete:** two disconnected `EventBus` instances exist post-boot — the loader's own (discarded after boot) and `device_identity`'s separate singleton (the only one anything actually publishes through). This is latent today (no module implements `HasEventSubscriptions` yet) but means MOD-03's "modules can subscribe... and react accordingly" claim has no working end-to-end path the moment a real subscriber is added — which Phase 5.1/5.2 (Notifications, Improved Device Identity) are very likely to need.

These three items are evaluated as a genuine scope gap against the requirement text as written in REQUIREMENTS.md/ROADMAP.md, not an acceptable narrower reading. The strongest evidence for this judgment is internal to the codebase itself: the settings page's own confirmation-dialog copy promises dependent-module shutdown that does not happen, and the project's own test suite directly proves the `device_identity` silent-disable path is reachable through the public API today. All three gaps are root-caused in `main.py`'s boot sequence (collector startup never consults `ModuleConfig`; the loader's registry/bus are thrown away) and `routes/modules.py`'s toggle endpoint (no kind filter) — a focused follow-up plan addressing `main.py` and `routes/modules.py`/`routes/capture.py` together would close all three gaps without touching the already-solid retrofit/schema-isolation work.

---

_Verified: 2026-06-21T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
