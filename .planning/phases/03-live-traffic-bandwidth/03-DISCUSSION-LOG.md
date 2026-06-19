# Phase 3: Live Traffic + Bandwidth - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 3-Live Traffic + Bandwidth
**Areas discussed:** Traffic capture depth, Destination resolution (domain vs IP), Live feed semantics

---

## Traffic capture depth

| Option | Description | Selected |
|--------|-------------|----------|
| Per-packet sniff + in-process aggregation | Aggregate bytes per src-MAC in memory over ~5-10s before POSTing a rollup | ✓ |
| Per-packet POST (no aggregation) | POST immediately for every packet | |
| Periodic interface counter polling | Read interface/ARP-table byte counters instead of sniffing | |

| Option | Description | Selected |
|--------|-------------|----------|
| 5-tuple flow | (src IP/MAC, dst IP, dst port, protocol) flow key | ✓ |
| Device ↔ destination IP only | No ports/protocol in the key | |
| Device-level totals only | No destination dimension at all | |

| Option | Description | Selected |
|--------|-------------|----------|
| dpkt for the bulk traffic loop | Separate high-volume loop using dpkt, keep Scapy for ARP/DHCP/mDNS | ✓ |
| Reuse Scapy for everything | One consistent library across all capture loops | |

| Option | Description | Selected |
|--------|-------------|----------|
| New `traffic_flows` hypertable, separate from `bandwidth_metrics` | Detailed flow table feeds TRAF-01/03; simple rollup table feeds TRAF-02/04 | ✓ |
| Single flow-level table, derive device totals via SQL aggregation | `bandwidth_metrics` becomes a continuous aggregate computed from flow data | |

| Option | Description | Selected |
|--------|-------------|----------|
| Keep raw flow rows forever | Same "never auto-delete by default" policy as `bandwidth_metrics` | ✓ |
| Downsample/expire raw flows after a short window | Prune detail after 7-30 days, keep device rollups forever | |

| Option | Description | Selected |
|--------|-------------|----------|
| Internet-bound traffic only | Track WAN-bound traffic; skip device-to-device LAN traffic | ✓ |
| All traffic, LAN and internet | Track everything including local chatter | |

| Option | Description | Selected |
|--------|-------------|----------|
| Design a swappable source interface now | Matches PROJECT.md's adapter-pattern decision; Phase 7's UniFi adapter can plug in later | ✓ |
| Keep it simple — single hardcoded path | No abstraction layer; rework when Phase 7 arrives | |

**User's choice:** Aggregated passive capture via dpkt, 5-tuple flow keys, separate `traffic_flows` hypertable, internet-bound only, never auto-deleted, designed behind a swappable source interface for the future UniFi adapter.

**Notes:** User flagged that several of these questions were too in-the-weeds technically and asked for a plain-language recap. Stated priorities: "pick up the information in the best way, can work with direct access to router, or fallback to using other methods when direct router access is not available. power, manageability, easy to maintain and build on." After a plain-language summary of the recommended approach and how it fits the project's existing adapter-pattern/dual-mode architecture, user confirmed it matched their intent with no changes.

---

## Destination resolution (domain vs IP)

| Option | Description | Selected |
|--------|-------------|----------|
| Passive DNS sniffing | Watch DNS query/response traffic, build IP→domain cache | ✓ |
| Active reverse-DNS lookup | Ask for domain ownership of an IP after the fact | |
| Raw IPs only, no domain names | Skip domain resolution entirely | |

| Option | Description | Selected |
|--------|-------------|----------|
| Show the raw IP as a fallback | Display IP when no DNS-sniffed domain is known | ✓ |
| Best-effort reverse-DNS lookup only for unresolved IPs | Active lookup fallback for the minority of unresolved IPs | |

| Option | Description | Selected |
|--------|-------------|----------|
| Group by registered domain | Roll up subdomains (www./api./ipv4. netflix.com) under one entry | ✓ |
| Show each exact hostname separately | No grouping, every distinct hostname is its own row | |

**User's choice:** Passive DNS sniffing only, raw-IP fallback when unresolved, subdomains grouped by registered domain in the breakdown view.

**Notes:** No pushback — all three picks were the recommended option, in line with the passive-only philosophy already established for ARP/DHCP/mDNS discovery.

---

## Live feed semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Every few seconds (~5s), matching the capture aggregation window | SSE update cadence follows the capture rollup interval | ✓ |
| Near real-time (sub-second), per-packet/per-flow push | Stream events as they're seen instead of batching | |

| Option | Description | Selected |
|--------|-------------|----------|
| Rolling window (e.g. last 5 minutes) | Smooths "top talkers" ranking against bursty traffic | ✓ |
| Pure live snapshot | Ranking reflects only the most recent ~5s interval | |

| Option | Description | Selected |
|--------|-------------|----------|
| Single global SSE channel | One broadcast endpoint; frontend filters client-side per device | ✓ |
| Per-device SSE channels | Backend tracks and pushes to N concurrent per-device streams | |

**User's choice:** SSE updates every ~5-10s in step with the capture aggregation window, "top talkers" ranked over a rolling ~5-minute window, single global SSE channel.

**Notes:** No pushback — all three picks were the recommended option.

---

## Claude's Discretion

- Exact aggregation interval within the ~5-10s range
- Exact rolling-window length for "top talkers" within the few-minutes range
- Internal schema/column naming for `traffic_flows` and the source-interface abstraction
- Whether daily/weekly/monthly bandwidth charts (TRAF-04) use raw `bandwidth_metrics` rows or a TimescaleDB continuous aggregate — this was the fourth originally-presented gray area ("Bandwidth-to-device binding & chart aggregation"); user chose not to discuss it separately and it was carried into discretion instead
- How `device_mac`-keyed bandwidth/flow tables reconcile against Phase 2's MAC-rotation identity fusion (`IdentityResolver`) — also originally part of the fourth gray area
- DNS cache TTL/expiry behavior for the passive IP→domain mapping
- Exact registered-domain grouping logic (public-suffix-list-based vs simple heuristic)

## Deferred Ideas

None — discussion stayed within phase scope; no new capabilities were proposed.
