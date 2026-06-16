# Project Research Summary

**Project:** Innkeeper
**Domain:** Self-hosted home network monitoring & management platform
**Researched:** 2026-06-16
**Confidence:** MEDIUM-HIGH

## Executive Summary

Innkeeper is a self-hosted home-network monitoring and management platform that gives a single household full visibility into its devices and traffic — and the ability to act on it — across two modes: **home mode** (deep router integration for control) and **travel mode** (passive scanning to defend your own devices on untrusted networks). The expert pattern for this category is well established: device discovery via multiple fused sources, time-series storage for bandwidth, a real-time push dashboard, and an alerting layer. What makes Innkeeper genuinely novel is the **combination** — no existing tool (ntopng sees but can't act; Pi-hole blocks DNS but doesn't show devices; UniFi does both but only on UniFi gear) unifies visibility + control + dual-mode across any router brand. That combination, delivered through a router-agnostic adapter layer with passive fallback, is the moat.

The recommended build approach is dictated by two hard realities. First, the architecture must split into a **privileged data plane** (a tiny, isolated capture/scan container with only `NET_RAW`/`NET_ADMIN`, never `--privileged`) and an **unprivileged control/presentation plane** (FastAPI + Svelte + Postgres/TimescaleDB). Second, the **Device Registry is the keystone** — new-device alerts, security scans, and travel-mode scan scope all derive their meaning from it — so discovery -> registry must come early, with bandwidth/traffic as a parallel TimescaleDB track. The stack is modern and verified (FastAPI 0.136, Svelte 5/SvelteKit 2, PostgreSQL 17 + TimescaleDB 2.27, SSE via sse-starlette), with one required correction: **adopt Python 3.13, not 3.12**, because `aiounifi` v91 (the first router adapter) requires `>=3.13`.

The dominant risk, flagged independently by all four researchers, is that **packet capture is fundamentally crippled on Docker Desktop for macOS** — the stated Mac Mini target. On macOS, Docker runs containers inside a Linux VM, so `network_mode: host` is silently accepted-but-ignored and a Scapy sniffer sees only VM-internal traffic, not the LAN. This invalidates the headline features on the exact deployment hardware. The recommended resolution is to make the capture engine a **separable component**: run it as a native host process (or daemon) on macOS feeding the containerized backend, while a full Docker deployment with `network_mode: host` remains the path on Linux hosts. This must be settled with a **capture-feasibility spike as the literal first phase**, go/no-go, before any capture code is committed. Secondary risks — Scapy being the wrong tool for the bandwidth hot path, MAC randomization breaking device identity, UniFi API churn on firmware updates, and TimescaleDB unbounded growth under "never auto-delete" — all have known mitigations captured below.

## Key Findings

### Recommended Stack

The architectural backbone (FastAPI, Svelte 5, PostgreSQL+TimescaleDB, SSE, Docker Compose) was pre-decided in PROJECT.md; research confirmed current versions and prescribed supporting libraries. Confidence is HIGH (versions verified against PyPI/npm June 2026). **One decision conflict must be resolved first:** `aiounifi` v91 sets `requires-python = ">=3.13.0"`, so the project baseline must move from Python 3.12 to **Python 3.13** — every other library supports 3.13 and it is the correct long-term choice for a 2026 greenfield. See STACK.md for the full table and rationale.

**Core technologies:**
- **Python 3.13** (corrected from 3.12): backend runtime — required by `aiounifi`; latest stable.
- **FastAPI 0.136 + Pydantic 2.13 + Uvicorn (+uvloop):** async-native HTTP API — the standard for this profile.
- **sse-starlette:** production-grade Server-Sent Events — don't hand-roll SSE.
- **PostgreSQL 17 + TimescaleDB 2.27:** single store for config/registry + time-series hypertables — SQL-native, Grafana-compatible.
- **SQLAlchemy 2.0 async + asyncpg + Alembic:** ORM/migrations; create hypertables via explicit `create_hypertable` SQL, not the thin `sqlalchemy-timescaledb` dialect.
- **Scapy 2.7 + python-zeroconf + python-nmap (HA-libs fork) + mac-vendor-lookup:** discovery (ARP/mDNS/nmap/OUI) — Scapy for discovery only, **not** the bandwidth hot path.
- **aiounifi 91:** UniFi adapter (drives the 3.13 requirement), behind a `RouterAdapter` interface.
- **httpx (+ optional Apprise):** notifications to ntfy.sh/Pushover — avoid the unrelated PyPI `ntfy` package.
- **Svelte 5.56 / SvelteKit 2.65 / Vite 6 / TypeScript:** static SPA build (`adapter-static`), native `EventSource` for SSE.
- **Typer + Rich:** CLI reusing the backend API/models.

### Expected Features

The table-stakes set maps almost 1:1 to PROJECT.md's Device Visibility / Live Traffic requirements (HIGH confidence, consistent across 8 surveyed tools). The differentiators live in the *combination*, with dual-mode as the signature novel positioning. See FEATURES.md.

**Must have (table stakes):**
- Device discovery (IP, MAC, hostname, vendor, last-seen) — entry point of the whole category.
- Live device list with online/offline state (needs grace period to avoid flapping).
- **Device registry (name/owner/type)** — the keystone that makes "unknown device" meaningful.
- New/unknown-device alert — #1 home security expectation; depends entirely on the registry.
- Per-device bandwidth (current + historical) — the #1 home use case; drives TimescaleDB design.
- Real-time auto-updating dashboard (SSE); notifications to a channel; activity/event log; simple Docker Compose deploy.

**Should have (competitive differentiators):**
- **Dual-mode (home vs travel)** — no mainstream self-hosted tool models this; genuinely novel.
- **Unified visibility + control** (block device / block domain from the dashboard) — the "act on it" moat.
- Router-agnostic adapter architecture with passive fallback (core must work with zero adapters).
- Per-device security scan (open ports -> version-based CVE flagging); suspicious-traffic / bad-IP alerting.
- Configurable retention, never auto-deleted; Pi-hole + Grafana curated integrations; CLI.

**Defer (v2+) / anti-features:**
- Full PCAP capture, DPI built from scratch, active vuln exploitation/pen-testing.
- Auto-blocking / NAC-style quarantine (keep humans in the loop — alert + manual block for v1).
- Multi-network/multi-site, remote/WAN access, cloud sync, mobile native app, plugin marketplace, per-user RBAC, becoming the network's DHCP/DNS.

### Architecture Approach

Innkeeper splits into a **privileged data plane** (one minimal, host-networked, capability-scoped container that does *all* raw network access) and an **unprivileged control/presentation plane** (FastAPI + Svelte + Postgres). Data always flows source -> engine/adapter -> Postgres -> API -> SSE -> dashboard; control actions flow the reverse direction through the router adapter. The capture engine exposes no inbound ports and initiates all connections (outbound-only). Confidence is HIGH for component structure and privilege model. See ARCHITECTURE.md.

**Major components:**
1. **Capture/Scan Engine (privileged)** — Scapy sniffing, ARP/mDNS/nmap discovery, byte accounting; the *only* component with `NET_RAW`/`NET_ADMIN`.
2. **API Server (FastAPI, unprivileged)** — REST + SSE, business logic, Mode Manager, orchestration; the sole gateway for the frontend.
3. **Router Adapter Layer** — brand-specific control behind a `RouterAdapter` Protocol with `Capability` flags; UniFi first, travel mode = `NullRouterAdapter` (empty capabilities).
4. **Device Registry** — CRUD + MAC<->IP<->hostname identity reconciliation; the keystone and the travel-mode allow-list.
5. **Alert/Rule Engine + Notifier** — evaluates rules, pushes outbound-only to ntfy/Pushover.
6. **Postgres + TimescaleDB** — hypertables (continuous aggregates, no auto-delete) + relational config/registry/alerts.
7. **Frontend (Svelte 5)** — capability-gated UI reading `{mode, capabilities}` to honestly enable/disable controls.

### Critical Pitfalls

Top pitfalls ranked by impact (see PITFALLS.md for full detail and detection signs):

1. **Packet capture is crippled on Docker Desktop for macOS (the target hardware).** `network_mode: host` silently does nothing inside the macOS Linux VM; the sniffer sees VM-internal traffic, not the LAN — invalidating headline features. **Avoid by** making capture a separable component (native host agent on macOS feeding the containerized backend; full Docker `host` networking on Linux) and **gating it behind a Phase-0 feasibility spike** with a startup self-check that warns loudly if it can't see ARP/broadcast traffic.
2. **Scapy is the wrong tool for the bandwidth hot path.** Per-packet Python parsing drops packets, blows up RAM (`store=1`), and floods the DB. **Avoid by** using Scapy only for ARP/discovery; source bandwidth from router counters (home mode) or lightweight flow accounting (travel mode); always `sniff(store=0, filter=<BPF>)`; aggregate into time buckets and never store raw packets.
3. **Over-broad capture privilege turns the security tool into the attack surface.** **Avoid by** isolating capture to one tiny container with exactly `NET_RAW`+`NET_ADMIN` (`cap_drop: ALL` first, never `--privileged`/root), `no-new-privileges`, read-only FS, no inbound listeners, LAN-only bind on the UI, encrypted-at-rest credentials.
4. **Device identity built on MAC/ARP alone is unreliable.** MAC randomization (iOS/Android) makes one phone look like many "new devices," firing false alerts and fragmenting history. **Avoid by** fusing DHCP + mDNS + router client list + OUI into a stable fingerprint, detecting the locally-administered bit, allowing manual merge/claim, and correlating by hostname/mDNS before alerting.
5. **UniFi API breaks on firmware updates** (port/path moves, `X-API-KEY` auth shift). **Avoid by** making the adapter *real* isolation behind a stable internal interface, preferring `aiounifi`, supporting API-key auth, detecting controller version at connect, and degrading loudly to travel mode with a clear banner.
6. **TimescaleDB unbounded growth under "never auto-delete."** Wrong chunk sizing, high-cardinality `segmentby`, and no aggregates make dashboards time out and the SSD fill. **Avoid by** separating hypertables from config tables, deliberate `chunk_time_interval`, compression with low-cardinality `segmentby`, continuous aggregates, and reconciling "never delete" as **downsample-not-delete** (user-configurable high-res window).

## Implications for Roadmap

Based on combined research, the roadmap should follow the **capture-feasibility spine**: prove the hardest infra (privileged host-net capture, with the macOS caveat) early, then build the Device Registry keystone, then bandwidth, then control, then integrations. Suggested phase structure:

### Phase 0: Capture-Feasibility Spike + Skeleton
**Rationale:** The macOS/Docker capture constraint (Pitfall #1) is a *feasibility gate*, not a "be careful" item — it must be answered before any roadmap commits to capture topology. Pair it with the deploy skeleton so everything has a place to land.
**Delivers:** Decision on capture topology (native macOS agent vs Linux host vs router-sourced); a spike proving the chosen path can see real ARP/broadcast traffic; `docker compose up` skeleton (Postgres/Timescale + FastAPI health + Svelte shell).
**Addresses:** Docker Compose deployment (table stakes).
**Avoids:** Pitfall #1 (capture crippled on macOS) — with a go/no-go before capture code is written.

### Phase 1: Device Registry + Schema + Device-List UI
**Rationale:** The registry is the keystone; identity reconciliation (MAC/IP/hostname) is the data model everything references. TimescaleDB schema concerns (Pitfall #6) are cheapest to get right now.
**Delivers:** Device CRUD API, registry schema (name/owner/type, first/last-seen), device-list UI; separated hypertable-vs-config table design.
**Implements:** Device Registry component.
**Avoids:** Pitfall #6 (schema separation, chunk sizing) established early.

### Phase 2: Capture/Scan Engine — Passive Discovery (privileged container)
**Rationale:** Highest-risk component — build before depending on it. Proves the privilege + host-net + L2 problem against the Phase-0 topology decision.
**Delivers:** Isolated capture engine (NET_RAW/NET_ADMIN only) doing ARP + mDNS discovery, fused multi-source identity, writing devices to the registry.
**Uses:** Scapy, python-zeroconf, python-nmap, mac-vendor-lookup.
**Avoids:** Pitfalls #3 (least-privilege isolation) and #4 (multi-source identity, MAC-randomization handling).

### Phase 3: Real-Time Pipeline (engine -> Postgres -> LISTEN/NOTIFY -> SSE -> live list)
**Rationale:** Delivers the headline value ("see devices in real time") and validates the full data-flow spine end to end.
**Delivers:** Live device list updating via SSE; in-process event broker.
**Uses:** sse-starlette, native `EventSource`.
**Avoids:** Pitfall #10 (throttled aggregated snapshots, heartbeats + cleanup, disable proxy buffering).

### Phase 4: Per-Device Bandwidth Metrics (TimescaleDB hypertables + aggregates)
**Rationale:** First time-series feature; the #1 home use case; exercises continuous aggregates and the retention model.
**Delivers:** Byte counting (producer->buffer->consumer batched writes), hypertables, continuous aggregates, dashboard charts.
**Avoids:** Pitfall #2 (no per-packet parsing; router counters / flow accounting) and #6 (downsample-not-delete).

### Phase 5: Dual-Mode — NullRouterAdapter + Mode Manager + Capability-Gated UI
**Rationale:** Forces the adapter interface into existence *before* the UniFi adapter, and is immediately useful to the user (currently in a rental with no controllable router). Travel mode reframed as "defend your own devices."
**Delivers:** `RouterAdapter` Protocol + `Capability` flags, Mode Manager, honest capability-gated UI; travel scans scoped to registered devices only.
**Addresses:** Dual-mode differentiator; mode switcher requirement.
**Avoids:** Pitfall #8 (passive + own-devices-only default; captive-portal detection) and #9 (no dead control buttons in travel mode).

### Phase 6: UniFi Router Adapter (Home Mode)
**Rationale:** Adds control + more accurate metrics; depends on the adapter interface from Phase 5. Gated on the user's planned UniFi hardware purchase.
**Delivers:** `UniFiAdapter` (list clients, client stats, block/unblock) via `aiounifi`.
**Avoids:** Pitfall #5 (version-detect, API-key auth, graceful loud degradation) and #9 (declarative desired-state blocks reconciled on reconnect).

### Phase 7: Alert/Rule Engine + Notifier
**Rationale:** Needs device + metric data to evaluate against; outbound-only and low coupling.
**Delivers:** Rule engine (new-device, bad-IP, bandwidth-threshold) + ntfy/Pushover delivery.
**Avoids:** Pitfall #14 (rank/aggregate threat hits, user allow-listing) and #7 (encrypted secrets).

### Phase 8: Security Scan (nmap + CVE lookup)
**Rationale:** Reuses the privileged engine; independent feature; slots anytime after Phase 2.
**Delivers:** Open-port scan + version-based CVE flagging on registered/own devices.

### Phase 9: Curated Integrations (Pi-hole, Grafana) + Phase 10: CLI
**Rationale:** Sidecar/adapter additions on a stable core; CLI is a thin client over the stabilized API.
**Delivers:** Pi-hole domain-block path, Grafana read-only Postgres role, Typer/Rich CLI.

### Phase Ordering Rationale

- **Capture feasibility is the gate.** Phase 0's go/no-go on the macOS constraint shapes how much of the stack lives in Docker; nothing downstream is safe to plan until it's answered.
- **Registry before everything that derives meaning from it.** Unknown-device alerts, security scans, and travel-mode scope are all defined against the registry.
- **Riskiest infra (privileged capture) before features that depend on it** — surprises surface before the roadmap is committed.
- **Adapter interface (via cheap travel mode) before the UniFi adapter** — prevents `if router == "unifi"` leaking into core (Anti-Pattern #2) and is useful immediately to a router-less user.
- **Bandwidth depends on the real-time spine, which depends on the engine, which depends on the registry** — a strict dependency chain.
- **Hold the anti-creep line:** security scan, integrations, and CLI are deliberately late, each behind an adapter/integration boundary so they can be deferred without touching core.

### Research Flags

Phases likely needing `--research-phase` during planning:
- **Phase 0:** Capture topology on macOS — the cleanest mitigation (native agent vs Linux host vs router-sourced) is HIGH-confidence-problem / MEDIUM-confidence-fix. **Hard gate.**
- **Phase 1/4:** TimescaleDB schema — downsample-vs-"never-delete" policy and `segmentby` choice (expensive to change after years of data).
- **Phase 2:** MAC-randomization reconciliation / identity model — non-trivial and central.
- **Phase 4:** Travel-mode bandwidth accounting backend (flow vs router stats) — load-bearing, MEDIUM confidence.
- **Phase 5:** Captive-portal detection + safe-scan policy; travel-mode "network trust assessment" feature set (no off-the-shelf reference).
- **Phase 6:** UniFi adapter per-firmware specifics + graceful-degradation contract.
- **Phase 8:** Offline CVE/vuln data source under the no-cloud constraint; threat-intel/bad-IP feed for Phase 7.

Phases with standard patterns (skip research-phase):
- **Phase 3:** SSE real-time — well-documented (sse-starlette + LISTEN/NOTIFY); pitfalls known.
- **Phase 7 delivery / Phase 9 / Phase 10:** notifications, Pi-hole/Grafana integrations, CLI — established patterns over existing APIs.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified against PyPI/npm/official repos June 2026; Python 3.13 read from `aiounifi` pyproject. Bandwidth hot-path backend is MEDIUM. |
| Features | MEDIUM-HIGH | Table stakes consistent across 8 tools; dual-mode is novel with little prior art (MEDIUM there). |
| Architecture | HIGH | Component structure, privilege model, Docker boundaries verified against NetAlertX/Wireshark/Docker docs; exact build-order tradeoffs MEDIUM. |
| Pitfalls | MEDIUM-HIGH | Core mechanics (macOS capture, Scapy perf, MAC randomization, UniFi churn, TimescaleDB) verified against vendor docs; some operational items are domain experience. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **macOS capture mitigation (highest priority):** Problem is HIGH-confidence; cleanest fix is MEDIUM. Resolve in the Phase-0 spike with a real go/no-go and a startup self-check.
- **Travel-mode bandwidth accounting:** How to do flow-level accounting without per-packet Scapy. Resolve in Phase-4 research.
- **MAC-randomization identity model:** How aggressively to dedupe rotating MACs. Resolve in Phase-2 research.
- **TimescaleDB downsample-not-delete policy + segmentby:** Resolve in Phase-1/4 schema research before long-lived data accumulates.
- **CVE / threat-intel feeds (no-cloud):** Which offline-updatable sources. Resolve when Phases 7/8 are planned.
- **python-nmap fork publish status:** Confirm the HA-libs fork's PyPI/pin path before depending on it.
- **Captive-portal detection + "network trust assessment":** No off-the-shelf reference; scope as a Phase-5 feature.

## Sources

### Primary (HIGH confidence)
- aiounifi PyPI + pyproject.toml — v91, `requires-python >=3.13` (drives the Python version correction).
- FastAPI / Pydantic / TimescaleDB 2.27 / Scapy 2.7 / Svelte 5.56 / SvelteKit 2.65 release notes — version verification (June 2026).
- Docker host-networking unsupported on Mac (docs + roadmap issue #238); macvlan promiscuous requirement — capture constraint.
- NetAlertX network-mode docs; Wireshark CapturePrivileges; excessive-capabilities cheat sheet — privilege model.
- MAC-randomization (Apple/Android docs + academic study); UniFi API breaking changes (ubntwiki + HA community); TimescaleDB chunk/compression/continuous-aggregate docs.
- UniFi / Pi-hole / Home Assistant feature docs — table-stakes and registry patterns.

### Secondary (MEDIUM confidence)
- Scapy vs dpkt vs pyshark benchmark; Granian vs Uvicorn comparison — hot-path and ASGI tradeoffs.
- ntopng / Fing / Sniffnet reviews — differentiator landscape.
- Captive-portal detection / untrusted-network scanning risk; streaming-pipeline and network-monitor architecture references.

### Tertiary (LOW confidence)
- Dual-mode "network trust assessment" framing, blocking-persistence, SSE specifics, OUI/interface-naming — domain experience cross-referenced with PROJECT.md constraints; validate during phase planning.

---
*Research completed: 2026-06-16*
*Ready for roadmap: yes*
