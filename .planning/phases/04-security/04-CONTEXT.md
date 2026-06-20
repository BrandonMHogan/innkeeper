# Phase 4: Security - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Build Innkeeper's first **active** security layer on top of the passive discovery/traffic foundation: on-demand + lightweight scheduled port scans per device, a 3-state (good/warning/critical) security badge derived from scan results and traffic behavior, malicious-IP / suspicious-traffic detection, and a durable alert record for unknown-device joins and security findings. Alert *delivery* (push) is explicitly out of scope — that's Phase 5's notification plugin; this phase only needs to detect, classify, and durably record alerts in a way Phase 5 can consume. No blocking/control (Phase 6+), no router-adapter-sourced scan data (Phase 7).

</domain>

<decisions>
## Implementation Decisions

User delegated all four gray areas to Claude's judgment ("pick your own recommended ideas... pick what is best for the product... while keeping up with our existing ideals of clean, easy to maintain, testable code"). Decisions below were chosen for product strength, maintainability, and consistency with prior-phase architecture — not for implementation ease.

### Port Scan Trigger, Scope & Engine
- **D-01:** Two trigger paths: an on-demand "Scan" button per device (SEC-01's explicit ask) **and** a low-impact automatic background re-scan (daily) for *registered* devices only — keeps the security badge from going stale without the user remembering to click, while not scanning unknown/transient devices (e.g. guest phones) on a schedule.
- **D-02:** Scan scope is nmap's **top-1000 common ports**, not a full 1–65535 sweep — full-range scans are slow, CPU-heavy on a low-power always-on box, and add little signal for a home network. A "full scan" option is explicitly deferred (see Deferred Ideas), not built now.
- **D-03:** Scans run from the **capture container**, not the backend — the capture container already holds `CAP_NET_RAW`/`CAP_NET_ADMIN` (Phase 1 D-05) for a TCP SYN scan; this avoids granting new elevated capabilities to the backend and keeps the "backend stays unprivileged" boundary intact. Scan results are POSTed to the API via a new ingest route, following the same trust pattern as the existing `/api/capture/*` routes.
- **D-04:** Use the **home-assistant-libs/python-nmap fork** wrapping the system `nmap` binary, exactly per CLAUDE.md's stack guidance (the original `xael/python-nmap` on PyPI is unmaintained) — `nmap` gets added to the capture container's Dockerfile.

### Unexpected-Port Rule Baseline
- **D-05:** Two-tier, table-driven rule (not a single allowlist) — chosen because it's testable as plain data and gives meaningfully different severities instead of one big "anything weird" bucket:
  - **Universal risky-ports set** (any device, any type): telnet (23), FTP (21), SMB (139/445), RDP (3389), VNC (5900), and other classic unauthenticated/legacy-remote-access ports. An open risky port is **always flagged**, regardless of device type.
  - **Per-device-type expected-ports allowlist** (keyed off `Device.type`, the closed enum locked in Phase 2 D-14 specifically for this purpose): e.g. `router_network` expects 53/80/443/22; `iot_smart_home` expects little to nothing; `phone`/`laptop`/`desktop`/`tablet` expect nothing by default. Any open port outside the type's allowlist *and* not in the risky set is "unexpected" (lower severity — e.g. a desktop running a Plex server on 32400 is informational, not alarming).

### Security Status Derivation (good/warning/critical)
- **D-06:** Status is computed, table-driven, from two signal classes — no opaque scoring formula:
  - **critical:** device has an open *risky* port (D-05) **or** device has communicated with a known-malicious IP (SEC-03).
  - **warning:** device has an open *unexpected-but-not-risky* port (D-05) **or** a bandwidth-anomaly signal fires (D-09 below).
  - **good:** none of the above. A device that has never been scanned also defaults to **good** (not warning) — an unscanned device isn't assumed guilty; the UI surfaces "not yet scanned" separately via the scan button/timestamp, not via the badge color.
- **D-07:** Status is recomputed whenever new scan results land or a new traffic-pattern/malicious-IP match is recorded — it is a derived/cached field on the device (or a join at read time), not something the user sets.

### Malicious-IP / Suspicious-Traffic Detection
- **D-08:** Default, zero-config detector is a **bundled static blocklist** (a vendored data file shipped in the backend image, updated via normal app releases) — satisfies the hard "no telemetry, no external calls unless user explicitly configures an integration" constraint out of the box. A `ThreatIntelSource` interface (mirroring the swappable-source pattern already used for bandwidth in Phase 3 D-07) has this `StaticBlocklistSource` as the only built-in implementation.
- **D-09 (suspicious traffic patterns):** Scoped narrowly and concretely for v1 — a **bandwidth-spike anomaly**: a device's traffic in the current window exceeds N× its own rolling historical average (reusing Phase 3's `bandwidth_metrics`/`traffic_flows` data, no new capture infra needed). This is a `warning`-level signal (more false-positive-prone than a malicious-IP hit — e.g. a video call or big download), not `critical`. No bespoke anomaly-detection ML — a simple, testable threshold comparison.
- **D-10:** A remote/updatable threat-feed source (e.g. Spamhaus DROP, FireHOL) is **explicitly an opt-in setting, off by default** — if/when built, it's the user "explicitly configuring an integration" the constraint already carves out. Building the remote-feed UI itself is not required this phase (see Deferred Ideas); the `ThreatIntelSource` interface should make adding it later a non-rewrite.

### Unknown-Device & Alert Surfacing (pre-notifications)
- **D-11:** A durable **`security_alerts`** table (device_id nullable, type: `unknown_device` / `malicious_ip` / `suspicious_traffic` / `unexpected_port`, severity, message, created_at, acknowledged) is the canonical alert record. This is deliberately shaped so Phase 5's event bus (PLUG-03) can subscribe to/poll it directly — not throwaway work.
- **D-12:** Dashboard gets an **alerts feed/banner** (unacknowledged alerts, dismissible) above the device grid, alongside the existing Phase 2 D-13 summary banner — this is the "you need to act on this" view. The per-device good/warning/critical badge (D-06) remains the "at a glance" view on each card. Both are needed; neither replaces the other.
- **D-13:** SEC-02 (unknown device joins) and SEC-04 (status badge) both write into `security_alerts` for visibility now; actual push delivery is correctly deferred to Phase 5 per the roadmap — this phase's job stops at "detected, classified, and durably recorded."

### Claude's Discretion
- Exact daily-scan scheduling mechanism (cron-like loop vs APScheduler vs simple interval task) — implementation detail, not product-visible.
- Exact bandwidth-anomaly threshold multiplier (D-09) and rolling-average window length — tune during implementation/testing.
- Exact per-device-type expected-ports allowlist contents beyond the examples above (D-05) — researcher/planner should finalize the full table per `DeviceType` enum value.
- `security_alerts` schema details (indexes, exact column types) beyond the shape specified in D-11.
- Whether scan results themselves are persisted as a separate `port_scan_results` history table or only the latest result per device — left to planner, as long as the derived status (D-06/D-07) is always queryable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements & Roadmap
- `.planning/ROADMAP.md` — Phase 4 section: goal, success criteria (4 items), requirements SEC-01..04
- `.planning/REQUIREMENTS.md` — Full SEC-01..04 requirement text (SEC-02 explicitly notes delivery is deferred to Phase 5)
- `.planning/PROJECT.md` — Key Decisions table: adapter pattern (informs D-08/D-10's `ThreatIntelSource`), "no telemetry/no external calls unless configured" constraint (directly governs D-08/D-10), Docker Compose / CAP_NET_RAW+CAP_NET_ADMIN-never-privileged constraint (informs D-03)

### Prior Phase Context
- `.planning/phases/02-device-registry-discovery/02-CONTEXT.md` — D-08 (discovery stays pure-passive, active scanning explicitly punted to Phase 4), D-14 (closed `DeviceType` enum created specifically to key Phase 4's port rules off of), D-16 (`trusted` boolean, still unconsumed — Phase 4 does not need to consume it either)
- `.planning/phases/03-live-traffic-bandwidth/03-CONTEXT.md` — D-05/D-07 swappable-source-interface pattern (mirrored for D-08's `ThreatIntelSource`); `traffic_flows`/`bandwidth_metrics` shape reused for D-09's bandwidth-anomaly signal
- `.planning/STATE.md` — Phase 1/3 note that TimescaleDB schema changes are expensive later (relevant if `security_alerts` or scan-result tables need hypertable treatment — they don't; both are plain relational tables, not time-series)

### Technology Stack
- `CLAUDE.md` — Network Inspection & Discovery section: `home-assistant-libs/python-nmap` fork (not the unmaintained `xael/python-nmap`) and system `nmap` binary install (directly informs D-04)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/src/models/device.py` — `DeviceType` enum (phone/laptop/desktop/tablet/iot_smart_home/tv_streaming/game_console/router_network/other) and `trusted: bool` field — the per-type expected-ports allowlist (D-05) keys directly off this existing enum, no schema change needed on `Device` itself for that part.
- `backend/src/routes/capture.py` — Existing `/api/capture/arp|dhcp|mdns` ingest-route pattern (loopback/gateway-trusted-only, Pydantic payload models) — the new scan-result ingest route (D-03) should follow this exact trust-boundary shape.
- `backend/src/services/domain_grouping.py` / `traffic_broadcaster.py` (Phase 3) — `traffic_flows`/`bandwidth_metrics` query patterns to reuse for the bandwidth-anomaly check (D-09) — no new capture/ingest path needed, just a new read-side query + threshold comparison.
- `capture/capture.py` + `capture/traffic_sniff.py` — Existing capture-container loop pattern (Scapy for low-volume ARP/DHCP/mDNS, dpkt for high-volume traffic) that the new on-demand/scheduled scan loop (D-01/D-03) should follow architecturally — same container, same POST-to-API discipline, new dependency (`nmap` binary + python-nmap fork per D-04).
- `frontend/src/lib/components/DeviceCard.svelte` — Existing card shape (type icon map keyed off `DeviceType`, Popover pattern for the Phase 2.1 info affordance) — the good/warning/critical badge (D-06) and a "Scan" button slot directly onto this component; the Popover pattern can likely be reused for showing scan-result detail on click.

### Established Patterns
- Capture container never writes to the DB directly — always POSTs to the API; ingest routes trust only loopback + runtime-detected default gateway. The new scan-result route follows this without exception (D-03).
- Swappable source/adapter interfaces are the established way to keep a feature open to future richer backends without a rewrite (router adapters, Phase 3's `BandwidthSource`) — `ThreatIntelSource` (D-08/D-10) is the same pattern applied to threat data.
- `DeviceType` as a closed enum exists specifically so a later phase (this one) could build type-aware rules — Phase 2's D-14 explicitly anticipated this.

### Integration Points
- New scan-trigger + scan-result-ingest routes sit alongside `backend/src/routes/devices.py` and `backend/src/routes/capture.py`.
- New `security_alerts` table and the status-derivation logic (D-06/D-07) sit between scan/traffic data and both `DeviceCard.svelte` (badge) and a new dashboard alerts-feed component (D-12).
- `capture/capture.py` gains a new scan loop/trigger-listener alongside its existing ARP/DHCP/mDNS/traffic threads.

</code_context>

<specifics>
## Specific Ideas

- User explicitly handed decision-making to Claude for all four gray areas in this phase, with the instruction to optimize for product strength, maintainability/testability, and consistency with the project's established architectural patterns (adapter/swappable-source pattern, capture-container-owns-privilege, table-driven rules over opaque logic) — not for the easiest implementation path.

</specifics>

<deferred>
## Deferred Ideas

- **Full 1–65535 port scan option** — deferred; top-1000 (D-02) is the v1 default. Could be a later opt-in "deep scan" if a user specifically needs it.
- **User-configurable remote threat-feed UI** (Spamhaus/FireHOL/etc.) — deferred; the `ThreatIntelSource` interface (D-08/D-10) is built to allow this later without rework, but the settings UI/fetch-scheduler itself is not built in Phase 4.
- **ML-based / statistical anomaly detection** beyond the simple bandwidth-spike threshold (D-09) — deferred; revisit only if the simple threshold proves insufficient in practice.

</deferred>

---

*Phase: 4-Security*
*Context gathered: 2026-06-20*
