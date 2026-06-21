# Phase 5: Module Platform Foundation - Context

**Gathered:** 2026-06-21
**Status:** Ready for planning
**Source:** ADR Ingest Express Path (docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md)

<domain>
## Phase Boundary

Retrofit the already-built Devices, Traffic, and Security features (currently core-app code in `backend/src/{models,routes,services}/`) onto a real module-host platform, before any further feature work proceeds:

1. Host infrastructure: `ModuleRegistry`, `EventBus`, `ModuleLoader`, capability Protocols, `ModuleManifest`, per-module Alembic branch wiring
2. Frontend host work: consolidate design tokens + shared component library, document the UI convention
3. Retrofit DeviceIdentity out of today's discovery/inference/Device-model code into a support module with its own Postgres schema
4. Retrofit Devices into a thin feature module that calls DeviceIdentity for everything
5. Retrofit Traffic onto its own schema + `DeviceLookupInterface` calls in place of direct device joins
6. Retrofit Security — same retrofit pattern as Traffic
7. Linked-module data model + "Linked Apps" dashboard section (groundwork only)

This phase is **not** building Notifications (deferred to Phase 5.2) and **not** shipping a real linked/third-party module (deferred to v2). It is rewriting working code, not just adding new code, and is expected to be larger/heavier than Phases 1-4.

</domain>

<decisions>
## Implementation Decisions

### Module Categories
- **D-01:** Every module is one of three kinds: **feature** (has UI, may have own schema for data it's the source of truth for — Traffic, Security, Notifications, Devices), **support** (no UI, internal only, owns canonical domain data — DeviceIdentity), or **linked** (UI is just a card/link to an externally-run app, no code, manifest only — Jellyfin, v2+). A module's schema reflects what it's the source of truth for, evaluated per table, not whether it has a database at all.

### Capability Protocols (composition, not a fat base class)
- **D-02:** Capabilities are small, independent `typing.Protocol`s, not a single `Module` base class with optional overrides and not pure file-convention discovery. A module is any Python object that structurally satisfies zero or more Protocols — no inheritance required. Defined Protocols: `HasAPIRoutes` (`get_router() -> APIRouter`), `HasUIPage` (`get_ui_route() -> str`), `HasEventSubscriptions` (`get_subscriptions() -> dict[str, Callable]`), `HasCollector` (`async run_collector(stop_event: asyncio.Event) -> None`).
- **D-03:** The loader uses `@runtime_checkable` + `isinstance()` to detect which capabilities a module instance actually has, and only wires up those. No module is forced to stub out unused capabilities.
- **D-04:** If a capability Protocol's shape must change incompatibly later, define a new version (e.g. `HasAPIRoutesV2`) rather than mutating the original; the loader checks the newer version first and falls back. Existing modules are never forced to migrate on someone else's schedule.

### Support Interfaces (cross-module data sharing)
- **D-05:** A support module exposes its functionality as its own named Protocol, independent of module identity (e.g. `DeviceLookupInterface` is a contract, not "the DeviceIdentity module's interface"). Example: `class DeviceLookupInterface(Protocol): async def lookup(self, identifier: str) -> DeviceInfo: ...`
- **D-06:** Modules declare `provides: list[type]` and `requires: list[type]` (Protocol types) in their `ModuleManifest` (fields: `id`, `display_name`, `version`, `kind: Literal["feature","support"]`, `provides`, `requires`, `db_schema`).
- **D-07:** A central `ModuleRegistry` (host infrastructure, not a module) maps `Protocol type -> provider instance`. Consumer modules never name the module they're calling — they ask the registry for whoever implements a Protocol. This is what makes implementations swappable: disable the old provider, enable a new one satisfying the same Protocol, and every consumer keeps working unmodified.
- **D-08:** Wiring is **constructor injection resolved at startup**, not lazy lookup. The loader resolves all of a module's `requires` before instantiating it and passes resolved interfaces into its factory function: `def create(deps: dict[type, object]) -> ModuleInstance: ...`. A missing or conflicting dependency fails loudly at startup, never mid-request.

### Loader Startup Sequence
- **D-09:** Sequence is: (1) scan `backend/src/modules/*/manifest.py`, collect all `ModuleManifest`s; (2) build a dependency graph from `requires`/`provides` edges, topologically sort; (3) fail fast if a `requires` has no matching `provides` among enabled modules, or two enabled modules `provide` the same interface; (4) instantiate modules in dependency order — support modules before the feature modules that need them; (5) register each instance's `provides` interfaces in the `ModuleRegistry`, wire its capabilities (mount `HasAPIRoutes`' router under `/api/modules/<id>/`, register `HasUIPage`'s frontend route, subscribe `HasEventSubscriptions`' handlers to the `EventBus`, spawn `HasCollector`'s background loop with its own `asyncio.Event`/`asyncio.Task`).
- **D-10:** The `EventBus`'s existing fire-and-forget pub/sub design is **carried over unchanged** from the original (superseded) Phase 5 research — see `.planning/phases/05-plugin-system-notifications/_superseded-bolt-on-plugin-model/05-RESEARCH.md` for that design's rationale; only the module-loading/contract layer around it is new.

### DB Schema Ownership
- **D-11:** Each module with `db_schema` set owns a real Postgres schema: `device_identity.*`, `traffic.*`, `security.*`, `notifications.*`, `devices.*` (Devices' UI-only tables).
- **D-12:** Each module's package has its own `migrations/` directory; root Alembic config uses branch labels per module so one module's migration never blocks or entangles another's.
- **D-13:** A module may only query its own schema directly. Anything else goes through a `requires`-resolved interface — enforced by convention/code review for now, not Postgres grants (unnecessary at single-process, single-DB-user scale).
- **D-14:** Traffic retrofit implementation note: TimescaleDB hypertables work in any schema, but `create_hypertable()` calls must be schema-qualified once `traffic_flows` moves out of `public` into `traffic.*`.

### Devices / DeviceIdentity Split
- **D-15:** **DeviceIdentity** (support module, new schema) is the sole source of truth for canonical device data — discovery fusion, identity resolution, merge logic, vendor/type inference (today's `discovery.py` + `identity_inference.py` + the `Device` model). Exposes `DeviceLookupInterface` for read access and the actual CRUD/merge operations for write access.
- **D-16:** **Devices** (feature module, thin) is the dashboard card grid + register/merge dialogs. It calls into DeviceIdentity for every read and write operation rather than owning device data itself. It may own its own schema only for genuinely UI-owned concerns (sort order, search history, display prefs) — never for canonical device fields.
- **D-17:** Any other module needing "what is this device" (Traffic, Security, future modules) calls `DeviceLookupInterface` directly rather than tracking its own copy of device names/types.

### Frontend: Shared Design System
- **D-18:** One canonical token source: `frontend/src/app.css` holds the CSS variables (`--color-accent`, `--color-good`, spacing/typography scale) already established in Phases 1-4. Tailwind config references these vars.
- **D-19:** One shared component library: `frontend/src/lib/components/ui/` (shadcn-svelte primitives already started in Phase 4: tooltip, alert, alert-dialog). Native module UI pages import from here rather than rebuilding primitives.
- **D-20:** Convention, not runtime enforcement — using shared tokens/components is the default and path of least resistance; a module that genuinely needs a different look just writes its own scoped styles. Enforced at UI-spec/review time (`gsd-ui-phase`/`gsd-ui-checker`), not by code. Linked modules are exempt by definition (third-party UIs bring their own look).
- **D-21:** No module federation — SvelteKit still compiles to one bundle for the whole app (carried over from the existing Key Decision); there is no runtime boundary to enforce on the frontend the way Protocols enforce the backend boundary, since Svelte already scopes component CSS by default.
- **D-22:** This design-system consolidation work lands **before** the Devices/Traffic/Security UI retrofit touches markup, so the retrofit is the first proof the shared system holds across modules.

### Linked Modules
- **D-23:** A linked module is a manifest entry only (`id`, `name`, `icon_url`, `target_url`) producing a dashboard card that opens the third-party app's own UI — no code at all. Linked modules are exempt from every isolation/contract rule above. v1 builds the data model and dashboard section for these but does not ship a real one; the first real linked module is v2 scope.

### Terminology
- **D-24:** "Module" replaces "plugin" throughout code, docs, and routes: `plugin_configs` → `module_configs`, `/api/plugins` → `/api/modules`, `backend/src/plugins/` → `backend/src/modules/`, `/settings/plugins` → `/settings/modules`, `/plugins/[slug]` → `/modules/[slug]`.

### Claude's Discretion
- Exact shape of per-module Alembic branch label naming convention — implementation detail consistent with D-12.
- Exact internal structure of `ModuleLoader`'s dependency-graph/topological-sort implementation — implementation detail consistent with D-09.
- Whether `ModuleRegistry` is a singleton, app-state object, or DI container — implementation detail consistent with D-07/D-08.
- Exact UI-owned schema fields for Devices (D-16) — sort order, search history, display prefs column shapes are implementation detail.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Source
- `docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md` — the approved design this CONTEXT.md was ingested from; full rationale, rejected alternatives, and code stubs for every decision above

### Roadmap / Requirements
- `.planning/ROADMAP.md` (Phase 5: Module Platform Foundation section) — success criteria and MOD-01..MOD-08 requirement mapping
- `.planning/REQUIREMENTS.md` — full requirement text for MOD-01..MOD-08

### Superseded Prior Art (history only — do not use as planning input except where explicitly carried over)
- `.planning/phases/05-plugin-system-notifications/_superseded-bolt-on-plugin-model/05-RESEARCH.md` — retired bolt-on-plugin research; the `EventBus` fire-and-forget pub/sub design specifically is carried over per D-10, everything else in this file is built against the retired contract and must not be reused
- `.planning/phases/05-plugin-system-notifications/_superseded-bolt-on-plugin-model/05-01-PLAN.md` through `05-04-PLAN.md` — retired plans, kept for history only

### Code Being Retrofitted (existing source of truth for current behavior)
- `backend/src/discovery.py`, `backend/src/identity_inference.py`, and the existing `Device` model — current canonical device logic, to be moved into the DeviceIdentity module per D-15
- `backend/src/traffic_broadcaster.py` (`update_snapshot_loop`'s `stop_event` + `asyncio.wait_for(..., timeout=...)` pattern) — referenced as the precedent collector-loop pattern for `HasCollector` implementations

</canonical_refs>

<specifics>
## Specific Ideas

- Module categories table (feature / support / linked) with UI/schema/example columns — see design doc "Module Categories" section
- Capability Protocol code stubs (`HasAPIRoutes`, `HasUIPage`, `HasEventSubscriptions`, `HasCollector`, `DeviceLookupInterface`) and the `ModuleManifest` Pydantic model shown verbatim in the design doc — planner should reproduce these signatures exactly, not reinvent equivalents

</specifics>

<deferred>
## Deferred Ideas

- Notifications module implementation — explicitly out of scope this phase, deferred to Phase 5.2
- A real linked/third-party module (e.g. Jellyfin) — deferred to v2
- Postgres-level grant enforcement of schema isolation — convention/code-review only for now; revisit if multi-tenant or multi-DB-user scale is ever needed

</deferred>

<scope_fence>
## Scope Fence

**Out of scope for this phase:**
- Building or wiring the Notifications module (Phase 5.2)
- Shipping any real linked/third-party module (v2)
- Enforcing schema boundaries via Postgres grants/roles
- Changing the `EventBus`'s underlying pub/sub mechanics (D-10 — carried over unchanged; only the module-loading/contract layer around it is new)

</scope_fence>

<risk_summary>
## Risk Summary

- **Known dependency wrinkle (accepted trade-off):** Security's existing success criterion #4 ("alert delivery handled once notifications exist") and Dual-Mode's auto-degrade-and-notify criterion both implicitly wait on Notifications, which is now Phase 5.2/7. Those criteria stay open until that phase closes — accepted in exchange for prioritizing the module-platform foundation and device-identification quality first.
- This phase rewrites working code (Devices/Traffic/Security retrofit), not just adds new code — higher regression risk than Phases 1-4; plans should include explicit before/after behavior parity checks for retrofitted endpoints.

</risk_summary>

---

*Phase: 05-plugin-system-notifications (directory name predates the pivot; phase content is "Module Platform Foundation" per ROADMAP.md)*
*Context gathered: 2026-06-21 via ADR Ingest Express Path*
