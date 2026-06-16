# Innkeeper

## What This Is

Innkeeper is a self-hosted home network monitoring and management platform. It runs on a local server (Mac Mini or similar) and gives you full visibility into your network — connected devices, live traffic, bandwidth usage per device, and security issues. It operates in two modes: **home mode** (deep router integration for full control) and **travel mode** (passive scanning to secure your own devices on untrusted networks). Designed for a single user/household but architected from day one for open-source distribution and potential commercial use.

## Core Value

See every device on your network and what it's doing, in real time — and be able to act on it.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Device Visibility**
- [ ] Discover all devices on the network (IP, MAC, hostname, vendor, last seen)
- [ ] Device registry — user registers known devices (name, owner, type)
- [ ] Live device list on the dashboard showing connected/disconnected state
- [ ] Per-device bandwidth usage (historical, configurable retention, never auto-deleted)

**Live Traffic**
- [ ] Real-time traffic monitoring — active connections and top talkers per device
- [ ] Per-device traffic breakdown by destination (domain/IP)
- [ ] Dashboard updates in real time via SSE

**Security**
- [ ] Security scan per device — open ports, known vulnerabilities
- [ ] Alert on unknown/unregistered devices joining the network
- [ ] Alert on suspicious traffic patterns or known bad IPs

**Control**
- [ ] Block a device from the network
- [ ] Block a domain or IP across the network

**Dual-Mode Operation**
- [ ] Home mode: deep integration via router adapter (UniFi first)
- [ ] Travel mode: passive scanning (ARP, mDNS, nmap) — own registered devices only
- [ ] Mode switcher in the dashboard; features that require home mode are clearly indicated when unavailable

**Notifications**
- [ ] Push alerts to phone via ntfy.sh or Pushover
- [ ] Configurable alert rules (new device, security issue, bandwidth threshold)

**Curated Integrations**
- [ ] Pi-hole integration (DNS-level ad/domain blocking)
- [ ] Grafana integration (expose metrics for custom dashboards)

**Platform**
- [ ] Web dashboard (primary interface, accessible from any device on the network)
- [ ] CLI for power users and scripting
- [ ] Docker Compose deployment — single command to stand up the full stack

### Out of Scope

- Remote access from outside home network — adds security complexity; use a VPN externally
- Cloud sync or any cloud dependencies for core features — all data stays local
- Mobile app — the web dashboard works from any phone browser on the network
- Open plugin marketplace — curated integrations only for v1; community plugins are a future milestone
- Support for multiple simultaneous networks — one active network profile at a time

## Context

**Hardware target:** Mac Mini or old PC (x86 / Apple Silicon), running Docker Compose. Chosen for low power consumption and always-on operation on the home network.

**Router situation:** User is currently in a rental (limited router access). Planning to purchase a **UniFi** router (Dream Router or Dream Machine) when moving back to their own home. UniFi has a strong API (aiounifi Python library available), making it the natural first adapter target.

**Network approach:** Router adapters provide the deepest integration. For networks without a supported router (rentals, hotels, Airbnb), Innkeeper falls back to passive scanning — ARP, mDNS, nmap — which still surfaces device discovery and security info but loses blocking/control capabilities.

**Open-source intent:** Architecture decisions (adapter pattern, Docker Compose, no hard-coded network assumptions) are made with open-source and potential commercial distribution in mind. Nothing should be tied to one machine, network, or router brand.

**Data:** Time-series metrics (bandwidth, traffic) live in PostgreSQL + TimescaleDB. Config, device registry, and alerts live in the same PostgreSQL instance. Retention is user-configurable with no automatic deletion.

## Constraints

- **Portability**: No machine-specific or network-specific assumptions anywhere — must work on any Docker-capable machine joined to any network
- **Self-hosted only**: All data stays local; no cloud services required for any core feature
- **Deployment via Docker Compose**: The full stack (backend, frontend, DB, optional integrations) must be launchable with `docker compose up`
- **Router-agnostic core**: Router integrations are adapters — the core platform must function (in limited mode) with no router integration at all
- **Data privacy**: Network traffic data is sensitive; no telemetry, no external calls unless user explicitly configures an integration

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python 3.13 + FastAPI for backend | aiounifi v91 requires Python ≥ 3.13; best network library ecosystem (Scapy, python-nmap, aiounifi); async-native; easy for open-source contributions | — Pending |
| Svelte 5 + TypeScript for frontend | User preference; clean syntax; smaller bundle than React; good for dashboard UIs | — Pending |
| PostgreSQL + TimescaleDB for all data | Single DB for config + time-series; SQL querying; Grafana-compatible; no InfluxDB query language to learn | — Pending |
| SSE over WebSockets for real-time | Dashboard data flows server → client only; SSE auto-reconnects, works through HTTP proxies, simpler to maintain | — Pending |
| Adapter pattern for router integrations | UniFi first, but architecture is extensible — enables other router brands and open-source contributions without core changes | — Pending |
| Dual-mode (home/travel) | Home network gives full control via router API; untrusted networks fall back to passive scanning focused on user's own registered devices | — Pending |
| Docker Compose deployment | Maximum portability; single-command setup; enables open-source adoption without complex install instructions | — Pending |
| Plugin-first architecture | All integrations (UniFi, Pi-hole, Grafana, ntfy.sh) are implemented as first-party plugins using the plugin contract — proves the system and enables third-party plugins later without architectural changes | — Pending |
| Plugin UI via dedicated routes | Each plugin gets its own page at /plugins/[name]; no module federation or Svelte rebuild required to add/remove plugins | — Pending |
| Plugin contract scope | Plugins can: add a UI page, subscribe to platform events, add API routes, register data collectors; they cannot replace core platform components | — Pending |
| No plugin marketplace in v1 | Config-file + dashboard toggle is sufficient; hosted registry is a future business decision | — Pending |
| OpenSpec + GSD dual-layer process | GSD manages macro level (phases, requirements, roadmap, verification); OpenSpec manages micro level (per-feature spec → Given/When/Then scenarios → tests → implementation). For each PLAN.md task: `/opsx:propose` first, write tests from scenarios (TDD), implement to pass tests, then `/opsx:sync` + `/opsx:archive`. Specs live in `openspec/` at project root. | — Pending |
| ntfy.sh / Pushover for push notifications | Lightweight, self-hostable (ntfy.sh), no proprietary push infrastructure required | — Pending |
| UniFi as first router integration target | User's planned router; strong API via aiounifi; large prosumer user base = most impactful first adapter | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-16 after initialization*
