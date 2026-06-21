# Phase 5: Plugin System + Notifications - Context

> **SUPERSEDED 2026-06-21** — built against the retired bolt-on plugin contract. See `docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md` and the new Phase 5 (Module Platform Foundation) in ROADMAP.md. Kept for history only; do not use as input to planning or execution.


**Gathered:** 2026-06-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the plugin contract end-to-end (manifest, optional API routes, event subscriptions, data collectors, UI page route) and prove it with the notification plugin as the first real consumer: user can view/enable/disable/configure plugins from a dashboard settings page, an enabled plugin with a UI page appears at `/plugins/[plugin-name]` with no core rebuild, plugins can subscribe to platform events, and the notification plugin delivers a real push alert (ntfy.sh or Pushover) when an unknown device joins. Visual/interaction design is locked by `05-UI-SPEC.md`; this discussion covers backend/product behavior decisions UI-SPEC does not define.

</domain>

<decisions>
## Implementation Decisions

### Secret Storage
- **D-01:** Plugin secrets (ntfy.sh access token, Pushover user key) are stored as **plaintext in a DB column** — no encryption-at-rest layer. Rationale: the self-hosted Postgres instance is already the trust boundary for a single-user, non-multi-tenant, no-cloud deployment (matches research's A1 assumption). Secrets are never echoed back in plaintext via the API — only the masked display (`••••a1b2`) per UI-SPEC.

### "No Rebuild" Scope (PLUG-04)
- **D-02:** Directory-scan-at-startup is the loading model (research Pattern 2). Toggling/configuring an **already-discovered** plugin is fully zero-restart (enable/disable/configure via API, no container restart). Adding a **brand-new** plugin directory that the backend has never scanned before requires **one container restart** to be picked up — this is explicitly acceptable for v1, since there is no plugin-install UI this phase (URL install is v2's `PDST-01`) and all v1 plugins ship as code in this repo. "No core rebuild" means no image rebuild, not true hot-loading of arbitrary new plugin code.

### Disabling a Plugin's Background Collector
- **D-03:** When a plugin with a data collector is disabled, its in-flight collection cycle **finishes its current tick** before stopping — not killed mid-cycle. Implementation: a per-plugin `asyncio.Event` the collector loop checks between ticks, mirroring `traffic_broadcaster.update_snapshot_loop`'s existing `stop_event` + `asyncio.wait_for(..., timeout=...)` pattern exactly (one event per plugin, not one shared global event). Avoids partial/torn writes or a dangling mid-request httpx call.

### Event Wiring Depth (PLUG-03)
- **D-04:** All five event-type contracts (`new_device`, `device_lost`, `security_alert`, `traffic_spike`, `mode_change`) are defined as typed Pydantic models in the `EventBus` this phase, so later phases never need to retrofit the contract.
- **D-05:** `device_lost` gets a **real minimal detector** built this phase — a periodic asyncio loop (same cadence pattern as `update_snapshot_loop`) checking each device's `last_seen` against a threshold and firing `device_lost` when it's exceeded. Rationale: PLUG-03's "subscribe and react" success criterion can't be proven end-to-end for an event that never fires, and no existing detector covers this today.
- **D-06:** `traffic_spike` gets **wired to Phase 4's existing bandwidth-anomaly check** (`bandwidth_anomaly.py`'s `check_bandwidth_anomaly()`, D-09 from Phase 4) to also call `event_bus.publish("traffic_spike", ...)` alongside its existing `security_alerts` write — the detector logic already exists and already fires, so this is a small addition that makes the event provably reachable, consistent with the `device_lost` decision.
- **D-07:** `mode_change` stays **define-only / unpublished** this phase — no mode-switching logic exists yet (that's Phase 6), so there's nothing real to wire it to. Phase 6 calls `event_bus.publish("mode_change", ...)` into the already-built typed contract.

### Claude's Discretion
- Exact threshold/window for the `device_lost` detector (D-05) — tune during implementation.
- Exact field shape of each event's Pydantic payload model beyond what's needed for `new_device`/`security_alert`/`traffic_spike` to round-trip through real publishers.
- Plugin secret DB schema details (column types, which fields are marked `secret: true` in the manifest config schema) — implementation detail consistent with D-01.
- Per-plugin `asyncio.Event`/`asyncio.Task` bookkeeping shape in the loader (dict keyed by plugin_id, per research's Open Question 1 recommendation) — implementation detail consistent with D-03.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements & Roadmap
- `.planning/ROADMAP.md` — Phase 5 section: goal, success criteria (4 items), requirements PLUG-01..05, FPLG-04
- `.planning/REQUIREMENTS.md` — Full PLUG-01..05 and FPLG-04 requirement text
- `.planning/PROJECT.md` — Key Decisions table: plugin-first architecture, plugin UI via dedicated routes, plugin contract scope, no plugin marketplace in v1, ntfy.sh/Pushover for notifications; "Data privacy: no telemetry, no external calls unless user explicitly configures an integration" constraint (directly governs D-01 and the notification plugin's outbound calls)

### UI Design Contract
- `.planning/phases/05-plugin-system-notifications/05-UI-SPEC.md` — Approved design contract: settings/plugins list page, generic `/plugins/[slug]` page, config form (masked-secret pattern, provider-swap behavior), Switch toggle, accessibility contract. Locks all visual/interaction decisions — not re-discussed here.

### Phase Research
- `.planning/phases/05-plugin-system-notifications/05-RESEARCH.md` — Architecture patterns (Plugin Contract as Protocol, manifest-driven directory scan, in-process EventBus, generic data-driven plugin UI page), Pitfalls 1-5 (FastAPI router un-registration, event payload drift, silent collector task death, notification delivery blocking, ntfy.sh rate limiting), Assumptions Log A1/A5 (resolved by D-01/D-02 above), Open Questions 1-3 (resolved by D-03/D-05/D-06/D-07 above), Validation Architecture (test file map), Security Domain section
- `.planning/phases/05-plugin-system-notifications/05-VALIDATION.md` — Validation strategy for this phase

### Prior Phase Context
- `.planning/phases/04-security/04-CONTEXT.md` — D-09 (bandwidth-anomaly detection, the detector D-06 above wires into), D-11 (`security_alerts` table shape, the canonical alert record PLUG-03's `security_alert` event should align with)
- `.planning/phases/03-live-traffic-bandwidth/03-CONTEXT.md` — D-07 (swappable source-interface pattern, same idiom referenced for the EventBus design in research)

### Technology Stack
- `CLAUDE.md` — Notifications section: httpx + thin client (or Apprise) for ntfy.sh/Pushover; SSE over WebSockets; Data privacy constraint

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/src/services/traffic_broadcaster.py` — `update_snapshot_loop`'s `stop_event` + `asyncio.wait_for(..., timeout=...)` pattern is the direct template for D-03's per-plugin collector shutdown behavior.
- `backend/src/services/bandwidth_anomaly.py` — `check_bandwidth_anomaly()` is the existing detector D-06 wires into for `traffic_spike` publishing.
- `backend/src/models/security_alert.py` and `backend/src/models/app_settings.py` — existing single-row-config and alert-record patterns relevant to plugin config storage and the `security_alert` event payload shape.
- `backend/src/routes/capture.py` — existing ingest-route trust pattern (loopback/gateway-trusted-only, Pydantic payload models) for any new plugin-facing API routes.
- `backend/src/services/discovery.py` — `upsert_discovered_identity()` is where `new_device` publishing hooks in (already fires `unknown_device` alerts per Phase 4 D-13).

### Established Patterns
- Swappable source/adapter interfaces (Phase 3's `BandwidthSource`, Phase 4's `ThreatIntelSource`) are the established way to keep a feature open to future richer backends — the Plugin Contract as `Protocol` (research Pattern 1) follows this same idiom.
- No settings page exists yet anywhere in the frontend — Phase 5 introduces `/settings/plugins` as the first settings sub-route.
- No event bus exists yet — Phase 5 introduces the in-process `EventBus` from scratch (research Pattern 3).

### Integration Points
- New `EventBus` sits between existing detection sites (`discovery.py`, `bandwidth_anomaly.py`, the unknown-device alert path) and plugin subscribers.
- New plugin loader (directory scan at startup) sits alongside FastAPI's route registration at app startup.
- New `/settings/plugins` and `/plugins/[slug]` frontend routes sit alongside the existing `/dashboard`, `/setup`, `/login` routes.

</code_context>

<specifics>
## Specific Ideas

No specific product references beyond what's captured in the decisions above — discussion focused on resolving research's flagged assumptions (A1, A5) and open questions (1-3) rather than introducing new specifics.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Custom per-plugin UI pages, plugin install-from-URL, capability-permission display, collector status visibility, and mode-switcher UI were already explicitly deferred in `05-UI-SPEC.md`'s "What This Contract Does NOT Define" section — not re-opened here.)

</deferred>

---

*Phase: 5-Plugin System + Notifications*
*Context gathered: 2026-06-21*
