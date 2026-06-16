# Architecture Patterns

**Domain:** Self-hosted home network monitoring & management platform
**Project:** Innkeeper
**Researched:** 2026-06-16
**Confidence:** HIGH for component structure & privilege model; MEDIUM for exact build-order tradeoffs; HIGH for Docker boundaries.

---

## Recommended Architecture

Innkeeper splits into a **privileged data plane** (raw network access) and an **unprivileged control/presentation plane** (API + UI + DB). This split is the single most important architectural decision and it falls directly out of how Docker handles raw network access (see Privilege Model below).

```
                          ┌──────────────────────────────────────────────┐
                          │                 HOST NETWORK                   │
                          │                                                │
   ┌──────────────┐       │   ┌───────────────────────────────────────┐   │
   │  Browser     │       │   │  CAPTURE/SCAN ENGINE  (privileged)     │   │
   │  (Svelte 5)  │       │   │  network_mode: host                    │   │
   └──────┬───────┘       │   │  cap_add: NET_RAW, NET_ADMIN           │   │
          │ HTTP + SSE    │   │                                        │   │
          ▼               │   │  - Passive sniffer (Scapy)             │   │
   ┌──────────────┐       │   │  - Active scanner (nmap, ARP, mDNS)    │   │
   │  API SERVER  │◀──────┼───│  - Per-device byte counters            │   │
   │  (FastAPI)   │ ipc   │   └───────────────┬───────────────────────┘   │
   │  bridge net  │       │                   │ writes observations        │
   └──┬────────┬──┘       └───────────────────┼────────────────────────────┘
      │        │                              │
      │        │ adapter calls (HTTPS)        │
      │        ▼                              ▼
      │  ┌──────────────┐            ┌─────────────────────┐
      │  │ ROUTER       │            │  POSTGRES +          │
      │  │ ADAPTER LAYER│───────────▶│  TimescaleDB         │
      │  │ (UniFi, ...) │  device/   │  - hypertables (ts)  │
      │  └──────────────┘  block ops │  - registry / config │
      │                              │  - alerts            │
      │  ┌──────────────┐            └─────────────────────┘
      └─▶│ NOTIFIER     │ ntfy/Pushover (outbound only)
         │ ALERT ENGINE │
         └──────────────┘

   Optional sidecars: Pi-hole (DNS block), Grafana (reads Postgres directly)
```

### Component Boundaries

| Component | Responsibility | Reads From | Writes To | Privilege |
|-----------|---------------|-----------|-----------|-----------|
| **Capture/Scan Engine** | Raw packet sniffing, ARP/mDNS/nmap discovery, per-device byte accounting | Host NIC | Postgres (raw observations + metrics) OR an ingest queue/API | **Privileged** (host net, NET_RAW/NET_ADMIN) |
| **API Server (FastAPI)** | REST + SSE endpoints, business logic, orchestration, auth | Postgres, Router Adapter, Engine status | Postgres, SSE stream | Unprivileged (bridge) |
| **Router Adapter Layer** | Brand-specific control: device list, block/unblock, DNS/IP block, client stats | Router API (UniFi etc.) | Postgres (enriched device data) | Unprivileged (HTTPS to router) |
| **Device Registry** | CRUD of known devices, name/owner/type, identity reconciliation (MAC↔IP↔hostname) | Postgres | Postgres | Unprivileged (a module inside API) |
| **Alert/Rule Engine** | Evaluate rules (new device, bad IP, bandwidth threshold), raise alerts | Postgres (events/metrics) | Postgres (alerts), Notifier | Unprivileged |
| **Notifier** | Deliver alerts to ntfy.sh / Pushover | Alert engine | External push service (outbound only) | Unprivileged |
| **Frontend (Svelte 5)** | Dashboard, device list, mode switcher, live updates | API (HTTP + SSE) | API (commands) | Unprivileged (static assets) |
| **Postgres + TimescaleDB** | Single store: time-series metrics (hypertables) + relational config/registry/alerts | — | Disk volume | Unprivileged |

**Boundary rules:**
- The **only** component that touches raw network interfaces is the Capture/Scan Engine. Nothing else needs `NET_RAW`. This keeps the attack surface of the privileged container as small as possible.
- The **only** component that talks to the router is the Router Adapter Layer, behind a single interface. Swapping UniFi for pfSense/OpenWrt must require zero changes elsewhere.
- The Frontend talks **only** to the API Server. It never reaches the engine, DB, or router directly.
- Grafana (optional) reads Postgres **directly** (read-only role) — it is an analytics escape hatch, not part of the core data path.

---

## Data Flow

Trace each data type from source to sink. Direction is always **left → right**.

### 1. Device presence (discovery)
```
Host NIC ─(ARP/mDNS reply, nmap, or router client list)→ Capture Engine / Router Adapter
   → normalize to {mac, ip, hostname, vendor, first_seen, last_seen}
   → Device Registry reconciliation (match to known device or flag unknown)
   → Postgres (devices table)
   → API reads → SSE push → Dashboard device list
```

### 2. Per-device bandwidth / traffic (time-series)
```
Host NIC packets ─(Scapy sniff, byte count per src/dst MAC)→ Capture Engine
   → aggregate into time buckets (e.g. 1s/10s flush)
   → Postgres TimescaleDB hypertable (device_metrics)
   → continuous aggregates roll up (1m/1h/1d) for fast dashboards
   → API queries window → SSE push → Dashboard charts
```
*Note:* Router adapters can supply per-client throughput counters directly (UniFi exposes `tx/rx bytes`), which is **more accurate and lower-overhead** than packet counting. Prefer adapter-sourced counters in home mode; fall back to Scapy counting in travel mode.

### 3. Top talkers / destination breakdown
```
Scapy flow records (src,dst,port,bytes) ─→ Capture Engine
   → optional reverse-DNS / SNI enrichment → Postgres (flows/connections)
   → API aggregates by destination → Dashboard per-device breakdown
```

### 4. Security scan
```
API (on schedule or on-demand) ─→ Capture Engine (nmap port scan of target)
   → results {open_ports, services, CVE lookup} → Postgres (scan_results)
   → Alert engine evaluates → Notifier if issue → Dashboard
```

### 5. Control actions (write path — reverse direction)
```
Dashboard "Block device" ─→ API (command) ─→ Router Adapter ─→ Router API
   → confirm → Postgres (device.blocked=true, audit log) → SSE state update
```
Domain/IP blocking routes to **Pi-hole adapter** (DNS-level) and/or router firewall adapter depending on capability.

### 6. Real-time fan-out
All dashboard liveness uses **SSE, server→client only** (per stack decision). The API maintains an in-process event broker; engine/adapter writes publish to it (via Postgres `LISTEN/NOTIFY` or an internal async queue), and connected SSE clients receive deltas. SSE auto-reconnect handles travel-mode network flaps gracefully.

---

## Router Adapter Pattern

This is the extensibility backbone. Define a single abstract interface; each brand is a concrete implementation discovered/registered by capability.

### Interface design

```python
# core/adapters/base.py
from typing import Protocol, runtime_checkable
from dataclasses import dataclass
from enum import Flag, auto

class Capability(Flag):
    LIST_CLIENTS    = auto()   # who's connected
    CLIENT_STATS    = auto()   # per-client tx/rx bytes (preferred metric source)
    BLOCK_DEVICE    = auto()   # block/unblock a client
    BLOCK_DOMAIN    = auto()   # DNS/firewall domain block
    BLOCK_IP        = auto()   # firewall IP block
    EVENTS          = auto()   # connect/disconnect event stream

@dataclass
class Client:
    mac: str
    ip: str | None
    hostname: str | None
    vendor: str | None
    rx_bytes: int | None
    tx_bytes: int | None
    is_blocked: bool

@runtime_checkable
class RouterAdapter(Protocol):
    name: str
    capabilities: Capability

    async def connect(self) -> None: ...
    async def health(self) -> bool: ...
    async def list_clients(self) -> list[Client]: ...
    async def block_device(self, mac: str) -> None: ...
    async def unblock_device(self, mac: str) -> None: ...
    async def block_domain(self, domain: str) -> None: ...
    async def block_ip(self, ip: str) -> None: ...
    # capability-gated; callers MUST check `capabilities` before invoking
```

### Design principles
1. **Capability flags, not assumptions.** The API queries `adapter.capabilities` and the UI greys out actions the active adapter can't do. This is the same mechanism that powers dual-mode (travel mode = "null adapter" with empty capabilities).
2. **Async-native.** UniFi's `aiounifi` is asyncio + aiohttp; the adapter contract is async to match FastAPI and avoid blocking the event loop.
3. **Normalize to a common `Client` model.** Each adapter translates brand-specific JSON into Innkeeper's canonical schema so the registry/UI never see vendor quirks.
4. **Health + reconnect.** `health()` lets the mode manager decide whether home mode is actually available right now (router reachable, creds valid).
5. **Registry of adapters.** A factory selects the adapter from config (`router.type = unifi`). Adding pfSense/OpenWrt = drop a new file implementing the Protocol; no core changes. This is the open-source extension point.

### Concrete first target
- **UniFi via `aiounifi`** — supports all listed capabilities (clients, stats, block via `block_client`, events). ⚠️ **Version flag:** current `aiounifi` (released 2026-03) requires **Python ≥ 3.13**, but PROJECT.md specifies Python 3.12. Either pin an older aiounifi release that supports 3.12, or bump the runtime to 3.13. Resolve this during the router-adapter phase. (Confidence: HIGH — from PyPI/pyproject.)

### Dual-mode as an adapter concern
- **Home mode** = a real `RouterAdapter` is connected and healthy → full capabilities, control actions enabled.
- **Travel mode** = `NullRouterAdapter` (capabilities = empty) → control actions disabled in UI; only the Capture/Scan Engine's passive paths run, scoped to **registered devices only** per PROJECT.md.
- A **Mode Manager** in the API owns the active mode: it inspects adapter health, exposes current mode + available capabilities via an endpoint the frontend reads to enable/disable UI affordances. Mode is explicit (user switcher) but can auto-degrade to travel if the configured router becomes unreachable.

---

## Privilege / Security Model (packet capture)

**The core problem:** Scapy raw sniffing and ARP/mDNS L2 discovery need raw sockets, AND they need to see the real LAN — Docker **bridge networking hides L2 traffic** (ARP/NBNS/mDNS multicast don't cross the bridge). Confirmed by NetAlertX docs and multiple sources.

### Recommended model
Run **only** the Capture/Scan Engine with elevated access; keep everything else unprivileged:

```yaml
# docker-compose.yml (engine service only)
services:
  capture-engine:
    network_mode: host          # required for L2 visibility (ARP/mDNS/multicast)
    cap_drop: [ALL]             # drop everything first
    cap_add:
      - NET_RAW                 # raw sockets for Scapy / ARP
      - NET_ADMIN               # interface config, promiscuous mode
    # NO --privileged: that grants all caps + lifts cgroup device limits
```

### Rules
1. **Least privilege, not `--privileged`.** Grant exactly `NET_RAW` + `NET_ADMIN`. Avoid `--privileged` entirely (multiple sources flag it as excessive).
2. **Isolate privilege to one tiny container.** The engine should be a minimal image whose only job is capture/scan. FastAPI, DB, frontend stay on the default bridge with no extra caps.
3. **Drop privileges inside the process where possible.** Acquire raw sockets at startup, then drop to a non-root user for the long-running loop if feasible (Scapy can be run by a user holding `cap_net_raw` via `setcap` on the Python binary). At minimum, run the engine process as non-root with file-capabilities rather than UID 0.
4. **No inbound listeners on the privileged container.** Because it's on host network, it must not expose ports. It communicates **outbound only** — writing to Postgres or POSTing to the API. This prevents the host-networked container from becoming a network entry point.
5. **Read-only filesystem + no-new-privileges.** Add `security_opt: [no-new-privileges:true]` and `read_only: true` (with a tmpfs for scratch) to the engine.
6. **macOS caveat.** PROJECT.md targets a Mac Mini. `network_mode: host` and Linux capabilities **do not behave the same on Docker Desktop for macOS** (containers run inside a Linux VM, so "host" is the VM, not macOS). For full L2 capture the realistic target is **Linux host or the engine running natively / in a Linux VM with the LAN bridged**. Flag this for the deployment phase — it materially affects how much works on a Mac Mini under Docker Desktop vs. Asahi/Linux. (Confidence: HIGH that this is a constraint; MEDIUM on the cleanest workaround.)

---

## Patterns to Follow

### Pattern 1: Privileged data plane / unprivileged control plane split
**What:** One small host-networked, capability-scoped container for capture; everything else normal bridge containers.
**When:** Always, given raw-capture requirements.
**Why:** Minimizes attack surface; keeps the API/UI/DB portable and CVE-exposed-only-to-normal-risk.

### Pattern 2: Producer → buffer → consumer ingestion
**What:** Engine produces observations; a bounded buffer/queue decouples capture rate from DB write rate; consumer batches inserts into TimescaleDB.
**When:** For the high-rate metrics/flows path.
**Example:** Engine flushes per-device byte counters every N seconds into batched COPY/INSERT; never one-row-per-packet.

### Pattern 3: TimescaleDB hypertables + continuous aggregates
**What:** Store raw metrics in a hypertable; define continuous aggregates (1m/1h/1d) for dashboard queries; **no automatic retention/drop** per PROJECT.md.
**When:** All time-series (bandwidth, flows).
**Why:** Fast dashboards without scanning raw rows; Grafana-friendly; respects "never auto-deleted."

### Pattern 4: Capability-gated UI
**What:** Frontend reads `{mode, capabilities}` from API and enables/disables controls.
**When:** Everywhere a control action depends on home mode.
**Why:** Makes dual-mode honest — no dead buttons, clear "requires home mode" indicators (a stated requirement).

### Pattern 5: Postgres LISTEN/NOTIFY → SSE
**What:** Writers issue `NOTIFY`; API holds a listener and fans out to SSE clients.
**When:** Real-time dashboard updates.
**Why:** Avoids polling; single source of truth is the DB; survives reconnects.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: One monolithic privileged container
**What:** Running FastAPI + capture + DB together with `--privileged` / host net for convenience.
**Why bad:** Massively enlarges attack surface; any FastAPI dependency CVE now runs with raw-socket/host access; breaks portability.
**Instead:** Isolate capture as described in the Privilege Model.

### Anti-Pattern 2: Router-specific logic leaking into core
**What:** `if router == "unifi"` branches in the API/registry/UI.
**Why bad:** Defeats the open-source extensibility goal; every new brand touches core.
**Instead:** Everything brand-specific lives behind the `RouterAdapter` Protocol + capability flags.

### Anti-Pattern 3: One DB row per packet / per flow event
**What:** Inserting on every packet.
**Why bad:** TimescaleDB will choke; disk explodes; defeats "never auto-delete."
**Instead:** Aggregate in the engine, batch-write time buckets; prefer router counters when available.

### Anti-Pattern 4: Frontend reaching past the API
**What:** Svelte hitting Postgres or the router directly.
**Why bad:** Breaks auth, breaks the adapter abstraction, couples UI to infra.
**Instead:** API is the only gateway; Grafana is the sole sanctioned direct-read consumer.

### Anti-Pattern 5: Assuming bridge networking will see the LAN
**What:** Default Docker bridge for the capture engine.
**Why bad:** ARP/mDNS/multicast invisible → discovery silently returns almost nothing.
**Instead:** `network_mode: host` for the engine only.

---

## Suggested Build Order

Ordered by dependency — each step unlocks the next and yields something demonstrable. This directly informs roadmap phases.

| # | Build | Why first / unlocks | Dependencies |
|---|-------|--------------------|--------------|
| **0** | **Skeleton: Docker Compose + Postgres/Timescale + FastAPI health + Svelte shell** | Establishes the deploy contract (the whole point: `docker compose up`); gives a place for everything to land | none |
| **1** | **Device Registry + schema + basic device CRUD API + device-list UI** | Core data model everything else references; reconciliation identity (MAC/IP/hostname) is foundational; demoable list | 0 |
| **2** | **Capture/Scan Engine — passive discovery (ARP + mDNS) in host-net privileged container, writing devices** | Proves the hardest infra problem (privilege + host net + L2) early; populates the registry with real devices; **this is the highest-risk component, build it before depending on it** | 0,1 |
| **3** | **Real-time pipeline: engine → Postgres → LISTEN/NOTIFY → SSE → live device list** | Delivers the headline value ("see devices in real time"); validates the whole data-flow spine end to end | 1,2 |
| **4** | **Per-device bandwidth metrics: Timescale hypertables + engine byte counting + dashboard charts** | First time-series feature; exercises continuous aggregates and retention model | 2,3 |
| **5** | **Travel mode = NullRouterAdapter + Mode Manager + capability-gated UI** | Cheap to add once the adapter interface exists; makes the app useful with no router (user's current rental situation!) | 1,3 |
| **6** | **UniFi Router Adapter (home mode): list clients, client stats, block/unblock** | Adds control + better metrics; depends on the adapter interface being defined in step 5 | 5 |
| **7** | **Alert/Rule Engine + Notifier (ntfy/Pushover): new-device + bad-IP + bandwidth-threshold rules** | Needs device/metric data to evaluate against; outbound-only, low coupling | 3,4 |
| **8** | **Security scan (nmap port scan + CVE lookup) via engine** | Reuses privileged engine; independent feature; can slot anytime after step 2 | 2 |
| **9** | **Curated integrations: Pi-hole (domain block), Grafana (read-only Postgres role)** | Both are sidecar/adapter additions; Pi-hole gives domain-block capability independent of router | 6 (Pi-hole as block path), 4 (Grafana) |
| **10** | **CLI** | Thin client over the same API; build once API surface is stable | 1–7 |

**Critical-path rationale:**
- Step 2 (privileged capture) is the **riskiest** piece (host-net + caps + macOS caveat). Build/validate it early so the privilege/deployment surprises surface before the roadmap commits to it.
- The **adapter interface** must exist (step 5) *before* the UniFi adapter (step 6); travel mode is the cheapest way to force that interface into existence and is immediately useful to the user (currently in a rental).
- Metrics (step 4) depend on the real-time spine (step 3), which depends on the engine (step 2) and registry (step 1).

---

## Docker Service Boundaries (Compose map)

| Service | Image basis | Network | Caps | Exposes | Notes |
|---------|------------|---------|------|---------|-------|
| `db` | timescale/timescaledb (Postgres+TSDB) | bridge | none | 5432 (internal) | named volume; no auto-retention |
| `api` | python:3.x + FastAPI/uvicorn | bridge | none | 8000 (proxied) | talks to db, adapter, engine status |
| `capture-engine` | minimal python + scapy/nmap | **host** | NET_RAW, NET_ADMIN | **none** | `no-new-privileges`, outbound-only |
| `frontend` | static (nginx/caddy serving Svelte build) | bridge | none | 80/443 | reverse-proxies `/api` + `/sse` to api |
| `pihole` (opt) | pihole/pihole | bridge/macvlan | NET_ADMIN | 53/80 | domain-block adapter target |
| `grafana` (opt) | grafana/grafana | bridge | none | 3000 | read-only DB role |

**Engine↔API/DB communication:** because the engine is on host network and exposes nothing, it must **initiate** all connections — connecting to `db` and `api` via the host-mapped ports (or a shared Docker network reachable from host net). Define this contract explicitly; it's the one place the privileged/unprivileged split needs a deliberate bridge.

---

## Scalability Considerations

A single household is small, but architecture should not actively prevent growth.

| Concern | Home (≤50 devices) | Heavy (≤500 devices / power user) | Notes |
|---------|--------------------|-----------------------------------|-------|
| Metric write volume | Direct batched inserts | Bounded queue + COPY batching | Pattern 2 already covers this |
| Dashboard queries | Query raw + 1m aggregate | Lean on continuous aggregates | Timescale handles it |
| Capture overhead | Scapy fine | Prefer router counters; sample flows | Adapter stats >> packet counting |
| Retention | Keep all (per requirement) | Compress old chunks (Timescale native compression, no delete) | Honors "never auto-delete" while controlling size |

---

## Sources

- [aiounifi · PyPI](https://pypi.org/project/aiounifi/) — current version, Python ≥3.13 requirement, async/aiohttp (HIGH)
- [aiounifi pyproject.toml (GitHub)](https://github.com/Kane610/aiounifi/blob/master/pyproject.toml) — dependency/runtime constraints (HIGH)
- [NetAlertX network mode docs](https://docs.netalertx.com/docker-troubleshooting/network-mode/) — bridge blocks ARP/NBNS/mDNS; host net + NET_RAW/NET_ADMIN/NET_BIND_SERVICE required (HIGH)
- [NetAlertX issue #1353](https://github.com/netalertx/NetAlertX/issues/1353) — host network mode in practice (MEDIUM)
- [Wireshark CapturePrivileges wiki](https://wiki.wireshark.org/capturesetup/captureprivileges) — CAP_NET_RAW for capture, least-privilege over root (HIGH)
- [Excessive Capabilities cheat sheet](https://0xn3va.gitbook.io/cheat-sheets/container/escaping/excessive-capabilities) — avoid --privileged, NET_ADMIN scope (HIGH)
- [Docker container capabilities guide](https://oneuptime.com/blog/post/2026-01-25-docker-container-capabilities/view) — cap_drop ALL + selective cap_add pattern (MEDIUM)
- [scapy issue #3151 run without sudo](https://github.com/secdev/scapy/issues/3151) — setcap on Python binary for raw sockets (MEDIUM)
- [Streaming data pipelines architecture](https://www.acceldata.io/blog/mastering-streaming-data-pipelines-for-real-time-data-processing) — ingest → process → store staging (MEDIUM)
- [Architecture of a Network Monitor (ICIR/nprobe)](https://www.icir.org/christian/publications/nprobe.pdf) — capture engine component structure (MEDIUM)
