# Phase 5: Plugin System + Notifications - Research

**Researched:** 2026-06-20
**Domain:** In-process plugin architecture (Python/FastAPI backend, SvelteKit SPA frontend), event subscription, background data collectors, push notifications (ntfy.sh / Pushover)
**Confidence:** MEDIUM-HIGH

## Summary

Innkeeper has no CONTEXT.md for this phase yet (no `/gsd-discuss-phase` run) and no knowledge graph — this research is driven entirely by ROADMAP.md/REQUIREMENTS.md goals plus direct codebase inspection of Phases 1-4.

The codebase already contains every primitive a v1 (in-process, MVP-mode, no sandboxing per v2's PDST-02 deferral) plugin system needs, just not yet generalized:

1. **A swappable-implementation pattern already exists** — `BandwidthSource` (`backend/src/services/bandwidth_source.py`) is a `typing.Protocol` with one concrete implementation today and an explicit comment that Phase 7's UniFi adapter will implement the same Protocol. This is the established idiom to reuse for the plugin contract's "capabilities" (notification senders, data collectors).
2. **`SecurityAlert` rows are explicitly designed to be Phase 5's event source.** Its docstring states: *"shaped so Phase 5's event bus (PLUG-03) can subscribe to/poll it directly, not throwaway work."* There is **no in-process pub/sub today** — Phase 3/4 use a poll-and-broadcast snapshot pattern (`traffic_broadcaster.py`, D-13) for SSE, and a plain DB-row-as-durable-event pattern for alerts. Phase 5 must decide whether to (a) add a true in-process event bus (asyncio pub/sub) that callers `publish()` into at the moment something happens, with `SecurityAlert`/future event rows as the durable log, or (b) have plugins poll new rows. **Recommendation: add a minimal in-process async pub/sub (a single `EventBus` class) that callers publish to synchronously at the point of occurrence, and have the DB write happen alongside it — not derived from it** — this avoids poll-latency and matches the "react accordingly… in real time" framing of PLUG-03/SEC-02 (push notification on unknown-device-join must feel immediate, not next-7s-tick).
3. **The frontend is `adapter-static` (SPA, `fallback: 200.html`).** There is no SvelteKit server runtime in production — all routing is client-side. This rules out filesystem-based dynamic `+page.svelte` route registration without a rebuild (SvelteKit's router is compiled at build time from `src/routes/`). The only way to satisfy PLUG-04 ("`/plugins/[plugin-name]` with no core rebuild") is a **single static catch-all route** `src/routes/plugins/[slug]/+page.svelte` that, at runtime, fetches the plugin's manifest/UI descriptor from the backend and renders a **generic, schema-driven plugin page** (config form + optional plugin-supplied HTML/iframe/Svelte-component-by-name lookup) — NOT a dynamically `import()`-ed `.svelte` file per plugin, since Vite cannot bundle a component that doesn't exist at build time. This is a hard architecture constraint to flag for planning.
4. **Plugin discovery should be directory-scanning + manifest file, not Python entry_points.** Entry_points require an installed distribution per plugin (setup.py/pyproject.toml + reinstall) — too heavy for "drop a plugin in a folder, toggle it on" UX and conflicts with PLAT-02's single `docker compose up` simplicity. A `backend/plugins/<plugin_id>/manifest.json` + `plugin.py` directory-scan (using `importlib` + `pkgutil`, mirroring patterns the WebSearch confirmed are standard) fits the existing monorepo layout and Docker volume-mount conventions already used by `capture/`.
5. **httpx is already a backend dependency** (no new package required for notifications) — confirmed in `backend/pyproject.toml`. ntfy.sh and Pushover are both simple `POST` form/text APIs, well within a thin internal client; no SDK package needed (`Apprise` is the only candidate worth considering and is explicitly NOT required since CLAUDE.md/PROJECT.md only ask for ntfy.sh OR Pushover, not a multi-backend abstraction).
6. **No secrets-storage infrastructure exists yet.** `AppSettings` is a single-row password table; there is no encrypted-secret column pattern anywhere in the codebase. Plugin config (ntfy topic, Pushover user/API tokens) needs a new `plugin_configs` table. Tokens are sensitive but not network-traffic-sensitive in the CLAUDE.md privacy sense — still, they should never be returned in plaintext from a GET endpoint once saved (write-only field convention), consistent with this being a self-hosted single-user tool where the DB itself is the trust boundary (no separate secrets manager needed for v1; flag as `[ASSUMED]`).

**Primary recommendation:** Build a minimal in-process plugin system: (1) a `PluginManifest` Pydantic model + directory-scan loader, (2) an `EventBus` (asyncio-based, synchronous-dispatch, in-memory, no persistence layer of its own — `SecurityAlert`-style tables remain the durable record), (3) a `plugin_configs` table for enable/disable + JSON config + secret fields, (4) dynamic `app.include_router()` per enabled plugin at startup/toggle-time, (5) a single generic `/plugins/[slug]` SvelteKit page that renders plugin UI from a backend-served descriptor rather than per-plugin compiled components, and (6) the notification plugin as the first and only first-party plugin this phase, sending via ntfy.sh or Pushover through httpx, triggered by subscribing to the `unknown_device`/`new_device` event class already proven by Phase 4's `SecurityAlert` pipeline.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Plugin manifest definition/validation | API/Backend | — | Manifests are Python-loaded Pydantic models; frontend only ever sees the serialized JSON |
| Plugin enable/disable/config storage | Database / Storage | API/Backend | Durable row per plugin (`plugin_configs`); backend is sole writer |
| Plugin settings UI (list, toggle, configure) | Browser / Client | API/Backend | SvelteKit settings page renders from `GET /api/plugins`, mutates via `POST` |
| Plugin UI page (`/plugins/[slug]`) | Browser / Client | API/Backend | Single generic SPA route; content is data-driven from a backend descriptor, not per-plugin compiled bundles |
| Event publication (`new_device`, `security_alert`, etc.) | API/Backend | — | Events originate from backend services (discovery.py, security routes) — never client-originated |
| Event subscription / dispatch to plugins | API/Backend | — | In-process `EventBus`; plugins are Python callables registered in the same process, not network services |
| Background data collectors | API/Backend | — | `asyncio.create_task` loops started in the FastAPI lifespan, same convention as `traffic_broadcaster.update_snapshot_loop` |
| Notification delivery (ntfy.sh/Pushover) | API/Backend | External Service | Backend makes outbound httpx calls; the notification plugin is backend-only, no UI page beyond config |
| Plugin secrets (API tokens) | Database / Storage | API/Backend | Stored in `plugin_configs`/`plugin_secrets`; never round-tripped in plaintext to the browser after initial save |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | already pinned (no version constraint in pyproject.toml — verify range) | Outbound HTTP to ntfy.sh/Pushover | Already a backend dependency (confirmed in `backend/pyproject.toml`); async-native, matches FastAPI's async stack |
| Pydantic | 2.13.4 (existing pin) | Plugin manifest schema + config validation | Already the project's validation layer; manifests are just another Pydantic model |
| importlib / pkgutil (stdlib) | n/a | Plugin directory discovery | No third-party plugin-loader package needed — stdlib is sufficient for directory-scan + dynamic import, and avoids adding an unaudited dependency for something this small |
| SQLAlchemy (existing) | 2.0.51 (existing pin) | `plugin_configs` table, Alembic migration | Same ORM/migration pattern as every other Phase 1-4 table |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio (stdlib) | n/a | In-process `EventBus` + background collector tasks | Same `asyncio.create_task` + `stop_event` convention already used by `traffic_broadcaster.update_snapshot_loop` and `capture/capture.py`'s threads |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Directory-scan + manifest.json plugin discovery | Python `entry_points` (`importlib.metadata`) | Entry points require each plugin to be its own installed Python distribution — heavier packaging, a rebuild/reinstall per plugin change, and conflicts with the "drop a plugin in, toggle it on" UX implied by PLUG-02. Directory-scan matches the existing monorepo/volume-mount conventions (`capture/` is volume-mounted in docker-compose.yml). |
| In-process asyncio `EventBus` | Redis pub/sub or a message broker | Total overkill for a single-process, single-host, self-hosted app — CLAUDE.md's portability/no-extra-services constraint argues strongly against adding Redis just for event fan-out. asyncio callbacks in the same process are sufficient and avoid a new Docker Compose service. |
| Generic data-driven `/plugins/[slug]` page | Per-plugin dynamic `import()` of a `.svelte` file at runtime | Vite/SvelteKit compiles all components at build time; a literal "drop a `.svelte` file in a folder, no rebuild" UI for third-party plugins is not achievable with `adapter-static` + Vite. (Module federation is explicitly listed as Out of Scope in REQUIREMENTS.md: "Svelte compile-time constraint; dedicated routes are sufficient for v1.") The generic schema-driven page is the only approach consistent with that explicit decision. |
| httpx-based thin notification client | Apprise (multi-backend notification library) | Apprise is the documented standard *if* spanning many backends (CLAUDE.md flags it as "good fit for a configurable alert channels feature"), but FPLG-04 only requires ntfy.sh OR Pushover — both are single-POST-request APIs. A 30-line internal client avoids an extra dependency for two backends this simple. Flag this as a discretion point for `/gsd-discuss-phase` if the user wants Apprise's future extensibility instead. |

**Installation:**
```bash
# No new packages required — httpx, Pydantic, SQLAlchemy, asyncio are all already
# present in backend/pyproject.toml from prior phases.
```

**Version verification:** No new external packages are introduced this phase. `httpx` is already pinned without a version constraint in `backend/pyproject.toml` (line: `"httpx",`) — confirm the installed/locked version in the venv before planning assumes a specific httpx API surface (httpx's API has been stable across 0.2x-0.28.x for the basic `AsyncClient.post()` calls this phase needs, so this is LOW risk).

## Package Legitimacy Audit

**No new external packages are required for this phase.** httpx, Pydantic, SQLAlchemy, and Python's stdlib (`importlib`, `pkgutil`, `asyncio`) are all either already vetted dependencies from Phases 1-4 or part of the standard library. The Package Legitimacy Gate is not applicable — no `npm install`/`pip install` of a new package is anticipated.

If planning decides to adopt **Apprise** instead of a hand-rolled httpx client (see Alternatives Considered), run the gate on `apprise` before that plan executes:
```bash
gsd-tools query package-legitimacy check --ecosystem pypi apprise
pip index versions apprise
```
This is flagged as a discretion point, not a locked decision — see Assumptions Log A2.

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────────────┐
                         │   Browser (SvelteKit SPA)    │
                         │                              │
                         │  /settings/plugins page  ────┼──┐
                         │  /plugins/[slug] page    ────┼──┤
                         └──────────────────────────────┘  │
                                                            │ fetch() (same-origin /api/)
                                                            ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ FastAPI Backend (single process, app.py lifespan)                         │
│                                                                             │
│  ┌─────────────┐    discovers manifests    ┌──────────────────────────┐   │
│  │ PluginLoader │ ─────────────────────────▶│ plugins/ directory scan │   │
│  │ (startup)    │   reads manifest.json      │ <plugin_id>/manifest.json│ │
│  └──────┬───────┘   imports plugin.py        │ <plugin_id>/plugin.py   │ │
│         │ for each enabled plugin             └──────────────────────────┘│
│         │                                                                  │
│         ▼                                                                  │
│  app.include_router(plugin.router)   ◀── optional API routes (PLUG-01)    │
│         │                                                                  │
│         ▼                                                                  │
│  EventBus.subscribe(event_type, plugin.handler)  ◀── PLUG-03              │
│         │                                                                  │
│         ▼                                                                  │
│  asyncio.create_task(plugin.collector_loop())    ◀── PLUG-05              │
│                                                                             │
│  ── Existing services publish into EventBus at the moment of occurrence ──│
│  discovery.py (upsert_discovered_identity) ──▶ EventBus.publish(          │
│      "new_device", {...})  + writes SecurityAlert row (durable)           │
│  security.py / bandwidth_anomaly.py ─────────▶ EventBus.publish(          │
│      "security_alert"/"traffic_spike", {...})                             │
│                                                                             │
│  EventBus dispatches synchronously, in-process, to every subscribed       │
│  plugin handler (notification plugin's handler calls ntfy.sh/Pushover)    │
│                                                                             │
│  GET  /api/plugins              → list + enabled state                    │
│  POST /api/plugins/{id}/enable  → toggle, mounts/unmounts router+sub      │
│  POST /api/plugins/{id}/config  → save config (ntfy topic, Pushover keys) │
└───────────────────────────────┬────────────────────────────────────────────┘
                                 │ httpx.AsyncClient (outbound only)
                                 ▼
                  ┌──────────────────────────────┐
                  │ ntfy.sh or Pushover REST API │
                  └──────────────────────────────┘
```

### Recommended Project Structure
```
backend/
├── src/
│   ├── plugins/
│   │   ├── __init__.py
│   │   ├── manifest.py        # PluginManifest Pydantic model + loader
│   │   ├── loader.py          # directory scan, import, enable/disable lifecycle
│   │   ├── event_bus.py       # EventBus class (publish/subscribe, in-process)
│   │   └── contract.py        # Plugin Protocol (router, event handlers, collector, manifest)
│   ├── models/
│   │   └── plugin_config.py   # plugin_configs table (id, plugin_id, enabled, config_json, secrets_json)
│   ├── routes/
│   │   └── plugins.py         # /api/plugins/* management routes
│   └── ...
plugins/                       # NEW top-level dir, volume-mounted like capture/
├── notification/
│   ├── manifest.json
│   ├── plugin.py              # registers event handlers, no UI route, no collector
│   └── senders/
│       ├── ntfy.py
│       └── pushover.py
frontend/
├── src/
│   ├── routes/
│   │   ├── settings/
│   │   │   └── plugins/
│   │   │       └── +page.svelte   # list/enable/disable/configure
│   │   └── plugins/
│   │       └── [slug]/
│   │           └── +page.svelte   # generic plugin page, renders backend-described UI
│   └── lib/
│       └── components/
│           └── PluginCard.svelte
```

### Pattern 1: Plugin Contract as a `Protocol` (mirrors `BandwidthSource`)
**What:** Define the plugin contract as a Python `Protocol` (or a small base class with default no-ops), exactly like `BandwidthSource` in `backend/src/services/bandwidth_source.py`.
**When to use:** Every plugin module exposes a module-level object implementing this contract; the loader introspects it rather than requiring inheritance.
**Example:**
```python
# Source: pattern extracted from backend/src/services/bandwidth_source.py (existing codebase)
from typing import Protocol
from fastapi import APIRouter

class Plugin(Protocol):
    manifest: "PluginManifest"
    router: APIRouter | None          # optional API routes (PLUG-01)
    event_subscriptions: dict[str, callable]  # optional event handlers (PLUG-03)

    async def start_collector(self, stop_event) -> None: ...  # optional (PLUG-05)
```

### Pattern 2: Manifest-driven directory scan (loader)
**What:** Each plugin lives in `plugins/<plugin_id>/` with a `manifest.json` (name, version, author, required_capabilities) and a `plugin.py` exposing a `PLUGIN` object matching Pattern 1.
**When to use:** At FastAPI startup (lifespan) and whenever a plugin is toggled on via the settings UI.
**Example:**
```python
# Source: pattern synthesized from WebSearch findings (pkgutil/importlib plugin
# auto-registration — https://medium.com/@bhagyarana80/how-i-built-a-plugin-driven-fastapi-backend-that-auto-registers-routes-e815a7298c29)
import importlib
import json
from pathlib import Path

PLUGINS_DIR = Path("plugins")

def discover_manifests() -> list[dict]:
    manifests = []
    for plugin_dir in PLUGINS_DIR.iterdir():
        manifest_path = plugin_dir / "manifest.json"
        if manifest_path.exists():
            manifests.append(json.loads(manifest_path.read_text()))
    return manifests

def load_plugin(plugin_id: str):
    module = importlib.import_module(f"plugins.{plugin_id}.plugin")
    return module.PLUGIN
```

### Pattern 3: In-process EventBus (new — no existing analog, but matches `traffic_broadcaster`'s async-loop idiom)
**What:** A minimal pub/sub dict-of-lists with an async `publish()` that awaits all subscribed handlers (or fires them as fire-and-forget tasks so a slow/broken plugin handler never blocks the publishing request).
**When to use:** Any place in the backend that currently writes a `SecurityAlert` row or equivalent "something happened" moment (`discovery.py`'s `upsert_discovered_identity`, future `device_lost`/`traffic_spike`/`mode_change` sites).
**Example:**
```python
# Source: synthesized — no third-party pub/sub library needed for a single-process app
import asyncio
from collections import defaultdict

class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: callable) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, payload: dict) -> None:
        # Fire-and-forget so one plugin's slow/broken handler (e.g. ntfy.sh
        # timeout) never blocks the caller (e.g. discovery.py's commit path).
        for handler in self._subscribers.get(event_type, []):
            asyncio.create_task(self._safe_call(handler, payload))

    @staticmethod
    async def _safe_call(handler, payload):
        try:
            await handler(payload)
        except Exception as exc:  # noqa: BLE001 — one plugin must never crash the bus
            print(f"[event_bus] handler {handler} failed: {exc}")
```

### Pattern 4: Generic data-driven plugin UI page (frontend)
**What:** A single SvelteKit route `src/routes/plugins/[slug]/+page.svelte` (with `export const ssr = false` already implied by adapter-static config) that fetches `GET /api/plugins/{slug}/page` and renders generically (a settings form built from the manifest's declared config fields, or — for plugins with no custom UI need beyond config — a simple key/value display).
**When to use:** Every plugin's `/plugins/[plugin-name]` page (PLUG-04). First-party plugins needing genuinely custom visuals (e.g. Phase 7's Pi-hole stats dashboard) are an explicit, documented exception requiring a real compiled route added at the next core release — flagged here as a known v1 limitation, not hidden.
**Example:**
```svelte
<!-- Source: pattern derived from existing frontend/src/routes/dashboard/+page.svelte structure -->
<script lang="ts">
  import { page } from '$app/stores';
  import { apiGet } from '$lib/api';
  let slug = $derived($page.params.slug);
  let pluginPage = $state<{ title: string; fields: unknown[] } | null>(null);
  // onMount: fetch(`/api/plugins/${slug}/page`) -> pluginPage
</script>
```

### Anti-Patterns to Avoid
- **Per-plugin dynamic `.svelte` import at runtime:** Vite bundles are fixed at build time; a third-party plugin cannot ship a `.svelte` file that gets compiled without a rebuild. Don't attempt `import(/* @vite-ignore */ pluginPath)` — this is explicitly the kind of module-federation approach REQUIREMENTS.md rules out.
- **Deriving events from polling `SecurityAlert` rows on a timer:** This reintroduces D-13's 7s-tick latency for something that should feel instant (an unknown device joins → push notification). Publish events synchronously at the point of occurrence; let the DB row remain the durable record, not the event source.
- **Storing plugin API tokens in plaintext and echoing them back on GET:** Even in a single-user self-hosted tool, returning a saved Pushover/ntfy token on every `GET /api/plugins/notification/config` call is an unnecessary leak surface (e.g. via browser dev tools/extension access). Treat secret fields as write-only after first save (return a masked placeholder like `"••••1234"` instead).
- **Coupling plugin enable/disable to a process restart:** PLUG-04 explicitly requires "no core rebuild" when toggling — design `include_router`/`EventBus.subscribe` calls to be idempotent and reversible (unsubscribe + a way to "un-mount" a router, e.g. by checking an `enabled` flag inside the route handlers rather than truly removing FastAPI routes, since FastAPI doesn't support clean route removal post-registration — see Pitfall 1).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ntfy.sh / Pushover request signing/auth | Custom OAuth-like flow | Plain `Authorization: Bearer <token>` header (ntfy) or form fields `token`/`user` (Pushover) per their docs | Both services intentionally use the simplest possible auth — there is nothing to "build," just two `httpx.post()` calls with the documented headers/fields |
| Plugin sandboxing/process isolation | Custom subprocess/IPC plugin runner | Nothing this phase — v1 plugins run in-process (PDST-02 process isolation is explicitly v2 scope) | REQUIREMENTS.md defers sandbox mode to v2; building it now is scope creep relative to the locked roadmap |
| Multi-backend notification routing (ntfy + Pushover + email + …) | A custom dispatch abstraction | If genuinely needed beyond ntfy/Pushover later, Apprise (already identified in CLAUDE.md) — not a hand-rolled equivalent | FPLG-04 only needs two backends; don't build a generalized notification framework speculatively |
| Settings/secrets encryption-at-rest | A custom crypto layer for `plugin_configs.secrets_json` | Nothing extra this phase (DB itself is the trust boundary, per self-hosted single-user threat model) — but DO mask on read | Building bespoke encryption for a single-user local Postgres instance is disproportionate; the real control is "never echo back," not "encrypt in a DB you already trust" |

**Key insight:** Every "hard" piece of this phase (event dispatch, plugin discovery, notification delivery) has a direct, already-vetted analog somewhere in Phases 1-4 of this exact codebase (`BandwidthSource` Protocol, `traffic_broadcaster`'s async loop, `SecurityAlert`'s durable-row pattern, `httpx` already present). The actual novelty is almost entirely in *wiring*, not new technology — resist the urge to reach for an external plugin framework, message broker, or notification SDK.

## Common Pitfalls

### Pitfall 1: FastAPI cannot cleanly un-register a router at runtime
**What goes wrong:** `app.include_router()` adds routes to `app.router.routes` permanently; there is no first-class `app.remove_router()`. A naive "disable plugin" implementation that calls `include_router` on enable but has no symmetric removal leaves disabled plugins' routes still reachable.
**Why it happens:** FastAPI/Starlette's routing table is an append-only list by design; route removal is an unsupported, fragile operation (manually filtering `app.router.routes`, which can break OpenAPI schema caching).
**How to avoid:** Either (a) register all discovered plugin routers once at startup regardless of enabled state, but have every plugin route handler check `is_plugin_enabled(plugin_id)` and return 404/403 if disabled (mirrors how `require_auth` is already a dependency check), or (b) restart-on-toggle is acceptable for v1 if the plan explicitly documents this UX tradeoff. **Recommendation: (a)** — it satisfies "no core rebuild" more honestly than restarting the process, and is a small addition to each plugin route as a `Depends(require_plugin_enabled("notification"))` dependency, following the exact `Depends(require_auth)` convention already in `routes/auth.py`.
**Warning signs:** A disabled plugin's API routes still return 200 instead of 404/403; integration tests for PLUG-02 must explicitly assert disabled-plugin routes are blocked.

### Pitfall 2: Event payload schema drift between publisher and plugin subscriber
**What goes wrong:** `discovery.py` publishes `new_device` with one set of fields, the notification plugin's handler expects another (e.g. expects `mac` but publisher sends `identity_key`) — this is exactly the class of bug STATE.md's Phase 3 P04 decision log flagged ("SSE/API payload field names must be verified against the actual backend response shape during live testing, not assumed from plan prose").
**Why it happens:** Event payloads are untyped dicts; nothing enforces a contract between publisher and subscriber at compile time.
**How to avoid:** Define a Pydantic model per event type (`NewDeviceEvent`, `SecurityAlertEvent`, etc.) in `event_bus.py` or a shared `events.py`, and have `publish()` accept the typed model (serialized to dict only at the handler boundary). This gives static/runtime validation instead of tribal-knowledge field names.
**Warning signs:** A plugin handler silently does nothing because `payload.get("mac")` returns `None` (the field was actually named `device_mac`).

### Pitfall 3: Background collector tasks dying silently
**What goes wrong:** A plugin's `start_collector()` loop raises an unhandled exception and `asyncio.create_task` swallows it until something calls `.result()` — the task just vanishes, and the plugin appears "enabled" in the UI but produces no data, with no visible error.
**Why it happens:** This is the exact failure mode `traffic_broadcaster.update_snapshot_loop` already defends against (`except Exception as exc: print(...)` + keep looping) — but that defense must be replicated for every plugin collector, since a third-party-style plugin's code can't be trusted to handle its own exceptions.
**How to avoid:** Wrap every plugin collector invocation in the loader (not in plugin code) with a try/except that logs and continues, matching the existing `update_snapshot_loop` idiom exactly. Never let plugin code structure decide whether the host loop survives.
**Warning signs:** A plugin's "last collected at" timestamp (if surfaced in the settings UI) stops advancing with no error shown anywhere.

### Pitfall 4: Notification delivery failures blocking the triggering request
**What goes wrong:** If `EventBus.publish()` awaits handlers synchronously and a plugin's `httpx.post()` to ntfy.sh times out (network blip, ntfy.sh down), the original request (e.g. discovery.py's `upsert_discovered_identity`, which is on the hot path of every ARP/DHCP/mDNS ingest from the capture container) hangs or fails.
**Why it happens:** Naive pub/sub implementations await all subscriber callbacks in the publishing coroutine.
**How to avoid:** Pattern 3's `asyncio.create_task` fire-and-forget dispatch is required, not optional — never `await handler(payload)` directly inside `publish()`. Additionally, the notification plugin's own httpx client must set an explicit timeout (`httpx.AsyncClient(timeout=10.0)`) so a hung ntfy.sh/Pushover call doesn't accumulate unbounded background tasks.
**Warning signs:** Capture ingest endpoints (`/api/capture/arp`, `/api/capture/dhcp`) become slow or start timing out after the notification plugin is enabled.

### Pitfall 5: ntfy.sh rate limiting on the public server
**What goes wrong:** The public `ntfy.sh` server rate-limits to a 60-message burst bucket refilling at 1 message/5s per visitor (IP-based) `[CITED: docs.ntfy.sh/publish]`. A burst of unknown-device alerts (e.g. first boot on a busy network discovering 15 devices at once) could hit 429s.
**Why it happens:** Shared free public infrastructure; self-hosted ntfy instances don't have this limit but the docs/default UX point users at ntfy.sh first.
**How to avoid:** Treat notification delivery failures (429 or any non-2xx) as non-fatal — log and drop, never retry-loop synchronously (would compound the rate-limit problem and block the EventBus task longer). Optionally debounce/batch rapid-fire `new_device` events into a single combined notification, but that is a UX decision for `/gsd-discuss-phase`, not a hard requirement.
**Warning signs:** Notification plugin's send function returns 429; user reports "got the first alert but not the rest" during initial network scan.

## Code Examples

### ntfy.sh send (httpx)
```python
# Source: https://docs.ntfy.sh/publish/ (CITED — WebFetch of official docs)
import httpx

async def send_ntfy(topic: str, message: str, title: str | None = None, token: str | None = None) -> bool:
    headers = {}
    if title:
        headers["X-Title"] = title
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"https://ntfy.sh/{topic}", content=message.encode("utf-8"), headers=headers)
        return resp.status_code == 200
```

### Pushover send (httpx)
```python
# Source: https://pushover.net/api (CITED — documented form fields; WebSearch-confirmed)
import httpx

async def send_pushover(api_token: str, user_key: str, message: str, title: str | None = None) -> bool:
    data = {"token": api_token, "user": user_key, "message": message}
    if title:
        data["title"] = title
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post("https://api.pushover.net/1/messages.json", data=data)
        return resp.status_code == 200 and resp.json().get("status") == 1
```

### Subscribing existing discovery.py code to the new EventBus (illustrative wiring point)
```python
# Source: extends backend/src/services/discovery.py's existing upsert_discovered_identity
# (read in full this session) — illustrates where EventBus.publish() is inserted
# alongside the existing SecurityAlert write, not instead of it.
if is_new_identity:
    db.add(SecurityAlert(device_id=None, type=SecurityAlertType.UNKNOWN_DEVICE, ...))
    await db.commit()
    await event_bus.publish("new_device", {"identity_key": identity_key, "mac": mac, "hostname": hostname})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Polling DB rows for "new" events (Phase 4's SecurityAlert pattern) | In-process synchronous-publish event bus alongside durable row writes | This phase (proposed) | Notification latency drops from "next poll tick" to "immediate" |
| Per-plugin compiled frontend routes (the "naive" idea) | Single generic data-driven `/plugins/[slug]` route | Constrained by REQUIREMENTS.md's explicit module-federation exclusion (pre-existing project decision, not new) | Plugin UI is necessarily simpler/more uniform in v1 than a true micro-frontend system would allow |

**Deprecated/outdated:** Nothing in this domain is deprecated — this is greenfield plugin-system design within an existing, recently-built (2026) codebase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Plugin secrets need no encryption-at-rest beyond "never echo back in plaintext," because the self-hosted Postgres DB is itself the trust boundary | Don't Hand-Roll, Architecture Patterns | If the user expects encrypted secrets (e.g. for a future multi-tenant or cloud-adjacent use case), this under-delivers; low risk for v1 single-user self-hosted scope, but should be confirmed in `/gsd-discuss-phase` since it touches "Data privacy" in CLAUDE.md constraints |
| A2 | httpx-based thin client (not Apprise) is the right choice for ntfy.sh/Pushover | Standard Stack, Alternatives Considered | If the user wants a notification system extensible to email/Telegram/etc. sooner than v2's roadmap implies, Apprise might be preferred now instead of later; low risk since FPLG-04 only requires ntfy/Pushover |
| A3 | An in-process asyncio EventBus (not Redis/a message broker) is sufficient for PLUG-03 | Architecture Patterns, Don't Hand-Roll | If a future plugin needs cross-process or cross-container event delivery (e.g. a plugin running as its own container per v2's PDST-02 sandboxing), this would need rework; correct for the explicit v1 in-process scope |
| A4 | The generic data-driven `/plugins/[slug]` page is an acceptable interpretation of PLUG-04, given adapter-static's build-time routing constraint | Architecture Patterns | If the user actually expects rich, fully-custom per-plugin UIs (e.g. Pi-hole's stats dashboard in Phase 7), the generic-page approach may need a documented escape hatch (a real compiled route shipped in a later release) — this is flagged explicitly as a known v1 limitation, not silently assumed away |
| A5 | "No core rebuild" for PLUG-04 means no container image rebuild + restart, not "routes appear without any backend code change ever" — i.e., first-party plugins still ship as code in this repo; only *third-party* plugin distribution (URL install, v2's PDST-01) would need true no-code-change loading | Summary, Architecture Patterns | If the user's intent is closer to true hot-loading of arbitrary plugin code without any container restart at all, the directory-scan-at-startup model (which still requires a container restart to pick up a *newly added* plugin directory, though not to toggle an *already-discovered* plugin) may not fully satisfy that bar — recommend clarifying in `/gsd-discuss-phase` whether "toggle" vs "install new plugin" both need zero-restart |

## Open Questions

1. **Should disabling a plugin stop its already-running background collector task immediately, or let it finish its current cycle?**
   - What we know: `traffic_broadcaster.update_snapshot_loop` uses a `stop_event` + `asyncio.wait_for(..., timeout=...)` pattern that cleanly exits on the next tick.
   - What's unclear: Whether plugin collectors should share one global stop mechanism or get individual per-plugin `asyncio.Event`s the loader manages.
   - Recommendation: Per-plugin `asyncio.Event`, mirroring the existing single-broadcaster pattern but multiplied per plugin — the loader keeps a `dict[plugin_id, asyncio.Event]` and a `dict[plugin_id, asyncio.Task]`.

2. **How does "mode_change" (MODE-01..04, a Phase 6 concept) get published if Phase 5 ships before Phase 6's mode-switching logic exists?**
   - What we know: PLUG-03 requires plugins be able to subscribe to `mode_change`, but the dual-mode feature itself is Phase 6.
   - What's unclear: Whether Phase 5 should define the event type/contract now (so Phase 6 just calls `event_bus.publish("mode_change", ...)` into an already-built bus) without any actual mode-switching code existing yet.
   - Recommendation: Yes — define the `EventBus` and the full set of event-type contracts (Pydantic models for all five: `new_device`, `device_lost`, `security_alert`, `traffic_spike`, `mode_change`) in Phase 5 even though only `new_device`/`security_alert` have real publishers today. This avoids Phase 6 needing to retrofit the bus's typed contract.

3. **Does `device_lost` have an existing detector anywhere, or is it net-new logic for this phase?**
   - What we know: Grep of Phases 1-4 source shows no existing "device went offline/lost" detection — `last_seen` timestamps exist on `Device` but nothing actively fires an event when a device stops being seen.
   - What's unclear: Whether PLUG-03's `device_lost` subscription capability requires Phase 5 to also build the *detector* (e.g. a periodic check: "no observation in N minutes → fire device_lost"), or whether the event type is defined now but left unpublished until a later phase supplies a real trigger.
   - Recommendation: Phase 5 should build a minimal `device_lost` detector (e.g. a periodic asyncio loop checking `last_seen` against a threshold, similar cadence to `update_snapshot_loop`) since PLUG-03's success criterion implies the event must actually be reachable to prove "subscribe and react" end-to-end — an event type that can never fire doesn't prove the contract. Flag this for `/gsd-discuss-phase` as it adds scope beyond the literal PLUG-03 wording.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| httpx (Python) | Notification plugin outbound calls | Yes (existing dependency) | unpinned in pyproject.toml | — |
| ntfy.sh (external service) | Notification plugin (if user chooses ntfy) | Network-dependent, not installable | n/a (public SaaS or self-hosted) | User can self-host ntfy or use Pushover instead — already an either/or per FPLG-04 |
| Pushover (external service) | Notification plugin (if user chooses Pushover) | Network-dependent, not installable | n/a (paid SaaS, one-time app fee) | User can use ntfy.sh instead |
| No new system packages | — | n/a | n/a | n/a |

**Missing dependencies with no fallback:** None — both notification backends are user-choice alternatives to each other per FPLG-04's "ntfy.sh or Pushover" wording.

**Missing dependencies with fallback:** ntfy.sh/Pushover are both optional/alternative — if neither is reachable at runtime (e.g. no internet on a fully air-gapped LAN), the notification plugin should fail closed (log + no-op) rather than crash the event bus, consistent with Pitfall 4's fire-and-forget dispatch design.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x + pytest-asyncio (asyncio_mode = "auto"), aiosqlite in-memory DB fixture |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/test_<module>.py -x` (run from `backend/`, using the project's Python 3.13 venv per STATE.md's prior-phase convention) |
| Full suite command | `pytest` (backend/, 108+ tests as of Phase 4 completion) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLUG-01 | Plugin manifest loads and validates against the documented schema | unit | `pytest tests/test_plugin_manifest.py -x` | ❌ Wave 0 |
| PLUG-02 | `GET /api/plugins`, `POST /api/plugins/{id}/enable`, `POST /api/plugins/{id}/config` round-trip correctly; disabled plugin's routes 404/403 | integration | `pytest tests/test_plugins_routes.py -x` | ❌ Wave 0 |
| PLUG-03 | Publishing `new_device` invokes a subscribed plugin handler; an unsubscribed event type is a no-op | unit | `pytest tests/test_event_bus.py -x` | ❌ Wave 0 |
| PLUG-04 | Enabling a plugin with a UI page causes `GET /api/plugins/{slug}/page` to return a descriptor (frontend route existence is svelte-check + manual-verify, since adapter-static SPA routing is not pytest-testable) | integration + manual | `pytest tests/test_plugins_routes.py -x` (backend) / manual browser check (frontend) | ❌ Wave 0 |
| PLUG-05 | A registered collector loop writes data and publishes an event on its tick | integration | `pytest tests/test_plugin_collector.py -x` | ❌ Wave 0 |
| FPLG-04 | Notification plugin sends via ntfy.sh/Pushover given valid config; gracefully no-ops on send failure (mocked httpx) | unit (httpx mocked, e.g. via `respx` or monkeypatching `httpx.AsyncClient.post`) | `pytest tests/test_notification_plugin.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** targeted `pytest tests/test_<new_file>.py -x`
- **Per wave merge:** full `pytest` (backend/)
- **Phase gate:** Full suite green before `/gsd-verify-work`; frontend has no automated test runner in this project (consistent with Phases 1-4 — svelte-check + manual verification is the established frontend validation path)

### Wave 0 Gaps
- [ ] `tests/test_plugin_manifest.py` — covers PLUG-01
- [ ] `tests/test_plugins_routes.py` — covers PLUG-02, PLUG-04 (backend half)
- [ ] `tests/test_event_bus.py` — covers PLUG-03
- [ ] `tests/test_plugin_collector.py` — covers PLUG-05
- [ ] `tests/test_notification_plugin.py` — covers FPLG-04 (requires mocking httpx — no `respx` dependency exists yet; either add it as a dev dependency or hand-roll a monkeypatch fixture matching the project's existing "no extra test deps beyond pytest/pytest-asyncio/aiosqlite" minimalism)
- [ ] No framework install needed beyond the above test files — pytest/pytest-asyncio/aiosqlite are already present

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (new surface) | Plugin management routes reuse the existing `Depends(require_auth)` session-cookie dependency — no new auth mechanism |
| V3 Session Management | No (new surface) | Same session middleware as all existing routes; nothing plugin-specific |
| V4 Access Control | Yes | Every `/api/plugins/*` route and every route a plugin itself registers must be gated by `Depends(require_auth)` (existing pattern) plus, for plugin-specific routes, a `Depends(require_plugin_enabled(plugin_id))` check (Pitfall 1) so a disabled plugin's endpoints are unreachable even though FastAPI can't truly un-register them |
| V5 Input Validation | Yes | Plugin manifests and plugin config payloads validated via Pydantic models (existing project convention — every route already uses Pydantic request models) |
| V6 Cryptography | Partial | No new cryptography is introduced; existing `hashlib.scrypt` password hashing is untouched. Plugin secret tokens (ntfy/Pushover) are stored as plaintext in Postgres per Assumption A1 — flagged, not hidden, as a scope decision rather than a crypto implementation |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Disabled plugin's API route still reachable (Pitfall 1) | Elevation of Privilege | `Depends(require_plugin_enabled(...))` dependency on every plugin-registered route, checked against the `plugin_configs.enabled` column on every request |
| Plugin secret token leaked back to browser on GET | Information Disclosure | Mask secret fields in API responses after first save (`"••••" + last4`); never include the raw stored value in any `GET /api/plugins/{id}/config` response body |
| SSRF via a malicious/compromised plugin's outbound notification URL (if config ever allows a custom ntfy server URL, not just topic) | Tampering / Information Disclosure | If "self-hosted ntfy server URL" becomes a configurable field (likely, since ntfy supports self-hosting), validate/sanitize the URL server-side and consider restricting to `https://` scheme only — flag this for the planner since it's a direct consequence of supporting self-hosted ntfy, which CLAUDE.md's self-hosted ethos likely wants supported |
| Unhandled exception in a plugin's event handler crashing the request that published the event | Denial of Service | Pattern 3's fire-and-forget `asyncio.create_task` + try/except wrapper around every handler invocation — never let plugin code run synchronously inside a core request path |
| A malicious/buggy plugin's manifest with `required_capabilities` requesting more than it needs (no capability enforcement layer this phase) | Elevation of Privilege | Out of scope for v1 per REQUIREMENTS.md's deferral of plugin sandboxing (PDST-02) to v2 — manifests are declarative/documentation only this phase, not an enforced permission system. Flag as a known v1 limitation, consistent with the project's "first-party plugins prove the contract" framing (all v1 plugins are trusted, first-party code in this repo) |

## Sources

### Primary (HIGH confidence)
- `backend/src/services/bandwidth_source.py` (read in full) — existing Protocol-based swappable-source pattern
- `backend/src/services/traffic_broadcaster.py` (read in full) — existing async background-loop + stop_event pattern
- `backend/src/services/discovery.py` (read in full, lines 1-115) — existing SecurityAlert-as-event-source pattern, dialect-aware upsert idiom
- `backend/src/models/security_alert.py` (read in full) — explicit docstring confirming this table is designed for Phase 5's event bus
- `backend/src/routes/auth.py`, `backend/src/auth.py` (read in full) — `Depends(require_auth)` dependency convention to mirror for `require_plugin_enabled`
- `backend/src/main.py` (read in full) — `app.include_router()` registration pattern, FastAPI lifespan convention
- `backend/pyproject.toml` (read in full) — confirms httpx already a dependency, no new package needed
- `frontend/svelte.config.js` (read in full) — confirms `adapter-static` with `fallback: 200.html` (SPA mode), the binding constraint on PLUG-04's UI architecture
- `frontend/src/lib/api.ts`, `frontend/src/routes/dashboard/+page.svelte` (read in full/partial) — existing fetch-based API client and dashboard composition conventions
- `backend/tests/conftest.py`, `backend/tests/test_security_alerts.py` (read in full/partial) — existing pytest fixture and test conventions to extend

### Secondary (MEDIUM confidence)
- [Sending messages - ntfy](https://docs.ntfy.sh/publish/) — WebFetch of official docs: POST format, headers, auth methods (Bearer token, Basic auth, query param), topic semantics `[CITED]`
- [Pushover: API](https://pushover.net/api) — official API reference for token/user/message POST format `[CITED]`

### Tertiary (LOW confidence)
- [How I Built a Plugin-Driven FastAPI Backend That Auto-Registers Routes](https://medium.com/@bhagyarana80/how-i-built-a-plugin-driven-fastapi-backend-that-auto-registers-routes-e815a7298c29) — WebSearch summary only, not independently fetched in full; pattern cross-checked against the project's own existing conventions before being adopted `[ASSUMED → corroborated by codebase pattern]`
- [The missing guide to understanding adapter-static in SvelteKit](https://khromov.se/the-missing-guide-to-understanding-adapter-static-in-sveltekit/) and [sveltejs/kit discussion #11977](https://github.com/sveltejs/kit/discussions/11977) — WebSearch summaries on adapter-static dynamic-route behavior, cross-checked against the project's actual `svelte.config.js` (which confirms the fallback/SPA setup independently) `[CITED via cross-check]`
- ntfy.sh rate-limit specifics (60-burst/5s-refill) — WebSearch summary, not independently re-verified against a live ntfy.sh rate-limit test; treat exact numbers as approximate `[ASSUMED]`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all tooling is already vetted and present in this exact codebase
- Architecture: MEDIUM-HIGH — event bus and plugin loader designs are synthesized from strong existing in-repo analogs (BandwidthSource, traffic_broadcaster) plus a hard, verified constraint (adapter-static SPA routing) rather than pure speculation; the generic-plugin-page approach is a reasoned conclusion from a real build-time limitation, not guesswork
- Pitfalls: MEDIUM — FastAPI router-removal limitation and ntfy rate limits are externally documented; the EventBus design pitfalls (fire-and-forget, payload schema drift) are inferred from this project's own documented Phase 3/4 postmortems (STATE.md decision log), which is a strong same-codebase signal

**Research date:** 2026-06-20
**Valid until:** 30 days (stable domain — FastAPI/SvelteKit/httpx APIs used here are mature and slow-moving; re-verify ntfy.sh/Pushover rate limits if this research is reused after that window)
