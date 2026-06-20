---
phase: 04-security
plan: 04
status: complete
---

# Plan 04-04 Summary: Frontend Security Surfaces

## What Was Built

Phase 4's frontend surfaces per `04-UI-SPEC.md`: a good/warning/critical
security badge and Scan/Re-scan button on every registered `DeviceCard`, a
new `ScanResultDialog` showing the flagged-port breakdown sourced from Plan
04-02's `GET /api/security/scan/{device_id}` route, and a new
`SecurityAlertsBanner` above the dashboard's existing Phase 2 summary
banner. Introduces the project's first `--color-good` token and first
`tooltip`/`alert`/`alert-dialog` shadcn-svelte component installs.

### Task 1 — shadcn-svelte components, `--color-good` token, `api.ts` extension
- Installed official shadcn-svelte `tooltip`, `alert`, `alert-dialog`
  components via `npx shadcn-svelte@latest add tooltip alert alert-dialog`.
  The CLI's interactive overwrite prompt for the pre-existing `button`
  component was confirmed byte-identical after regeneration (`git diff`
  empty) — no customization lost.
- `frontend/src/lib/styles/theme.css` — added `--color-good: #22c55e;`
  directly below `--color-warning`/`--color-warning-fg`, brand-alias-only
  (not mapped into `.dark`/`@theme inline`), matching the Phase 2
  `--color-warning` precedent.
- `frontend/src/lib/api.ts` — added `triggerScan(deviceId)`,
  `listAlerts()`, `ackAlert(alertId)`, `ackAllAlerts()`,
  `getScanResult(deviceId)`, all following the existing `apiGet`/`apiPost`
  wrapper convention.

### Task 2 — DeviceCard badge/scan flow, ScanResultDialog, SecurityAlertsBanner, dashboard wiring
- `frontend/src/lib/components/DeviceCard.svelte` — registered-device
  branch gained: a `security_status`-keyed Badge (`Good`/`Warning`/
  `Critical`, defaulting to `Good` when null/undefined per D-06) next to
  the existing online-status dot; a "Last scanned {relative time}" /
  "Not yet scanned" line; a Scan/Re-scan `Button` with local `scanning`
  state wrapped in an `aria-live="polite"` region, showing `Scanning…`
  while in flight and restoring its prior label plus an inline
  "Scan couldn't complete" message if the delegated `onScan` call
  throws/rejects; a "View results" text-button (shown once a device has a
  prior scan) wired to a new optional `onShowResults` prop — an addition
  beyond the plan's literal action text, needed to give the
  `ScanResultDialog` a concrete open affordance per the UI-SPEC's
  Interaction States ("opens on demand... clicking a 'view results'
  affordance").
- `frontend/src/lib/components/ScanResultDialog.svelte` (new) — props
  `{ device, open }`; on `open` becoming true, calls `getScanResult(device.id)`
  and renders per-port rows (`{port} ({service name})` + risky/unexpected/
  expected flag copy) or the `Not yet scanned` empty state when
  `ports.length === 0`; never reads port detail off the `device` prop
  itself. Local port→service-name lookup table covers the ports referenced
  in `port_rules.py`'s `RISKY_PORTS`/`EXPECTED_PORTS` plus common
  streaming-device ports (AirPlay/Chromecast).
- `frontend/src/lib/components/SecurityAlertsBanner.svelte` (new) — on
  mount, calls `listAlerts()`; renders nothing when the list is empty (no
  "all clear" banner); otherwise renders a `Security Alerts` heading, one
  row per alert (type-specific icon `aria-hidden="true"`, Copywriting
  Contract message text, relative timestamp, per-row dismiss `×` calling
  `ackAlert(id)` immediately with no confirmation), and — only at 2+
  alerts — a "Dismiss all" control that opens an `AlertDialog` confirming
  the exact Copywriting Contract title/body/buttons before calling
  `ackAllAlerts()`.
- `frontend/src/routes/dashboard/+page.svelte` — imports and renders
  `<SecurityAlertsBanner />` as the first element inside `<main>` after
  `<LiveTrafficFeed />`, above the existing Phase 2 summary-banner div
  (alerts banner → summary banner → device grid stacking order per
  D-12/UI-SPEC Layout). Added `handleScan(deviceId)` (calls `triggerScan`,
  then polls `loadDevices()` every 5s for up to 60s or until
  `last_scanned_at` changes) and `handleShowResults(deviceId)` (opens
  `ScanResultDialog` for the selected device), both passed into every
  `DeviceCard` render call alongside the existing `onRegister`/`onMerge`.

## Verification

- `cd frontend && npx svelte-check --tsconfig ./tsconfig.json` — 0 errors,
  3 pre-existing warnings (RegisterDialog `state_referenced_locally` x2,
  `node` type-lib lookup), 2 files with problems — both pre-existing,
  unrelated to this plan's changes.
- Grep-verified: `DeviceCard.svelte` contains all three literal badge
  labels (`'Good'`, `'Warning'`, `'Critical'`); `ScanResultDialog.svelte`
  calls `getScanResult(` and contains zero references to
  `device.security_status`/`device.open_ports`/`device.ports` (port detail
  is never derived from the device-list payload).
- Manually confirmed `SecurityAlertsBanner.svelte`'s top-level
  `{#if alerts.length > 0}` guard (no DOM when empty), `aria-hidden="true"`
  on alert-type icons, `aria-label="Dismiss alert"` on per-row dismiss, and
  the `alerts.length >= 2` gate on the "Dismiss all" control.
- No automated component-test runner exists in this frontend (no
  vitest/jest configured; `package.json` only defines `dev`/`build`/
  `preview`/`check` scripts) — the plan's 11 TDD behavior cases were
  verified by direct code inspection against the implementation plus
  `svelte-check`, consistent with how this frontend has been verified in
  every prior phase.

## Deviations From Plan

- **Added `onShowResults` prop to `DeviceCard.svelte` (not in the plan's
  file list or action text).** The plan specifies `ScanResultDialog` and
  dashboard-level `scanDialogOpen`/`selectedScanDeviceId` state but never
  specifies what UI element opens it for an already-scanned device — the
  UI-SPEC's Interaction States table defers this to "a dedicated 'view
  results' affordance... left to executor discretion." Implemented as a
  small underlined text-button next to the "Last scanned" line, shown only
  when `last_scanned_at` is non-null, calling a new optional
  `onShowResults?(deviceId)` prop wired to the dashboard's
  `handleShowResults`. Without this, the dialog component would exist but
  have no way for a user to open it for a device with an existing scan
  result (distinct from triggering a brand-new scan via the Scan/Re-scan
  button).
- **shadcn-svelte CLI overwrote the existing `button` component during
  install** (the CLI's "decide individually" flow defaulted to "Yes,
  overwrite" for `button` when navigating the prompt). Verified via
  `git diff` that the regenerated file is byte-identical to the
  pre-existing one — no customization was lost, no separate fix needed.

## Key Decisions / Notes for Downstream Plans

- `--color-good` is brand-alias-only (consumed via inline `style=`
  attributes), not mapped into the shadcn `.dark`/`@theme inline` token
  layers — matches the plan's explicit instruction and the existing
  `--color-warning` precedent.
- The alerts banner and per-device security badge are independent reads of
  the same backend signals (per UI-SPEC Layout) — dismissing an alert in
  `SecurityAlertsBanner` does not touch `DeviceCard`'s `security_status`
  badge; no shared client-side state was introduced between them.
- `handleScan`'s poll loop is a plain `setInterval` scoped to the
  dashboard page (not persisted across navigation) — acceptable for this
  phase's scope (single-page dashboard, no routing away mid-scan
  considered).
- Phase 4 (SEC-01..04) is now fully implemented across all four plans
  (04-01 schema/services, 04-02 backend routes, 04-03 capture-container
  scanning, 04-04 this plan's frontend surfaces). No further Phase 4 plans
  remain.

## Self-Check: PASSED
