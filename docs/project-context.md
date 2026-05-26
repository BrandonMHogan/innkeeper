# Project Context

> [!NOTE]
> This is the first document an Architect reads at the start of any session.
> If this file is empty or incomplete, ask the human to fill it in before proceeding — do not guess at the project's purpose.

---

## Project Name

**Innkeeper** — a self-hosted home network dashboard. Individual capabilities live in named modules (initial set: **Radar**, **Watch Dog**).

## What This Project Does

Innkeeper is a self-hosted dashboard that runs on a server on the operator's local network and provides visibility and control over every device on that network. It is composed of independent modules — each module owns a specific capability (device tracking, security scanning, etc.) and can be enabled or disabled independently. The dashboard is reachable from any device on the same LAN, behind authentication.

The two launch modules are:

- **Radar** — device inventory and (in home mode) traffic visibility. Discovers devices, lets the operator label/group/annotate them, tracks basic telemetry (up/down bandwidth, online/offline state), and — when the server is acting as the network gateway — reports per-device DNS/domain activity. Supports blocking and prioritizing devices via DNS blackhole.
- **Watch Dog** — security scanner. Sweeps the local network for open ports, identifies exposed services (unexpected web servers, open SSH, etc.), fingerprints service versions, and surfaces anything that looks like a vulnerability or misconfiguration.

The server is intentionally portable: the operator can start it, stop it, or carry it to a different network (e.g., an Airbnb). Innkeeper exposes a **Network Mode** setting that switches between two backend implementations of the same module interfaces:

- **Home mode** — the server is the network gateway (or the operator otherwise controls DNS/routing). Full functionality: bandwidth per device, DNS/domain logging, blocking, prioritization.
- **Portable mode** — the server is just another client on someone else's network. Discovery and security scanning still work; per-device traffic features gracefully degrade because the physics of switched/encrypted WiFi prevent passive capture of other devices' traffic.

The two modes sit behind a common interface so module code does not branch on mode; the runtime injects the appropriate backend at startup based on the operator's setting.

## Who Uses It

A single technically-comfortable operator (the project owner) running the server on their own hardware for their own household. Not multi-tenant, not a service offered to others. The operator is the only authenticated user in v1.

## Current State

Greenfield. The repository is initialized with Docker Compose, FastAPI, Svelte 5, and PostgreSQL scaffolding (see `docs/environment.md`). No module specs are written yet. The immediate next step is the SPEC-01 spec for Radar (device discovery and inventory), followed by SPEC-02 for Watch Dog.

## High-Level Goals

- **Full visibility on the home network** — every device that joins the LAN is discovered, labeled, and tracked, with bandwidth and domain telemetry available when the server is acting as the gateway.
- **Security awareness anywhere** — Watch Dog must produce useful results on *any* network the server connects to, including networks the operator does not own.
- **Portability without functional cliffs** — the same binary runs at home and on the road; the dashboard tells the operator clearly what each mode supports and degrades gracefully rather than failing.
- **Modularity as a first-class concern** — adding a new module (e.g., a future "Bandwidth Shaper" or "DNS Stats") must not require touching Radar, Watch Dog, the auth layer, or the dashboard chrome. Each module is its own self-contained unit with its own routes, jobs, schema, and frontend views, registered through a stable extension point.
- **One-command deploy** — `docker compose up` on any Linux host with Docker should produce a working dashboard.

## Out of Scope (Project-Level)

- **Cloud or SaaS deployment** — Innkeeper is self-hosted only; no hosted version, no telemetry phoning home, no per-tenant isolation.
- **Multi-user accounts and roles** — v1 ships with a single admin user and a password. RBAC, family/guest accounts, and SSO are deferred.
- **Router replacement or custom firmware** — Innkeeper does not replace OpenWrt/pfSense/UniFi and does not flash routers. It cooperates with whatever gateway exists.
- **Router API integrations for blocking/QoS** — v1 enforces blocks via DNS blackhole only. Pushing firewall rules to specific router vendors (UniFi, OpenWrt UCI, pfSense API) is a later module.
- **HTTPS interception / deep packet inspection** — Innkeeper does not MITM TLS traffic. Per-device visibility tops out at domains (via DNS) and flow metadata (via gateway accounting), not request bodies or full URLs.
- **Mobile native apps** — the dashboard is a responsive web app served to any device on the LAN; no iOS/Android binaries.
- **Capturing other devices' traffic in portable mode** — physically not possible without being the gateway; the system surfaces this limitation in the UI rather than pretending otherwise.
- **Internet-exposed access** — the dashboard binds to the LAN only. Remote access (Tailscale, VPN, reverse proxy) is the operator's responsibility, not a v1 feature.
