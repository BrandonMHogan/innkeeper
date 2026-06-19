# Phase 3: Live Traffic + Bandwidth - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the first traffic/bandwidth data pipeline Innkeeper has ever had: a passive, capture-engine-based flow accountant that attributes bytes to devices, tracks per-device destination (domain/IP) breakdown, and feeds both a live SSE dashboard view and historical per-device/network-wide bandwidth charts. No router adapter exists yet (UniFi adapter is Phase 7) — this phase is the no-router-access fallback path, designed so a future router-counter source can plug in later without a rewrite. No security scoring, no blocking/control, no DPI/payload inspection.

</domain>

<decisions>
## Implementation Decisions

### Capture Mechanism & Volume Handling
- **D-01:** The capture container sniffs raw data-plane packets (in addition to its existing ARP/DHCP/mDNS sniffing) and aggregates bytes **in-process over a short interval (~5-10s)** before POSTing a rollup to the API — never POSTs per-packet. This is required: a busy LAN at one-POST-per-packet would overwhelm a single FastAPI instance.
- **D-02:** The new high-volume traffic-sniff loop uses **dpkt** for packet parsing, not Scapy — Scapy stays for the existing low-volume ARP/DHCP/mDNS loops. This follows CLAUDE.md's explicit guidance (Scapy is ~130x slower than dpkt for bulk parsing; don't parse every packet in Scapy) and was a deliberate choice to keep CPU/power usage low on a low-power always-on server.
- **D-03:** Capture scope is **internet-bound (WAN) traffic only** — device-to-device LAN traffic (e.g. laptop → NAS, smart-home chatter) is explicitly out of scope. This is what "bandwidth usage" and "what is this device talking to" mean in practice for this product, and keeps capture volume and dashboard noise down.
- **D-04:** Flow tracking key is a **5-tuple** (src device MAC/IP, dst IP, dst port, protocol) — gives accurate per-destination and per-connection breakdown without full per-payload DPI, matching CLAUDE.md's "flow-level accounting is sufficient" stance.

### Storage Shape
- **D-05:** Per-destination flow data is stored in a **new TimescaleDB hypertable (`traffic_flows`: time, device, dst_ip, dst_port, protocol, bytes)**, separate from the existing `bandwidth_metrics` hypertable (which stays the simple per-device-per-time rollup feeding TRAF-02/04 charts). The capture aggregator writes/POSTs to both from the same in-memory per-interval flow table each cycle.
- **D-06:** `traffic_flows` rows are **never auto-deleted by default**, same policy as `bandwidth_metrics` and consistent with PROJECT.md's "never auto-delete" constraint — no special-case expiration carve-out for flow-level detail.
- **D-07:** The bandwidth-writing path is designed behind a **swappable source interface** (one source today — passive capture; same interface a future Phase 7 UniFi adapter writes through) — matches PROJECT.md's existing adapter-pattern decision for router integrations and avoids a rework when the router adapter arrives.

### Destination Resolution (Domain vs IP)
- **D-08:** Domain names for destinations come from **passive DNS sniffing** — the capture engine also watches DNS query/response traffic and builds an IP→domain cache from what devices actually resolved. No active/outbound lookups; consistent with the passive-only philosophy already used for ARP/DHCP/mDNS discovery.
- **D-09:** When no DNS-sniffed domain exists for an IP, the dashboard **shows the raw IP** as a fallback — no active reverse-DNS lookup fallback (those are unreliable for cloud/CDN IPs and would be the only outbound network call in an otherwise fully passive system).
- **D-10:** Subdomains are **grouped by registered domain** in the per-device destination breakdown (e.g. `www.netflix.com`, `api.netflix.com`, `ipv4.netflix.com` all roll up under "netflix.com") — matches how people actually think about "what is this device talking to." Raw per-hostname detail can still exist in the underlying flow data; grouping is a presentation/aggregation concern.

### Live Feed Semantics
- **D-11:** SSE pushes update on the **same ~5-10s cadence as the capture aggregation window** (D-01) — no sub-second/per-packet push. This is a deliberate consequence of choosing aggregated capture for load reasons; "live" means "updates every few seconds," not "instant per-packet."
- **D-12:** "Top talkers" ranks devices over a **rolling window (e.g. last 5 minutes)**, not a pure instant snapshot — smooths bursty traffic so the ranking doesn't flicker/reorder on every update.
- **D-13:** A **single global SSE channel** (one `/api/traffic/stream`-style endpoint) pushes the full live snapshot (all devices' current state) every interval; the frontend filters client-side for per-device views. No per-device SSE subscriptions — simpler backend, appropriate for a single-household dashboard's scale.

### Claude's Discretion
- Exact aggregation interval within the ~5-10s range (D-01/D-11)
- Exact rolling-window length for "top talkers" within the few-minutes range (D-12)
- Internal schema/column naming for `traffic_flows` and the source-interface abstraction (D-05/D-07), as long as the shapes above hold
- Whether daily/weekly/monthly bandwidth charts (TRAF-04) are served from raw `bandwidth_metrics` rows or a TimescaleDB continuous aggregate — not discussed in depth; left to researcher/planner to decide based on query performance, given the "never auto-delete" + "any time range" constraints already locked
- How device-MAC-to-current-device-identity resolution works for `traffic_flows`/`bandwidth_metrics` queries, given MAC rotation handled by Phase 2's `IdentityResolver` — not discussed in depth; researcher should reconcile against `identity_resolver.py` and the existing `device_mac`-keyed `bandwidth_metrics` schema
- DNS cache TTL/expiry behavior for the passive IP→domain mapping (D-08)
- Exact registered-domain grouping logic (e.g. public-suffix-list-based vs simple heuristic) for D-10

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements & Roadmap
- `.planning/ROADMAP.md` — Phase 3 section: goal, success criteria (4 items), requirements TRAF-01..04
- `.planning/REQUIREMENTS.md` — Full TRAF-01..04 requirement text; traceability table confirms TRAF-01..04 map to Phase 3 only
- `.planning/PROJECT.md` — Key Decisions table: adapter pattern for router integrations (informs D-07), SSE over WebSockets decision, "never auto-delete" data policy, TimescaleDB for time-series

### Prior Phase Context
- `.planning/phases/02-device-registry-discovery/02-CONTEXT.md` — D-01..D-06 identity fusion (`IdentityResolver`, hostname/MAC fallback); relevant to the deferred MAC-rotation reconciliation noted in Claude's Discretion above
- `.planning/STATE.md` — Blockers/Concerns: "TimescaleDB schema is expensive to change later — settle during early planning" (flagged since Phase 1/3)

### Technology Stack
- `CLAUDE.md` — Scapy vs dpkt guidance (Scapy for discovery, dpkt for bulk/hot-path parsing — directly informs D-02); SSE via sse-starlette; TimescaleDB 2.27 hypertable pattern; "flow-level accounting is sufficient, avoid full DPI" guidance (informs D-04)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `capture/capture.py` — Existing ARP/DHCP/mDNS sniff-and-POST pattern (Scapy `sniff()`, `httpx.post()`, shared `stop_event` for SIGTERM handling). The new traffic-sniff loop should follow the same container-stays-source-of-truth, POST-to-API shape, but with dpkt instead of Scapy and in-process aggregation instead of per-packet POST (D-01/D-02).
- `backend/src/models/bandwidth.py` — `BandwidthMetric` model already exists as a TimescaleDB hypertable (`bandwidth_metrics`: time, device_mac, bytes_rx, bytes_tx), created in Phase 1 specifically so this phase wouldn't need an expensive migration rewrite. Schema is locked per its own docstring — Phase 3 populates it, doesn't redesign it. Note it's keyed by `device_mac` directly, not `identity_key` — see Claude's Discretion above re: MAC rotation.
- `backend/alembic/versions/0001_initial.py` — Shows the `create_hypertable()` migration pattern already used for `bandwidth_metrics`; the new `traffic_flows` hypertable (D-05) should follow the same migration shape.
- `backend/src/routes/capture.py` — Existing `/api/capture/arp`, `/api/capture/dhcp`, `/api/capture/mdns` ingest routes (loopback/gateway-trusted-only, Pydantic payload models). A new `/api/capture/traffic` route (or similar) for the aggregated rollup POST should follow this same trust-boundary pattern.
- `backend/src/services/identity_resolver.py` — `IdentityResolver` / `MDNS_PLACEHOLDER_MAC` pattern for resolving raw observations to stable device identity; relevant when reconciling `device_mac` in bandwidth/flow tables against the fused device registry.

### Established Patterns
- Capture container never writes to the DB directly — always POSTs to the API (Phase 1 D-06, reaffirmed in Phase 2). The new traffic loop maintains this.
- Ingest routes trust only loopback + runtime-detected default gateway (`_detect_default_gateway()` in `capture.py`) — reuse this trust model for the new traffic ingest route.
- No SSE infrastructure exists yet anywhere in the codebase — this phase introduces it from scratch (sse-starlette is in CLAUDE.md's recommended stack but not yet a dependency).

### Integration Points
- New traffic-sniff loop plugs into the same capture container (`capture/capture.py`) alongside the existing ARP/DHCP/mDNS threads.
- New `traffic_flows` hypertable and the bandwidth source-interface (D-05/D-07) sit between capture ingest and both the SSE live-feed endpoint and the historical-chart query endpoints.
- Frontend dashboard (`frontend/src/routes/dashboard/+page.svelte`) currently has no traffic/bandwidth UI at all — this phase adds the live feed view and per-device/network-wide charts.

</code_context>

<specifics>
## Specific Ideas

- User's stated priority for this phase: "pick up the information in the best way, can work with direct access to router, or fallback to using other methods when direct router access is not available. power, manageability, easy to maintain and build on." This is the lens behind D-01, D-02, D-03, and D-07 — favor low CPU/power overhead, reuse of established patterns, and a design that doesn't need to be thrown away when the UniFi router adapter (Phase 7) arrives.
- User confirmed mid-discussion that the recommended technical approach (aggregated passive capture, dpkt, 5-tuple flows, separate flow table, swappable source interface) matched their intent when it was explained in plain terms — no pushback once the "why" was laid out.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. The fourth originally-presented gray area ("Bandwidth-to-device binding & chart aggregation" — MAC-rotation reconciliation for `bandwidth_metrics`/`traffic_flows` queries, and raw-rows-vs-continuous-aggregates for daily/weekly/monthly charts) was not separately discussed; it's carried into Claude's Discretion above rather than dropped, since it's an implementation detail researcher/planner can resolve against existing Phase 2 identity-fusion code and TimescaleDB best practices.

</deferred>

---

*Phase: 3-Live Traffic + Bandwidth*
*Context gathered: 2026-06-19*
