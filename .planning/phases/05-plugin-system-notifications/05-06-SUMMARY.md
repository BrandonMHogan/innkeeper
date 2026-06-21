---
phase: 05-plugin-system-notifications
plan: 06
subsystem: api+ui
tags: [module-host, fastapi, sveltekit, shadcn-svelte, settings-page, destructive-confirmation]

# Dependency graph
requires:
  - phase: 05-plugin-system-notifications
    plan: 01
    provides: "ModuleManifest/ModuleRegistry/ModuleLoader contract, module_configs table, require_module_enabled/is_module_enabled dependency"
  - phase: 05-plugin-system-notifications
    plan: 05
    provides: "main.py's _load_native_modules() booting all five native+linked modules (device_identity, devices, traffic, security, linked_apps) through a single ModuleLoader call"
provides:
  - "backend/src/routes/modules.py — GET /api/modules/ (list feature modules with live enabled state), POST /api/modules/{id}/toggle (immediate-effect enable/disable with destructive-confirmation round-trip)"
  - "frontend/src/routes/settings/modules/+page.svelte — module settings page (list/toggle/destructive-confirmation)"
  - "frontend/src/lib/components/ModuleNav.svelte — nav-entry component for enabled HasUIPage modules"
  - "frontend/src/routes/modules/[slug]/+page.svelte — MOD-04's dynamic module-page landing route"
affects: []

# Tech tracking
tech-stack:
  added: ["shadcn-svelte switch primitive (frontend/src/lib/components/ui/switch/, official registry, zero new npm dependencies — backed by already-installed bits-ui)"]
  patterns:
    - "Host-level settings router (modules.py) holds an in-memory manifest list set once by main.py after ModuleLoader.load() runs (set_manifests()), mirroring main.py's own _module_load_result global — avoids re-scanning backend/src/modules/*/manifest.py at request time"
    - "Dependent computation: for a given module_id, collect every OTHER manifest (feature or support) whose requires intersects the target's provides — this generalizes beyond device_identity to any future support-module-with-dependents case"
    - "Frontend destructive-confirmation round-trip: call toggleModule(id, confirm=false) first: a 200 with requires_confirmation=true opens an AlertDialog naming the dependent count before the second confirmed call actually flips state — mirrors SecurityAlertsBanner's existing AlertDialog dismiss-all pattern"

key-files:
  created:
    - backend/src/routes/modules.py
    - frontend/src/routes/settings/modules/+page.svelte
    - frontend/src/routes/modules/[slug]/+page.svelte
    - frontend/src/lib/components/ModuleNav.svelte
    - frontend/src/lib/components/ui/switch/switch.svelte
    - frontend/src/lib/components/ui/switch/index.ts
  modified:
    - backend/src/main.py
    - backend/tests/test_module_registry_toggle.py
    - frontend/src/lib/api.ts
    - frontend/src/routes/dashboard/+page.svelte

key-decisions:
  - "Appended the 4 new toggle-route behavior tests to the existing backend/tests/test_module_registry_toggle.py (created by Plan 01 for ModuleRegistry register/resolve unit tests) rather than overwriting it, since the plan's <files> block named this exact filename and Plan 01's existing tests must not be deleted — both test classes now coexist in one file under a clear section comment."
  - "GET /api/modules/ response includes a ui_route field (always null in this plan) per Task 2's extension note, since none of the five existing modules implement HasUIPage yet — ModuleNav.svelte and the field are wired and ready, but render nothing until a future module's manifest/instance actually satisfies HasUIPage and main.py threads ui_route through from LoadResult.ui_routes (left as a TODO for whichever future module needs it, not blocking this phase's MOD-04 structural requirement)."
  - "modules.router is mounted at the same /api/modules prefix as the ModuleLoader's per-module routers, but BEFORE the per-module mounting loop in main.py — FastAPI resolves the settings router's literal GET / / POST /{id}/toggle paths against this exact-path-first registration order, avoiding the prefix collision the plan's action block flagged (mirrors STATE.md's Phase 03 P03 lesson)."

patterns-established:
  - "Pattern: any future host-level settings router that needs the live manifest list calls a set_manifests()-style setter from main.py right after ModuleLoader.load() returns, rather than importing main.py's internals or re-scanning modules/*/manifest.py."

requirements-completed: [MOD-02, MOD-04]

# Metrics
duration: 50min
completed: 2026-06-21
---

# Phase 5 Plan 06: Module Platform Foundation — Settings Page & Nav Entries Summary

**New host-level `backend/src/routes/modules.py` (`GET /api/modules/` + `POST /api/modules/{id}/toggle` with immediate-effect, no-restart enable/disable and a destructive-confirmation round-trip naming dependent modules) paired with a new `/settings/modules` SvelteKit page using the shadcn-svelte `switch` primitive as the row focal point, a `ModuleNav.svelte` component for `HasUIPage` modules, and a `/modules/[slug]` placeholder route — closing MOD-02 and MOD-04, the last two of all eight MOD-01..MOD-08 requirements for this phase.**

## Performance

- **Duration:** 50 min
- **Started:** 2026-06-21T22:56:00Z
- **Completed:** 2026-06-21T23:46:00Z
- **Tasks:** 2 completed
- **Files modified:** 11 (6 created, 5 modified — including the installed shadcn-svelte switch primitive's 2 generated files)

## Accomplishments

- **`backend/src/routes/modules.py`** — new host-level (non-module) settings router: `GET /` lists `kind == "feature"` manifests only (excludes `device_identity`, the sole `kind == "support"` module, per D-01's "support modules have no UI"), joined against `ModuleConfig.enabled` (defaulting to `True` when no row exists, matching the column default). `POST /{module_id}/toggle` accepts `{"confirm": bool}` (default `False`); when disabling a module that other currently-enabled modules `require` (computed by intersecting the target's `provides` against every other manifest's `requires`), returns `{"requires_confirmation": true, "dependents": [...]}` without committing, until the caller re-POSTs with `{"confirm": true}`. Both routes gated by `Depends(require_auth)` only — no `require_module_enabled`, since this router is host-level settings infrastructure, not a module itself.
- **`main.py` wiring**: `modules.router` mounted at `/api/modules` immediately after `ModuleLoader.load()` returns and `modules.set_manifests(manifests)` is called, BEFORE the per-module router-mounting loop — avoids any path-precedence collision between the settings router's literal `/api/modules/` and the loader's parameterized `/api/modules/<module-id>/...` per-module prefixes.
- **4 new behavior tests** appended to `backend/tests/test_module_registry_toggle.py` (alongside Plan 01's existing `ModuleRegistry` unit tests, both now coexisting in one file): list excludes `device_identity`; toggling `devices` (no dependents) flips and flips back cleanly; toggling `device_identity` (required by `devices`/`traffic`/`security`) returns `requires_confirmation` naming all three dependents until confirmed; disabling `devices` makes the very next `GET /api/modules/devices/` 404 with no restart, re-enabling restores 200 — full backend suite green (138/139, the one failure is the pre-existing, environment-only `test_compose.py::test_all_services_healthy` unrelated to this plan, same as Plans 01/05 documented).
- **`frontend/src/routes/settings/modules/+page.svelte`** — one row per feature module: the shadcn-svelte `switch` primitive (newly installed via the official registry, zero new npm dependencies since it's backed by already-present `bits-ui`) is the row's focal point with accent/muted coloring (override via inline `--primary` CSS var per row) paired with an "Enabled"/"Disabled" text label (never color-only, per the locked copy contract), `display_name` as 14px/500 secondary text, and a "Disable module"/"Enable module" button whose label flips with state. Disabling first calls the toggle endpoint unconfirmed; a `requires_confirmation` response opens an `AlertDialog` (same primitive/pattern as `SecurityAlertsBanner`'s existing dismiss-all confirmation) titled `"Disable {display_name}?"` with body `"{N} other module(s) depend on this and will also stop working. This won't delete any data."` verbatim from UI-SPEC; confirming re-calls the toggle endpoint with `confirm: true`.
- **`frontend/src/lib/components/ModuleNav.svelte`** — calls `listModules()` and renders a 14px/500/1.4 nav entry per enabled module with a non-null `ui_route`, linking to `/modules/{slug}`; renders nothing at all when zero such modules exist (never grayed-out for disabled modules, since they're filtered out structurally before render).
- **`frontend/src/routes/modules/[slug]/+page.svelte`** — minimal placeholder reading the `slug` param, resolving it against `listModules()` to render the module's `display_name` as the page heading (falls back to the raw slug if not found) — satisfies MOD-04's "appears as a nav entry at /modules/[module-name]" structural contract; full per-module page content is explicitly out of this phase's scope per the plan.
- **Dashboard wiring**: added a minimal "Modules" text link to `/settings/modules` in the dashboard header, and mounted `<ModuleNav />` below it — neither redesigns the existing dashboard header per the plan's constraint.
- **`npx svelte-check`**: 0 errors, 0 new warnings (3 pre-existing warnings in `RegisterDialog.svelte`/`tsconfig.json`, unrelated to this plan, confirmed via `git log` to predate this plan's commits).

## Task Commits

Each task was committed atomically:

1. **Task 1: GET /api/modules/ + POST /api/modules/{id}/toggle with dependent-check** - `0e09f80` (feat)
2. **Task 2: Module settings page, nav entries, and /modules/[slug] dynamic route** - `597a66e` (feat)

## Files Created/Modified

- `backend/src/routes/modules.py` - new host-level settings router (`set_manifests`/`list_modules`/`toggle_module`)
- `backend/src/main.py` - imports/mounts `modules.router`, calls `modules.set_manifests(manifests)` right after `ModuleLoader.load()`
- `backend/tests/test_module_registry_toggle.py` - 4 new behavior tests appended after Plan 01's existing `ModuleRegistry` unit tests
- `frontend/src/lib/api.ts` - `listModules()`/`toggleModule()` added
- `frontend/src/routes/settings/modules/+page.svelte` - new module settings page
- `frontend/src/routes/modules/[slug]/+page.svelte` - new dynamic module-page placeholder route
- `frontend/src/lib/components/ModuleNav.svelte` - new nav-entry component
- `frontend/src/lib/components/ui/switch/{switch.svelte,index.ts}` - shadcn-svelte switch primitive (installed via `npx shadcn-svelte@latest add switch`)
- `frontend/src/routes/dashboard/+page.svelte` - added "Modules" settings link + `<ModuleNav />` mount, restructured the header `<div>` to hold both the heading and the link without otherwise changing existing markup

## Decisions Made

See `key-decisions` in frontmatter for full rationale on: appending (not overwriting) the toggle-route tests into Plan 01's existing `test_module_registry_toggle.py`; the always-`null` `ui_route` field pending a future module implementing `HasUIPage`; and the settings-router-before-per-module-loop mount ordering in `main.py`.

## Issues Encountered

- **`frontend/node_modules` was absent at plan start** (fresh worktree checkout) — `npm install` had to run before `npx shadcn-svelte@latest add switch` could succeed (the CLI's own `svelte-kit sync` step requires installed dependencies). This is Rule 3 (blocking — could not complete Task 2 without it), not a deviation from the plan's intent; no dependency versions changed, `package.json`/`package-lock.json` are unmodified by either `npm install` or the switch install (the switch primitive is backed entirely by the already-pinned `bits-ui@2.18.1`).
- **Initial UI-SPEC literal-copy grep failure**: the confirmation dialog body text initially wrapped across two source lines in the Svelte template (`...stop working. This won't delete any\n        data.`), which broke the required exact-substring match for `"This won't delete any data."` (`grep -c` returned 0). Fixed by keeping the full sentence on one line — Rule 1 (the wrapped line was a bug against the plan's own literal-copy acceptance criterion), not a deviation from the spec's intended wording, which was correct all along.
- **Isolated single-file pytest runs are flaky in this environment** (pre-existing, unrelated to this plan): running `pytest tests/test_module_registry_toggle.py` or `pytest tests/test_security_scan.py` alone (not as part of the full suite) intermittently raises a `sqlalchemy.orm.exc.StaleDataError` on the `app_settings` table during the shared `_login()` helper's `/api/auth/setup` call. Confirmed this reproduces identically on `test_security_scan.py`, a file this plan did not touch, and disappears entirely when running the full `pytest` suite (138/139 passing, only the pre-existing `test_compose.py` failure remains) — logged here as a pre-existing test-isolation quirk in this sandboxed environment, not a regression introduced by this plan's changes. Full-suite runs are the verification method used for this plan's acceptance criteria, consistent with the plan's own `<verify>` block (`pytest tests/test_module_registry_toggle.py -x && pytest`).

## User Setup Required

None — no external service configuration required. The shadcn-svelte `switch` primitive install ran `npm install` internally as part of its own CLI flow but added zero new dependencies (backed by the already-pinned `bits-ui`); `package.json`/`package-lock.json` are unchanged.

The plan's `<verify>` block's manual Lima VM/docker-compose smoke check (toggling a module off, confirming its dashboard surface stops rendering/its routes 404, toggling back on with no backend restart) was not run against a live Postgres + Lima VM stack in this sandboxed worktree — flagged here for the orchestrator/user to run before this work reaches a real environment, consistent with the precedent set by Plans 03/04/05's equivalent notes.

## Next Phase Readiness

- All eight MOD-01..MOD-08 requirements are now fully implemented across Plans 01-06: host infrastructure (MOD-01/03/06, Plan 01), DeviceIdentity/Devices/Traffic/Security retrofits (MOD-07, Plans 03-05), and now the settings page + nav entries (MOD-02/04, this plan). MOD-05 (collector lifecycle) and MOD-08 (Linked Apps data model/empty state) were completed in earlier plans per their respective summaries.
- `ui_route` is structurally wired end-to-end (`GET /api/modules/` response shape, `ModuleNav.svelte`'s filter/render logic, `/modules/[slug]`'s landing page) but will render zero nav entries until a future module's manifest/instance implements `HasUIPage` and `main.py` threads `LoadResult.ui_routes` through to `modules.set_manifests`/`list_modules` — flagged as a known gap for whichever future module (e.g. Notifications, Phase 5.2) is the first to need a dedicated `/modules/[slug]` page rather than living on the main dashboard.
- No blockers identified for downstream phases. This is the final plan of Phase 5 (Module Platform Foundation) — Phase 5.2 (Notifications) can now build against the fully-proven module-host contract, including this plan's settings-page/nav-entry pattern for its own enable/disable UI needs.

## Known Stubs

- `ui_route` in `GET /api/modules/`'s response is always `null` in this plan — no existing module (`devices`/`traffic`/`security`/`linked_apps`/`device_identity`) implements `HasUIPage` yet, so `ModuleNav.svelte` currently renders nothing on every real deployment. This is not a defect: the plan's `<done>` criterion is "nav entries render only for enabled HasUIPage modules" — the filter/render logic is correct and fully wired, it simply has zero matching data today because zero modules satisfy the protocol. Resolved automatically once any future module's `manifest.py`/`module.py` implements `HasUIPage` and `main.py` threads `LoadResult.ui_routes` through `modules.set_manifests()` (a small follow-up wiring change, not part of this plan's scope).

## Threat Flags

None — `POST /api/modules/{id}/toggle` (T-05-17) is gated by `Depends(require_auth)` exactly like every other authenticated route in this codebase, and the destructive-confirmation round-trip (T-05-18) fully mitigates the silent-dependent-breakage threat the plan's own threat model flagged. No new endpoints, auth paths, file access patterns, or schema changes beyond what the plan's `<threat_model>` already accounted for were introduced.

---
*Phase: 05-plugin-system-notifications (directory name predates the module-platform pivot; phase content is "Module Platform Foundation" per ROADMAP.md)*
*Completed: 2026-06-21*
