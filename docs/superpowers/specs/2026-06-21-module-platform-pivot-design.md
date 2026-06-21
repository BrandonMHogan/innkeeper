# Innkeeper Module Platform Pivot — Design

**Date:** 2026-06-21
**Status:** Approved (pending written-spec review)
**Supersedes:** The "plugin" model implied by PROJECT.md's Key Decisions table (`Plugin contract scope`, `Plugin UI via dedicated routes`, `Plugin-first architecture`) and the in-flight Phase 5 plans (`05-01` through `05-04-PLAN.md`), which were built against the old bolt-on contract.

## Motivation

Innkeeper's original framing was a monolithic network-monitoring app with a few bolt-on integrations ("plugins") layered on top — UniFi, Pi-hole, Grafana, notifications. Phases 1-4 (Devices, Traffic, Security) were built directly into the core backend (`backend/src/{models,routes,services}/`), and the in-progress Phase 5 plan encoded a contract where plugins explicitly **cannot replace core platform components**.

The actual long-term vision is different: Innkeeper is a **home-server host** — a thin container + UI shell — where almost everything, including the original networking features, is an isolated **module** with its own API and data. The host's job is to load modules, route between them, and provide a shared UI shell and design system. v1 covers networking (devices, traffic, security); v2+ extends into media, cameras, and third-party apps (Jellyfin-style) without re-architecting the host.

This pivot retrofits the already-built features into the new model and replaces Phase 5 of the roadmap with the platform foundation work, before any further feature phases proceed.

## Module Categories

Every module is one of three kinds:

| Kind | Has UI? | Has own DB schema? | Example |
|---|---|---|---|
| **Feature module** | Yes — dashboard card / settings page | Often — but only for data it's the source of truth for (see below) | Traffic, Security, Notifications, Devices |
| **Support module** | No — internal only, consumed by other modules | Yes — owns canonical domain data | DeviceIdentity |
| **Linked module** | Yes — just a card/link to an externally-run app | No — no code at all, manifest only | Jellyfin (v2+) |

**A module's schema reflects what it's the source of truth for, not whether it has UI.** Devices is a feature module that owns no canonical device data (DeviceIdentity does) but may still own its own schema for UI-layer concerns it's actually responsible for — sort order, search history, display preferences. The boundary is "who's the source of truth for *this specific data*," evaluated per table, not "does this module have a database at all."

Linked modules are exempt from every isolation/contract rule below — they're a manifest entry (`id`, `name`, `icon_url`, `target_url`) producing a dashboard card that opens the third-party app's own UI. v1 builds the data model and dashboard section for these but does not ship a real one; the first real linked module is v2 scope.

## Module Contract

### Capability Protocols (composition, not a fat base class)

Rejected alternatives: a single `Module` base class with optional-override methods (violates interface segregation, bloats as capabilities grow, risky to evolve once 20+ modules subclass it), and pure file-convention discovery with no typed contract (too close to an "anything goes" gateway, no static or runtime check that a module actually does what it claims).

Instead, capabilities are small, independent `typing.Protocol`s. A module is any Python object that structurally satisfies zero or more of them — no inheritance required:

```python
class HasAPIRoutes(Protocol):
    def get_router(self) -> APIRouter: ...

class HasUIPage(Protocol):
    def get_ui_route(self) -> str: ...

class HasEventSubscriptions(Protocol):
    def get_subscriptions(self) -> dict[str, Callable]: ...

class HasCollector(Protocol):
    async def run_collector(self, stop_event: asyncio.Event) -> None: ...
```

The loader uses `@runtime_checkable` + `isinstance()` to detect which capabilities a module instance actually has, and only wires up those. No module is forced to stub out capabilities it doesn't use. Adding a new capability later (e.g. `HasHealthCheck`) is a new Protocol — it touches zero existing modules.

If a capability Protocol's shape must change incompatibly later, the project defines a new version (`HasAPIRoutesV2`) rather than mutating the original; the loader checks for the newer version first and falls back. Existing modules are never forced to migrate on someone else's schedule.

### Support interfaces (the cross-module data-sharing mechanism)

A support module exposes its functionality as its own named Protocol, independent of the module's identity — e.g. `DeviceLookupInterface` is a contract, not "the DeviceIdentity module's interface":

```python
class DeviceLookupInterface(Protocol):
    async def lookup(self, identifier: str) -> DeviceInfo: ...
```

Modules declare what they `provide` and `require` in their manifest:

```python
class ModuleManifest(BaseModel):
    id: str
    display_name: str
    version: str
    kind: Literal["feature", "support"]
    provides: list[type]      # Protocol types this module satisfies
    requires: list[type]      # Protocol types this module needs from others
    db_schema: str | None
```

A central `ModuleRegistry` (host infrastructure, not a module) maps `Protocol type -> provider instance`. Consumer modules never name the module they're calling — they ask the registry for whoever implements a Protocol. This is what makes implementations swappable later: disable the old provider, enable a new one that satisfies the same Protocol, and every consumer keeps working unmodified, because they were never coupled to *which* module answered, only to the contract.

**Wiring is constructor injection, resolved at startup, not lazy lookup.** The loader resolves all of a module's `requires` before instantiating it, and passes the resolved interfaces into its factory function:

```python
def create(deps: dict[type, object]) -> ModuleInstance: ...
```

This means a missing or conflicting dependency fails loudly at startup, never mid-request, and a module's dependencies are visible just by reading its manifest and factory signature.

### Loader startup sequence

1. Scan `backend/src/modules/*/manifest.py`; collect all `ModuleManifest`s.
2. Build a dependency graph from `requires`/`provides` edges; topologically sort.
3. **Fail fast** if: a `requires` has no matching `provides` among enabled modules, or two enabled modules `provide` the same interface.
4. Instantiate modules in dependency order — support modules (e.g. DeviceIdentity) before the feature modules that need them.
5. Register each instance's `provides` interfaces in the `ModuleRegistry`; wire its capabilities — mount `HasAPIRoutes`' router under `/api/modules/<id>/`, register `HasUIPage`'s frontend route, subscribe `HasEventSubscriptions`' handlers to the `EventBus` (existing fire-and-forget pub/sub design carried over from the original Phase 5 research), spawn `HasCollector`'s background loop with its own `asyncio.Event`/`asyncio.Task`.

### DB schema ownership

- Each module with `db_schema` set owns a real Postgres schema (`device_identity.*`, `traffic.*`, `security.*`, `notifications.*`, `devices.*` for Devices' UI-only tables).
- Each module's package has its own `migrations/` directory; root Alembic config uses branch labels per module so one module's migration never blocks or entangles another's.
- A module may only query its own schema directly. Anything else goes through a `requires`-resolved interface — enforced by convention/code review for now, not Postgres grants (unnecessary at single-process, single-DB-user scale).
- **Implementation note for the Traffic retrofit:** TimescaleDB hypertables work in any schema, but `create_hypertable()` calls must be schema-qualified once `traffic_flows` moves out of `public` into `traffic.*` — flag for the phase planner/researcher, not a design-level concern.

## Devices / DeviceIdentity Split

- **DeviceIdentity** (support module, new schema) — single source of truth for canonical device data: discovery fusion, identity resolution, merge logic, vendor/type inference (today's `discovery.py` + `identity_inference.py` + the `Device` model). Exposes `DeviceLookupInterface` for read access and the actual CRUD/merge operations for write access.
- **Devices** (feature module, thin) — dashboard card grid, register/merge dialogs. Calls into DeviceIdentity for every read and write operation rather than owning device data itself. May own its own schema for genuinely UI-owned concerns (sort order, search history, display prefs) — never for canonical device fields.
- Any other module needing "what is this device" (Traffic, Security, future modules) calls `DeviceLookupInterface` directly rather than tracking its own copy of device names/types.

## Frontend: Shared Design System

SvelteKit compiles to one bundle for the whole app (no module federation, carried over from the existing Key Decision) — there's no runtime boundary to enforce on the frontend the way Protocols enforce the backend boundary, and Svelte already scopes component CSS by default so one module's styles can't leak into another's without any special plumbing.

- **One canonical token source** — `frontend/src/app.css` holds the CSS variables (`--color-accent`, `--color-good`, spacing/typography scale) already established in Phases 1-4. Tailwind config references these vars.
- **One shared component library** — `frontend/src/lib/components/ui/` (shadcn-svelte primitives already started in Phase 4: tooltip, alert, alert-dialog). Native module UI pages import from here rather than rebuilding primitives.
- **Convention, not runtime enforcement.** Using the shared tokens/components is the default and the path of least resistance; a module that genuinely needs a different look just writes its own scoped styles — no opt-out mechanism is needed because nothing forces it in the first place. Enforced at UI-spec/review time (`gsd-ui-phase`/`gsd-ui-checker`), not by code.
- **Linked modules are exempt by definition** — third-party UIs bring their own look.

This work lands in Phase 5, before the Devices/Traffic/Security UI retrofit touches markup, so the retrofit is the first proof the shared system holds across modules.

## Terminology

"Module" replaces "plugin" throughout code, docs, and routes: `plugin_configs` → `module_configs`, `/api/plugins` → `/api/modules`, `backend/src/plugins/` → `backend/src/modules/`, `/settings/plugins` → `/settings/modules`, `/plugins/[slug]` → `/modules/[slug]`.

## Roadmap Changes

**Phase 5: Module Platform Foundation** (replaces "Plugin System + Notifications"; the 4 drafted-but-unexecuted `05-0X-PLAN.md` files and `05-PATTERNS.md`/`05-CONTEXT.md` are retired — built against the superseded bolt-on contract):

1. Host infrastructure: `ModuleRegistry`, `EventBus`, `ModuleLoader`, capability Protocols, `ModuleManifest`, per-module Alembic branch wiring
2. Frontend host work: consolidate design tokens + shared component library, document the UI convention
3. Retrofit DeviceIdentity (support module, new schema) out of today's discovery/inference/Device-model code
4. Retrofit Devices (feature module, thin) to call DeviceIdentity for everything; keep its own schema only for UI-owned concerns
5. Retrofit Traffic (feature module) onto its own schema + `DeviceLookupInterface` calls in place of direct device joins
6. Retrofit Security (feature module) — same pattern as Traffic
7. Linked-module data model + "Linked Apps" dashboard section (groundwork only, no real third-party module yet)

Notably, this phase is **not** building Notifications — that's deferred (see below) — and is **not** building a real linked module (deferred to v2). It is rewriting working code, not just adding new code, and is expected to be larger/heavier than Phases 1-4.

**Phase 6: Improve Device Identity** (promotes backlog item 999.1) — better OUI/vendor inference, hostname heuristics, broader mDNS parsing, MAC-randomization handling, smarter merge. Now isolated, swappable work inside the DeviceIdentity module instead of tangled in core discovery code.

**Phase 7: Notifications** (demoted from the old Phase 5) — event subscriber module, ntfy.sh/Pushover senders. First module built clean on the new contract with no retrofit baggage.

**Phase 8: Dual-Mode + Control** (was Phase 6, unchanged in scope)

**Phase 9: UniFi + Integrations** (was Phase 7, unchanged in scope)

**Phase 10: Network Visualization** (was Phase 8, unchanged in scope)

**Known dependency wrinkle (accepted trade-off):** Security's existing success criterion #4 ("alert delivery handled once notifications exist") and Dual-Mode's auto-degrade-and-notify criterion both implicitly wait on Notifications. Pushing it to Phase 7 means those criteria stay open until Phase 7 closes, in exchange for prioritizing device-identification quality first.

**Backlog item 999.2** (dashboard grouping for stale/unidentified devices) is unaffected — stays in backlog, belongs to the Devices feature module's UI-owned concerns whenever it's picked up.

## PROJECT.md Updates Required

- `Plugin contract scope` Key Decision ("plugins... cannot replace core platform components") — mark superseded by this design.
- `Plugin-first architecture`, `Plugin UI via dedicated routes`, `Plugin contract scope`, `No plugin marketplace in v1` Key Decisions — reworded to "module" terminology; "no marketplace in v1" still holds (linked modules are config/manifest-driven, not a hosted registry).
- "What This Is" section should mention the host/module framing explicitly, since it currently reads as a fixed-feature network monitor rather than an extensible module host.
- Out of Scope's "Open plugin marketplace... community plugins are a future milestone" stays accurate under the new terminology — community/third-party modules remain a v2+ concern.
