# Phase 5: Module Platform Foundation - Research

**Researched:** 2026-06-21
**Domain:** Python capability-based plugin architecture (typing.Protocol), multi-schema Postgres/TimescaleDB migrations, FastAPI dynamic router mounting, Devices/Traffic/Security retrofit
**Confidence:** MEDIUM-HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Module Categories**
- D-01: Every module is one of three kinds: **feature** (UI, may have own schema for data it's source of truth for — Traffic, Security, Notifications, Devices), **support** (no UI, internal only, owns canonical domain data — DeviceIdentity), or **linked** (UI is just a card/link to an external app, no code, manifest only — Jellyfin, v2+). Schema reflects what's owned per table, not whether a module has a DB at all.

**Capability Protocols (composition, not a fat base class)**
- D-02: Capabilities are small, independent `typing.Protocol`s, not a single `Module` base class and not pure file-convention discovery. A module is any Python object that structurally satisfies zero or more Protocols — no inheritance required. Defined Protocols: `HasAPIRoutes` (`get_router() -> APIRouter`), `HasUIPage` (`get_ui_route() -> str`), `HasEventSubscriptions` (`get_subscriptions() -> dict[str, Callable]`), `HasCollector` (`async run_collector(stop_event: asyncio.Event) -> None`).
- D-03: The loader uses `@runtime_checkable` + `isinstance()` to detect which capabilities a module instance actually has, and only wires up those. No module is forced to stub out unused capabilities.
- D-04: If a capability Protocol's shape must change incompatibly later, define a new version (e.g. `HasAPIRoutesV2`) rather than mutating the original; loader checks the newer version first and falls back.

**Support Interfaces (cross-module data sharing)**
- D-05: A support module exposes its functionality as its own named Protocol, independent of module identity (e.g. `DeviceLookupInterface` is a contract, not "the DeviceIdentity module's interface").
- D-06: Modules declare `provides: list[type]` and `requires: list[type]` (Protocol types) in their `ModuleManifest` (fields: `id`, `display_name`, `version`, `kind: Literal["feature","support"]`, `provides`, `requires`, `db_schema`).
- D-07: A central `ModuleRegistry` (host infrastructure, not a module) maps `Protocol type -> provider instance`. Consumers never name the module they call — they ask the registry for whoever implements a Protocol.
- D-08: Wiring is **constructor injection resolved at startup**, not lazy lookup. The loader resolves all of a module's `requires` before instantiating it and passes resolved interfaces into its factory function: `def create(deps: dict[type, object]) -> ModuleInstance: ...`. Missing/conflicting dependency fails loudly at startup.

**Loader Startup Sequence**
- D-09: (1) scan `backend/src/modules/*/manifest.py`, collect `ModuleManifest`s; (2) build dependency graph from `requires`/`provides`, topologically sort; (3) fail fast on unsatisfied `requires` or `provides` conflict; (4) instantiate in dependency order — support before feature; (5) register `provides` in `ModuleRegistry`, wire capabilities (mount `HasAPIRoutes` router under `/api/modules/<id>/`, register `HasUIPage` frontend route, subscribe `HasEventSubscriptions` to `EventBus`, spawn `HasCollector` loop with its own `asyncio.Event`/`asyncio.Task`).
- D-10: The `EventBus`'s existing fire-and-forget pub/sub design is **carried over unchanged** from the superseded Phase 5 research (`_superseded-bolt-on-plugin-model/05-RESEARCH.md`); only the module-loading/contract layer around it is new.

**DB Schema Ownership**
- D-11: Each module with `db_schema` set owns a real Postgres schema: `device_identity.*`, `traffic.*`, `security.*`, `notifications.*`, `devices.*`.
- D-12: Each module's package has its own `migrations/` directory; root Alembic config uses branch labels per module.
- D-13: A module may only query its own schema directly. Anything else goes through a `requires`-resolved interface — convention/code review enforced, not Postgres grants.
- D-14: TimescaleDB hypertables work in any schema, but `create_hypertable()` calls must be schema-qualified once `traffic_flows` moves out of `public` into `traffic.*`.

**Devices / DeviceIdentity Split**
- D-15: **DeviceIdentity** (support module, new schema) is sole source of truth for canonical device data — discovery fusion, identity resolution, merge logic, vendor/type inference (today's `discovery.py` + `identity_inference.py` + `Device` model). Exposes `DeviceLookupInterface` for reads, plus actual CRUD/merge for writes.
- D-16: **Devices** (feature module, thin) is the dashboard card grid + register/merge dialogs. Calls DeviceIdentity for every read/write. May own schema only for UI-owned concerns (sort order, search history, display prefs) — never canonical device fields.
- D-17: Any other module needing "what is this device" calls `DeviceLookupInterface` directly rather than tracking its own copy.

**Frontend: Shared Design System**
- D-18: One canonical token source: `frontend/src/app.css` holds CSS variables already established in Phases 1-4. Tailwind config references these vars.
- D-19: One shared component library: `frontend/src/lib/components/ui/` (shadcn-svelte primitives started Phase 4). Native module UI pages import from here.
- D-20: Convention, not runtime enforcement — default and path of least resistance; a module that needs different look writes scoped styles. Enforced at UI-spec/review time, not by code. Linked modules exempt.
- D-21: No module federation — SvelteKit compiles to one bundle (carried over). No runtime boundary on frontend; Svelte already scopes component CSS.
- D-22: Design-system consolidation lands **before** Devices/Traffic/Security UI retrofit touches markup.

**Linked Modules**
- D-23: A linked module is a manifest entry only (`id`, `name`, `icon_url`, `target_url`) producing a dashboard card opening the third-party app's own UI — no code. Exempt from every isolation/contract rule. v1 builds data model + dashboard section only.

**Terminology**
- D-24: "Module" replaces "plugin" throughout: `plugin_configs` → `module_configs`, `/api/plugins` → `/api/modules`, `backend/src/plugins/` → `backend/src/modules/`, `/settings/plugins` → `/settings/modules`, `/plugins/[slug]` → `/modules/[slug]`.

### Claude's Discretion
- Exact shape of per-module Alembic branch label naming convention — implementation detail consistent with D-12.
- Exact internal structure of `ModuleLoader`'s dependency-graph/topological-sort implementation — implementation detail consistent with D-09.
- Whether `ModuleRegistry` is a singleton, app-state object, or DI container — implementation detail consistent with D-07/D-08.
- Exact UI-owned schema fields for Devices (D-16) — sort order, search history, display prefs column shapes are implementation detail.

### Deferred Ideas (OUT OF SCOPE)
- Notifications module implementation — explicitly out of scope this phase, deferred to Phase 5.2.
- A real linked/third-party module (e.g. Jellyfin) — deferred to v2.
- Postgres-level grant enforcement of schema isolation — convention/code-review only for now; revisit if multi-tenant or multi-DB-user scale is ever needed.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MOD-01 | Module contract defined/documented — capability Protocols, typed ModuleManifest, ModuleLoader with constructor injection | Architecture Patterns (Capability Protocols, ModuleLoader), Code Examples |
| MOD-02 | User can view/enable/disable/configure modules via dashboard settings page | Architecture Patterns (module_configs table + settings route pattern, carried over from superseded research's Pitfall 1 enable/disable-without-restart approach) |
| MOD-03 | Modules subscribe to platform events (`new_device`, `device_lost`, `security_alert`, `traffic_spike`, `mode_change`) via EventBus | Architecture Patterns (EventBus, carried over per D-10), Code Examples |
| MOD-04 | Enabled module with UI page appears as nav entry at `/modules/[module-name]`; no rebuild on toggle | Common Pitfalls (FastAPI router un-registration), Architecture Patterns |
| MOD-05 | Modules register data collectors — background tasks feeding storage/event stream | Architecture Patterns (HasCollector + asyncio.Event loop pattern from traffic_broadcaster.py) |
| MOD-06 | ModuleRegistry resolves support interfaces by Protocol type, not module identity; loader fails fast on unsatisfied requires/provides conflict | Architecture Patterns (ModuleRegistry, ModuleLoader topological sort), Code Examples |
| MOD-07 | Devices/Traffic/Security retrofitted onto module contract; DeviceIdentity becomes support module, sole source of truth, exposes DeviceLookupInterface | Runtime State Inventory, Migration Strategy section, Code Being Retrofitted notes |
| MOD-08 | Linked-module manifest format + "Linked Apps" dashboard section (data model + UI only) | Architecture Patterns (LinkedModuleManifest), Code Examples |
</phase_requirements>

## Summary

This phase has two genuinely separable bodies of work that share almost no implementation risk: (1) **host infrastructure** — capability Protocols, `ModuleManifest`, `ModuleLoader`, `ModuleRegistry`, per-module Alembic branch wiring, and the carried-over `EventBus` — which is new code with no existing behavior to preserve, and (2) **retrofitting working Phase 1-4 code** (Devices, Traffic, Security) into that host, which is a behavior-preserving rewrite with real regression risk. The host-infra half is well-supported by `typing.Protocol` + `@runtime_checkable`, which is the correct, idiomatic Python tool for this job and needs no third-party DI framework — confirmed by official typing docs and PEP 544. The retrofit half is harder than it looks: production runs PostgreSQL with real schemas, but the test suite runs on **in-memory SQLite**, which has no schema/namespace concept in the way Postgres does — this is the single biggest land-mine for this phase and must be resolved explicitly in the plan, not discovered mid-execution.

DeviceIdentity is the highest-risk single piece: `discovery.py`'s `record_observation()`/`upsert_discovered_identity()` is on the hot path of every ARP/DHCP/mDNS ingest from the capture container, and it currently writes directly into the same `Device` table that `routes/devices.py`, `routes/security.py`, and `routes/traffic.py` all also query via direct joins on `Device.last_known_mac`. Moving canonical device data into a new `device_identity` schema while keeping Devices/Traffic/Security working requires either a phased dual-write/dual-read period or a single atomic cutover commit per consumer — the plan should pick one explicitly, not improvise it during execution. TimescaleDB's `create_hypertable()` needs no special syntax for a non-public schema beyond passing the schema-qualified table name as a string (`'traffic.traffic_flows'`) — this was a documented but resolvable upstream tooling gotcha (pgAdmin-specific), not a real blocker.

**Primary recommendation:** Build host infrastructure (Protocols, ModuleManifest, ModuleLoader, ModuleRegistry, EventBus carryover) as net-new code in `backend/src/host/` first and prove it end-to-end with a trivial module before touching any retrofit; then retrofit DeviceIdentity (resolve the SQLite/Postgres schema question explicitly before writing migration 0006), then Devices, then Traffic, then Security, each as its own commit with before/after behavior-parity verification per the Risk Summary's explicit ask. This phase's scope is large enough that the planner should seriously consider splitting host-infra-only into one wave and each retrofit (DeviceIdentity+Devices, Traffic, Security) into separate subsequent waves — flagged explicitly below, not decided here.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Module contract (Protocols, Manifest, Loader, Registry) | API/Backend | — | Pure in-process Python composition; no client or DB involvement at the contract level |
| EventBus pub/sub | API/Backend | — | In-process asyncio, same process as the FastAPI app; not a separate service |
| Module enable/disable + settings UI | Frontend Server (SSR) / Browser | API/Backend | Settings page is Svelte UI reading/writing `module_configs` via API; toggle logic itself lives in backend (router-mount-with-enabled-check pattern) |
| DeviceIdentity canonical data (discovery fusion, merge, inference) | API/Backend | Database/Storage | Pure backend service logic + its own Postgres schema; no UI of its own (support module) |
| DeviceLookupInterface (cross-module device queries) | API/Backend | — | A Python Protocol resolved in-process by ModuleRegistry; not a network call |
| Devices dashboard card grid / register / merge UI | Browser | API/Backend | Renders via Svelte; all device reads/writes proxy through DeviceIdentity via the backend |
| Traffic/Security retrofit onto own schemas | Database/Storage | API/Backend | Schema-per-module is a DB-tier concern; the route/service layer is the consumer |
| Linked Apps dashboard section | Browser | API/Backend | Static manifest data rendered as cards; backend serves the manifest list, no runtime logic beyond that |
| Shared design tokens / component library | Browser | — | CSS variables + Svelte components compiled into the single SPA bundle; no server involvement |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typing.Protocol / @runtime_checkable | stdlib (Python 3.13) | Capability-based structural typing for module contracts | The standard, zero-dependency mechanism for "duck typing with a contract" in modern Python; this is exactly PEP 544's design target and requires no third-party DI/plugin framework [VERIFIED: docs.python.org] |
| pydantic | 2.13.4 (already pinned in backend/pyproject.toml) | `ModuleManifest`, event payload models, `LinkedModuleManifest` | Already the project's validation standard; manifest fields map directly onto a `BaseModel` as shown in the design doc |
| alembic | 1.16.5 (already pinned) | Per-module migration branches via `branch_labels` + `version_locations` | Already the project's migration tool; branch labels are a first-class, documented Alembic feature for exactly this multi-app-module scenario [CITED: alembic.sqlalchemy.org/en/latest/branches.html] |
| asyncio (stdlib) | 3.13 | EventBus fire-and-forget dispatch, HasCollector background loops | Already the project's concurrency primitive (`traffic_broadcaster.update_snapshot_loop`, capture threads); D-10 carries the EventBus design over unchanged |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| networkx (optional) | latest | Topological sort for ModuleLoader's dependency graph | Only if the manual topo-sort (Kahn's algorithm, ~20 lines) feels worth outsourcing; CONTEXT.md's Claude's Discretion note explicitly leaves the topo-sort implementation open, and the "convention not framework" tone in the design doc favors hand-rolling this trivial graph algorithm over adding a dependency for it — **recommend NOT adding networkx**, write Kahn's algorithm directly (see Code Examples) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| typing.Protocol composition | A single `Module` ABC with optional-override methods | Explicitly rejected in the design doc (D-02) — violates interface segregation, bloats as capabilities grow, risky to evolve once many modules subclass it |
| In-process asyncio EventBus | Redis pub/sub or a message broker | Carried over rejection from superseded research — total overkill for a single-process, self-hosted app; CLAUDE.md's portability constraint argues against adding a new Docker Compose service just for event fan-out |
| Alembic branch labels (single alembic.ini, multiple version dirs) | A fully separate alembic.ini/env.py per module | Branch labels keep one `alembic_version`-tracking setup and one `env.py` while still giving each module migration independence; fully separate Alembic projects per module would require N separate `alembic upgrade` invocations and N separate DB connection configs — disproportionate for a single-process app |
| Manual Kahn's-algorithm topo-sort | `graphlib.TopologicalSorter` (stdlib, Python 3.9+) | **Recommended over hand-rolling AND over networkx** — `graphlib.TopologicalSorter` is stdlib, exactly fits "small dependency graph, fail loudly on cycles" (raises `CycleError`), and needs zero new dependencies [VERIFIED: docs.python.org/3/library/graphlib.html] |

**Installation:**
No new backend dependencies required for host infrastructure — `typing`, `asyncio`, and `graphlib` are all stdlib; `pydantic`/`alembic` are already pinned in `backend/pyproject.toml`.

**Version verification:** No new packages recommended this phase; see Package Legitimacy Audit below for confirmation that nothing new needs registry verification.

## Package Legitimacy Audit

**No new external packages are required for this phase.** All capability-Protocol/ModuleLoader/EventBus/ModuleRegistry infrastructure is built from Python stdlib (`typing`, `asyncio`, `graphlib`) plus already-installed project dependencies (`pydantic`, `alembic`, `fastapi`, `sqlalchemy`). The optional `networkx` alternative considered above is explicitly **not recommended** — no audit needed since it is not part of the recommendation.

If the planner decides to add `graphlib`-equivalent tooling or any other new package during planning, run the Package Legitimacy Gate protocol at that time. For now:

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| *(none — no new packages this phase)* | — | — | — | — | — | N/A |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────── Startup (ModuleLoader) ────────────────────────────┐
│                                                                                  │
│  1. scan backend/src/modules/*/manifest.py                                     │
│     ──▶ collect ModuleManifest[] (id, kind, provides, requires, db_schema)     │
│                                                                                  │
│  2. build dependency graph (provides/requires edges)                          │
│     ──▶ graphlib.TopologicalSorter ──▶ ordered module list                    │
│         (raises CycleError / fails fast if requires has no provides match,    │
│          or two modules provide the same interface)                           │
│                                                                                  │
│  3. for each module in topo order:                                             │
│     resolve requires from ModuleRegistry (already-registered earlier modules) │
│         │                                                                       │
│         ▼                                                                       │
│     module_factory.create(deps: dict[type, object]) ──▶ module instance       │
│         │                                                                       │
│         ▼                                                                       │
│     ModuleRegistry.register(provides_types, instance)                        │
│         │                                                                       │
│         ├─ isinstance(instance, HasAPIRoutes)? ──▶ app.include_router(        │
│         │     instance.get_router(), prefix=f"/api/modules/{id}")            │
│         ├─ isinstance(instance, HasUIPage)? ──▶ register frontend nav entry  │
│         ├─ isinstance(instance, HasEventSubscriptions)? ──▶ EventBus.subscribe│
│         │     for each (event_type, handler) in get_subscriptions()          │
│         └─ isinstance(instance, HasCollector)? ──▶ asyncio.create_task(       │
│               instance.run_collector(stop_event))                            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────── Runtime request flow (example: Devices) ──────────────┐
│                                                                                  │
│  Browser ──▶ GET /api/modules/devices/  (HasAPIRoutes router)                 │
│                  │                                                              │
│                  ▼                                                             │
│            Devices module's route handler                                    │
│                  │                                                              │
│                  ▼  (constructor-injected at startup, not looked up per-req)  │
│            self._device_lookup: DeviceLookupInterface                        │
│                  │                                                              │
│                  ▼                                                             │
│            DeviceIdentity module instance (device_identity schema)            │
│                  │                                                              │
│                  ▼                                                             │
│            Postgres: device_identity.devices / device_identity.discovered_*   │
│                                                                                  │
│  Capture container ──▶ POST /api/capture/arp ──▶ DeviceIdentity.record_       │
│       observation() ──▶ EventBus.publish("new_device", payload)              │
│                                  │ (fire-and-forget asyncio.create_task)       │
│                                  ▼                                             │
│                     any HasEventSubscriptions module's handler runs           │
│                     (e.g. future Notifications module in Phase 5.2)           │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
backend/src/
├── host/                          # NEW — module-host infrastructure (not a module itself)
│   ├── protocols.py                # HasAPIRoutes, HasUIPage, HasEventSubscriptions, HasCollector
│   ├── manifest.py                 # ModuleManifest (Pydantic)
│   ├── registry.py                 # ModuleRegistry (Protocol type -> provider instance)
│   ├── loader.py                   # ModuleLoader (scan, topo-sort, instantiate, wire)
│   └── event_bus.py                # EventBus (carried over from superseded research, D-10)
├── modules/
│   ├── device_identity/            # support module — sole device-data source of truth
│   │   ├── manifest.py
│   │   ├── module.py                # factory create(deps) -> DeviceIdentityModule
│   │   ├── interfaces.py            # DeviceLookupInterface (Protocol)
│   │   ├── models.py                # Device, DiscoveredIdentity, DeviceMacHistory (moved)
│   │   ├── service.py               # discovery.py + identity_inference.py logic (moved)
│   │   └── migrations/              # own Alembic branch, device_identity schema
│   ├── devices/                     # feature module — thin UI client of DeviceIdentity
│   │   ├── manifest.py
│   │   ├── module.py
│   │   ├── routes.py                # register/merge dialogs' backing endpoints
│   │   ├── models.py                # UI-owned only: sort order, search history, display prefs
│   │   └── migrations/              # own Alembic branch, devices schema
│   ├── traffic/                     # feature module
│   │   ├── manifest.py
│   │   ├── module.py
│   │   ├── routes.py                # moved from routes/traffic.py
│   │   ├── models.py                # TrafficFlow, BandwidthMetric (moved)
│   │   ├── broadcaster.py           # traffic_broadcaster.py (moved, HasCollector-wrapped)
│   │   └── migrations/              # own Alembic branch, traffic schema
│   ├── security/                    # feature module
│   │   ├── manifest.py
│   │   ├── module.py
│   │   ├── routes.py                # moved from routes/security.py
│   │   ├── models.py                # PortScanResult, SecurityAlert, PendingScanRequest (moved)
│   │   └── migrations/              # own Alembic branch, security schema
│   └── linked_apps/                 # NEW — manifest-only data model + dashboard section
│       ├── manifest.py
│       └── linked_manifest.py       # LinkedModuleManifest (id, name, icon_url, target_url)
├── main.py                          # calls ModuleLoader at startup instead of static includes
└── ... (auth.py, database.py, settings.py unchanged — host-level, not module concerns)
```

### Pattern 1: Capability Protocols (composition, not inheritance)
**What:** Small, independent `@runtime_checkable` `Protocol`s a module structurally satisfies.
**When to use:** Defining what a module *can do*, never what it *is*.
**Example:**
```python
# Source: docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md (verbatim per CONTEXT.md specifics)
from typing import Protocol, runtime_checkable, Callable
import asyncio
from fastapi import APIRouter

@runtime_checkable
class HasAPIRoutes(Protocol):
    def get_router(self) -> APIRouter: ...

@runtime_checkable
class HasUIPage(Protocol):
    def get_ui_route(self) -> str: ...

@runtime_checkable
class HasEventSubscriptions(Protocol):
    def get_subscriptions(self) -> dict[str, Callable]: ...

@runtime_checkable
class HasCollector(Protocol):
    async def run_collector(self, stop_event: asyncio.Event) -> None: ...
```
**Gotcha (verified):** `@runtime_checkable` is required on every Protocol used with `isinstance()` — omitting it raises `TypeError: Instance and class checks can only be used with @runtime_checkable protocols` at the very first loader pass. Also note `isinstance()` checks against a runtime-checkable Protocol only verify that members **exist**, not that their signatures match — a module implementing `get_router(self, x) -> None` would still pass `isinstance(instance, HasAPIRoutes)` and then explode at call time. The loader cannot statically catch a parameter-count mismatch; this is a known, documented limitation of PEP 544 [VERIFIED: typing.python.org/en/latest/spec/protocol.html].

### Pattern 2: ModuleManifest + provides/requires (Pydantic)
**What:** Typed declaration of what a module is, what it provides, and what it requires.
**When to use:** Every module's `manifest.py`.
**Example:**
```python
# Source: docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md (verbatim)
from typing import Literal
from pydantic import BaseModel

class ModuleManifest(BaseModel):
    id: str
    display_name: str
    version: str
    kind: Literal["feature", "support"]
    provides: list[type]      # Protocol types this module satisfies
    requires: list[type]      # Protocol types this module needs from others
    db_schema: str | None
```
**Gotcha:** Pydantic v2 validates `list[type]` permissively (any `type` object passes), so a manifest declaring `provides=[str]` would be schema-valid but semantically wrong. The loader's fail-fast check (matching `requires` against `provides` across all manifests) is the real safety net here, not Pydantic's field validation — don't expect Pydantic to catch a manifest author declaring the wrong Protocol.

### Pattern 3: ModuleRegistry (Protocol type -> provider instance map)
**What:** Central map from Protocol type to whichever module instance implements it; consumers ask the registry, never the module by name.
**Example:**
```python
# Source: synthesized from design doc D-07/D-08 — no third-party DI framework needed
class ModuleRegistry:
    def __init__(self) -> None:
        self._providers: dict[type, object] = {}

    def register(self, protocol_type: type, instance: object) -> None:
        if protocol_type in self._providers:
            raise RuntimeError(
                f"Provider conflict: {protocol_type} already provided by "
                f"{self._providers[protocol_type]!r}, cannot also register {instance!r}"
            )
        self._providers[protocol_type] = instance

    def resolve(self, protocol_type: type) -> object:
        try:
            return self._providers[protocol_type]
        except KeyError:
            raise RuntimeError(f"No provider registered for {protocol_type}") from None
```

### Pattern 4: ModuleLoader — topological sort via stdlib `graphlib`
**What:** Resolve module instantiation order from `requires`/`provides` edges, fail fast on missing/conflicting dependencies, instantiate via constructor injection.
**Example:**
```python
# Source: stdlib graphlib.TopologicalSorter — docs.python.org/3/library/graphlib.html (VERIFIED)
from graphlib import TopologicalSorter, CycleError

def build_load_order(manifests: list[ModuleManifest]) -> list[str]:
    provides_index: dict[type, str] = {}
    for m in manifests:
        for protocol_type in m.provides:
            if protocol_type in provides_index:
                raise RuntimeError(
                    f"provides conflict: {protocol_type} declared by both "
                    f"{provides_index[protocol_type]} and {m.id}"
                )
            provides_index[protocol_type] = m.id

    graph: dict[str, set[str]] = {m.id: set() for m in manifests}
    for m in manifests:
        for required_type in m.requires:
            provider_id = provides_index.get(required_type)
            if provider_id is None:
                raise RuntimeError(f"{m.id} requires {required_type}, no module provides it")
            graph[m.id].add(provider_id)

    try:
        return list(TopologicalSorter(graph).static_order())
    except CycleError as exc:
        raise RuntimeError(f"Module dependency cycle detected: {exc}") from exc
```
**Then, per the design's D-08 constructor-injection requirement:**
```python
registry = ModuleRegistry()
instances: dict[str, object] = {}
for module_id in build_load_order(manifests):
    manifest = manifest_by_id[module_id]
    deps = {req_type: registry.resolve(req_type) for req_type in manifest.requires}
    factory = factory_by_id[module_id]   # the module's create(deps) function
    instance = factory.create(deps)
    instances[module_id] = instance
    for provided_type in manifest.provides:
        registry.register(provided_type, instance)
    # then isinstance-check + wire HasAPIRoutes/HasUIPage/HasEventSubscriptions/HasCollector
```

### Pattern 5: EventBus (carried over unchanged per D-10)
**What:** Minimal fire-and-forget asyncio pub/sub.
**Example:**
```python
# Source: .planning/phases/05-plugin-system-notifications/_superseded-bolt-on-plugin-model/05-RESEARCH.md (carried over verbatim per D-10)
import asyncio
from collections import defaultdict

class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: callable) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, payload: dict) -> None:
        for handler in self._subscribers.get(event_type, []):
            asyncio.create_task(self._safe_call(handler, payload))

    @staticmethod
    async def _safe_call(handler, payload):
        try:
            await handler(payload)
        except Exception as exc:  # noqa: BLE001 — one module must never crash the bus
            print(f"[event_bus] handler {handler} failed: {exc}")
```

### Pattern 6: DeviceLookupInterface (support interface, Protocol not module identity)
**What:** Named contract any consumer of "what is this device" calls — never coupled to the DeviceIdentity module by name.
**Example:**
```python
# Source: docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md (verbatim)
from typing import Protocol, runtime_checkable

@runtime_checkable
class DeviceLookupInterface(Protocol):
    async def lookup(self, identifier: str) -> "DeviceInfo": ...
```
Traffic/Security retrofit pattern: replace `select(Device).where(Device.last_known_mac == observation.mac)`-style direct joins (currently in `routes/traffic.py::_resolve_device_macs`, `routes/security.py`) with a call to the injected `DeviceLookupInterface` instance instead. The MAC-history resolution logic (`DeviceMacHistory` union with `last_known_mac`) moves into DeviceIdentity's implementation of `lookup()`, not into each consumer.

### Pattern 7: Per-module Alembic branch labels (single alembic.ini, separate version dirs)
**What:** One Alembic config, N independent migration lineages — exactly D-12's requirement.
**Example:**
```ini
# Source: alembic.sqlalchemy.org/en/latest/branches.html (CITED)
# backend/alembic.ini
[alembic]
script_location = alembic
version_locations =
    %(here)s/src/modules/device_identity/migrations
    %(here)s/src/modules/devices/migrations
    %(here)s/src/modules/traffic/migrations
    %(here)s/src/modules/security/migrations
    %(here)s/alembic/versions
path_separator = os
```
```bash
# One-time branch creation per module (Claude's Discretion: naming convention)
alembic revision -m "device_identity initial schema" \
  --head=base --branch-label=device_identity \
  --version-path=src/modules/device_identity/migrations

# Subsequent migrations on that branch:
alembic revision -m "add merge_log table" --head=device_identity@head

# Upgrade everything:
alembic upgrade heads
```
**Gotcha (verified):** "When using multiple version directories, initial revisions must be specified with `--version-path`" [CITED: alembic.sqlalchemy.org/en/latest/branches.html] — forgetting `--version-path` on the very first revision of a new branch silently writes the file into the default `alembic/versions/` directory instead of the module's own `migrations/` folder, defeating the entire point of D-12. Verify the file landed in the right directory after every `alembic revision --branch-label=...` call.

### Pattern 8: Schema-qualified `create_hypertable()`
**What:** TimescaleDB hypertable creation in a non-public schema.
**Example:**
```sql
-- Source: github.com/timescale/timescaledb/issues/5687 (CITED — confirms psql syntax works;
-- the reported failure was pgAdmin/tool-specific, not a real syntax limitation)
CREATE SCHEMA IF NOT EXISTS traffic;
CREATE TABLE traffic.traffic_flows (
    time TIMESTAMPTZ NOT NULL,
    device_mac VARCHAR(17) NOT NULL,
    dst_ip VARCHAR(45) NOT NULL,
    dst_port INTEGER,
    protocol INTEGER NOT NULL,
    bytes FLOAT NOT NULL DEFAULT 0,
    dst_hostname VARCHAR(255),
    PRIMARY KEY (time, device_mac, dst_ip, dst_port, protocol)
);
SELECT create_hypertable('traffic.traffic_flows', by_range('time', INTERVAL '1 week'));
```
The schema-qualified table name is passed as a single quoted string (`'traffic.traffic_flows'`), exactly like the existing unqualified call in migration `0004_traffic_flows.py` (`create_hypertable('traffic_flows', by_range(...))`) — no new function signature, no separate "schema" argument. The same applies to `add_compression_policy`, `add_continuous_aggregate_policy` — they all take the hypertable by name/regclass, schema-qualified or not, identically.

### Pattern 9: FastAPI router mount-once + enabled-flag check (carried over Pitfall 1 fix)
**What:** FastAPI/Starlette cannot cleanly un-register a router at runtime (`app.include_router()` is append-only). Mount every discovered module's router once at startup regardless of its initial enabled state; gate each route behind a `Depends(require_module_enabled(module_id))` dependency that returns 404 when disabled.
**Example:**
```python
# Source: pattern carried over from superseded research's documented Pitfall 1 fix,
# adapted to the new module-host vocabulary; mirrors src/auth.py's existing
# Depends(require_auth) convention already used by every route in this codebase
from fastapi import Depends, HTTPException

def require_module_enabled(module_id: str):
    async def _check(db: AsyncSession = Depends(get_db)) -> None:
        if not await is_module_enabled(db, module_id):
            raise HTTPException(status_code=404, detail="Module disabled")
    return _check
```
This satisfies MOD-04's "no core rebuild when modules are toggled" requirement honestly — toggling flips a `module_configs.enabled` boolean, and every already-mounted route immediately starts/stops 404ing without any FastAPI route-table mutation.

### Anti-Patterns to Avoid
- **A fat `Module` base class with optional-override methods:** Explicitly rejected by D-02. Don't reintroduce this even as a "convenience" — it's the exact pattern the design pivot is moving away from.
- **Lazy/per-request Protocol resolution instead of constructor injection:** D-08 is explicit — resolve `requires` once at startup, inject into the factory. A per-request `registry.resolve(DeviceLookupInterface)` call inside a route handler reintroduces "fails mid-request" risk the design explicitly avoids.
- **Deriving cross-module events from polling DB rows on a timer:** Carried over from superseded research — publish synchronously at the point of occurrence (inside the writing transaction's call site), never reconstruct events by polling `security_alert` or similar tables on an interval.
- **Treating SQLite (test fixture) and Postgres (production) as schema-interchangeable:** SQLite has no real schema/namespace primitive analogous to Postgres `CREATE SCHEMA`. See Common Pitfalls below — this needs an explicit per-module decision, not an assumption that `Base.metadata` with `schema="traffic"` "just works" identically on both dialects.
- **Big-bang retrofit in one commit:** The Risk Summary explicitly calls for before/after behavior-parity checks; rewriting Devices+Traffic+Security+DeviceIdentity in one undifferentiated change makes it impossible to bisect a regression to its source module.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dependency-graph topological sort | Custom DFS/Kahn's-algorithm implementation | stdlib `graphlib.TopologicalSorter` | Zero new dependencies, handles cycle detection (`CycleError`) for free, exactly fits "small DAG, fail loudly" need [VERIFIED: docs.python.org/3/library/graphlib.html] |
| Manifest scanning / module discovery | Custom file-walker + manual `importlib` boilerplate | `importlib.import_module` + `pkgutil.iter_modules` over `backend/src/modules/` (the same idiom the carried-over superseded research already documented for plugin discovery) | This is already a well-trodden, simple stdlib pattern in this exact codebase's prior research — no third-party plugin-loading library needed |
| Per-module Postgres schema isolation | A hand-rolled "schema router" layer or Postgres grants/roles | SQLAlchemy `Table(..., schema="traffic")` + Alembic branch labels + convention/code-review (D-13 explicitly defers grants to a future scale need) | Building real DB-level enforcement now is explicitly out of scope (Scope Fence) — convention is the locked decision for v1 |
| EventBus pub/sub | A message broker (Redis, RabbitMQ) | In-process asyncio `EventBus` (D-10 carryover) | Single-process, self-hosted app; CLAUDE.md's portability/no-extra-services constraint rules out adding infra just for event fan-out |
| Cross-module data-sharing contracts | Ad-hoc shared SQLAlchemy model imports across module packages | Protocol-typed support interfaces (`DeviceLookupInterface`) resolved via `ModuleRegistry` | This is the entire point of D-05/D-06/D-07 — importing another module's ORM model directly reintroduces the tight coupling the pivot is designed to remove |

**Key insight:** Every piece of "host infrastructure" needed this phase already has a stdlib or already-installed-dependency answer (`typing.Protocol`, `graphlib`, `pydantic`, `alembic` branch labels, `asyncio`). The genuine novelty and risk in this phase is **not** the module contract itself — it's safely relocating already-working, hot-path production code (`discovery.py`'s ingest pipeline) into a new schema boundary without breaking the capture container's live ARP/DHCP/mDNS flow.

## Runtime State Inventory

> This phase retrofits existing code into a new schema/module boundary — Runtime State Inventory applies.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Existing Postgres `devices`, `discovered_identities`, `device_mac_history`, `traffic_flows`, `bandwidth_metrics`, `port_scan_results`, `security_alerts`, `pending_scan_requests` tables all currently live in the `public` schema. Moving any of them to a module-owned schema (`device_identity.*`, `traffic.*`, `security.*`) is a **data migration**, not just a code edit — existing rows must be moved (`ALTER TABLE ... SET SCHEMA ...` in Postgres, or a create-new-table-and-copy if column shapes also change). | Data migration (Alembic `op.execute("ALTER TABLE devices SET SCHEMA device_identity")` style) for each table being relocated, sequenced per-module, not as one giant migration. |
| Live service config | None found — this project has no live external service configuration analogous to n8n/Datadog/Tailscale for this phase's scope. The capture container's polling endpoints (`/api/capture/pending-scans`, `/api/capture/queue-daily-scans`) are code, fully in git, not separately-configured runtime state. | None. |
| OS-registered state | None found — no Task Scheduler/launchd/pm2/systemd registrations reference table/schema names or module identifiers in this codebase. | None. |
| Secrets/env vars | None found that reference the renamed concepts. `DATABASE_URL`, `SESSION_SECRET` are unrelated to module/schema naming and need no change. | None. |
| Build artifacts | `backend/src/__pycache__` and any installed-editable package metadata (`innkeeper-backend.egg-info` if present) will go stale once `backend/src/{models,routes,services}/` files move into `backend/src/modules/*/`; a plain `pip install -e .` reinstall (already how the project installs, per `pyproject.toml`'s `[tool.setuptools.packages.find] include = ["src*"]`) picks up the new package layout automatically since `src*` is a wildcard glob, not an enumerated list — confirmed no `pyproject.toml` edit is needed for the new `src/modules/*` and `src/host/` subpackages, only a reinstall/rebuild of the Docker image is required (same "stale image after dependency add" lesson already logged in STATE.md's Phase 02.1 P01 entry). | Docker image rebuild (`docker compose build api` or equivalent) after the file moves — no `pyproject.toml` change needed. |

**Critical cross-cutting item not in the five fixed categories — flagged explicitly:** The test suite (`backend/tests/conftest.py`) creates its schema via `Base.metadata.create_all` against an **in-memory SQLite** engine, not via Alembic migrations. SQLite has no `CREATE SCHEMA` concept; SQLAlchemy's `schema="traffic"` table argument on SQLite is silently interpreted as an `ATTACH DATABASE` alias, not a Postgres-style namespace, and the existing conftest only attaches one in-memory engine. **This is the single biggest unresolved technical question for this phase — see Open Questions below.** It is not a "nothing found" item; it requires an explicit decision before any migration is written.

## Common Pitfalls

### Pitfall 1: SQLite test fixture cannot honor Postgres schema-qualified tables
**What goes wrong:** Once `Device`/`TrafficFlow`/etc. models declare `__table_args__ = {"schema": "device_identity"}` (or equivalent), `Base.metadata.create_all` against the existing single in-memory SQLite engine in `conftest.py` either errors (SQLite raises on unknown attached database `device_identity`) or silently creates the table unqualified, depending on how the schema is referenced in queries — either way, a model that works correctly against production Postgres can pass or fail tests for reasons unrelated to actual code correctness.
**Why it happens:** SQLite models a "schema" as a separate attached database file, not a namespace inside one database the way Postgres does; SQLAlchemy's cross-dialect schema support has fundamentally different runtime semantics per dialect.
**How to avoid:** Decide explicitly (flagged in Open Questions) between: (a) use SQLAlchemy's `schema_translate_map` execution option to map all module schemas to `None`/`main` for the SQLite test engine while leaving real schema names for Postgres, or (b) use `ATTACH DATABASE ':memory:' AS device_identity` style multi-attach for SQLite tests to mirror the multi-schema structure, or (c) switch the test fixture to a real (test) Postgres instance via testcontainers, abandoning SQLite for this phase's tests. **Recommend (a)** — `schema_translate_map` is the SQLAlchemy-native, documented mechanism for exactly this dialect-portability problem and requires no new test infrastructure (verify behavior in a throwaway script before relying on it across all four module schemas).
**Warning signs:** Tests pass locally against SQLite but the equivalent query 500s against real Postgres in the Lima VM/docker-compose stack — exactly the kind of dialect-divergence bug this project's STATE.md has already hit twice (the `pg_insert`/`sqlite_insert` dual-path upsert pattern in `discovery.py`, and the dst_port NOT NULL PK issue in Phase 03 P04).

### Pitfall 2: `isinstance()` against a runtime-checkable Protocol only checks member existence, not signature
**What goes wrong:** A module's `get_router(self, extra_arg) -> APIRouter` (wrong arity) still passes `isinstance(instance, HasAPIRoutes)` at loader time, then raises `TypeError: missing required positional argument` only when the loader actually calls `get_router()` — after the loader has already logged "module X capability HasAPIRoutes detected" as if it succeeded.
**Why it happens:** PEP 544 / `@runtime_checkable` structural checks are existence-only by design — Python's `isinstance()` cannot inspect call signatures at runtime [VERIFIED: typing.python.org/en/latest/spec/protocol.html].
**How to avoid:** Wrap each capability-wiring call (`get_router()`, `run_collector()`, etc.) in the loader's own try/except that logs which module and which capability failed, rather than letting a bad-signature module crash the entire startup sequence ambiguously. Treat this the same way the carried-over Pitfall 3 (background collector tasks dying silently) is treated — defensive wrapping at the loader, never trusting module code to be well-formed.
**Warning signs:** Startup logs show a module's capability detected, but its router never appears in `/docs` or its UI route never renders — check for a TypeError swallowed by an overly broad except clause somewhere in the wiring code.

### Pitfall 3: DeviceIdentity retrofit breaks the capture container's hot ingest path
**What goes wrong:** `discovery.py::record_observation()` is called by `routes/capture.py`'s ARP/DHCP/mDNS ingest endpoints on every single observation from the always-running capture container. If DeviceIdentity's retrofitted version changes the function signature, return type, or transaction-commit timing even slightly, every subsequent capture POST silently 500s or hangs — and because the capture container runs detached with its own retry/backoff loops, the failure mode is "devices stop updating" with no obvious error surfaced to the dashboard.
**Why it happens:** This is exactly the kind of "rewriting working code" risk the CONTEXT.md Risk Summary calls out explicitly. The function is called from a different container's network boundary (capture → API), not just from in-process Python — a contract change here has a wider blast radius than an in-process refactor.
**How to avoid:** Before refactoring `record_observation()`'s internals, write (or confirm coverage of) integration tests that exercise the full `POST /api/capture/arp` → `record_observation()` → DB-write path exactly as the capture container calls it today, then run the same tests after the retrofit with zero changes to expected response shape/status codes. This is the "before/after behavior parity check" the Risk Summary asks for, applied concretely to the single highest-traffic code path in this retrofit.
**Warning signs:** `test_discovery.py`/`test_capture.py` passing is necessary but not sufficient — also re-verify against the real Lima VM docker-compose stack with live capture traffic before considering DeviceIdentity's retrofit complete, mirroring the Phase 3 P04 precedent of live-stack verification before sign-off (STATE.md).

### Pitfall 4: Devices module accidentally re-owns canonical device fields
**What goes wrong:** Under time pressure, a "just add one more column" instinct puts something canonical (e.g. `device_type`, `trusted`) into Devices' UI-owned schema instead of routing it through DeviceIdentity — silently recreating the dual-source-of-truth problem D-15/D-16/D-17 exist specifically to eliminate.
**Why it happens:** Devices' register/merge dialogs are the only UI surface that *writes* device fields like name/type/trusted today, making it tempting to keep that write path local to the Devices module rather than proxying through DeviceIdentity's actual CRUD.
**How to avoid:** Every write that touches `name`, `owner`, `type`, `trusted`, `last_known_mac`, `identity_key`, `first_seen`/`last_seen` must go through a DeviceIdentity write method, never a direct Devices-schema insert/update. Devices' own schema should only ever contain UI-state columns that have no meaning outside this one feature module's rendering (sort order, search history, display prefs per D-16).
**Warning signs:** A new column appears in a `devices.*` migration that also exists conceptually in `device_identity.*` — that's the tell that the boundary slipped.

### Pitfall 5: Alembic `--version-path` omission silently breaks branch isolation
**What goes wrong:** Running `alembic revision --branch-label=traffic` without `--version-path=src/modules/traffic/migrations` on the very first revision of that branch writes the migration file into the default `alembic/versions/` directory instead, defeating D-12's "module migrations never collide" guarantee while still technically "working" (the migration runs fine, just lives in the wrong folder, mixed in with other modules' files).
**Why it happens:** `--version-path` is only strictly required by Alembic tooling on a branch's first revision; subsequent revisions on an already-established branch infer their directory automatically, making the omission easy to miss on the one revision where it actually matters [CITED: alembic.sqlalchemy.org/en/latest/branches.html].
**How to avoid:** After creating any new branch's first revision, immediately verify the generated file's path before committing — a simple `git status` after `alembic revision` should show the new file inside the intended module's `migrations/` directory, not `alembic/versions/`.
**Warning signs:** `alembic/versions/` directory contains files that conceptually belong to a specific module (filename mentions "traffic" or "security") instead of being default-bucket-only host migrations.

## Code Examples

### Stdlib topological sort with cycle detection
```python
# Source: docs.python.org/3/library/graphlib.html (VERIFIED — Python 3.13 stdlib)
from graphlib import TopologicalSorter, CycleError

ts = TopologicalSorter({"B": {"A"}, "C": {"A", "B"}})
print(list(ts.static_order()))  # ['A', 'B', 'C']
```

### SQLAlchemy schema_translate_map for cross-dialect schema portability
```python
# Source: docs.sqlalchemy.org/en/20/core/connections.html#translation-of-schema-names (pattern,
# documented SQLAlchemy 2.0 execution-option feature; recommend validating against this
# project's actual conftest.py fixture before relying on it for all four module schemas)
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    execution_options={"schema_translate_map": {
        "device_identity": None,
        "traffic": None,
        "security": None,
        "devices": None,
    }},
)
```

### EventBus subscriber wiring at loader time (illustrative)
```python
# Source: synthesized — composes Pattern 4 (loader) + Pattern 5 (EventBus)
for module_id, instance in instances.items():
    if isinstance(instance, HasEventSubscriptions):
        for event_type, handler in instance.get_subscriptions().items():
            event_bus.subscribe(event_type, handler)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Bolt-on "plugin" model — plugins cannot replace core platform components, `PluginManifest` + directory-scan loader | Module-host model — capability Protocols, swappable support-interface providers via `ModuleRegistry`, Devices/Traffic/Security are themselves modules | 2026-06-21 design pivot (this phase) | Everything in the superseded `05-RESEARCH.md`/`05-01..04-PLAN.md` files except the `EventBus` class itself (D-10) is retired; do not reuse the `PluginManifest`/`discover_manifests()`/`load_plugin()` patterns shown there |
| `hasattr()` checks for structural duck typing | `@runtime_checkable` `Protocol` + `isinstance()` | Python 3.8+ (PEP 544), refined in 3.12's `inspect.getattr_static()`-based implementation | More precise existence checks than ad-hoc `hasattr`, still no signature verification — see Pitfall 2 |
| Single `alembic/versions/` directory, sequential revisions | `version_locations` + `branch_labels`, one branch per module | Long-standing Alembic feature, newly relevant to this project at this phase | Required for D-12's "module migrations never collide" guarantee |

**Deprecated/outdated:**
- The bolt-on `PluginManifest`/file-convention loader pattern from the superseded research — explicitly retired by this pivot, not a "current best practice that changed," but a project-specific design reversal.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `schema_translate_map` is the right fix for the SQLite-test/Postgres-production schema divergence (Pitfall 1) | Common Pitfalls, Code Examples | If `schema_translate_map` doesn't behave as expected across all four module schemas simultaneously in this project's specific conftest.py setup, the planner may need to fall back to a real test-Postgres instance (testcontainers) instead — a bigger infra change than assumed here. This was not validated against this project's actual test fixture in this research session, only against general SQLAlchemy documentation. |
| A2 | A single atomic per-module retrofit commit sequence (DeviceIdentity → Devices → Traffic → Security) is the right migration ordering, rather than a longer dual-write/dual-read transition period | Summary, Runtime State Inventory | If DeviceIdentity's schema/interface needs revision after Devices is already retrofitted onto it, the planner pays a second migration cost; a more conservative dual-write period would catch contract mismatches earlier at higher up-front cost. This sequencing recommendation is a judgment call, not verified against any external authority. |
| A3 | `networkx` should NOT be added; `graphlib.TopologicalSorter` is sufficient | Standard Stack, Alternatives Considered | If the module dependency graph later needs features `graphlib` doesn't have (e.g. finding all valid orderings, not just one), this recommendation would need revisiting — low risk given the design's "convention not framework" tone and the graph's expected small size (handful of modules) |
| A4 | `pip install -e .`'s wildcard `src*` package discovery in pyproject.toml will pick up `backend/src/modules/*` and `backend/src/host/` automatically with no pyproject.toml edit | Runtime State Inventory | If setuptools' `find` directive behaves differently than assumed for nested subpackages without their own `__init__.py` files initially, the Docker build could silently omit the new module packages — verify with an actual `pip install -e .` + `python -c "import src.modules.device_identity"` smoke test early in implementation, not just at the end |

## Open Questions

> **Note (post-planning):** Open Question 1's resolution is deferred by design to Plan 01 Task 2's empirical schema-portability spike script (`backend/tests/schema_portability_spike.py`), not answered analytically here. The spike runs before any module's `migrations/` directory is written, exactly per this question's own Recommendation below, and its PASS/FAIL verdict is recorded in `05-01-SUMMARY.md` for Plan 03 to consume. This is intentional sequencing, not an unresolved gap.

1. **How should the test suite represent multiple Postgres schemas given the in-memory SQLite fixture?**
   - What we know: Production needs `device_identity`/`traffic`/`security`/`devices` as real Postgres schemas (D-11). The existing test fixture (`backend/tests/conftest.py`) uses a single in-memory SQLite engine with `Base.metadata.create_all`, which has no native multi-schema concept.
   - What's unclear: Whether `schema_translate_map` (Assumption A1) cleanly handles four simultaneous schema-to-`None` mappings without breaking SQLAlchemy's relationship/foreign-key resolution across "schemas" that are actually all flattened into the same SQLite file.
   - Recommendation: Spike this in isolation (a throwaway script with two simple models in two different declared schemas, against SQLite with `schema_translate_map`) before writing the real `device_identity`/`devices` split migrations — this is cheap to de-risk early and expensive to discover mid-retrofit.

2. **What is the exact transition strategy for the capture container's ingest contract during the DeviceIdentity retrofit?**
   - What we know: `routes/capture.py`'s ARP/DHCP/mDNS endpoints call `discovery.py::record_observation()` today; that logic is moving into `modules/device_identity/`.
   - What's unclear: Whether the retrofit can be a single atomic cutover (swap the import, same function signature, one commit) or needs a compatibility shim period where both the old `services/discovery.py` and the new `modules/device_identity/service.py` exist briefly during the transition.
   - Recommendation: Given this is in-process Python (not a network contract change for the capture container — only the API container's internal call path changes), a single atomic cutover per the Pitfall 3 mitigation (test parity before/after) should be sufficient; no compatibility shim needed since the capture container only ever talks to `/api/capture/*` HTTP routes, which can keep an identical request/response contract even as the backing implementation moves modules.

3. **Should this phase be split across multiple plan waves given its size?**
   - What we know: The phase combines net-new host infrastructure (low regression risk, four capability Protocols, ModuleLoader, ModuleRegistry, EventBus carryover, LinkedModuleManifest) with a behavior-preserving retrofit of three already-shipped feature areas plus extraction of a new support module (high regression risk, touches the hottest code path in the system).
   - What's unclear: Whether the orchestrator's context budget for a single phase comfortably covers both halves, or whether host-infra-only should be its own wave/sub-phase before any retrofit work begins.
   - Recommendation: **Surfaced for the planner/orchestrator to decide, not decided here per the task's instruction.** A natural split: Wave 1 = host infrastructure + LinkedModules data model (MOD-01, MOD-02, MOD-03, MOD-06, MOD-08 — no existing code touched, can ship and be verified independently). Wave 2 = DeviceIdentity extraction + Devices retrofit (MOD-07, the highest-risk single piece). Wave 3 = Traffic retrofit. Wave 4 = Security retrofit. Each retrofit wave should land as its own commit with explicit before/after behavior-parity verification per the Risk Summary.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | All backend module code, `graphlib`/`typing.Protocol` | ✓ (per pyproject.toml `requires-python>=3.13`, project already runs 3.13) | 3.13.x | — |
| PostgreSQL + TimescaleDB | Per-module schema isolation, hypertable retrofit | ✓ in Docker Compose stack (per CLAUDE.md stack); not directly probed this session — assume available per existing Phase 1-4 deployment | 17 / 2.27.x (per CLAUDE.md) | — |
| Alembic | Per-module migration branches | ✓ already pinned (`alembic==1.16.5`) | 1.16.5 | — |
| `graphlib` (stdlib) | ModuleLoader topo-sort | ✓ stdlib since Python 3.9 | bundled with 3.13 | — |
| `/tmp/innkeeper-venv313` (dev-only Python 3.13 venv, per STATE.md precedent) | Running `pytest` outside Docker for fast local iteration | ✓ confirmed present (109 tests collected this session) | — | Project still has no committed project-local venv; continue using the documented `/tmp/innkeeper-venv313` precedent until that's addressed, consistent with prior phases |

**Missing dependencies with no fallback:** none identified.

**Missing dependencies with fallback:** none — all required tooling is either stdlib or already present in this project per prior phases.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (`asyncio_mode = "auto"`), already configured in `backend/pyproject.toml` |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `/tmp/innkeeper-venv313/bin/python -m pytest backend/tests/test_<module>.py -x` |
| Full suite command | `cd backend && /tmp/innkeeper-venv313/bin/python -m pytest` (109 tests collected this session, all pre-existing) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MOD-01 | ModuleLoader topo-sorts manifests and fails fast on unsatisfied requires/conflicting provides | unit | `pytest tests/test_module_loader.py -x` | ❌ Wave 0 |
| MOD-02 | Toggling a module's enabled flag immediately blocks/unblocks its routes without restart | integration | `pytest tests/test_module_registry_toggle.py -x` | ❌ Wave 0 |
| MOD-03 | Publishing an event invokes subscribed handlers; unsubscribed event types are a no-op | unit | `pytest tests/test_event_bus.py -x` | ❌ Wave 0 (carried over from superseded research's identical gap) |
| MOD-04 | An enabled module with `HasUIPage` produces a discoverable nav entry; core app boots with zero modules enabled | integration | `pytest tests/test_module_loader.py::test_ui_page_registration -x` | ❌ Wave 0 |
| MOD-05 | A `HasCollector` module's background loop starts at startup and stops cleanly on shutdown | integration | `pytest tests/test_module_loader.py::test_collector_lifecycle -x` | ❌ Wave 0 |
| MOD-06 | Two modules declaring the same `provides` type fails loader startup with a clear error | unit | `pytest tests/test_module_loader.py::test_provides_conflict_fails_fast -x` | ❌ Wave 0 |
| MOD-07 | Devices/Traffic/Security retrofitted endpoints return identical response shapes to their pre-retrofit versions (behavior parity) | integration | `pytest tests/test_devices.py tests/test_traffic_destinations.py tests/test_security_alerts.py -x` (existing files, re-run post-retrofit, zero diff in assertions expected) | ✅ (existing, must stay green through retrofit) |
| MOD-08 | A `LinkedModuleManifest` round-trips through the dashboard's "Linked Apps" section (empty-state when zero entries) | unit + integration | `pytest tests/test_linked_apps.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** targeted module test file (`pytest tests/test_<changed_module>.py -x`)
- **Per wave merge:** full suite (`cd backend && /tmp/innkeeper-venv313/bin/python -m pytest`)
- **Phase gate:** Full suite green before `/gsd-verify-work`, plus a live Lima VM docker-compose smoke check of the capture container's ingest path per Pitfall 3 (mirrors the Phase 3 P04 precedent already logged in STATE.md)

### Wave 0 Gaps
- [ ] `tests/test_module_loader.py` — covers MOD-01, MOD-04, MOD-05, MOD-06
- [ ] `tests/test_module_registry_toggle.py` — covers MOD-02
- [ ] `tests/test_event_bus.py` — covers MOD-03 (same gap already identified, never closed, by the superseded research)
- [ ] `tests/test_linked_apps.py` — covers MOD-08
- [ ] A schema-portability spike script (not a permanent test file) resolving Open Question 1 before any module's `migrations/` directory is written

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (unchanged) | Existing session-cookie `Depends(require_auth)` convention carries over unchanged; no new auth surface introduced by the module host itself |
| V3 Session Management | no (unchanged) | Same as above — `SessionMiddleware` in `main.py` is host-level, not module-owned, and is out of this phase's scope |
| V4 Access Control | yes | Every retrofitted module route must keep `Depends(require_auth)` exactly as today; additionally, the new `Depends(require_module_enabled(module_id))` dependency (Pattern 9) is itself an access-control mechanism and must be applied to every module-mounted route, not just some |
| V5 Input Validation | yes | `ModuleManifest` (Pydantic) validates manifest shape at load time; route-level Pydantic models (`DeviceRegisterPayload`, etc.) carry over unchanged from the existing retrofitted routes |
| V6 Cryptography | no | No new cryptographic surface this phase — module configs storing secrets (e.g. future Notifications API tokens) are explicitly Phase 5.2 scope, not this phase's |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-module schema boundary violation (a module querying another module's schema directly, bypassing its Protocol interface) | Tampering / Information Disclosure | Convention/code-review enforcement per D-13 (explicitly not Postgres grants this phase, per Scope Fence) — flag any direct cross-schema `select()` against another module's table in code review as a hard block, not a style nit |
| Disabled module's routes still reachable (the FastAPI append-only router problem, Pattern 9/Pitfall in superseded research) | Elevation of Privilege | `Depends(require_module_enabled(module_id))` on every module route, verified by an explicit integration test asserting disabled-module routes return 404 |
| Module dependency cycle silently resolved by accident rather than detected | Denial of Service (startup hang/crash) | `graphlib.TopologicalSorter`'s `CycleError` is raised, not silently worked around — the loader must propagate this as a fail-fast startup error, never attempt a "best effort" partial load |
| Manifest `provides`/`requires` type confusion (a module declaring it provides a Protocol it doesn't actually implement) | Tampering | Loader's `isinstance()` capability checks at wiring time (Pattern 1) catch this for the four defined capability Protocols; support interfaces like `DeviceLookupInterface` need the same `isinstance()` discipline applied before registering a provider in `ModuleRegistry` |

## Sources

### Primary (HIGH confidence)
- [typing — Support for type hints (docs.python.org)](https://docs.python.org/3/library/typing.html) — `@runtime_checkable`, Protocol semantics
- [Protocols — typing documentation (typing.python.org)](https://typing.python.org/en/latest/spec/protocol.html) — structural subtyping spec, isinstance existence-only behavior
- [PEP 544 – Protocols: Structural subtyping](https://peps.python.org/pep-0544/) — original design rationale
- [graphlib — Functional Graph Operations (docs.python.org)](https://docs.python.org/3/library/graphlib.html) — `TopologicalSorter`, `CycleError`
- [Working with Branches — Alembic 1.18.4 documentation](https://alembic.sqlalchemy.org/en/latest/branches.html) — branch_labels, version_locations, --version-path requirement
- This project's own source: `backend/src/services/discovery.py`, `backend/src/services/identity_inference.py`, `backend/src/services/traffic_broadcaster.py`, `backend/src/models/device.py`, `backend/src/routes/{devices,traffic,security}.py`, `backend/alembic/env.py`, `backend/alembic/versions/0004_traffic_flows.py`, `backend/tests/conftest.py` — read in full this session

### Secondary (MEDIUM confidence)
- [GitHub: timescale/timescaledb Issue #5687](https://github.com/timescale/timescaledb/issues/5687) — confirms schema-qualified `create_hypertable('schema.table', ...)` syntax works in psql; the reported failure was tool-specific (pgAdmin), not a real syntax blocker
- [GitHub: python/cpython Issue #102433](https://github.com/python/cpython/issues/102433) — isinstance side-effects on @property for runtime_checkable Protocols (not directly relevant to this phase's Protocol shapes, which use plain methods, but worth knowing as a category of gotcha)
- `.planning/phases/05-plugin-system-notifications/_superseded-bolt-on-plugin-model/05-RESEARCH.md` — carried-over EventBus design (D-10) and FastAPI router-removal Pitfall 1, both independently corroborated by this session's general FastAPI plugin-architecture web search

### Tertiary (LOW confidence)
- General web search results on "FastAPI plugin architecture include_router at startup" (Medium articles, blog posts) — directionally consistent with the carried-over pattern but not independently verified against official FastAPI docs beyond the general `include_router`/Bigger Applications tutorial; treat as confirmatory, not authoritative
- SQLAlchemy `schema_translate_map` recommendation for SQLite/Postgres test portability (Assumption A1) — based on general SQLAlchemy 2.0 documentation knowledge of the feature's existence, not validated against this project's actual `conftest.py` in this session

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all recommended tools are stdlib or already-pinned project dependencies; no new package legitimacy risk
- Architecture: HIGH for capability-Protocol/ModuleLoader/EventBus patterns (directly sourced from the approved design doc and official Python typing docs); MEDIUM for the exact retrofit sequencing recommendation (a reasoned judgment call, flagged as Assumption A2)
- Pitfalls: MEDIUM-HIGH — FastAPI router limitation and Alembic --version-path gotcha are documented upstream facts; the SQLite/Postgres schema-portability pitfall (Pitfall 1) is HIGH-confidence as a problem statement but MEDIUM-confidence on the recommended fix (schema_translate_map), since it was not validated against this project's actual test fixture in this session

**Research date:** 2026-06-21
**Valid until:** 30 days (stable stdlib/Alembic/TimescaleDB APIs; re-verify if PostgreSQL/TimescaleDB versions change before planning executes)
</content>
