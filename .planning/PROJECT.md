# Innkeeper

## What This Is

Innkeeper is a self-hosted home-server **module host**: a thin container + dashboard shell that loads isolated modules, each with its own API and data, rather than a fixed feature set with bolt-on plugins. v1 is a home network monitoring and management platform — connected devices, live traffic, bandwidth usage per device, and security issues — built as the first set of native modules on that host. It operates in two modes: **home mode** (deep router integration for full control) and **travel mode** (passive scanning to secure your own devices on untrusted networks). Designed for a single user/household but architected from day one for open-source distribution, potential commercial use, and a v2+ expansion beyond networking (media, cameras, third-party apps) without re-architecting the host.

## Core Value

See every device on your network and what it's doing, in real time — and be able to act on it.

## Requirements

### Validated

**Device Visibility** — Validated in Phase 2/3: discovery, registry, dashboard device list, and historical bandwidth on TimescaleDB
- [x] Discover all devices on the network (IP, MAC, hostname, vendor, last seen)
- [x] Device registry — user registers known devices (name, owner, type)
- [x] Live device list on the dashboard showing connected/disconnected state
- [x] Per-device bandwidth usage (historical, configurable retention, never auto-deleted)

**Live Traffic** — Validated in Phase 3: SSE live traffic feed, per-device destinations, network-wide bandwidth charts
- [x] Real-time traffic monitoring — active connections and top talkers per device
- [x] Per-device traffic breakdown by destination (domain/IP)
- [x] Dashboard updates in real time via SSE

**Security** — Validated in Phase 4: per-device port scans via the capture container, security status derivation, malicious-IP/bandwidth-anomaly alerting, unknown-device alerting (push delivery deferred to Phase 5)
- [x] Security scan per device — open ports, known vulnerabilities
- [x] Alert on unknown/unregistered devices joining the network
- [x] Alert on suspicious traffic patterns or known bad IPs

### Active

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
- Open module marketplace — curated integrations only for v1; community/third-party modules are a v2+ milestone
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
| ~~Plugin-first architecture~~ — **superseded 2026-06-21** | Superseded by the module-host pivot below; integrations are first-party native modules, not bolt-on plugins layered over a fixed core | Superseded |
| ~~Plugin UI via dedicated routes~~ — **superseded 2026-06-21** | Superseded — see "Module UI via dedicated routes" below (same no-module-federation constraint, module terminology) | Superseded |
| ~~Plugin contract scope: cannot replace core platform components~~ — **superseded 2026-06-21** | Directly contradicted the actual vision: core features (Devices, Traffic, Security) ARE modules, not exempt from the contract. See docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md | Superseded |
| ~~No plugin marketplace in v1~~ — **superseded 2026-06-21** | Superseded by "No module marketplace in v1" below (same decision, module terminology) | Superseded |
| Module-host platform (capability Protocols) | Core features (Devices, Traffic, Security) and all integrations are isolated native modules with their own API/data, not a fixed core + bolt-on plugins. Modules are composed via small `typing.Protocol` capabilities (HasAPIRoutes, HasUIPage, etc.) rather than one fat base class — additive evolution, no forced stub methods, scales to 20+ modules | — Pending |
| Support modules + ModuleRegistry interface resolution | Cross-cutting data (e.g. device identity) lives in support modules exposing a named Protocol (e.g. DeviceLookupInterface); a registry resolves the Protocol to whichever module currently provides it, keyed by type not module identity — so implementations are swappable later with zero consumer changes | — Pending |
| Per-module Postgres schema isolation | Each module with its own data gets its own Postgres schema and its own Alembic migration branch; a module may only query its own schema, everything else goes through a resolved interface | — Pending |
| DeviceIdentity as sole source of truth | DeviceIdentity (support module) owns canonical device data/CRUD/merge/inference; Devices (feature module) is a thin UI client of it, keeping its own schema only for UI-owned concerns (sort/search/display prefs) | — Pending |
| Module UI via dedicated routes | Each module gets its own page at /modules/[name]; no module federation or Svelte rebuild required to add/remove modules | — Pending |
| Shared frontend design system, convention not runtime-enforced | One CSS-variable token source + one shared shadcn-svelte component library; native modules default to using them (path of least resistance), enforced at UI-spec/review time, not by code — Svelte's default style scoping already prevents cross-module leakage | — Pending |
| No module marketplace in v1 | Config-file + dashboard toggle is sufficient; hosted registry is a future business decision; linked-module manifest format exists in v1 but the first real third-party module ships in v2 | — Pending |
| OpenSpec + GSD dual-layer process | GSD manages macro level (phases, requirements, roadmap, verification); OpenSpec manages micro level (per-feature spec → Given/When/Then scenarios → tests → implementation). For each PLAN.md task: `/opsx:propose` first, write tests from scenarios (TDD), implement to pass tests, then `/opsx:sync` + `/opsx:archive`. Specs live in `openspec/` at project root. | — Pending |
| ntfy.sh / Pushover for push notifications | Lightweight, self-hostable (ntfy.sh), no proprietary push infrastructure required; delivered via the Notifications module (Phase 5.2), not a core platform feature | — Pending |
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
*Last updated: 2026-06-21 — module platform pivot (see docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md): Phase 5 replaced with Module Platform Foundation, Phases 5.1 (Improve Device Identity) and 5.2 (Notifications) inserted*
