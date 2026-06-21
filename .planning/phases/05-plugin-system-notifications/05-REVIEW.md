---
phase: 05-plugin-system-notifications
reviewed: 2026-06-21T00:00:00Z
depth: standard
files_reviewed: 83
files_reviewed_list:
  - backend/alembic.ini
  - backend/alembic/versions/0006_module_configs.py
  - backend/src/data/vendor_catalog.py
  - backend/src/host/__init__.py
  - backend/src/host/dependencies.py
  - backend/src/host/event_bus.py
  - backend/src/host/loader.py
  - backend/src/host/manifest.py
  - backend/src/host/protocols.py
  - backend/src/host/registry.py
  - backend/src/main.py
  - backend/src/models/__init__.py
  - backend/src/models/module_config.py
  - backend/src/modules/__init__.py
  - backend/src/modules/device_identity/__init__.py
  - backend/src/modules/device_identity/event_bus_singleton.py
  - backend/src/modules/device_identity/identity_inference.py
  - backend/src/modules/device_identity/identity_resolver.py
  - backend/src/modules/device_identity/interfaces.py
  - backend/src/modules/device_identity/manifest.py
  - backend/src/modules/device_identity/migrations/0001_initial.py
  - backend/src/modules/device_identity/models.py
  - backend/src/modules/device_identity/module.py
  - backend/src/modules/device_identity/service.py
  - backend/src/modules/devices/__init__.py
  - backend/src/modules/devices/manifest.py
  - backend/src/modules/devices/module.py
  - backend/src/modules/devices/routes.py
  - backend/src/modules/linked_apps/__init__.py
  - backend/src/modules/linked_apps/linked_manifest.py
  - backend/src/modules/linked_apps/manifest.py
  - backend/src/modules/linked_apps/module.py
  - backend/src/modules/linked_apps/routes.py
  - backend/src/modules/security/__init__.py
  - backend/src/modules/security/manifest.py
  - backend/src/modules/security/migrations/0001_initial.py
  - backend/src/modules/security/models.py
  - backend/src/modules/security/module.py
  - backend/src/modules/security/routes.py
  - backend/src/modules/traffic/__init__.py
  - backend/src/modules/traffic/broadcaster.py
  - backend/src/modules/traffic/manifest.py
  - backend/src/modules/traffic/migrations/0001_initial.py
  - backend/src/modules/traffic/models.py
  - backend/src/modules/traffic/module.py
  - backend/src/modules/traffic/routes.py
  - backend/src/routes/capture.py
  - backend/src/routes/modules.py
  - backend/src/services/bandwidth_anomaly.py
  - backend/src/services/bandwidth_source.py
  - backend/src/services/port_rules.py
  - backend/tests/conftest.py
  - backend/tests/schema_portability_spike.py
  - backend/tests/test_bandwidth_aggregates.py
  - backend/tests/test_bandwidth_anomaly.py
  - backend/tests/test_bandwidth_query.py
  - backend/tests/test_capture.py
  - backend/tests/test_device_identity_lookup.py
  - backend/tests/test_devices_module_boot.py
  - backend/tests/test_devices.py
  - backend/tests/test_discovery.py
  - backend/tests/test_event_bus.py
  - backend/tests/test_identity_inference.py
  - backend/tests/test_identity_resolver.py
  - backend/tests/test_linked_apps.py
  - backend/tests/test_mac_history.py
  - backend/tests/test_models_scaffold.py
  - backend/tests/test_module_loader.py
  - backend/tests/test_module_registry_toggle.py
  - backend/tests/test_port_rules.py
  - backend/tests/test_require_module_enabled.py
  - backend/tests/test_security_alerts.py
  - backend/tests/test_security_scan.py
  - backend/tests/test_traffic_destinations.py
  - backend/tests/test_traffic_stream.py
  - frontend/src/lib/api.ts
  - frontend/src/lib/components/LinkedAppsSection.svelte
  - frontend/src/lib/components/ModuleNav.svelte
  - frontend/src/lib/components/ui/switch/index.ts
  - frontend/src/lib/components/ui/switch/switch.svelte
  - frontend/src/routes/dashboard/+page.svelte
  - frontend/src/routes/modules/[slug]/+page.svelte
  - frontend/src/routes/settings/modules/+page.svelte
findings:
  critical: 5
  warning: 8
  info: 5
  total: 18
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-06-21T00:00:00Z
**Depth:** standard
**Files Reviewed:** 83
**Status:** issues_found

## Summary

This phase retrofits the existing devices/traffic/security/device_identity feature surface onto a new module-host platform (ModuleLoader, ModuleRegistry, EventBus, capability Protocols, per-module schemas, and a runtime enable/disable toggle). The infrastructure pieces (`host/loader.py`, `host/registry.py`, `host/protocols.py`) are clean and well-tested in isolation. However, the retrofit has several correctness gaps once the pieces are wired together end-to-end in `main.py` and `routes/modules.py`:

- The "disable a module" feature (MOD-02/MOD-04) does not actually stop a disabled module's *capabilities* from running — only its HTTP routes 404. A disabled `traffic` or `security` module's background collector keeps running, and a disabled `device_identity` keeps accepting writes from the hot capture-ingest path, silently contradicting the UI's promise that "this won't delete any data" but implying the feature is fully off.
- `main.py` discards the `ModuleLoader`'s own `EventBus`/`ModuleRegistry` instances after `load()` returns, while `device_identity` publishes through a totally separate singleton `EventBus` (`event_bus_singleton.py`) that no other module's `get_subscriptions()` is ever wired into — `new_device` events are currently published into a void.
- The capture ingest trust boundary (`_TRUSTED_HOSTS`) is computed once at import time from `/proc/net/route`, which is read before the container's network is necessarily up, and is never recomputed — a routing change after boot permanently locks out (or, worse, never includes) the real gateway IP without a process restart.
- Confirmation-gated module disable (`_dependents_of`) only checks one level of the dependency graph, not transitive dependents, and silently ignores any module appearing in `requires` more than once with no provider edge of its own (already covered by loader fail-fast, but worth flagging as a latent gap if the graph grows deeper than the current 1-hop fan-out).

## Critical Issues

### CR-01: Disabling `device_identity` does nothing — module has no routes, so the toggle is a no-op masquerading as a real control

**File:** `backend/src/routes/modules.py:55-58`, `backend/src/modules/device_identity/module.py` (entire file)
**Issue:** `device_identity` is `kind="support"` and is excluded from `_feature_manifests()` (line 58), so it never appears in `GET /api/modules/` and the frontend never renders a toggle for it. However, `test_module_registry_toggle.py::test_toggle_device_identity_requires_confirmation_naming_dependents` *does* successfully `POST /api/modules/device_identity/toggle` and flips `device_identity`'s `ModuleConfig.enabled` to `False` — `toggle_module` itself has no `kind` filter, only the *listing* endpoint does. Once that row exists with `enabled=False`, nothing in the codebase ever calls `require_module_enabled("device_identity")` anywhere (`device_identity` has no routes/router at all — confirmed: `DeviceIdentityModule` does not satisfy `HasAPIRoutes`). The toggle silently succeeds, the UI has no way to know it happened (the module is invisible in the list), and `record_observation`/`lookup()` continue running on the hot ingest path regardless — the disable has zero effect while the API reports `enabled: false` as if it worked.
**Fix:** Either exclude `device_identity` from `POST /{module_id}/toggle` entirely (404/400 for support-kind modules, mirroring the existing `_feature_manifests()` filter used for listing), or make every consumer of `DeviceLookupInterface`/`record_observation` actually check `is_module_enabled(db, "device_identity")` before proceeding. Given the current architecture (support modules have no enforcement point), the safer minimal fix is to reject toggling any non-`"feature"`-kind module id at the route level:
```python
@router.post("/{module_id}/toggle")
async def toggle_module(module_id: str, payload: ToggleRequest, ...):
    target = next((m for m in _manifests if m.id == module_id), None)
    if target is None or target.kind != "feature":
        raise HTTPException(status_code=404, detail="Module not found")
    ...
```

### CR-02: Disabling `traffic` or `security` stops the HTTP routes but never stops the background collector or hot-path writes

**File:** `backend/src/main.py:42-73`, `backend/src/modules/traffic/broadcaster.py:99-119`, `backend/src/routes/capture.py:220-385`
**Issue:** `_start_collectors()` starts a `HasCollector` task for every loaded module instance unconditionally at boot and never consults `ModuleConfig`/`is_module_enabled`. Once `traffic` is toggled off via `/api/modules/traffic/toggle`, `update_snapshot_loop` keeps querying `TrafficFlow`/`Device` every 7 seconds forever — only the SSE route 404s, the snapshot itself keeps recomputing in memory. Worse, `routes/capture.py`'s `ingest_traffic`/`ingest_scan_result`/`queue_daily_scans` handlers write `TrafficFlow`/`BandwidthMetric`/`SecurityAlert`/`PortScanResult` rows directly and never call `is_module_enabled` for `"traffic"` or `"security"` at all — disabling either module from the settings UI has *no effect whatsoever* on data ingestion, despite MOD-02's enable/disable promise and the UI copy ("this won't delete any data" implies the feature itself stops, not just its UI).
**Fix:** Either (a) gate `capture.py`'s ingest handlers behind `is_module_enabled(db, "traffic")`/`is_module_enabled(db, "security")` checks (treating a disabled module as "stop processing this kind of event"), or (b) explicitly scope MOD-02 to "hide the UI/API surface only" and document that data collection is unaffected — but the current behavior contradicts the destructive-confirmation dialog's framing ("X other modules depend on this and will also stop working") since nothing actually stops.

### CR-03: `device_identity`'s `event_bus_singleton` publishes `"new_device"` into a bus that no module ever subscribes to — the event is silently dropped

**File:** `backend/src/modules/device_identity/event_bus_singleton.py`, `backend/src/main.py:93-108`, `backend/src/host/loader.py:143-148`
**Issue:** `_load_native_modules()` constructs a fresh `EventBus()` for the `ModuleLoader` (`main.py:93`) and that is the only bus the loader wires `HasEventSubscriptions.get_subscriptions()` handlers into. Meanwhile, `device_identity/service.py::upsert_discovered_identity` publishes `"new_device"` exclusively through the separate `event_bus_singleton.event_bus` instance (`service.py:121`). None of the five native modules (`device_identity`, `devices`, `traffic`, `security`, `linked_apps`) implement `HasEventSubscriptions`, so today this is latent rather than actively broken — but the design is internally inconsistent: there are now *two independent EventBus instances* in the same process with no way for a future module's `get_subscriptions()` to ever observe `event_bus_singleton`'s traffic, since the ModuleLoader only ever subscribes handlers onto its own internally-constructed bus. Any future module declaring `get_subscriptions({"new_device": handler})` will silently never fire, with no error, no log, nothing — a debugging trap.
**Fix:** Either pass the single shared `EventBus` instance that `ModuleLoader.event_bus` owns into `device_identity`'s factory (`create(deps)`) so `service.py` publishes onto the *same* bus the loader wires subscribers into, or make `event_bus_singleton.event_bus` the one true process-wide bus and have `ModuleLoader.__init__` default to importing it instead of constructing a brand new `EventBus()`. As written, two parallel buses exist and only one is reachable by the loader's subscription-wiring path.

### CR-04: Capture ingest trust boundary (`_TRUSTED_HOSTS`) is computed once at import time and never refreshed — fails open or closed permanently depending on boot-time network state

**File:** `backend/src/routes/capture.py:67-70`
**Issue:** `_default_gateway = _detect_default_gateway()` and `_TRUSTED_HOSTS = frozenset(...)` are evaluated exactly once, at module import time (i.e., at `create_app()` time inside the same process). If the backend container starts before its network interface has a route table populated (a realistic race in Docker Compose with dependent service startup ordering), `_detect_default_gateway()` permanently returns `None` for the lifetime of the process — and every gateway-relayed capture request is rejected with 403 until a manual restart, even though the design intent (per the inline comment) is "trust loopback or detected default gateway." Conversely, if the gateway changes after boot (DHCP lease renewal on the host's WAN-facing interface, VPN reconnect, etc.), the stale cached gateway IP remains trusted forever — a low-severity unauthorized-injection surface for capture data, though mitigated by requiring host-network-level access already.
**Fix:** Recompute `_detect_default_gateway()` per-request (cheap — a single small file read) or on a periodic timer rather than once at import time:
```python
def _is_trusted_host(client_host: str | None) -> bool:
    if client_host in {"127.0.0.1", "::1"}:
        return True
    return client_host == _detect_default_gateway()
```
and replace every `if client_host not in _TRUSTED_HOSTS` check across the five capture routes with this function call.

### CR-05: `_load_native_modules()`'s `ModuleLoader`'s own `ModuleRegistry`/`EventBus` are discarded after boot — nothing in the running process can resolve a Protocol post-startup

**File:** `backend/src/main.py:93-108`
**Issue:** `loader = ModuleLoader(registry=ModuleRegistry(), event_bus=EventBus())` is a local variable; `loader.registry` and `loader.event_bus` are never stored anywhere accessible after `_load_native_modules()` returns (`result = loader.load(...)` only captures `LoadResult`, which has no reference to the registry/bus). This means there is currently no way for any future runtime code (a new route, a CLI command, an admin debug endpoint) to call `ModuleRegistry.resolve()` against the live registry that was actually populated at boot — the registry and event bus are throwaway objects, alive only during the synchronous `load()` call, then garbage. Combined with CR-03, this confirms two independent, unreachable `EventBus`/`ModuleRegistry` instances exist with no path back to them.
**Fix:** Store the loader (or at least its `registry`/`event_bus`) on the app state or a module-level global, mirroring `_module_load_result`:
```python
_module_loader: ModuleLoader | None = None

def _load_native_modules(app: FastAPI):
    global _module_loader
    loader = ModuleLoader(registry=ModuleRegistry(), event_bus=EventBus())
    ...
    _module_loader = loader
    result = loader.load(manifests, factory_by_id)
    ...
```

## Warnings

### WR-01: `_dependents_of` only walks one hop of the dependency graph — a transitive dependent is never warned about

**File:** `backend/src/routes/modules.py:61-76`
**Issue:** `_dependents_of(module_id)` computes direct dependents only (modules whose `requires` directly intersects `module_id`'s `provides`). If a future module C requires something B provides, and B requires something A provides, disabling A only warns about B, never C — C's breakage is silent. With the current five-module graph this is moot (max depth is 1), but the function's docstring claims "who would break if module_id were disabled," which is a transitive claim the implementation doesn't fulfill.
**Fix:** Walk the full dependent closure via BFS/DFS over `_manifests`, not just the immediate `provides ∩ requires` intersection.

### WR-02: `toggle_module`'s "enabling" path is exempt from any safety check while disabling re-enables modules whose own dependencies might themselves be disabled

**File:** `backend/src/routes/modules.py:94-122`
**Issue:** Enabling a module (e.g. `devices`, which `requires=[DeviceLookupInterface]`) never checks whether `device_identity` (its provider) is itself enabled. Per CR-01, `device_identity` *can* be toggled disabled via the raw API even though it's hidden from the UI list — so a client could disable `device_identity` then re-enable `devices`, producing a `devices` module that is "enabled" per its own `ModuleConfig` row but whose only data source is, per CR-01, not actually gated at all (since `device_identity` has no enforcement point) — this is a logically inconsistent state with no validation anywhere.
**Fix:** When enabling a module, validate that everything in its `requires` chain is itself enabled (or, simpler, close CR-01 first so `device_identity` can never be independently disabled).

### WR-03: `frontend/src/routes/settings/modules/+page.svelte::handleToggle` fires two network requests for a no-confirmation disable/enable, with no loading-state guard against double-click

**File:** `frontend/src/routes/settings/modules/+page.svelte:61-89`
**Issue:** Clicking the switch and clicking the adjacent button both call `handleToggle(module)` with no debounce/disabled-while-pending guard. A rapid double click (switch then button, or two quick clicks) issues two concurrent `POST /toggle` calls against the same `module_id`; since `toggle_module` reads-then-writes (`current_enabled = await _enabled_state(...)`, then later writes `new_enabled = not current_enabled`), two concurrent requests racing on the same `module_id` with no row-level locking can both read `enabled=True` and both attempt to write `enabled=False`, or — more subtly — one request's "toggle to False" can land after a second concurrent "toggle to True," leaving the UI's optimistic expectation out of sync with the actual final DB state until the next `load()`.
**Fix:** Disable the switch/button while a toggle request for that `module.id` is in flight, and/or add a `SELECT ... FOR UPDATE` (or an atomic `UPDATE ... SET enabled = NOT enabled` in SQL) on the backend instead of separate read-then-write.

### WR-04: `device_bandwidth`/`device_destinations` build a SQL `IN (...)` clause from `device_info.macs`, which can be an empty set if a registered device has neither `last_known_mac` nor any `DeviceMacHistory` rows

**File:** `backend/src/modules/traffic/routes.py:172-227`, `backend/src/modules/device_identity/module.py:126-140`
**Issue:** `_to_device_info` builds `macs` purely from `DeviceMacHistory` plus `device.last_known_mac` (skipped if `None`). A newly-registered device created from an mDNS-only placeholder identity (`register_device` sets `last_known_mac=None`, see `module.py:74`) and which has never produced a `DeviceMacHistory` row yet (no ARP/DHCP observation since registration) has `macs == set()`. `BandwidthMetric.device_mac.in_(macs)` with an empty set degenerates to a query that matches nothing (correct in intent), but this is undocumented/untested — there is no test exercising a device with zero MACs, so a future SQL-dialect change (e.g. a dialect that throws on an empty `IN ()` rather than translating it to `false`) would silently regress with no test coverage to catch it.
**Fix:** Add an explicit early-return / test for the empty-`macs` case: `if not macs: return {"device_id": device_id, "start": start, "end": end, "points": []}`.

### WR-05: `traffic/broadcaster.py::_compute_snapshot` resolves devices by `Device.last_known_mac` only, silently dropping MAC-rotated devices from the live SSE feed mid-rotation

**File:** `backend/src/modules/traffic/broadcaster.py:43-77`
**Issue:** The module docstring explicitly excuses this ("acceptable here because the rolling window is far shorter than any realistic MAC-rotation interval"), but the implementation still has a real edge case the comment doesn't address: if a device's MAC rotates (e.g. iOS private MAC rotation on Wi-Fi reconnect) at any point *during* the 5-minute rolling window, `TrafficFlow` rows written under the old MAC within that window will appear in `top_talkers` keyed by the stale MAC with `device_name: device_mac` (raw MAC string) instead of the device's friendly name, fragmenting one device's traffic into two separate "top talker" rows for up to 5 minutes — a real, user-visible glitch on every rotation, not a hypothetical.
**Fix:** At minimum, document this as a known limitation in the UI/changelog; ideally resolve `device_by_mac` against the same MAC-history union `DeviceLookupInterface` exposes, accepting the added per-tick query cost.

### WR-06: `EventBus._safe_call`/`ModuleLoader._wire_capabilities` swallow all exceptions via bare `print()`, with no structured logging or metric

**File:** `backend/src/host/event_bus.py:28-33`, `backend/src/host/loader.py:128-156`
**Issue:** Every failure path in the module-host infrastructure (`EventBus` handler exceptions, all four capability-wiring try/excepts) is logged via `print()` to stdout rather than the standard `logging` module. In a containerized deployment this is workable but loses log levels, structured fields (module_id, exception type), and any ability to alert on a module silently failing to wire — a module's `get_router()` raising at startup is currently indistinguishable in the logs from routine INFO output, and there's no test asserting these failure paths are even observable (no caplog assertions in `test_module_loader.py`).
**Fix:** Replace `print(...)` with `logging.getLogger(__name__).exception(...)` / `.error(...)` throughout `host/loader.py` and `host/event_bus.py`.

### WR-07: `linked_apps/linked_manifest.py`'s fallback `ModuleManifest` local class has drifted from `host/manifest.py`'s canonical shape (`kind` literal includes `"linked"`, the real one doesn't)

**File:** `backend/src/modules/linked_apps/linked_manifest.py:14-28`, `backend/src/host/manifest.py:23`
**Issue:** The lazy-import fallback's `Literal["feature", "support", "linked"]` includes a `"linked"` kind that `host/manifest.py`'s canonical `ModuleManifest.kind` (`Literal["feature", "support"]`) does not support. Since `host/manifest.py` now exists (this phase landed it), the fallback branch in `linked_manifest.py` is dead code — `from src.host.manifest import ModuleManifest` always succeeds — but the file's own docstring promises "dropping the fallback branch" as the only required follow-up change, and that cleanup was never done. The stale `"linked"` literal is misleading to a future reader skimming this file for the canonical `kind` vocabulary.
**Fix:** Delete the `try/except ModuleNotFoundError` fallback block entirely now that `src.host.manifest` is a real, always-importable module — `linked_apps/manifest.py` already imports it directly without any fallback, proving the fallback in `linked_manifest.py` is unnecessary today.

### WR-08: `routes/modules.py::list_modules` always returns `"ui_route": None`, even though `host/protocols.py::HasUIPage` exists and `ModuleLoader.load()` already collects `result.ui_routes`

**File:** `backend/src/routes/modules.py:79-91`, `backend/src/host/loader.py:79`
**Issue:** `LoadResult.ui_routes` is populated by the loader for any module implementing `HasUIPage`, but `routes/modules.py` never reads it — `list_modules` hardcodes `"ui_route": None` for every module. The frontend's `ModuleNav.svelte` explicitly filters `modules.filter((m) => m.enabled && m.ui_route)`, meaning the nav is permanently empty for every native module regardless of capability, since the backend never threads `ui_routes` through to this endpoint. None of the five native modules currently implement `HasUIPage` so this is not user-visible yet, but the wiring is incomplete and the dead `ui_route: null` literal is a footgun for the next module that does implement `HasUIPage` expecting the nav to "just work."
**Fix:** Either wire `_module_load_result.ui_routes` into `set_manifests`'s caller (`main.py`) and thread it through to `list_modules`, or remove `ui_route` from the response/frontend contract until a real `HasUIPage` consumer exists.

## Info

### IN-01: `_load_native_modules` docstring and the `device_identity.module.py` module both claim "every module this codebase has goes through this single ModuleLoader call," but `linked_apps` (which is itself listed in the same `manifests` list) is, per its own manifest's docstring, "a manifest entry only (no code)" for *third-party* linked apps — yet it's wired as a full native-style module with `create()`/`get_router()`

**File:** `backend/src/main.py:76-92`, `backend/src/modules/linked_apps/linked_manifest.py:1-6`
**Issue:** Minor doc inconsistency: `LinkedModuleManifest` (the data-only shape for *third-party* apps with zero code) is a completely different concept from the `linked_apps` *native* feature module (which does have code: `module.py`, `routes.py`). The naming overlap (`linked_apps` module vs. `LinkedModuleManifest`) is confusing on first read and risks a future contributor conflating "linked app" (a dashboard card linking out to a third-party app's own UI) with "linked_apps module" (the native FastAPI module that will eventually serve the list of such cards).
**Fix:** No functional change needed; consider renaming `LinkedModuleManifest` to something like `ThirdPartyLinkSpec` or adding a clarifying module docstring distinguishing the two concepts more sharply.

### IN-02: `record_observation`'s docstring claims "byte-identical" behavior preservation in several places (`module.py::register`/`merge`), but no test directly diffs old vs. new behavior — these are now unverifiable claims baked into comments

**File:** `backend/src/modules/device_identity/module.py:59-62, 84-86`
**Issue:** Multiple docstrings assert "byte-identical behavior to the pre-retrofit routes" as a load-bearing correctness claim, but since the pre-retrofit code no longer exists in this codebase (it was moved/deleted), there's no way for a future reader to verify this claim against anything; it's an unfalsifiable assertion baked into a comment.
**Fix:** Not urgent, but consider trimming these comments to describe current behavior rather than relative-to-deleted-code claims, since the comparison point won't be inspectable once the migration history is squashed/archived.

### IN-03: `capture.py`'s five route handlers repeat the identical `client_host = ...; if client_host not in _TRUSTED_HOSTS: raise HTTPException(...)` block five times verbatim

**File:** `backend/src/routes/capture.py:124-128, 153-157, 184-186, 238-240, 318-320, 395-397, 434-436`
**Issue:** Code duplication — the exact same 4-line trust-boundary check appears seven times (once per route) with identical error message and status code. This compounds CR-04: when the fix for CR-04 lands, it must be applied in all seven places unless extracted first.
**Fix:** Extract into a FastAPI dependency, e.g. `Depends(require_trusted_capture_source)`, applied uniformly across all `/api/capture/*` routes.

### IN-04: `evaluate_open_ports`'s `RISKY_PORTS` includes a bare `512, 513, 514` without each individually commented despite the file's otherwise-thorough per-port commenting convention

**File:** `backend/src/services/port_rules.py:12-14`
**Issue:** Minor inconsistency in an otherwise well-documented constants table — every other port has an inline comment naming the service; `512, 513, 514` share one trailing comment (`# rexec/rlogin/rsh`) for three values, breaking the per-line convention used elsewhere in the same dict/set literal.
**Fix:** Either keep the grouped comment as intentional (acceptable) or split for consistency: `512,  # rexec` / `513,  # rlogin` / `514,  # rsh`.

### IN-05: `DeviceIdentityModule._find_device` and `routes/capture.py` both independently re-implement "look up a Device by MAC," diverging slightly in null-handling

**File:** `backend/src/modules/device_identity/module.py:112-124`, `backend/src/routes/capture.py:142-144, 287-289, 325`
**Issue:** `capture.py` queries `select(Device).where(Device.last_known_mac == payload.src_mac)` directly in three separate places instead of routing through `DeviceLookupInterface`, which the rest of the codebase (Devices/Traffic/Security modules) is required to do per `T-05-07`/`T-05-11`'s stated convention. This is explicitly justified in `bandwidth_anomaly.py`'s docstring (same-session transaction reasons) but `capture.py`'s direct `Device` queries have no equivalent justifying comment — it's unclear if this is an intentional, documented exception to the "go through DeviceLookupInterface" rule or an oversight, since `capture.py` is explicitly called out as "not itself a module in this phase's scope" but still imports `Device` directly six times.
**Fix:** Add a docstring note (mirroring `bandwidth_anomaly.py`'s) clarifying that `capture.py`'s direct ORM access is an intentional, scoped exception for same-transaction hot-path reasons, so a future reviewer doesn't flag this as a T-05-07 violation.

---

_Reviewed: 2026-06-21T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
