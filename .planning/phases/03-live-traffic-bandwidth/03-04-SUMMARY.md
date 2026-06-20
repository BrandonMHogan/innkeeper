---
phase: 03-live-traffic-bandwidth
plan: 04
subsystem: ui
tags: [svelte, sse, eventsource, layerchart, shadcn-svelte, tabs, scroll-area, bandwidth, traffic]

# Dependency graph
requires:
  - phase: 03-live-traffic-bandwidth (plan 03)
    provides: GET /api/traffic/stream (SSE), GET /api/traffic/bandwidth/{device_id}, GET /api/traffic/bandwidth/network, GET /api/traffic/devices/{id}/destinations
provides:
  - LiveTrafficFeed.svelte — SSE-driven Top Talkers + Active Connections live feed with Live/Reconnecting/Error states
  - BandwidthHistoryChart.svelte — per-device bandwidth chart with adjustable start/end time range
  - DestinationsBreakdown.svelte — per-device destination list sorted descending by bytes
  - NetworkBandwidthChart.svelte — Daily/Weekly/Monthly tabbed network-wide bandwidth chart
  - Dashboard integration: LiveTrafficFeed mounted independently of device-picker/tab navigation lifecycle
affects: [phase-04-security, future-phases-touching-dashboard-or-traffic-ui]

# Tech tracking
tech-stack:
  added: ["layerchart@1.0.13", "shadcn-svelte tabs primitive", "shadcn-svelte scroll-area primitive"]
  patterns:
    - "Native browser EventSource (no client library) for SSE consumption, withCredentials:true for session cookie"
    - "formatBytes() shared helper in utils.ts — single source of truth for B/KB/MB/GB formatting across all traffic/bandwidth components"
    - "Consecutive-error-count heuristic to distinguish transient EventSource reconnect from terminal failure (3+ consecutive onerror without an intervening snapshot = error state)"
    - "Each-block keys derived from explicit composite identifiers (e.g. `${device_id}-${i}`) rather than implicit string-concat on a field that may be undefined"

key-files:
  created:
    - frontend/src/lib/components/LiveTrafficFeed.svelte
    - frontend/src/lib/components/BandwidthHistoryChart.svelte
    - frontend/src/lib/components/DestinationsBreakdown.svelte
    - frontend/src/lib/components/NetworkBandwidthChart.svelte
    - frontend/src/lib/components/ui/scroll-area/
    - frontend/src/lib/components/ui/tabs/
  modified:
    - frontend/src/lib/api.ts
    - frontend/src/lib/utils.ts
    - frontend/src/routes/dashboard/+page.svelte
    - frontend/package.json
    - backend/src/routes/capture.py
    - capture/traffic_sniff.py
    - backend/tests/test_traffic_stream.py

key-decisions:
  - "layerchart@1.0.13 pinned after Task 0 package-legitimacy checkpoint approval"
  - "traffic_flows' composite PK forces dst_port to NOT NULL at the Postgres level regardless of the SQLAlchemy model's nullable=True — portless protocols (ICMP/IGMP) must coerce None to a 0 sentinel at both the capture source (traffic_sniff.py) and the API ingest trust boundary (capture.py), since the swappable BandwidthSource interface (D-07) means any future source could hit the same gap"
  - "Svelte {#each} block keys must never rely on implicit string-concat of a possibly-undefined field plus a number — `undefined + number` evaluates to NaN (not string concatenation) in JS, collapsing every row to the same NaN key and crashing with each_key_duplicate; keys must be built from explicit template-literal composites of verified-present fields"
  - "SSE snapshot payload field names (device_id/device_name for top_talkers, device_mac for active_connections) must be read from the actual backend response shape, not assumed from the plan's prose — frontend types drifted from the real payload on first pass and were only caught by live browser verification, not svelte-check"

requirements-completed: [TRAF-01, TRAF-02, TRAF-03, TRAF-04]

duration: 102min
completed: 2026-06-19
---

# Phase 3 Plan 4: Live Traffic + Bandwidth UI Summary

**SSE-driven live traffic feed, per-device bandwidth history chart, destinations breakdown, and Daily/Weekly/Monthly network-wide chart — wired into the dashboard and confirmed against real WAN traffic in a live Lima-VM stack, including two bug fixes (dst_port NULL-PK coercion, SSE field-name/each-key crash) found and fixed during that live verification.**

## Performance

- **Duration:** 102 min (18:17–19:59 across 5 commits)
- **Started:** 2026-06-19T18:17:59-04:00
- **Completed:** 2026-06-19T19:59:34-04:00
- **Tasks:** 3 planned (all auto) + 2 deviation fix commits surfaced by live manual verification
- **Files modified:** 16 (across frontend components/api/utils + backend capture ingest + capture sniff loop + 1 new test)

## Accomplishments
- Live Traffic feed renders Top Talkers + Active Connections via native `EventSource` against `GET /api/traffic/stream`, with an `aria-live="polite"` Live/Reconnecting/Error indicator and a consecutive-error heuristic to distinguish transient reconnects from terminal failure
- Per-device Bandwidth History chart (LayerChart) with a user-adjustable arbitrary start/end time range, loading/empty/error states
- Per-device Destinations breakdown list, server-sorted descending by bytes
- Network-Wide Bandwidth chart with Daily/Weekly/Monthly tabs (shadcn-svelte `Tabs`), re-querying on tab change
- Dashboard wiring: `LiveTrafficFeed` mounted once with a lifecycle independent of device-picker/tab navigation elsewhere on the page, per UI-SPEC's explicit "SSE connection does not get torn down by unrelated navigation" requirement
- Live-verified end-to-end against a real Lima-VM docker-compose stack with live WAN traffic: ingest writing real `traffic_flows` rows, SSE emitting periodic full snapshots with correct device-name resolution, all four query endpoints returning real data, and all four dashboard chart/feed surfaces rendering correctly in-browser with zero console errors after the two fixes below

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies, API client functions, live traffic feed** - `4c44ba4` (feat)
2. **Task 2: Bandwidth history chart + destinations breakdown** - `6cc9cc7` (feat)
3. **Task 3: Network-wide bandwidth chart, dashboard wiring, device-picker integration** - `2a6f963` (feat)

**Deviation fix commits (found during live manual verification, see below):**

4. `17024ad` (fix) — coerce null `dst_port` to 0 sentinel for portless protocols
5. `1485de9` (fix) — correct SSE payload field names + each-block keys in LiveTrafficFeed

**Plan metadata:** (this commit)

## Files Created/Modified
- `frontend/src/lib/components/LiveTrafficFeed.svelte` - SSE-driven live feed (top talkers, active connections, connection-state indicator)
- `frontend/src/lib/components/BandwidthHistoryChart.svelte` - per-device bandwidth chart with adjustable time range
- `frontend/src/lib/components/DestinationsBreakdown.svelte` - per-device destination list
- `frontend/src/lib/components/NetworkBandwidthChart.svelte` - Daily/Weekly/Monthly network-wide chart
- `frontend/src/lib/components/ui/scroll-area/*` - shadcn-svelte scroll-area primitive
- `frontend/src/lib/components/ui/tabs/*` - shadcn-svelte tabs primitive
- `frontend/src/lib/api.ts` - `openTrafficStream`, `getDeviceBandwidth`, `getNetworkBandwidth`, `getDeviceDestinations`
- `frontend/src/lib/utils.ts` - shared `formatBytes()` helper
- `frontend/src/routes/dashboard/+page.svelte` - mounts all four new sections in UI-SPEC's specified order, with device-picker-driven re-query for chart/destinations independent of the live feed's mount lifecycle
- `frontend/package.json` - `layerchart@1.0.13`
- `backend/src/routes/capture.py` - coerce null `dst_port` to 0 sentinel at the ingest trust boundary
- `capture/traffic_sniff.py` - coerce null `dst_port` to 0 sentinel at the capture source
- `backend/tests/test_traffic_stream.py` - regression test for portless-protocol ingest

## Decisions Made
- `layerchart@1.0.13` pinned after Task 0's package-legitimacy checkpoint was explicitly approved by the user
- `traffic_flows`' composite primary key forces `dst_port` to `NOT NULL` at the Postgres level even though the SQLAlchemy model declares `nullable=True` — fixed at both the capture source and the API ingest boundary so any future `BandwidthSource` implementation (per D-07's swappable-source contract) doesn't reintroduce the same gap
- Svelte `{#each}` keys must be built from explicit, verified-present fields via template literals — never an implicit `field + i` concatenation, since `undefined + number` is numeric addition (`NaN`) in JS, not string concatenation, and produces duplicate keys that crash Svelte's reconciler
- SSE snapshot payload field names were verified against the real backend response during live testing (`device_id`/`device_name` for top talkers, `device_mac` for active connections) rather than trusted from the plan's prose alone

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] dst_port NULL violates traffic_flows composite PK for portless protocols**
- **Found during:** Live manual verification (post-Task-3), first real ICMP packet captured against live WAN traffic
- **Issue:** `traffic_flows`' composite primary key includes `dst_port`; Postgres enforces `NOT NULL` on every PK column regardless of the SQLAlchemy model's `nullable=True` declaration. `dpkt` has no `.dport` for protocols without ports (ICMP/IGMP), so `traffic_sniff.py`'s 5-tuple key carried `None` straight through to the DB, causing a Postgres `IntegrityError` on ingest.
- **Fix:** Coerce `None` to a `0` sentinel for `dst_port` at both the capture source (`capture/traffic_sniff.py`) and the API ingest trust boundary (`backend/src/routes/capture.py`), since the swappable `BandwidthSource` interface (D-07) means any future source could hit the same gap.
- **Files modified:** `backend/src/routes/capture.py`, `capture/traffic_sniff.py`, `backend/tests/test_traffic_stream.py` (new regression test)
- **Verification:** Regression test added; re-verified live against real ICMP/IGMP traffic post-fix — 29 `traffic_flows` rows written including `dst_port=0` sentinel rows
- **Committed in:** `17024ad`

**2. [Rule 1 - Bug] LiveTrafficFeed used nonexistent SSE field names, causing each_key_duplicate crash**
- **Found during:** Live manual verification (post-Task-3), first SSE snapshot received in-browser
- **Issue:** `talker.device` and `conn.device` don't exist on the real SSE snapshot payload — the backend sends `device_id`/`device_name` for `top_talkers` and `device_mac` for `active_connections`. Worse, the `{#each}` block key `talker.device + i` evaluated `undefined + number` as `NaN` (JS numeric addition, not string concatenation), so every Top Talkers row collapsed to the same key, crashing the page with Svelte's `each_key_duplicate` error on the very first snapshot.
- **Fix:** Corrected the `TopTalker`/`ActiveConnection` interfaces to match the real payload shape, and rewrote both each-block keys as explicit template-literal composites (`` `${talker.device_id ?? talker.device_name}-${i}` `` and `` `${conn.device_mac}-${conn.dst_ip}-${i}` ``).
- **Files modified:** `frontend/src/lib/components/LiveTrafficFeed.svelte`
- **Verification:** Re-verified live in-browser — dashboard loads with no console errors, Live Traffic feed renders and updates correctly on every SSE snapshot
- **Committed in:** `1485de9`

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs surfaced only by live verification against real traffic and a real browser, not by svelte-check or unit tests)
**Impact on plan:** Both fixes were necessary for basic correctness — without them, ingest crashed on any portless-protocol packet and the live feed crashed on its very first SSE message. No scope creep; both fixes are scoped exactly to the bug found.

## Issues Encountered
None beyond the two deviations documented above — both were found and resolved during the live manual verification pass itself, which is exactly the purpose of that checkpoint.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness

Phase 3 (Live Traffic + Bandwidth) is now fully complete — all 4 requirements (TRAF-01 through TRAF-04) are implemented, integrated, and live-verified end-to-end against a real running stack with real WAN traffic. This is the last plan in Phase 3; Phase 4 (Security) can begin.

Two gotchas future phases should be aware of (also logged in STATE.md decisions):
1. Any new table with a composite primary key that includes an optional/nullable business field must coerce that field to a sentinel value before insert — Postgres enforces `NOT NULL` on PK columns regardless of the ORM model's `nullable` declaration.
2. Any new Svelte `{#each}` block must use explicit, verified-present fields in its key expression — never an implicit `field + i` string-concat assumption, since `undefined + number` silently produces `NaN` rather than throwing or string-concatenating.

## Self-Check: PASSED

All created files verified present on disk; all 5 commits (4c44ba4, 6cc9cc7, 2a6f963, 17024ad, 1485de9) verified present in git history.

---
*Phase: 03-live-traffic-bandwidth*
*Completed: 2026-06-19*
