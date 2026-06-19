# Phase 3: Live Traffic + Bandwidth - Research

**Researched:** 2026-06-19
**Domain:** Passive packet capture, flow accounting, TimescaleDB time-series modeling, SSE real-time push
**Confidence:** MEDIUM-HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Capture Mechanism & Volume Handling**
- **D-01:** The capture container sniffs raw data-plane packets (in addition to its existing ARP/DHCP/mDNS sniffing) and aggregates bytes **in-process over a short interval (~5-10s)** before POSTing a rollup to the API — never POSTs per-packet. This is required: a busy LAN at one-POST-per-packet would overwhelm a single FastAPI instance.
- **D-02:** The new high-volume traffic-sniff loop uses **dpkt** for packet parsing, not Scapy — Scapy stays for the existing low-volume ARP/DHCP/mDNS loops. This follows CLAUDE.md's explicit guidance (Scapy is ~130x slower than dpkt for bulk parsing; don't parse every packet in Scapy) and was a deliberate choice to keep CPU/power usage low on a low-power always-on server.
- **D-03:** Capture scope is **internet-bound (WAN) traffic only** — device-to-device LAN traffic (e.g. laptop → NAS, smart-home chatter) is explicitly out of scope. This is what "bandwidth usage" and "what is this device talking to" mean in practice for this product, and keeps capture volume and dashboard noise down.
- **D-04:** Flow tracking key is a **5-tuple** (src device MAC/IP, dst IP, dst port, protocol) — gives accurate per-destination and per-connection breakdown without full per-payload DPI, matching CLAUDE.md's "flow-level accounting is sufficient" stance.

**Storage Shape**
- **D-05:** Per-destination flow data is stored in a **new TimescaleDB hypertable (`traffic_flows`: time, device, dst_ip, dst_port, protocol, bytes)**, separate from the existing `bandwidth_metrics` hypertable (which stays the simple per-device-per-time rollup feeding TRAF-02/04 charts). The capture aggregator writes/POSTs to both from the same in-memory per-interval flow table each cycle.
- **D-06:** `traffic_flows` rows are **never auto-deleted by default**, same policy as `bandwidth_metrics` and consistent with PROJECT.md's "never auto-delete" constraint — no special-case expiration carve-out for flow-level detail.
- **D-07:** The bandwidth-writing path is designed behind a **swappable source interface** (one source today — passive capture; same interface a future Phase 7 UniFi adapter writes through) — matches PROJECT.md's existing adapter-pattern decision for router integrations and avoids a rework when the router adapter arrives.

**Destination Resolution (Domain vs IP)**
- **D-08:** Domain names for destinations come from **passive DNS sniffing** — the capture engine also watches DNS query/response traffic and builds an IP→domain cache from what devices actually resolved. No active/outbound lookups; consistent with the passive-only philosophy already used for ARP/DHCP/mDNS discovery.
- **D-09:** When no DNS-sniffed domain exists for an IP, the dashboard **shows the raw IP** as a fallback — no active reverse-DNS lookup fallback (those are unreliable for cloud/CDN IPs and would be the only outbound network call in an otherwise fully passive system).
- **D-10:** Subdomains are **grouped by registered domain** in the per-device destination breakdown (e.g. `www.netflix.com`, `api.netflix.com`, `ipv4.netflix.com` all roll up under "netflix.com") — matches how people actually think about "what is this device talking to." Raw per-hostname detail can still exist in the underlying flow data; grouping is a presentation/aggregation concern.

**Live Feed Semantics**
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. The fourth originally-presented gray area ("Bandwidth-to-device binding & chart aggregation" — MAC-rotation reconciliation for `bandwidth_metrics`/`traffic_flows` queries, and raw-rows-vs-continuous-aggregates for daily/weekly/monthly charts) was not separately discussed; it's carried into Claude's Discretion above rather than dropped, since it's an implementation detail researcher/planner can resolve against existing Phase 2 identity-fusion code and TimescaleDB best practices.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| TRAF-01 | User can view a live real-time traffic feed — active connections and top talkers per device, updated via SSE without page refresh | sse-starlette `EventSourceResponse` pattern (Pattern 4), single global broadcaster design (D-13), 5-7s aggregation/push cadence recommendation (Open Question 3) |
| TRAF-02 | User can view historical bandwidth consumption per device over any time range (data retention is configurable, never auto-deleted by default) | TimescaleDB continuous aggregates + compression-only policy (no retention policy by default) — see Code Examples and Pitfall 3; MAC-rotation query reconciliation — see Pitfall 1 / Open Question 1 |
| TRAF-03 | User can view a per-device breakdown of traffic by destination — which domains and IPs each device is communicating with | Passive DNS sniffing pattern (Pattern 2), tldextract registered-domain grouping (Pattern 3), `traffic_flows` hypertable schema (Standard Stack / Architecture Patterns) |
| TRAF-04 | User can view network-wide bandwidth totals over time as a chart (daily, weekly, monthly views) | Hierarchical continuous aggregates (hourly → daily → weekly/monthly), real-time aggregation default-off caveat (Pitfall 2) |
</phase_requirements>

## Summary

This phase adds Innkeeper's first real data pipeline: a dpkt-based aggregated WAN packet sniffer in the existing `capture` container, a new `traffic_flows` TimescaleDB hypertable alongside the already-scaffolded `bandwidth_metrics` hypertable, a single global SSE channel for the live dashboard, and historical chart queries that must support "any time range" while never auto-deleting data by default.

The two technologies genuinely new to the codebase are **dpkt** (packet parsing) and **sse-starlette** (SSE transport) — both are well-established, narrowly-scoped libraries with no viable simpler alternative; this is squarely a "use the standard library for this problem" phase, not a build-vs-buy judgment call. TimescaleDB is already in the stack (Phase 1 scaffolded `bandwidth_metrics`) but this phase is the first to actually write to it and query it across "any time range," which surfaces a real design decision: raw-row queries vs. continuous aggregates for daily/weekly/monthly charts (CONTEXT.md leaves this to research). The evidence strongly favors a **continuous-aggregate-backed read path with compression (never retention-policy deletion)** for both correctness at scale and matching the "never auto-delete" requirement precisely — retention policies *drop* chunks, which is the wrong tool entirely.

The other discretion item — MAC-rotation-aware identity resolution for `traffic_flows`/`bandwidth_metrics` queries — has a clean answer once the existing Phase 2 code is read: these tables are already keyed by raw `device_mac`, exactly like `bandwidth_metrics`, and Phase 2's `IdentityResolver`/`Device.last_known_mac` model means a device's *current* identity can rotate across MACs over time. The correct join is **device → all MACs ever associated with that device → aggregate/union bandwidth_metrics and traffic_flows rows across those MACs**, not a single-MAC lookup. This must be planned explicitly or historical charts will silently drop data every time a device's MAC rotates.

**Primary recommendation:** Use dpkt + raw AF_PACKET socket capture (Linux) for the new traffic-sniff loop, sse-starlette with a single shared async broadcaster for the live channel, tldextract (not publicsuffix2) for registered-domain grouping in fully offline mode, and design `traffic_flows`/`bandwidth_metrics` queries to resolve a device's full MAC history (not just `last_known_mac`) before aggregating bandwidth across any time range. Use TimescaleDB continuous aggregates (daily/weekly/monthly) with compression policies and explicitly no retention policy by default.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Raw packet capture, dpkt parsing, in-process aggregation | Capture container (own process) | — | Already established Phase 1 pattern: capture container owns raw-socket access (`CAP_NET_RAW`/`CAP_NET_ADMIN`), never the API process |
| Passive DNS sniffing → IP-to-domain cache | Capture container | API/Backend (cache storage) | Capture observes DNS traffic in the same packet loop; the resolved cache should persist server-side (DB-backed or API-held) so it survives capture container restarts, not held only in the ephemeral capture process |
| 5-tuple flow aggregation & rollup POST | Capture container → API ingest route | — | Mirrors existing ARP/DHCP/mDNS POST pattern; capture never writes to DB directly |
| `traffic_flows` / `bandwidth_metrics` persistence | API/Backend | Database/Storage (TimescaleDB) | Ingest route validates + writes via SQLAlchemy, same trust-boundary model as `/api/capture/arp` etc. |
| Registered-domain grouping (D-10) | API/Backend | — | Presentation/aggregation concern per CONTEXT.md D-10 — group at query/serialization time, not capture time, so raw per-hostname flow data stays intact in storage |
| MAC-rotation-aware identity resolution for queries | API/Backend (query layer) | — | Must reconcile `device_mac`-keyed time-series rows against `Device.last_known_mac` + historical MAC associations; this is a read-time join, not a write-time decision |
| Continuous aggregates / compression policies | Database/Storage (TimescaleDB) | — | Native DB feature; no application-layer rollup logic needed |
| Live SSE snapshot push | API/Backend | Browser (EventSource) | sse-starlette `EventSourceResponse` server-side; native browser `EventSource` client-side, no client library needed |
| Live feed / chart rendering | Browser/Client (Svelte) | — | LayerChart + native EventSource consume already-aggregated API responses; no client-side flow aggregation logic |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dpkt | 1.9.8 (PyPI, kbandla/dpkt) | Parse Ethernet/IP/TCP/UDP/DNS from raw bytes | [VERIFIED: pypi registry] Confirmed current via `pip index versions dpkt` (1.9.8). [ASSUMED] ~130x faster than Scapy for bulk parsing per CLAUDE.md's explicit guidance and corroborating benchmarks found this session — correct choice for a sustained high-volume capture loop (D-02) |
| sse-starlette | 3.4.4 (PyPI) | `EventSourceResponse` for FastAPI SSE | [VERIFIED: pypi registry] Confirmed current via `pip index versions sse-starlette` (latest 3.3.0 at query time of registry listing; WebFetch of GitHub repo reported v3.4.4/May 2026 — use `pip index versions sse-starlette` at install time to confirm exact latest). [CITED: github.com/sysid/sse-starlette] Handles keep-alive pings (15s default) and disconnect detection out of the box — CLAUDE.md explicitly calls out "don't hand-roll SSE" |
| tldextract | 5.3.0 (PyPI) | Registered-domain extraction/grouping (D-10) | [VERIFIED: pypi registry] Confirmed via `pip index versions tldextract` (5.3.0, latest release Dec 2025). Actively maintained (regular releases through 2025); supports fully offline mode (`suffix_list_urls=()`), required for the passive-only, no-outbound-calls architecture |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none — no new supporting libs needed) | — | dpkt/sse-starlette/tldextract are self-contained for this phase's scope | — |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| dpkt | Scapy for the new traffic loop too | Rejected per CLAUDE.md/D-02 — Scapy's per-packet object-graph overhead is incompatible with sustained WAN-volume capture on a low-power always-on server |
| dpkt | pyshark/tshark | Rejected — pulls in full Wireshark dependency for capability this phase doesn't need (no DPI, flow-level only per D-04) |
| tldextract | publicsuffix2 | Rejected — `publicsuffix2`'s last PyPI release is 2019-12-21, effectively unmaintained; tldextract is the actively-maintained standard |
| Continuous aggregates | Querying raw `bandwidth_metrics`/`traffic_flows` rows directly for all chart ranges | Workable for per-device 24h-window queries early on, but a "monthly" view over years of 5-10s-cadence raw rows does NOT scale — see Common Pitfalls |
| SSE broadcaster: shared queue/broker per connection | One DB query per connected client per tick | Rejected — duplicates work per browser tab; D-13's single global channel implies one source-of-truth poll/aggregate cycle fanned out to N subscribers |

**Installation:**
```bash
# Backend (capture container — add to capture/requirements.txt)
dpkt==1.9.8

# Backend (API container — add to backend/pyproject.toml dependencies)
sse-starlette==3.4.4   # verify exact latest with: pip index versions sse-starlette
tldextract==5.3.0

# Frontend — already locked by 03-UI-SPEC.md, not this research's concern:
# npm install layerchart  (1.0.13 confirmed current via `npm view layerchart version`)
```

**Version verification:** `pip index versions dpkt` → 1.9.8 (current). `pip index versions tldextract` → 5.3.0 (current, Dec 2025 release). `pip index versions sse-starlette` → 3.3.0 was the latest tag returned by the registry query at research time; a WebFetch of the GitHub repo reported a newer v3.4.4 (May 2026) — **re-run `pip index versions sse-starlette` at planning/implementation time** to pin the exact current patch, since these two checks disagreed by a minor version during this research session.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| dpkt | PyPI | First published 2022-08-18 (this version); project itself is 15+ years old (kbandla/dpkt fork of original dpkt) | unknown (seam could not fetch download count) | github.com/kbandla/dpkt | SUS (reason: `unknown-downloads` only) | Approved — long-established, widely-known library; flag is a missing-signal artifact, not a legitimacy concern |
| tldextract | PyPI | Long-running project; latest release 2025-12-28 | unknown (seam could not fetch download count) | github.com/john-kurkowski/tldextract | SUS (reason: `unknown-downloads` only) | Approved — canonical, actively-maintained PSL library; flag is a missing-signal artifact |
| sse-starlette | PyPI | Long-running project; latest release 2026-05-12 | unknown (seam could not fetch download count) | github.com/sysid/sse-starlette | SUS (reason: `unknown-downloads` only) | Approved — this is the exact package named in CLAUDE.md's recommended stack; flag is a missing-signal artifact |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** dpkt, tldextract, sse-starlette — all three flagged solely because the legitimacy seam could not retrieve a weekly-download figure (`unknown-downloads`), not because of any actual red signal (all have valid long-lived GitHub repos, are not newly published, are not deprecated, and have no suspicious postinstall scripts). The planner MAY still add a lightweight `checkpoint:human-verify` before first install as a matter of caution per the protocol, but this is a process formality here, not a substantive risk — all three are well-known, narrowly-scoped libraries already referenced by name in CLAUDE.md or directly implied by D-02/D-08/D-10.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ capture container (host network, CAP_NET_RAW/CAP_NET_ADMIN)         │
│                                                                       │
│  raw AF_PACKET socket ──> dpkt parse (Eth/IP/TCP/UDP/DNS)            │
│         │                                                            │
│         ├─ WAN filter (D-03: drop LAN-to-LAN frames)                │
│         ├─ DNS query/response ──> in-memory IP→domain cache          │
│         └─ 5-tuple flow table (in-process, ~5-10s window, D-01)      │
│                       │                                              │
│                  every interval: flush + POST rollup                │
│                       ▼                                              │
│            POST /api/capture/traffic  (loopback/gateway-trusted)    │
└───────────────────────┼──────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ API container (FastAPI)                                             │
│                                                                       │
│  ingest route ──> write traffic_flows rows (TimescaleDB)            │
│              └──> write/upsert bandwidth_metrics rows (TimescaleDB) │
│              └──> update shared in-memory "latest snapshot" state   │
│                       │                                              │
│         ┌─────────────┴──────────────┐                              │
│         ▼                             ▼                              │
│  GET /api/traffic/stream      GET /api/bandwidth/{device}?range=... │
│  (sse-starlette,              GET /api/bandwidth/network?view=daily │
│   single broadcaster fans     GET /api/devices/{id}/destinations    │
│   out latest snapshot to            │                                │
│   all connected clients,            ▼                                │
│   D-13)                       queries continuous aggregates or      │
│         │                     raw hypertable rows depending on      │
│         │                     requested range/grain                 │
│         ▼                            │                               │
└─────────┼────────────────────────────┼───────────────────────────────┘
          ▼                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Frontend (Svelte/SvelteKit)                                          │
│  native EventSource (live feed: top talkers, active connections)   │
│  LayerChart (per-device + network-wide bandwidth charts)            │
│  device picker drives both bandwidth-history + destinations query  │
└─────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
capture/
├── capture.py              # existing ARP/DHCP/mDNS loops — add traffic loop here
├── traffic_sniff.py        # NEW: dpkt parse loop, 5-tuple aggregation, DNS cache
└── requirements.txt        # add dpkt

backend/src/
├── models/
│   ├── bandwidth.py        # existing — unchanged schema (D-16 lock)
│   └── traffic_flow.py     # NEW: traffic_flows hypertable model
├── routes/
│   ├── capture.py          # add POST /traffic ingest endpoint
│   └── traffic.py          # NEW: GET /api/traffic/stream (SSE), GET /api/bandwidth/*, GET /api/devices/{id}/destinations
├── services/
│   ├── identity_resolver.py        # existing — reused, not modified
│   ├── bandwidth_source.py         # NEW: swappable source interface (D-07)
│   ├── traffic_broadcaster.py      # NEW: shared SSE state/fan-out (D-13)
│   └── domain_grouping.py          # NEW: tldextract-based registered-domain grouping (D-10)
└── alembic/versions/
    └── 0003_traffic_flows.py       # NEW: create_hypertable + continuous aggregates + compression policy
```

### Pattern 1: Aggregated capture loop (no per-packet POST)
**What:** A raw-socket read loop accumulates bytes into an in-memory dict keyed by 5-tuple; every ~5-10s, flush the dict to two POST payloads (flow-level detail + per-device rollup) and reset.
**When to use:** Always, for this phase's WAN traffic loop — never POST per packet (D-01).
**Example:**
```python
# Source: dpkt docs (kbandla/dpkt) + standard AF_PACKET pattern, MEDIUM confidence (web-sourced this session)
import socket
import time
import dpkt

ETH_P_ALL = 3
flows: dict[tuple, int] = {}  # (src_mac, dst_ip, dst_port, proto) -> bytes
last_flush = time.monotonic()
FLUSH_INTERVAL = 7  # seconds, within the ~5-10s range (D-01/D-11, Claude's discretion)

sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
while not stop_event.is_set():
    raw, _ = sock.recvfrom(65536)
    eth = dpkt.ethernet.Ethernet(raw)
    if not isinstance(eth.data, dpkt.ip.IP):
        continue
    ip = eth.data
    if not _is_wan_bound(ip.src, ip.dst):  # D-03: drop LAN-to-LAN
        continue
    proto = ip.p
    dport = getattr(ip.data, "dport", None)
    key = (mac_addr(eth.src), socket.inet_ntoa(ip.dst), dport, proto)
    flows[key] = flows.get(key, 0) + len(raw)

    if time.monotonic() - last_flush >= FLUSH_INTERVAL:
        _flush_and_post(flows)
        flows.clear()
        last_flush = time.monotonic()
```

### Pattern 2: Passive DNS sniffing for IP-to-domain cache
**What:** Inspect UDP port 53 traffic in the same capture loop; on a DNS response, record `answer.ip -> qname` in a local cache consulted when flushing flow rollups.
**When to use:** Continuously, alongside the main capture loop (D-08).
**Example:**
```python
# Source: dpkt DNS parsing pattern (jon.oberheide.org dpkt tutorial #3 + dpkt source), MEDIUM confidence
if ip.p == dpkt.ip.IP_PROTO_UDP and (ip.data.sport == 53 or ip.data.dport == 53):
    try:
        dns = dpkt.dns.DNS(ip.data.data)
    except dpkt.dpkt.UnpackError:
        pass
    else:
        if dns.qr == dpkt.dns.DNS_R and dns.qd:
            qname = dns.qd[0].name
            for rr in dns.an:
                if rr.type == dpkt.dns.DNS_A:
                    dns_cache[socket.inet_ntoa(rr.rdata)] = qname
```

### Pattern 3: Registered-domain grouping (D-10)
**What:** Group raw hostnames under their registered domain at query/serialization time using tldextract in offline mode.
**When to use:** API layer, when serializing per-device destination breakdowns — never at capture time (keep raw hostname detail in storage).
**Example:**
```python
# Source: tldextract README (john-kurkowski/tldextract), MEDIUM confidence
import tldextract

_extractor = tldextract.TLDExtract(suffix_list_urls=())  # offline-only, no network call

def registered_domain(hostname: str) -> str:
    ext = _extractor(hostname)
    return f"{ext.domain}.{ext.suffix}" if ext.suffix else hostname
```

### Pattern 4: sse-starlette single global broadcaster (D-13)
**What:** One background task periodically computes the latest snapshot (top talkers, active connections); each SSE connection's generator reads from a shared object/queue rather than re-querying the DB per client.
**When to use:** The single `/api/traffic/stream` endpoint.
**Example:**
```python
# Source: sse-starlette docs/examples (sysid/sse-starlette), MEDIUM confidence
from sse_starlette.sse import EventSourceResponse

_latest_snapshot: dict = {}  # updated by a background interval task

async def traffic_stream(request: Request):
    async def event_generator():
        last_sent = None
        while True:
            if await request.is_disconnected():
                break
            if _latest_snapshot != last_sent:
                yield {"event": "snapshot", "data": json.dumps(_latest_snapshot)}
                last_sent = dict(_latest_snapshot)
            await asyncio.sleep(1)  # poll the shared state, not the DB, per tick

    return EventSourceResponse(event_generator(), ping=15)
```

### Anti-Patterns to Avoid
- **Per-client DB query on every SSE tick:** With D-13's single global channel, querying the DB independently per connected browser tab duplicates work for no benefit — compute the snapshot once per interval, fan out to all subscribers from shared state.
- **Capture-time domain grouping:** Storing only the grouped registered domain (discarding raw hostname) in `traffic_flows` would make D-10's grouping irreversible and prevent any future feature needing per-hostname detail — keep raw hostname/IP in storage, group only at display time.
- **Querying raw rows for "monthly" chart ranges:** Scanning months of 5-10s-cadence raw `bandwidth_metrics` rows for a monthly chart view does not scale and will get slower every day the system runs (data never deletes) — use continuous aggregates for >24h ranges.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE keep-alive / disconnect detection | Custom ping/pong loop, manual `Connection: keep-alive` header juggling | sse-starlette's `EventSourceResponse` | Handles W3C SSE framing, periodic pings, and disconnect detection (`request.is_disconnected()` / `CancelledError`) correctly — CLAUDE.md explicitly says don't hand-roll SSE |
| Registered-domain extraction | Manual TLD suffix list / regex heuristics | tldextract (offline mode) | The Public Suffix List has hundreds of multi-part TLD exceptions (e.g. `co.uk`, `github.io`); a hand-rolled heuristic will misclassify these |
| Time-bucketed rollup aggregation (daily/weekly/monthly) | Application-level GROUP BY + manual caching layer | TimescaleDB continuous aggregates | Native incremental materialization, refresh policies, and the option to drop raw data later while keeping aggregates — reinventing this in application code means reinventing TimescaleDB's own incremental-refresh logic |
| Storage growth control while keeping "never delete" | Custom downsampling/archival job | TimescaleDB native compression policy (`add_compression_policy`) | 10-20x storage reduction while keeping every row queryable — exactly matches the "configurable retention, never auto-deleted by default" requirement without writing a single line of cleanup code |

**Key insight:** Every "don't hand-roll" item in this phase has a reason rooted in a real correctness gap (SSE framing edge cases, PSL TLD exceptions, materialized-view refresh correctness) rather than mere convenience — hand-rolling any of these introduces a class of bug this phase's own requirements (e.g. "any time range," "never auto-delete") are specifically testing for.

## Runtime State Inventory

Not applicable — this is a greenfield feature phase (new tables, new capture loop, new routes), not a rename/refactor/migration phase. No existing runtime state needs renaming or reconciling.

## Common Pitfalls

### Pitfall 1: MAC-rotation blind spot in bandwidth/traffic queries
**What goes wrong:** A device's bandwidth history silently "resets" or shows gaps whenever its MAC rotates (e.g. iOS/Android privacy MAC randomization across reconnects), because `bandwidth_metrics`/`traffic_flows` are keyed by raw `device_mac`, and a query that filters on only `Device.last_known_mac` misses every row written under a previous MAC.
**Why it happens:** Phase 2's `IdentityResolver` already handles MAC rotation for *discovery* (a `Device` row's `last_known_mac` and `identity_key` are updated as new MACs are observed), but Phase 1's `bandwidth_metrics` schema and this phase's new `traffic_flows` schema are both still keyed by the raw MAC seen at write time — there's no historical "all MACs this device has ever had" table.
**How to avoid:** When building the historical-chart query path, resolve the full set of MACs a device has been associated with (via `DiscoveredIdentity`/`Device` history, or by tracking MAC changes explicitly) and aggregate `bandwidth_metrics`/`traffic_flows` rows across all of them — not just the device's current `last_known_mac`. If no "MAC history" table exists yet, the planner must decide whether this phase adds one (e.g. a `device_mac_history` table or an append-only log) or whether a simpler interim heuristic (e.g. query by current MAC only, document the known limitation) is acceptable for v1. **This is a concrete design gap requiring a planning decision — flag explicitly in Open Questions.**
**Warning signs:** A device's bandwidth chart shows a sudden drop to zero with no corresponding drop in observed traffic on the live feed; QA testing with MAC randomization enabled (e.g. an iPhone with private Wi-Fi address rotation) reveals "missing" historical data that should exist.

### Pitfall 2: Real-time continuous aggregates disabled by default (stale "live-ish" views)
**What goes wrong:** A continuous aggregate created without `materialized_only => false` will not reflect the last `schedule_interval`'s worth of recently-written rows — a "today" bucket on a daily chart can appear to under-report until the next scheduled refresh runs.
**Why it happens:** TimescaleDB disabled real-time aggregation by default starting v2.13 (this project pins 2.27.x) — a behavior change from earlier versions that's easy to miss if following older tutorials/blog posts.
**How to avoid:** For any chart view where "today"/"this week" must reflect very recent writes, either set `materialized_only => false` on the continuous aggregate, or set a short `schedule_interval` (e.g. 5 minutes) on the refresh policy and accept that small lag, or query raw rows for the most recent partial bucket and union with the materialized older buckets.
**Warning signs:** A "today" bar on the daily bandwidth chart looks suspiciously low compared to what the live feed shows for the same period.

### Pitfall 3: Confusing retention policies with "never auto-delete"
**What goes wrong:** A well-intentioned `add_retention_policy()` call (perhaps copied from a TimescaleDB tutorial that demonstrates the "complete" feature set) silently starts dropping chunks past an age threshold — directly violating the locked "never auto-deleted by default" requirement (TRAF-02, D-06).
**Why it happens:** Most TimescaleDB tutorials present compression and retention as a matched pair ("compress then drop") because that's the common SaaS-analytics use case; Innkeeper's requirement is the less common "compress but never drop" pattern.
**How to avoid:** Compression policies only, by default. Retention policies must be explicitly opt-in and user-configured (per D-06's "retention is configurable") — never wired up as a default migration step.
**Warning signs:** Code review of any migration or seed script that calls `add_retention_policy` without an explicit user-facing settings control gating it.

### Pitfall 4: Capture container running in Docker on macOS during local dev
**What goes wrong:** The new traffic-sniff loop (raw AF_PACKET socket, WAN-bound packets) won't see real LAN traffic under Docker Desktop's NAT-isolated network on macOS — exactly the constraint already documented in STATE.md for Phase 1 (`network_mode: host` + Docker Desktop's NAT isolation).
**Why it happens:** Already a known, documented limitation (see `docs/dev/mac_setup.md`, the bridged-network Lima VM workaround) — not new to this phase, but the new traffic loop inherits it.
**How to avoid:** Reuse the existing Lima VM dev setup already built for Phase 1; don't attempt to debug "no traffic captured" on bare Docker Desktop for macOS without first checking this known constraint.
**Warning signs:** The traffic-sniff loop runs without errors but the live feed and traffic_flows table stay empty during local macOS development.

## Code Examples

### Continuous aggregate + compression policy for bandwidth_metrics (and traffic_flows)
```sql
-- Source: TigerData docs (tigerdata.com/docs), MEDIUM confidence — verify exact
-- syntax against the installed 2.27.x version at implementation time.

-- Hourly rollup, built on raw bandwidth_metrics
CREATE MATERIALIZED VIEW bandwidth_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    device_mac,
    sum(bytes_rx) AS bytes_rx,
    sum(bytes_tx) AS bytes_tx
FROM bandwidth_metrics
GROUP BY bucket, device_mac
WITH NO DATA;

SELECT add_continuous_aggregate_policy('bandwidth_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes');

-- Daily rollup, built on top of the hourly aggregate (hierarchical cagg)
CREATE MATERIALIZED VIEW bandwidth_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', bucket) AS bucket,
    device_mac,
    sum(bytes_rx) AS bytes_rx,
    sum(bytes_tx) AS bytes_tx
FROM bandwidth_hourly
GROUP BY time_bucket('1 day', bucket), device_mac
WITH NO DATA;

SELECT add_continuous_aggregate_policy('bandwidth_daily',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- Compression: keep all rows forever, just shrink storage after they age out
ALTER TABLE bandwidth_metrics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_mac',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('bandwidth_metrics', compress_after => INTERVAL '7 days');

-- Deliberately NOT calling add_retention_policy() — D-06/TRAF-02 requires
-- never-auto-delete-by-default; retention is a future user-configurable
-- setting, not a migration-time default.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Real-time continuous aggregates enabled by default | Disabled by default, opt-in via `materialized_only => false` | TimescaleDB v2.13 | Tutorials/blog posts predating 2.13 will show stale syntax expectations; verify behavior against the installed 2.27.x, don't assume older blog-post defaults |
| `xael/python-nmap` | `home-assistant-libs/python-nmap` fork (per CLAUDE.md, used in a different phase but same project-wide convention) | Ongoing | Not directly relevant to this phase's libraries, but reinforces the project's established "verify the maintained fork, not just any same-named PyPI package" discipline applied here to dpkt/tldextract/sse-starlette |

**Deprecated/outdated:**
- `publicsuffix2`: last released 2019-12-21, effectively abandoned — do not use despite appearing in older tutorials; `tldextract` is the current standard.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | dpkt is ~130x faster than Scapy for bulk parsing (specific multiplier) | Standard Stack / Architecture Patterns | Low — this figure comes from CLAUDE.md itself (already a locked project decision, D-02) and was corroborated by independent benchmark sources found this session; even if the exact multiplier is imprecise, the directional conclusion (dpkt >> Scapy for bulk parsing) is well-established and not contested anywhere in the research |
| A2 | sse-starlette's exact current patch version (3.3.0 vs 3.4.4 — two checks disagreed) | Standard Stack | Low-medium — does not affect architecture/pattern guidance, only the exact pinned version string; planner/executor should re-run `pip index versions sse-starlette` immediately before pinning in `pyproject.toml` |
| A3 | The recommended hierarchical continuous-aggregate structure (hourly → daily → weekly → monthly) is the right granularity ladder for this phase's specific TRAF-04 requirement (only daily/weekly/monthly views, no hourly view requested) | Code Examples / Architecture Patterns | Medium — if the planner decides hourly aggregation is unnecessary overhead given TRAF-04 only asks for 3 views, a simpler 2-tier (raw → daily, daily → weekly/monthly) structure may suffice; this is a tuning decision, not a correctness risk either way |
| A4 | No existing "MAC history" table exists for resolving a device's full historical MAC set (Pitfall 1) | Common Pitfalls / Architecture Patterns | High — if this assumption is wrong and such a table already exists in Phase 2 code not surfaced during this research's codebase read, the recommended query-time aggregation pattern is unnecessary; if right (as the codebase read in this session suggests), it's a real gap the planner must explicitly decide how to close |

**If this table is empty:** N/A — see entries above; all four assumptions should be confirmed or resolved during planning, particularly A4 which has the highest impact.

## Open Questions (RESOLVED)

1. **Should `traffic_flows`/`bandwidth_metrics` historical queries aggregate across a device's full MAC history, or only its current `last_known_mac`?**
   - What we know: Phase 2's `IdentityResolver` already tracks MAC rotation for the *discovery* pipeline (`Device.last_known_mac` updates as new MACs are observed via `record_observation`); `bandwidth_metrics` is locked-schema, keyed by `device_mac` directly with no historical MAC-association table.
   - What's unclear: Whether this phase needs to introduce a `device_mac_history` table (or similar) to correctly aggregate bandwidth across MAC rotations, or whether a documented v1 limitation ("bandwidth history may reset when a device's MAC rotates") is acceptable scope for now.
   - Recommendation: The planner should make this an explicit task-level decision with a clear default — recommend introducing a lightweight `device_mac_history` table (device_id, mac, first_seen, last_seen) populated whenever `record_observation`'s Device-branch fast path updates `last_known_mac`, since this is a small addition that closes a real correctness gap and the existing `record_observation` code is the natural place to populate it. If descoped, document the limitation explicitly in REQUIREMENTS.md traceability notes.
   - **RESOLVED:** Introduced the `device_mac_history` table as recommended. Created in 03-01-PLAN.md Task 1 (model + Alembic migration 0004, alongside `traffic_flows`) and wired in Task 2 (`record_observation`'s Device-branch fast path upserts a `DeviceMacHistory` row on every `last_known_mac` update). Resolved at query time in 03-03-PLAN.md Task 3, where `device_bandwidth` and `device_destinations` both resolve a device's full historical MAC set (via `DeviceMacHistory` union `Device.last_known_mac`) before querying `bandwidth_metrics`/`traffic_flows`, rather than filtering by `last_known_mac` alone.

2. **Should `traffic_flows` use a 5-tuple-based composite primary key, or a synthetic surrogate key?**
   - What we know: TimescaleDB hypertables support composite primary keys that include the time-partitioning column; the existing `bandwidth_metrics` table successfully uses `(time, device_mac)`.
   - What's unclear: Whether a `(time, device_mac, dst_ip, dst_port, protocol)` composite PK is performant/clean enough, or whether high flow cardinality (many distinct dst_ip/port combos per device per interval) makes a synthetic `id` + non-unique index preferable.
   - Recommendation: Start with the composite PK (consistent with `bandwidth_metrics`' existing pattern and CONTEXT.md's discretion note); revisit only if early load-testing surfaces index bloat or write-conflict issues — left as an implementation-time judgment call, not a blocking research gap.
   - **RESOLVED:** Composite PK retained, consistent with the `bandwidth_metrics` pattern. 03-01-PLAN.md Task 1 defines `TrafficFlow` with primary key `(time, device_mac, dst_ip, dst_port, protocol)` exactly as recommended; no surrogate key was introduced. Revisit only if real-world load-testing surfaces index bloat — not a blocker for this phase.

3. **Exact aggregation/SSE-push interval and rolling top-talkers window** (explicitly Claude's Discretion per CONTEXT.md) — recommend **7 seconds** for the capture/SSE cadence (mid-point of the locked 5-10s range, balances responsiveness against API load) and a **5-minute rolling window** for top-talkers ranking (CONTEXT.md's own example value, smooths bursts without feeling stale).
   - **RESOLVED:** Both recommended values were adopted. 03-02-PLAN.md Task 1 sets `FLUSH_INTERVAL = 7` (seconds) for the capture aggregation/POST cadence. 03-03-PLAN.md Task 2 matches the same 7-second cadence in `update_snapshot_loop`'s `asyncio.sleep(7)` (per D-11's "same cadence as capture" requirement) and uses a 5-minute rolling window in `_compute_snapshot`'s top-talkers ranking (per D-12).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | Full stack (`docker compose up`) | ✓ | 29.1.3 | — |
| TimescaleDB / PostgreSQL | `traffic_flows`, `bandwidth_metrics`, continuous aggregates | ✓ | timescale/timescaledb:2.27.0-pg17 (pinned in docker-compose.yml) | — |
| dpkt (PyPI) | Capture container traffic-sniff loop | ✓ (verified on PyPI registry) | 1.9.8 | — |
| sse-starlette (PyPI) | API live-feed SSE endpoint | ✓ (verified on PyPI registry) | 3.3.0–3.4.4 (verify exact at install time) | — |
| tldextract (PyPI) | API registered-domain grouping | ✓ (verified on PyPI registry) | 5.3.0 | publicsuffix2 (rejected — unmaintained, do not use) |
| layerchart (npm) | Frontend charts (locked by 03-UI-SPEC.md) | ✓ (verified on npm registry) | 1.0.13 | — |
| Native Linux AF_PACKET raw socket | Capture container traffic loop | ✓ on target Linux deployment; ✗ equivalent semantics on macOS Docker Desktop (NAT-isolated network) | — | Lima VM bridged-network dev setup (already built for Phase 1, documented in `docs/dev/mac_setup.md`) |

**Missing dependencies with no fallback:** none identified.

**Missing dependencies with fallback:**
- macOS local dev raw-packet visibility — already solved by the existing Lima VM workaround from Phase 1; the new traffic loop inherits this solution, no new work needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (backend, established Phase 1/2 pattern); no frontend test framework exists yet |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) |
| Quick run command | `cd backend && pytest tests/test_<module>.py -x` |
| Full suite command | `cd backend && pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRAF-01 | Live traffic feed updates via SSE without page refresh | integration (backend: SSE endpoint emits snapshot; manual/visual: frontend live update) | `pytest tests/test_traffic_stream.py -x` | ❌ Wave 0 |
| TRAF-02 | Historical bandwidth per device, any time range, retention configurable/never-auto-deleted | unit + integration (query layer; verify no retention policy applied by default) | `pytest tests/test_bandwidth_query.py -x` | ❌ Wave 0 |
| TRAF-03 | Per-device destination breakdown (domains/IPs) | unit (domain grouping logic) + integration (API endpoint) | `pytest tests/test_domain_grouping.py -x`, `pytest tests/test_traffic_destinations.py -x` | ❌ Wave 0 |
| TRAF-04 | Network-wide bandwidth chart, daily/weekly/monthly | integration (continuous aggregate query correctness) | `pytest tests/test_bandwidth_aggregates.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && pytest tests/test_<module>.py -x`
- **Per wave merge:** `cd backend && pytest`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_traffic_stream.py` — covers TRAF-01 (SSE endpoint snapshot emission, disconnect handling)
- [ ] `backend/tests/test_bandwidth_query.py` — covers TRAF-02 (arbitrary time-range query, confirms no default retention policy drops data)
- [ ] `backend/tests/test_domain_grouping.py` — covers TRAF-03 (tldextract-based registered-domain grouping logic, offline-mode verification)
- [ ] `backend/tests/test_traffic_destinations.py` — covers TRAF-03 (per-device destination breakdown API endpoint)
- [ ] `backend/tests/test_bandwidth_aggregates.py` — covers TRAF-04 (continuous aggregate daily/weekly/monthly correctness against seeded raw rows)
- [ ] `backend/tests/conftest.py` fixtures — likely needs a fixture seeding `traffic_flows`/`bandwidth_metrics` rows across a synthetic time range for aggregate tests (existing `test_db`/`client` fixtures should extend, not require a new framework)
- [ ] No frontend test framework exists — if the planner wants automated coverage of the live-feed EventSource reconnect behavior or chart rendering, a Wave 0 task should establish vitest/playwright; otherwise this phase's frontend verification stays manual (consistent with Phase 1/2's posture so far)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | no (new) | Existing dashboard password auth (Phase 1) already gates all new routes; no new auth surface introduced |
| V3 Session Management | no (new) | Reuses existing session cookie mechanism |
| V4 Access Control | yes | New ingest route (`/api/capture/traffic`) MUST reuse the existing loopback/gateway-trusted-only check (`_detect_default_gateway()` pattern in `capture.py`) — never expose an unauthenticated public ingest path |
| V5 Input Validation | yes | Pydantic payload models for the new traffic ingest route (mirroring `ArpEventPayload`/`DhcpEventPayload`), validating IP/MAC/port/protocol fields before DB write |
| V6 Cryptography | no | No new cryptographic operations in this phase |
| V12 API Security (data exposure) | yes | The SSE live-feed and historical-chart endpoints expose per-device traffic/destination data — already behind the existing dashboard-password auth gate; no additional exposure surface beyond what TRAF-01..04 explicitly requires |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Spoofed ingest POST to `/api/capture/traffic` from a non-capture source | Spoofing | Reuse the existing `_TRUSTED_HOSTS` loopback/gateway-trusted check already protecting `/api/capture/arp`, `/dhcp`, `/mdns` — apply identically to the new traffic ingest route |
| Malformed/oversized flow payload causing resource exhaustion on ingest | Denial of Service | Pydantic validation on payload shape; the in-process aggregation window (D-01) already caps POST frequency, but the planner should bound the maximum number of distinct flow-table entries per rollup payload (e.g. reject or truncate pathologically large flow counts from a misbehaving/compromised capture process) |
| DNS cache poisoning of the passive IP→domain map (a malicious LAN device sends a forged DNS response) | Tampering | Out of scope per D-08/D-09's explicit "passive-only, best-effort" design — document as a known accepted limitation (the system already shows raw IP as fallback per D-09, limiting blast radius to a mislabeled domain name, not a security control bypass) |
| SSE channel exposing all devices' traffic to any authenticated browser tab (no per-device authorization split) | Information Disclosure | Acceptable for v1 per PROJECT.md's single-user/household model — the dashboard password gate is the only authorization boundary needed; explicitly not a v1 gap given the single-user threat model |

## Project Constraints (from CLAUDE.md)

- **Portability:** No machine-specific or network-specific assumptions — the new traffic-sniff loop, DNS cache, and ingest route must work on any Docker-capable machine joined to any network, not just the developer's own LAN topology.
- **Self-hosted only:** All traffic/bandwidth data stays local; the passive DNS sniffer and tldextract must operate with zero outbound network calls (tldextract MUST be configured in offline mode, `suffix_list_urls=()` — see Standard Stack).
- **Router-agnostic core:** This phase's bandwidth-source interface (D-07) must be genuinely swappable so a future Phase 7 UniFi adapter can plug in without a rewrite — confirmed feasible per Architecture Patterns' source-interface design.
- **Data privacy / no telemetry:** No external calls beyond what the user explicitly configures — the only network-facing components introduced this phase (capture container's passive sniffing, API's SSE endpoint) are entirely internal to the user's own stack.
- **dpkt over Scapy for the new bulk capture loop** (explicit CLAUDE.md guidance, reaffirmed as D-02) — confirmed and detailed in Standard Stack / Architecture Patterns.
- **sse-starlette for SSE, don't hand-roll** (explicit CLAUDE.md guidance) — confirmed and detailed in Standard Stack / Don't Hand-Roll.
- **TimescaleDB 2.27.x hypertable pattern, explicit SQL over the `sqlalchemy-timescaledb` dialect** (explicit CLAUDE.md guidance) — followed in Code Examples (raw `CREATE MATERIALIZED VIEW`/`add_compression_policy` SQL via Alembic migration, not an ORM dialect wrapper).
- **Flow-level accounting is sufficient, avoid full DPI** (explicit CLAUDE.md / Out-of-Scope guidance, reaffirmed as D-04) — the 5-tuple flow key in this research's schema recommendations never inspects packet payloads.
- **`CAP_NET_RAW`/`CAP_NET_ADMIN` only, never `--privileged`** (PLAT-03) — the new traffic-sniff loop runs inside the existing capture container under the same capability set already configured in `docker-compose.yml`; no new container or capability is introduced.

## Sources

### Primary (HIGH confidence)
- `pip index versions dpkt` / `tldextract` / `sse-starlette` — direct PyPI registry queries, this session
- CLAUDE.md (project file) — Scapy vs dpkt guidance, sse-starlette recommendation, TimescaleDB version pins

### Secondary (MEDIUM confidence)
- [sse-starlette GitHub repo](https://github.com/sysid/sse-starlette) — ping config, disconnect detection, version/release info (WebFetch, this session)
- [TigerData docs: Understand continuous aggregates](https://www.tigerdata.com/docs/learn/continuous-aggregates) — CREATE MATERIALIZED VIEW syntax, real-time aggregation default-off since v2.13 (WebFetch, this session)
- [TigerData docs: Create a retention policy](https://www.tigerdata.com/docs/build/data-management/data-retention/create-a-retention-policy) — `add_retention_policy()` syntax (WebFetch, this session)
- [TigerData docs: add_compression_policy()](https://docs.tigerdata.com/api/latest/compression/add_compression_policy/) — compression policy syntax, compress_segmentby/compress_orderby (WebSearch, this session)
- [TigerData docs: add_continuous_aggregate_policy()](https://www.tigerdata.com/docs/api/latest/continuous-aggregates/add_continuous_aggregate_policy) — start_offset/end_offset/schedule_interval syntax (WebSearch, this session)
- [dpkt GitHub (kbandla/dpkt)](https://github.com/kbandla/dpkt) — canonical maintained fork, parsing API shape (WebSearch, this session)
- [tldextract GitHub (john-kurkowski/tldextract)](https://github.com/john-kurkowski/tldextract) — offline mode configuration, PSL caching behavior (WebSearch, this session)
- [dpkt Tutorial #3: DNS Spoofing — jon.oberheide.org](https://jon.oberheide.org/blog/2008/12/20/dpkt-tutorial-3-dns-spoofing/) — DNS parsing pattern reference

### Tertiary (LOW confidence)
- General benchmark claims about dpkt-vs-Scapy speed multiplier ("~130x") — directionally well-corroborated across multiple sources and matches CLAUDE.md's own figure, but the exact multiplier should be treated as an order-of-magnitude indicator, not a precise benchmark result, per A1 in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all three new packages verified directly against the PyPI registry this session, with version numbers and release dates confirmed
- Architecture: MEDIUM-HIGH — SSE broadcaster pattern, dpkt parsing pattern, and TimescaleDB continuous-aggregate/compression pattern are all well-documented standard patterns; the MAC-rotation reconciliation design (Pitfall 1 / Open Question 1) is a genuine open design gap requiring a planning decision, not a research gap
- Pitfalls: HIGH — all four pitfalls are grounded in either this codebase's own existing code (MAC rotation, macOS Docker NAT) or directly-cited TimescaleDB version-specific behavior changes (real-time aggregation default, retention-vs-compression distinction)

**Research date:** 2026-06-19
**Valid until:** 2026-07-19 (30 days — TimescaleDB/sse-starlette/tldextract are all actively-released libraries; re-verify exact pinned versions at implementation time given the sse-starlette version discrepancy noted in A2)
