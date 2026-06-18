---
phase: 02-device-registry-discovery
plan: 03
subsystem: frontend
tags: [svelte5, sveltekit, shadcn-svelte, device-dashboard, ui-vertical-slice]

# Dependency graph
requires:
  - phase: 02-01
    provides: GET /api/devices (list, unknown-tagged), POST /api/devices (register), POST /api/devices/{identity_id}/merge — all auth-gated REST endpoints this plan wires to
provides:
  - "/dashboard" live device card grid with summary banner, sorted unknown-first
  - DeviceCard.svelte (registered/unknown variants per UI-SPEC anatomy)
  - RegisterDialog.svelte and MergeDialog.svelte (modal forms wired to the registry API)
  - frontend/src/lib/api.ts listDevices/registerDevice/mergeDevice typed client functions
affects: [phase-2-verification, future-dashboard-enhancements]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Device cards composed from existing shadcn-svelte primitives (Card, Badge, Button) rather than hand-rolled markup"
    - "Dialogs share a single page-level selectedIdentityId state, set by whichever card action (Register/Merge) was clicked"
    - "Hand-rolled formatRelativeTime helper (4 granularities) instead of pulling in dayjs/date-fns, per RESEARCH.md Don't Hand-Roll guidance"
    - "bits-ui Select.Value imported directly (not re-exported from ui/select/index.ts) for placeholder/selected-label display in Select triggers"

key-files:
  created:
    - frontend/src/lib/components/DeviceCard.svelte
    - frontend/src/lib/components/RegisterDialog.svelte
    - frontend/src/lib/components/MergeDialog.svelte
  modified:
    - frontend/src/lib/api.ts
    - frontend/src/routes/dashboard/+page.svelte

key-decisions:
  - "Used bits-ui's Select.Value (imported directly from 'bits-ui', not via the project's ui/select/index.ts re-exports) inside SelectTrigger to render the placeholder/selected label — the project's existing index.ts didn't re-export it and adding a wrapper component wasn't worth the indirection for two call sites"
  - "Card grid de-dup key uses device.id + a unknown/registered suffix since unknown identity ids and registered device ids are drawn from separate tables and could theoretically collide"

patterns-established:
  - "Pattern: page-level dialogs (not per-card) driven by a single selected-identity state, reused for any future per-item-action dialog on this dashboard"

requirements-completed: [DISC-02, DISC-03, DISC-04]

# Metrics
duration: 18min
completed: 2026-06-18
---

# Phase 2 Plan 3: Dashboard Device Card Grid + Register/Merge Dialogs Summary

**`/dashboard` now renders a live, sorted device card grid from `GET /api/devices` with a summary banner and fully wired Register/Merge dialogs — completing the user-visible vertical slice for Phase 2's discovery and registry backend.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-06-18T19:33:33Z
- **Completed:** 2026-06-18T19:37:37Z
- **Tasks:** 2
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments
- Extended `frontend/src/lib/api.ts` with typed `listDevices`/`registerDevice`/`mergeDevice` wrappers matching the existing `apiGet`/`apiPost` shape
- Built `DeviceCard.svelte` rendering both registered and unknown card variants exactly per UI-SPEC anatomy (icon/name/status-dot for registered; dashed warning border + badge + Register/Merge buttons for unknown), with a 9-entry `DeviceType` → Lucide icon map and an accessible `sr-only` Online/Offline label so status isn't color-only
- Built `RegisterDialog.svelte` (name/owner/type/trusted form, calls `registerDevice`) and `MergeDialog.svelte` (target-device picker with irreversible-merge confirmation copy baked into the dialog body, calls `mergeDevice`) — both composed from existing `Dialog`/`Select`/`Input`/`Label`/`Button` shadcn-svelte primitives, following the exact try/catch/finally loading/error pattern from `setup/+page.svelte`
- Wired `frontend/src/routes/dashboard/+page.svelte` to fetch devices on mount, render a summary banner ("N devices · M unknown", M in warning color), and a CSS grid of cards sorted unknown-first; both dialogs live once at the page level, driven by a shared `selectedIdentityId` state set by whichever card's action button was clicked; successful register/merge re-fetches the device list in place with no page reload
- `npm run build` and `npx svelte-check` both pass with zero errors across both tasks

## Task Commits

Each task was committed atomically:

1. **Task 1: API client extension + DeviceCard component** - `4337046` (feat)
2. **Task 2: Register/Merge dialogs + dashboard wiring** - `7dc1512` (feat)

## Files Created/Modified
- `frontend/src/lib/api.ts` - added `listDevices`, `registerDevice`, `mergeDevice`
- `frontend/src/lib/components/DeviceCard.svelte` - registered/unknown card variants, `formatRelativeTime` helper, `sr-only` status text
- `frontend/src/lib/components/RegisterDialog.svelte` - Register form dialog wired to `registerDevice`
- `frontend/src/lib/components/MergeDialog.svelte` - Merge picker dialog wired to `mergeDevice`, destructive-adjacent outline submit button
- `frontend/src/routes/dashboard/+page.svelte` - summary banner + sorted card grid, dialog state wiring, in-place re-fetch on success

## Decisions Made
- `bits-ui`'s `Select.Value` is imported directly (`import { Select as SelectPrimitive } from 'bits-ui'`) inside both dialogs' `SelectTrigger`, since the project's `ui/select/index.ts` re-exports don't include a `SelectValue` wrapper — avoided adding a new wrapper component for two call sites.
- Card grid `{#each}` keys use `device.id + (unknown ? '-unknown' : '-registered')` since unknown (DiscoveredIdentity) and registered (Device) rows are drawn from separate DB tables/id sequences and could theoretically share numeric ids.

## Deviations from Plan

None - plan executed exactly as written. Both tasks match the plan's `<action>` specifications, including exact function signatures, copy strings, color/border treatments, and dialog wiring via shared `selectedIdentityId`.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- The full Phase 2 vertical slice (DISC-01 through DISC-04) is now complete end-to-end: backend fusion/registry API (Plan 01) + real DHCP/mDNS capture (Plan 02) + this dashboard UI (Plan 03).
- Manual UAT checkpoint remains per VALIDATION.md's Manual-Only Verifications table: load `/dashboard` against the live backend, confirm unknown devices show dashed border + badge + sorted to top, and confirm Register/Merge actions function end-to-end. This was not exercised in this automated execution pass (no live backend/browser session available) — recommend exercising it during `/gsd-verify-work` or before phase close.
- No blockers for phase completion.

## Self-Check: PASSED

All claimed files exist and all claimed commits are present in git history (verified below).
