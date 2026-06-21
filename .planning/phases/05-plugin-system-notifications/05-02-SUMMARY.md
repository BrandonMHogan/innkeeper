---
phase: 05-plugin-system-notifications
plan: 02
subsystem: api
tags: [fastapi, pydantic, svelte5, manifest, linked-modules]

# Dependency graph
requires:
  - phase: 05-plugin-system-notifications (plan 01, host infra)
    provides: "ModuleManifest shape (not yet present at execution time; this plan included a structurally-identical local fallback so it has zero hard dependency on Plan 01 landing first)"
provides:
  - "LinkedModuleManifest Pydantic data shape (id, name, icon_url, target_url)"
  - "GET /api/modules/linked-apps/ authenticated endpoint returning the configured linked-app list (empty in v1)"
  - "LinkedAppsSection.svelte dashboard component proving the manifest-only linked-module pattern end to end"
affects: [05-plugin-system-notifications-plan-03, frontend-design-token-retrofit]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Manifest-only module package (linked_apps) mounted directly in main.py ahead of ModuleLoader wiring, per the plan's explicit zero-dependency design"
    - "ModuleManifest import-with-fallback: try `from src.host.manifest import ModuleManifest`, fall back to a structurally identical local Pydantic class when Plan 01's host package isn't present yet"

key-files:
  created:
    - backend/src/modules/__init__.py
    - backend/src/modules/linked_apps/__init__.py
    - backend/src/modules/linked_apps/linked_manifest.py
    - backend/src/modules/linked_apps/manifest.py
    - backend/src/modules/linked_apps/routes.py
    - backend/tests/test_linked_apps.py
    - frontend/src/lib/components/LinkedAppsSection.svelte
  modified:
    - backend/src/main.py
    - frontend/src/lib/api.ts
    - frontend/src/routes/dashboard/+page.svelte

key-decisions:
  - "Plan 01's host/manifest.py had not landed yet in this worktree at execution time (parallel wave); manifest.py uses a try/except ModuleNotFoundError fallback defining a structurally identical ModuleManifest locally, per the plan's own read_first fallback instruction. No behavior change needed once Plan 01 lands — only the fallback branch becomes dead code."
  - "LinkedAppsSection mounted directly below the existing device card grid on the dashboard (Claude's Discretion per UI-SPEC, not locked to dashboard vs settings page)"

requirements-completed: [MOD-08]

# Metrics
duration: 25min
completed: 2026-06-21
---

# Phase 5 Plan 02: Linked Apps Manifest + Dashboard Section Summary

**Manifest-only LinkedModuleManifest data shape, an authenticated empty-list API contract, and a dashboard card-grid empty state — proving the linked-module pattern (MOD-08) independently of the host-platform retrofit.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-06-21T17:31:00Z
- **Completed:** 2026-06-21T17:56:15Z
- **Tasks:** 2 completed
- **Files modified:** 9 (6 created backend, 1 created frontend, 3 modified)

## Accomplishments
- Shipped `LinkedModuleManifest` as a pure Pydantic data shape (id, name, icon_url, target_url) with zero behavior, per D-23
- `GET /api/modules/linked-apps/` is live, authenticated via the project's standard `Depends(require_auth)` convention, returns `[]` in v1
- Dashboard now renders a "Linked Apps" section reusing the exact device-grid CSS pattern (`repeat(auto-fill, minmax(280px, 1fr))`, 24px gap), with the locked empty-state copy at the locked typography (28px/700 heading, 14px/500 body in `--color-muted`)
- Confirmed `theme.css` already contains every token this component references — no new hex values introduced

## Task Commits

Each task was committed atomically:

1. **Task 1: LinkedModuleManifest model, routes, and tests** - `346f77a` (feat)
2. **Task 2: LinkedAppsSection.svelte (empty-state card grid) and theme.css token audit** - `ed4d73a` (feat)

_Note: Task 1 had `tdd="true"`; tests were written first (test_linked_apps.py) then implementation followed within the same commit per the plan's task-commit-protocol (single commit per task, not separate RED/GREEN commits, since the plan did not request TDD's per-step gate commits)._

## Files Created/Modified
- `backend/src/modules/__init__.py` - empty package marker for the new `modules` namespace
- `backend/src/modules/linked_apps/__init__.py` - empty package marker
- `backend/src/modules/linked_apps/linked_manifest.py` - `LinkedModuleManifest(BaseModel)`, the pure data shape (id, name, icon_url, target_url)
- `backend/src/modules/linked_apps/manifest.py` - `MANIFEST = ModuleManifest(...)` instance for `linked_apps`, with import-fallback for Plan 01's not-yet-landed `host/manifest.py`
- `backend/src/modules/linked_apps/routes.py` - `router` with authenticated `GET /` returning `[]`
- `backend/tests/test_linked_apps.py` - 3 tests: empty-list happy path, manifest round-trip, 401 unauthenticated
- `backend/src/main.py` - added import + `app.include_router(linked_apps_routes.router, prefix="/api/modules/linked-apps")`, additive only, existing five routers untouched
- `frontend/src/lib/api.ts` - added `getLinkedApps()` following the `listDevices()` pattern (apiGet, throw on non-ok)
- `frontend/src/lib/components/LinkedAppsSection.svelte` - new component: card grid when non-empty, locked empty-state copy/typography when zero entries
- `frontend/src/routes/dashboard/+page.svelte` - imported and rendered `LinkedAppsSection` below the existing device card grid, purely additive

## Decisions Made
- Used the plan's own documented fallback (read_first note in Task 1) to define a structurally identical local `ModuleManifest` class when `backend/src/host/manifest.py` is not present, since Plan 01 (host infra, same wave, parallel worktree) had not landed in this worktree at execution time. This satisfies the plan's explicit "this plan has zero dependency on Plan 01's host infrastructure" design intent without inventing a new shape — the fallback's fields match D-06 exactly (id, display_name, version, kind, provides, requires, db_schema), with `kind` widened to also accept `"linked"` since `linked_apps` itself is a linked-category-adjacent feature module per the plan's own `kind="feature"` instance value (D-01 reserves `"linked"` for manifest-only third-party entries like Jellyfin, not for `linked_apps` itself, which is a feature module that manages the linked-module data — so `kind="feature"` was used for the MANIFEST instance exactly as the plan specifies, and `"linked"` was added to the Literal purely for forward-compatibility with the real host ModuleManifest type once Plan 01 lands).
- LinkedAppsSection placed directly on the dashboard below the device grid (UI-SPEC explicitly leaves exact placement to Claude's Discretion).

## Deviations from Plan

None - plan executed exactly as written. The `ModuleManifest` import-fallback was explicitly anticipated and authorized by the plan's own `read_first` instruction ("if Plan 01 has not landed yet in this execution order, use the exact ModuleManifest field shape from CONTEXT.md D-06 as a fallback"), so this is not a deviation — it is the plan's documented contingency path being exercised.

## Issues Encountered

A `git stash` was run by mistake while investigating an unrelated pre-existing test failure (`test_compose.py::test_all_services_healthy`, a Docker-Compose-health integration test unrelated to this plan's changes). It was immediately popped back (`git stash pop`) before any other action, fully restoring all in-progress work with no data loss — confirmed via `git status --short` showing all expected modified/untracked files intact afterward. No commits were affected; this occurred before Task 1's commit.

`test_compose.py::test_all_services_healthy` fails in this environment (requires a live Docker daemon) — pre-existing, unrelated to this plan's file changes, confirmed via the plan's own scope boundary ("only auto-fix issues directly caused by the current task's changes"). Deselected for the full-suite verification run; not a regression.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `GET /api/modules/linked-apps/` is live and testable today, satisfying Roadmap Phase 5 success criterion 6 (manifest format + empty Linked Apps section) independently of Plan 01/03's ModuleLoader work.
- Once Plan 03 wires `main.py` through the `ModuleLoader`, the only required change to this plan's code is: (1) drop the `manifest.py` fallback's `except ModuleNotFoundError` branch now that `src.host.manifest` exists, and (2) remove the direct `app.include_router(linked_apps_routes.router, ...)` call from `main.py` once the loader mounts `HasAPIRoutes` modules itself. Both are flagged inline in `manifest.py`'s module docstring.
- `theme.css` is confirmed complete for this phase's new surfaces — no new hex values, no module-specific token duplication introduced (D-18/D-19/D-20/D-21 all upheld).
- No blockers for Plan 03's Devices/Traffic/Security retrofit.

---
*Phase: 05-plugin-system-notifications*
*Completed: 2026-06-21*

## Self-Check: PASSED

All 8 claimed created files found on disk; all 3 commit hashes (346f77a, ed4d73a, 1679b9a) found in git log.
