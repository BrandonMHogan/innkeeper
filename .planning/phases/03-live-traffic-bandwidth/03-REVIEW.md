---
phase: 03-live-traffic-bandwidth
reviewed: 2026-06-20T00:19:51Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - backend/alembic/versions/0004_traffic_flows.py
  - backend/pyproject.toml
  - backend/src/main.py
  - backend/src/models/device_mac_history.py
  - backend/src/models/traffic_flow.py
  - backend/src/routes/capture.py
  - backend/src/routes/traffic.py
  - backend/src/services/bandwidth_source.py
  - backend/src/services/discovery.py
  - backend/src/services/domain_grouping.py
  - backend/src/services/traffic_broadcaster.py
  - backend/tests/conftest.py
  - backend/tests/test_bandwidth_aggregates.py
  - backend/tests/test_bandwidth_query.py
  - backend/tests/test_domain_grouping.py
  - backend/tests/test_mac_history.py
  - backend/tests/test_traffic_destinations.py
  - backend/tests/test_traffic_stream.py
  - capture/capture.py
  - capture/requirements.txt
  - capture/traffic_sniff.py
  - frontend/src/lib/api.ts
  - frontend/src/lib/components/BandwidthHistoryChart.svelte
  - frontend/src/lib/components/DestinationsBreakdown.svelte
  - frontend/src/lib/components/LiveTrafficFeed.svelte
  - frontend/src/lib/components/NetworkBandwidthChart.svelte
  - frontend/src/lib/components/ui/scroll-area/scroll-area-scrollbar.svelte
  - frontend/src/lib/components/ui/scroll-area/scroll-area.svelte
  - frontend/src/lib/components/ui/tabs/tabs-content.svelte
  - frontend/src/lib/components/ui/tabs/tabs-list.svelte
  - frontend/src/lib/components/ui/tabs/tabs-trigger.svelte
  - frontend/src/lib/components/ui/tabs/tabs.svelte
  - frontend/src/lib/utils.ts
  - frontend/src/routes/dashboard/+page.svelte
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-20T00:19:51Z
**Depth:** standard
**Files Reviewed:** 33
**Status:** issues_found

## Summary

This phase wires up the live-traffic SSE pipeline, historical bandwidth/destinations queries, and the supporting capture/ingest layer. The two previously-identified bugs (traffic_flows' NOT-NULL-on-composite-PK dst_port gotcha, and LiveTrafficFeed's bad each-block keys) are both correctly fixed in the reviewed code, with regression tests covering the dst_port fix (`test_traffic_ingest_coerces_null_dst_port_to_zero`).

Two new BLOCKER-class issues were found during this review, both in the same spirit as the bugs already fixed:

1. **`update_snapshot_loop` has no exception handling around `_compute_snapshot`** — any transient DB error permanently kills the live-feed background task for the life of the process, with no visible symptom other than a live feed that silently stops updating.
2. **`BandwidthHistoryChart.svelte`'s time-range inputs produce timezone-naive strings** that get sent straight to the backend's `datetime` query parameters the moment a user actually uses the "any time range" control — this is the literal feature TRAF-02 promises and the date pickers are the only UI surface for it.

In addition, the ingest route performs multiple non-atomic commits per rollup (deviating from the plan's "commit once" instruction), the `TrafficFlow.dst_port` model still incorrectly declares `nullable=True` despite the DB enforcing NOT NULL via the composite PK (the code works around this with a sentinel, but the model's own type annotation is now a documented lie), and there are a few cases of backend JSON payloads vs. frontend TS interfaces drifting (none currently crash-level, but the LiveTrafficFeed protocol/port fields are typed `string | number | null` against an actual `int`/`int | None` backend shape, which is the exact class of bug flagged for special attention in this review).

## Critical Issues

### CR-01: `update_snapshot_loop` has no exception handling — a single DB hiccup permanently kills the live feed

**File:** `backend/src/services/traffic_broadcaster.py:94-104`
**Issue:** The background loop that recomputes `_latest_snapshot` every 7 seconds has no `try`/`except` around `_compute_snapshot(db)` or around opening the session. Any transient error — a dropped DB connection, a query timeout, a deadlock, a momentary Postgres restart — propagates out of the `while` loop and terminates the `asyncio.Task` permanently. `main.py`'s lifespan never restarts it. From that point on, `get_latest_snapshot()` returns whatever `_latest_snapshot` was last set to, forever, and `/api/traffic/stream` keeps serving that stale snapshot to every connected/reconnecting client with no error surfaced anywhere (the SSE endpoint itself never errors — it only reads the in-memory dict). The live feed (TRAF-01, the headline feature of this phase) silently and permanently stops updating until the whole API process is restarted.
**Fix:**
```python
async def update_snapshot_loop(stop_event: asyncio.Event, session_factory) -> None:
    global _latest_snapshot
    while not stop_event.is_set():
        try:
            async with session_factory() as db:
                _latest_snapshot = await _compute_snapshot(db)
        except Exception as exc:  # noqa: BLE001 - one bad tick must never kill the loop
            print(f"[traffic_broadcaster] snapshot refresh failed: {exc}")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=7)
        except asyncio.TimeoutError:
            pass
```

### CR-02: `BandwidthHistoryChart.svelte`'s datetime-local inputs break the "any time range" query once a user touches them

**File:** `frontend/src/lib/components/BandwidthHistoryChart.svelte:25-26,83,87`
**Issue:** `start`/`end` are initialized to full ISO8601 UTC strings (`defaultStart()`/`defaultEnd()` use `.toISOString()`), but they are bound directly (`bind:value`) to `<Input type="datetime-local">` elements. The native `datetime-local` input's value format is `YYYY-MM-DDTHH:mm` (or `:ss`) with **no timezone/offset information** and in the browser's **local** time, not UTC. The instant a user actually exercises the time-range control — the only UI for TRAF-02's "any time range" requirement — `start`/`end` are overwritten with a timezone-naive, local-time string. That string is then sent verbatim as the `start`/`end` query parameters to `GET /api/traffic/bandwidth/{device_id}`, which FastAPI parses as a naive `datetime`. Comparing a naive datetime against `BandwidthMetric.time` (a `timestamptz` column, always timezone-aware) is ambiguous at best (asyncpg silently treats naive datetimes as the session's local/UTC convention, which will not match the user's actual browser-local intent) and at worst returns wrong/empty results with no error — the query never gets the date range the user actually selected.
**Fix:** Convert the `datetime-local` value to an explicit UTC ISO8601 string before sending it to the API, e.g.:
```ts
function toIsoUtc(localValue: string): string {
  return new Date(localValue).toISOString();
}
// in load():
const res = await getDeviceBandwidth(currentDeviceId, toIsoUtc(currentStart), toIsoUtc(currentEnd));
```
Keep the raw naive string bound to the `<Input>` for editing UX, but always convert through `new Date(...)` (which interprets the naive datetime-local string as browser-local time and produces a correct epoch) before constructing the query string.

## Warnings

### WR-01: Ingest route performs multiple non-atomic commits per rollup, contradicting the plan's "commit once" design

**File:** `backend/src/routes/capture.py:209-239`, `backend/src/services/bandwidth_source.py:42-50`
**Issue:** `ingest_traffic` calls `await db.commit()` once after adding all `TrafficFlow` rows (line 229), then loops over `bytes_by_mac` calling `PassiveCaptureBandwidthSource().write_rollup(...)` per distinct MAC — and `write_rollup` itself calls `await db.commit()` internally (bandwidth_source.py:50). For a rollup with N distinct device MACs, this produces 1 + N separate commits per POST instead of the single atomic commit the plan specified ("Commit once after all rows are added/written," 03-03-PLAN.md Task 1). If the process crashes or the DB connection drops between commits, `TrafficFlow` rows for the interval are durably written but some/all `BandwidthMetric` rollups for that same interval are lost — a partial-write state that a single transaction would have avoided.
**Fix:** Either commit once at the end of `ingest_traffic` (move the bandwidth writes to use `db.add(...)` without committing inside `write_rollup`, and commit once after the loop), or accept multiple commits but document why per-mac atomicity isn't required. Given `BandwidthSource.write_rollup`'s docstring describes it as a swappable interface other adapters will implement, the cleanest fix is to drop the internal `await db.commit()` from `PassiveCaptureBandwidthSource.write_rollup` and let the caller control transaction boundaries — committing once after both the flow-row loop and the bandwidth-write loop complete.

### WR-02: `TrafficFlow.dst_port` model annotation contradicts the database's actual constraint

**File:** `backend/src/models/traffic_flow.py:31`
**Issue:** `dst_port: Mapped[int | None] = mapped_column(Integer, nullable=True, primary_key=True)` declares the column nullable, but because it's part of the composite primary key, Postgres silently forces it `NOT NULL` regardless of the `nullable=True` annotation — this is exactly the bug already found and fixed at the call sites (`capture/traffic_sniff.py` and `backend/src/routes/capture.py` both coerce `None` to `0` before writing). The model itself, however, still asserts the column accepts `NULL`, which is false for any row that ever reaches the database. Anyone reading the model in isolation (without reading the two ingest call sites' comments) would reasonably write code that passes `None` directly and get a runtime `IntegrityError` on Postgres — the SQLite test fixture won't catch this because SQLite doesn't enforce NOT-NULL-via-PK the same way.
**Fix:** Change the annotation to `Mapped[int]` with `nullable=False`, and add a code comment at the model (not just at the call sites) documenting the 0-sentinel convention for portless protocols:
```python
# dst_port uses 0 as a sentinel for protocols without a port (ICMP, etc.) —
# this column cannot actually be NULL despite the absence of a port, because
# it is part of the composite primary key and Postgres enforces NOT NULL on
# every PK column. See backend/src/routes/capture.py's ingest_traffic for
# the None -> 0 coercion performed before any row reaches this model.
dst_port: Mapped[int] = mapped_column(Integer, nullable=False, primary_key=True)
```

### WR-03: `LiveTrafficFeed.svelte`'s TypeScript interfaces type-mismatch the actual backend payload for `protocol`/`dst_port`

**File:** `frontend/src/lib/components/LiveTrafficFeed.svelte:16-24`, `backend/src/services/traffic_broadcaster.py:75-85`
**Issue:** The frontend's `ActiveConnection` interface types `protocol?: string | number | null` and `dst_port?: number | null`. The actual backend payload (`_compute_snapshot`'s `active_connections` list) always sends `protocol` as a raw integer (`flow.protocol`, an IANA protocol number like `6` for TCP or `17` for UDP — never a string) and `dst_port` as an integer that is never actually `null` once written (the ingest route coerces `None` to `0` before persisting, so every `TrafficFlow.dst_port` read back from the DB is `0` or a real port, never `null`). The `string` half of the `protocol` union type is dead/incorrect, and the component's render logic (`{conn.protocol ?? ''}{conn.dst_port ? `:${conn.dst_port}` : ''}`) silently renders nothing for the protocol number `0`... and because `dst_port` is never actually `0`-or-null in a way the UI distinguishes, ICMP-like flows (`dst_port === 0`) will never show a port suffix, which is correct behavior by accident rather than design — the type signature doesn't tell a future maintainer any of this. This is exactly the backend-payload-vs-frontend-interface drift class of bug flagged for this review (TypeScript interfaces are author-asserted, not validated against the real payload).
**Fix:** Tighten the interface to match the actual emitted shape and add a comment documenting the 0-sentinel convention so a future reader doesn't need to cross-reference the backend:
```ts
interface ActiveConnection {
  device_mac: string;
  dst_ip: string;
  dst_hostname?: string | null;
  dst_port: number; // 0 is the portless-protocol sentinel (e.g. ICMP), never null
  protocol: number; // IANA protocol number (6=TCP, 17=UDP, 1=ICMP, ...), never a string
  bytes: number;
}
```

### WR-04: No test exercises the `_MAX_FLOWS_PER_ROLLUP` DoS-mitigation boundary (T-03-08)

**File:** `backend/src/routes/capture.py:89,206-207`, `backend/tests/test_traffic_stream.py`
**Issue:** The ingest route explicitly bounds rollup size at 5000 flows per the threat model's T-03-08 mitigation, and rejects oversized payloads with a 413. No test in `test_traffic_stream.py` (or anywhere else) exercises this boundary — there is no test asserting that a payload with >5000 flows returns 413, nor one confirming exactly 5000 is accepted. A documented security control with zero test coverage is a silent regression risk: a future refactor could change or remove the check without any test failing.
**Fix:** Add a test such as:
```python
async def test_traffic_ingest_rejects_oversized_rollup(client):
    payload = {
        "interval_start": "2026-06-19T12:00:00Z",
        "interval_end": "2026-06-19T12:00:07Z",
        "flows": [
            {"src_mac": "aa:bb:cc:dd:ee:ff", "dst_ip": "1.1.1.1", "dst_port": 443, "protocol": 6, "bytes": 1, "dst_hostname": None}
            for _ in range(5001)
        ],
    }
    response = await client.post("/api/capture/traffic", json=payload)
    assert response.status_code == 413
```

### WR-05: Network-bandwidth bucket tests can't detect bucket-misalignment bugs

**File:** `backend/tests/test_bandwidth_aggregates.py:28-55`
**Issue:** All three view tests (`daily`/`weekly`/`monthly`) compute `total_tx = sum(bucket["bytes_tx"] for bucket in body["buckets"])` and assert it equals the sum of *all* seeded rows' `bytes_tx`. Since every seeded row falls into some bucket regardless of bucket width or alignment, this assertion passes even if the bucketing logic groups rows into the wrong buckets, uses the wrong bucket width, or even collapses everything into a single bucket — it only proves no rows were dropped or double-counted, not that the daily/weekly/monthly distinction actually does anything. Given `network_bandwidth`'s SQLite fallback path computes buckets via `epoch_days // bucket_days` with a hardcoded `30`-day "month" (not calendar-month-aware, unlike the real Postgres `time_bucket('1 month', ...)` continuous aggregate it's meant to approximate for tests), a bucket-width or off-by-one bug in that fallback would not be caught by any current test.
**Fix:** Assert on the actual bucket boundaries/count, not just the cross-bucket total, e.g. assert the number of distinct buckets returned for `daily` differs from `monthly` given the seeded spread (1, 1+2h, 10, 40 days ago), and that each bucket's `bytes_tx` matches the expected per-bucket sum (e.g. the `daily` view should show the two same-day seed rows—-1d and -1d-2h—-merged into one bucket).

## Info

### IN-01: `device_mac_history`'s FK has no `ON DELETE` policy

**File:** `backend/alembic/versions/0004_traffic_flows.py:39-47`
**Issue:** `sa.ForeignKeyConstraint(["device_id"], ["devices.id"])` has no `ondelete` clause. There is currently no device-delete route, so this is dormant today, but if device deletion is ever added, deleting a `Device` row with existing `DeviceMacHistory` rows will raise an `IntegrityError` rather than cascading or nulling, with no code path currently anticipating that.
**Fix:** When a device-delete feature is added, decide explicitly between `ondelete="CASCADE"` (delete history with the device) or handling the FK violation in the delete route; not a blocker for this phase since no delete path exists yet.

### IN-02: `_compute_snapshot` fetches all in-window `TrafficFlow` rows before bounding in Python

**File:** `backend/src/services/traffic_broadcaster.py:46-54,84`
**Issue:** The query `select(TrafficFlow).where(TrafficFlow.time >= window_start)` has no SQL-level `LIMIT` — it fetches every flow row written in the last 5 minutes, then only slices to `_MAX_ACTIVE_CONNECTIONS` (100) after the full result set is already in memory. T-03-12's accepted disposition assumes "the backend's own snapshot cap... bound[s] both data volume," but the cap is applied after the unbounded fetch, not before it — on a busy LAN with thousands of distinct 5-tuples per 7s window (within the 5000-per-rollup ingest cap, but accumulating across multiple rollups inside the 5-minute window), this query can still fetch tens of thousands of rows every 7 seconds. Out of v1 performance scope per review instructions, but worth flagging since the threat model's own mitigation text implies the cap happens earlier than it does.
**Fix:** Add `.limit(_MAX_ACTIVE_CONNECTIONS)` to the flow-rows query used for `active_connections`, and a separate aggregate query (`GROUP BY device_mac, SUM(bytes)`) for `top_talkers` instead of summing in Python over the same unbounded fetch.

### IN-03: `DestinationsBreakdown.svelte`'s error copy is copy-pasted from the bandwidth chart and doesn't describe destinations

**File:** `frontend/src/lib/components/DestinationsBreakdown.svelte:65-70`
**Issue:** The error state renders "Couldn't load bandwidth history" / "Something went wrong loading this chart..." — both strings describe a chart failure, not a destinations-list failure, and this component has no chart at all. This is a leftover from copying `BandwidthHistoryChart.svelte`'s error block.
**Fix:**
```svelte
<p ...>Couldn't load destinations</p>
<p ...>Something went wrong loading this device's destination breakdown. Try again, or check the server logs if this keeps happening.</p>
```

### IN-04: `LiveTrafficFeed`'s live-region text goes blank (not announced) in the terminal error state

**File:** `frontend/src/lib/components/LiveTrafficFeed.svelte:90-92`
**Issue:** The `aria-live="polite"` span's text is `connectionState === 'live' ? 'Live' : connectionState === 'reconnecting' ? 'Reconnecting…' : ''` — when `connectionState === 'error'`, this span renders an empty string. The error state is visually conveyed via the separate `AlertTriangle` card below, but the one designated `aria-live` element (per the component's own UI-SPEC-driven accessibility contract) announces nothing when the feed transitions to its terminal error state, which is arguably the single most important state change to announce to an assistive-technology user.
**Fix:**
```svelte
{connectionState === 'live' ? 'Live' : connectionState === 'reconnecting' ? 'Reconnecting…' : 'Unavailable'}
```

---

_Reviewed: 2026-06-20T00:19:51Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
