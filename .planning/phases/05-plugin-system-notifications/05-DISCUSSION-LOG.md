# Phase 5: Plugin System + Notifications - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-21
**Phase:** 05-plugin-system-notifications
**Areas discussed:** Secret storage approach, "No rebuild" scope for new plugins, Disabling a running plugin's collector, How far to wire unpublished events this phase

---

## Secret Storage Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Plaintext in DB column | Matches research's A1 assumption: self-hosted Postgres IS the trust boundary already. Simplest, no key-management problem. Never echoed back in plaintext via the API. | ✓ |
| Encrypted at rest | Symmetric-encryption layer (e.g. Fernet) with a key derived from an env var. More defense-in-depth, but introduces a key-management story for a single-user self-hosted box. | |
| You decide | Let Claude pick. | |

**User's choice:** Plaintext in DB column (Recommended)
**Notes:** Resolves research's Assumption A1 explicitly.

---

## "No Rebuild" Scope for New Plugins

| Option | Description | Selected |
|--------|-------------|----------|
| Restart OK for new plugins | Directory-scan-at-startup; new plugin directories need one restart, toggling already-discovered plugins is zero-restart. Matches research's A5 interpretation. | ✓ |
| True zero-restart for everything | Backend watches the plugins directory and hot-loads new plugin code with no restart ever. Adds real complexity (live module loading, runtime FastAPI router registration — Pitfall 1) for a v1 with no install UI yet. | |
| You decide | Let Claude pick. | |

**User's choice:** Restart OK for new plugins (Recommended)
**Notes:** Resolves research's Assumption A5 explicitly.

---

## Disabling a Running Plugin's Collector

| Option | Description | Selected |
|--------|-------------|----------|
| Finish current tick | Per-plugin asyncio.Event, mirrors traffic_broadcaster's existing stop_event + wait_for(timeout) pattern. Avoids partial/torn writes. | ✓ |
| Kill immediately | Cancel the asyncio.Task outright. Faster to reflect "disabled" state, but risks a half-finished write or dangling httpx call. | |
| You decide | Let Claude pick. | |

**User's choice:** Finish current tick (Recommended)
**Notes:** Resolves research's Open Question 1 — per-plugin Event (not one shared global Event).

---

## How Far to Wire Unpublished Events This Phase

### device_lost

| Option | Description | Selected |
|--------|-------------|----------|
| Build a minimal real detector | Periodic asyncio loop checking last_seen against a threshold, same cadence pattern as update_snapshot_loop. | ✓ |
| Define only, leave unpublished | Same treatment as mode_change — contract exists, nothing calls publish(). | |
| You decide | Let Claude pick. | |

**User's choice:** Build a minimal real detector (Recommended)
**Notes:** Resolves research's Open Question 3 — without a real detector, PLUG-03's "subscribe and react" criterion can't be proven end-to-end for this event.

### traffic_spike

| Option | Description | Selected |
|--------|-------------|----------|
| Wire it to publish now | Phase 4's existing bandwidth-anomaly check (D-09) already fires — add event_bus.publish("traffic_spike", ...) alongside its existing security_alert write. | ✓ |
| Define only, leave unpublished | Same bucket as mode_change. | |
| You decide | Let Claude pick. | |

**User's choice:** Wire it to publish now (Recommended)
**Notes:** Consistency with the device_lost decision — the detector already exists, so wiring it is a small addition.

### mode_change

Not separately voted on — confirmed via context that it stays define-only/unpublished this phase (research's Open Question 2 recommendation), since no mode-switching logic exists until Phase 6.

---

## Claude's Discretion

- Exact threshold/window for the device_lost detector.
- Exact Pydantic payload field shape for each event type beyond what's needed for the three real publishers (new_device, security_alert, traffic_spike) to round-trip.
- Plugin secret DB schema details (column types, which manifest config fields are marked `secret: true`).
- Per-plugin asyncio.Event/asyncio.Task bookkeeping shape in the loader.

## Deferred Ideas

None — discussion stayed within phase scope. Custom per-plugin UI pages, plugin install-from-URL, capability-permission display, collector status visibility, and mode-switcher UI were already explicitly deferred in `05-UI-SPEC.md`.
