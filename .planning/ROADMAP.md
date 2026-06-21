# Roadmap: Innkeeper

## Overview

Innkeeper delivers full visibility and control over a home network through a privileged capture engine feeding an unprivileged FastAPI + Svelte stack. The journey starts by resolving the single hardest unknown — whether packet capture is even feasible on the macOS/Docker target — and standing up a deployable, password-protected skeleton. From there the Device Registry keystone is built (everything downstream derives meaning from it), followed by the real-time traffic and bandwidth spine and per-device security. Phase 5 then retrofits Devices, Traffic, and Security onto a true module-host platform — capability-Protocol contracts, a registry that resolves support interfaces by type so implementations stay swappable, and per-module schema isolation — so the rest of the roadmap (and the eventual v2 expansion into media/cameras/third-party modules) builds on a real foundation instead of bolt-on plugins. Device identification quality is improved next (now isolated and swappable inside its own module), then notifications, dual-mode operation (travel/home), the UniFi adapter and curated integrations, and finally the topology map and Wake-on-LAN round out the network visualization.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation + Capture Feasibility** - Deployable skeleton, password auth, and a go/no-go capture-topology spike resolving the macOS constraint (completed 2026-06-18)
- [x] **Phase 2: Device Registry + Discovery** - Multi-source device discovery feeding a registry with named/owned devices and unknown-device detection (completed 2026-06-18)
- [x] **Phase 3: Live Traffic + Bandwidth** - SSE-powered live traffic feed and per-device + network-wide bandwidth history on TimescaleDB (completed 2026-06-19)
- [x] **Phase 4: Security** - Per-device port scans, security status, and alerts for unknown devices and suspicious traffic (completed 2026-06-20)
- [x] **Phase 5: Module Platform Foundation** - Module-host infrastructure (registry, event bus, capability protocols) and retrofit of Devices/Traffic/Security onto isolated, swappable modules (completed 2026-06-21)
- [ ] **Phase 5.1: Improve Device Identity** (INSERTED) - Deeper inference (hostname heuristics, broader mDNS parsing, MAC-randomization handling) inside the now-isolated DeviceIdentity module
- [ ] **Phase 5.2: Notifications** (INSERTED) - First-party notification module (ntfy.sh/Pushover) built clean on the new module contract
- [ ] **Phase 6: Dual-Mode + Control** - Travel mode passive scanning, mode switcher with capability-gated UI, auto-degrade, and device blocking
- [ ] **Phase 7: UniFi + Integrations** - UniFi home-mode adapter, Pi-hole and Grafana plugins, and network-wide domain blocking
- [ ] **Phase 8: Network Visualization** - Interactive topology map and Wake-on-LAN from the dashboard

## Phase Details

### Phase 1: Foundation + Capture Feasibility

**Goal**: A user can run `docker compose up`, complete a first-run password setup, and reach a protected dashboard shell — and the capture-engine topology question (native macOS agent vs Linux host networking) is resolved with a working spike before any capture feature is built.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: PLAT-01, PLAT-02, PLAT-03, AUTH-01, AUTH-02, AUTH-03
**Success Criteria** (what must be TRUE):

  1. User can stand up the full stack (API, frontend, database, capture engine) with a single `docker compose up` on a Docker-capable machine
  2. On first run, the user is prompted to set a dashboard password and cannot reach the UI until it is set
  3. User must authenticate to view any page, and the session persists across browser refresh
  4. User can open the dashboard from any other device on the local network with nothing installed on that device
  5. A documented go/no-go decision and working spike prove the chosen capture topology can observe real ARP/broadcast LAN traffic; the capture engine runs with only CAP_NET_RAW + CAP_NET_ADMIN (never --privileged)

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Backend foundation: settings, DB, models, Alembic/TimescaleDB migration, auth + capture-ingest routes with pytest coverage
- [x] 01-03-PLAN.md — SvelteKit frontend: scaffold, theme tokens, API client, /setup /login /dashboard pages per UI-SPEC

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Capture service + docker-compose.yml topology; D-05 go/no-go ARP capture spike (human-verify checkpoint)

### Phase 2: Device Registry + Discovery

**Goal**: A user can see every device on the network — automatically discovered with fused multi-source identity — register the ones they own with name/owner/type, and have unrecognized devices surface as unknown.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: DISC-01, DISC-02, DISC-03, DISC-04
**Success Criteria** (what must be TRUE):

  1. System automatically discovers devices via ARP, mDNS, and DHCP lease analysis, fusing sources so a single MAC-randomizing phone is not fragmented into many phantom devices
  2. User can register a device and assign it a name, owner, type, and trusted flag
  3. User can view each device's first-seen and last-seen timestamps
  4. A device that is not in the registry appears clearly marked as unknown when it joins the network

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Backend discovery foundation: DHCP/mDNS models, IdentityResolver fusion seam, discovery orchestration, devices registry API

**Wave 2** *(blocked on Wave 1 completion, parallel with each other)*

- [x] 02-02-PLAN.md — Capture container: real DHCP sniff + AsyncZeroconf mDNS browser, zeroconf legitimacy checkpoint
- [x] 02-03-PLAN.md — Frontend: dashboard card grid, summary banner, Register/Merge dialogs

### Phase 02.1: Device Identification Hints (INSERTED)

**Goal:** When an unknown device shows up on the dashboard, the user has an immediate, best-effort idea of what it is (vendor + likely type) without needing to open the register dialog to investigate — and that same guess pre-fills the register form as a starting point the user can freely override.
**Mode:** mvp
**Requirements**: DISC-05, DISC-06
**Depends on:** Phase 2
**Success Criteria** (what must be TRUE):

  1. An unknown device's card shows an inferred vendor name (e.g. "Apple", "Samsung", "Sonos") derived from its MAC OUI prefix, when a real (non-placeholder) MAC is available
  2. An unknown device's card shows a best-effort type/category guess (e.g. phone, computer, TV/streaming, smart-home) derived from vendor + mDNS service type + DHCP vendor class, when enough signal exists to guess
  3. When no reliable signal exists for vendor or type, the card shows plain "Unknown" rather than a fabricated guess
  4. Opening the Register dialog for an unknown device pre-fills the type field (and name field, when a hostname is available) with the inferred guess — the user can change or clear it before submitting, and the inference is never silently saved as fact

**Plans:** 2/2 plans executed

Plans:
**Wave 1**

- [x] 02.1-01-PLAN.md — Backend inference engine: schema extension (mdns_service_type/dhcp_vendor_class), identity_inference.py vendor/type-guess logic, /api/devices/ wiring

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02.1-02-PLAN.md — Frontend: inference line + raw-signal info popover on DeviceCard, Register dialog pre-fill

### Phase 3: Live Traffic + Bandwidth

**Goal**: A user can watch network activity update live without refreshing and explore both per-device and network-wide bandwidth over any time range, with data retained indefinitely by default.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: TRAF-01, TRAF-02, TRAF-03, TRAF-04
**Success Criteria** (what must be TRUE):

  1. User can view a live traffic feed of active connections and top talkers per device that updates via SSE without a page refresh
  2. User can view historical bandwidth per device over any chosen time range, with retention configurable and never auto-deleted by default
  3. User can see, per device, which domains and IPs that device is communicating with
  4. User can view network-wide bandwidth totals as a chart with daily, weekly, and monthly views

**Plans**: 4 plans
Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Backend storage foundation: traffic_flows hypertable, device_mac_history, swappable BandwidthSource interface, domain grouping
- [x] 03-02-PLAN.md — Capture container: dpkt WAN traffic sniff loop, 5-tuple aggregation, passive DNS cache

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-03-PLAN.md — Backend: /api/capture/traffic ingest route, SSE broadcaster, historical/destinations/network-wide query routes

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-04-PLAN.md — Frontend: live traffic feed (SSE), bandwidth history chart, destinations breakdown, network-wide chart

### Phase 4: Security

**Goal**: A user can assess the security posture of each device at a glance and be alerted when something concerning happens — an unknown device appears or a device talks to a known-bad destination.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04
**Success Criteria** (what must be TRUE):

  1. User can run an open-port scan against any device and see results, with ports flagged as unexpected for that device type
  2. Each device card prominently shows a security status of good, warning, or critical derived from scan results
  3. System detects and alerts when a device connects to a known malicious IP or shows suspicious traffic patterns
  4. System raises an alert when an unregistered device joins the network (delivery handled once notifications exist)

**Plans**: 4 plans
Plans:
**Wave 1**

- [x] 04-01-PLAN.md — Backend data layer: Device security columns, port_scan_results/security_alerts/pending_scan_requests tables, port_rules/security_status/threat_intel_source pure-function services, vendored FireHOL blocklist

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-02-PLAN.md — Backend routes: /api/security/* (scan-trigger, alerts), /api/capture/* extensions (scan ingest, pending-scan poll, daily-rescan queue, malicious-IP check), SEC-02 unknown-device alert hook

**Wave 3** *(blocked on Wave 2 completion, parallel with each other)*

- [x] 04-03-PLAN.md — Capture container: nmap port-scan listener + daily-rescan trigger, python-nmap fork dependency (human-verify checkpoint)
- [x] 04-04-PLAN.md — Frontend: security badge + Scan button on DeviceCard, ScanResultDialog, SecurityAlertsBanner

**UI hint**: yes

### Phase 5: Module Platform Foundation

**Goal**: Devices, Traffic, and Security — already built as core-app code in Phases 1-4 — are retrofitted into isolated, independently-replaceable modules on a real module-host platform, proving the platform supports both first-party native modules and (eventually) third-party linked modules before any further feature work proceeds.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: MOD-01, MOD-02, MOD-03, MOD-04, MOD-05, MOD-06, MOD-07, MOD-08
**Success Criteria** (what must be TRUE):

  1. A documented module contract exists: capability Protocols (HasAPIRoutes, HasUIPage, HasEventSubscriptions, HasCollector), a typed ModuleManifest (id, kind, provides, requires, db_schema), and a ModuleLoader that topologically sorts and instantiates modules via constructor injection
  2. A ModuleRegistry resolves support interfaces (e.g. DeviceLookupInterface) by Protocol type rather than module identity, so a provider can be swapped later without touching any consumer; the loader fails fast at startup on an unsatisfied `requires` or a `provides` conflict
  3. DeviceIdentity exists as a support module (its own Postgres schema) — sole source of truth for device data, CRUD, merge, and inference, exposing DeviceLookupInterface; Devices, Traffic, and Security are retrofitted to call it instead of owning or duplicating device data
  4. Devices is a thin feature module (dashboard card grid, register/merge dialogs) that performs every device read/write through DeviceIdentity, keeping its own schema only for UI-owned concerns (sort order, search history, display prefs)
  5. A shared frontend design-token source and shared component library exist and are used by the retrofitted Devices/Traffic/Security UI, proving the "use ours by default, opt out if needed" convention holds across modules
  6. A linked-module manifest format and a "Linked Apps" dashboard section exist (data model + empty-state UI only — no real third-party module ships this phase)

**Plans**: 6 plans (supersedes the 4 plans originally drafted against the retired bolt-on plugin contract; see `.planning/phases/05-plugin-system-notifications/_superseded-bolt-on-plugin-model/`)
Plans:
**Wave 1**

- [x] 05-01-PLAN.md — Host infrastructure: capability Protocols, ModuleManifest, ModuleRegistry, ModuleLoader (graphlib topo-sort), EventBus, module_configs table, schema-portability spike
- [x] 05-02-PLAN.md — Linked Apps data model + dashboard empty-state section, frontend design-token/component-library consolidation

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 05-03-PLAN.md — DeviceIdentity support module extraction (own Postgres schema, DeviceLookupInterface) + Devices feature module retrofit

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 05-04-PLAN.md — Traffic feature module retrofit (own schema, DeviceLookupInterface, HasCollector-wrapped broadcaster)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 05-05-PLAN.md — Security feature module retrofit (own schema, DeviceLookupInterface) + final main.py ModuleLoader consolidation

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 05-06-PLAN.md — Module settings page (enable/disable + dependent confirmation), module nav entries

**UI hint**: yes

### Phase 5.1: Improve Device Identity (INSERTED)

**Goal**: Now that device identification logic is isolated in its own DeviceIdentity module, materially improve its accuracy — today's curated 8-vendor OUI list + tiny mDNS service-type map only produces a usable guess for ~2 of 16 real devices on a typical LAN.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: DISC-07, DISC-08
**Success Criteria** (what must be TRUE):

  1. DeviceIdentity uses DHCP vendor-class fingerprinting, hostname heuristics, and broader mDNS record parsing (beyond the Phase 2.1 curated map) to materially raise the fraction of unknown devices that get a non-"Unknown" vendor/type guess
  2. DeviceIdentity has a documented strategy for randomized/private MAC addresses (iOS/macOS MAC randomization) — either an alternate signal that identifies the device, or an explicit, visible "can't identify by MAC" state rather than a silent no-op
  3. Every consumer of DeviceLookupInterface (Devices, Traffic, Security) gets improved results automatically, with no code changes required outside the DeviceIdentity module itself — the swappability promise from Phase 5 holds in practice

**Plans**: TBD
**UI hint**: no

### Phase 5.2: Notifications (INSERTED)

**Goal**: The platform can deliver push alerts to the user's phone — the first module built clean on the new module contract, with no retrofit baggage, closing the notification-delivery gap left open since Phase 4's unknown-device alerting.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: FMOD-04
**Success Criteria** (what must be TRUE):

  1. User configures the notification module (ntfy.sh or Pushover channel/topic) from the dashboard settings page
  2. User receives a push alert on their phone when an unknown device joins the network, closing SEC-02/SEC-04's deferred delivery gap
  3. The notification module subscribes to platform events via the EventBus rather than being special-cased into Security/Devices code

**Plans**: TBD
**UI hint**: yes

### Phase 6: Dual-Mode + Control

**Goal**: A user on any network — including an untrusted rental or hotel — can run Innkeeper in travel mode to defend their own registered devices, switch modes from the dashboard with honest capability gating, and block a device where the active adapter supports it.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: MODE-02, MODE-03, MODE-04, CTRL-01
**Success Criteria** (what must be TRUE):

  1. User can run travel mode using passive scanning (ARP, mDNS, nmap) scoped to registered devices only
  2. User can switch between home and travel mode from the dashboard, and the UI clearly grays out or labels controls the active mode cannot provide
  3. When the configured router adapter becomes unreachable, the system automatically degrades to travel mode and notifies the user
  4. User can block a specific device from the network when an active adapter has block capability, with the control clearly disabled and labeled when it does not

**Plans**: TBD
**UI hint**: yes

### Phase 7: UniFi + Integrations

**Goal**: A user with UniFi hardware gets deep home-mode control and more accurate metrics, plus curated Pi-hole and Grafana integrations and the ability to block a domain network-wide — all delivered as first-party plugins on the existing contract.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: MODE-01, FPLG-01, FPLG-02, FPLG-03, CTRL-02
**Success Criteria** (what must be TRUE):

  1. User can connect a UniFi controller in home mode and get a full device list, per-client bandwidth counters, and block/unblock control; it degrades loudly to travel mode when the controller is unreachable
  2. User can connect a Pi-hole instance and block/unblock domains and view Pi-hole stats on the plugin page
  3. User can block a domain network-wide, executed via the Pi-hole plugin or the active router adapter
  4. User can point Grafana at Innkeeper's PostgreSQL as a data source via the Grafana plugin page, with no custom Grafana plugin required

**Plans**: TBD
**UI hint**: yes

### Phase 8: Network Visualization

**Goal**: A user can understand their network at a glance through an interactive topology map and take a common action — waking a sleeping device — directly from the dashboard.
**Mode:** mvp
**Depends on**: Phase 7
**Requirements**: VIZ-01, VIZ-02
**Success Criteria** (what must be TRUE):

  1. User can view an interactive topology map showing discovered devices, their connections, and each device's security status
  2. User can send a Wake-on-LAN magic packet to any registered device that supports it, directly from the dashboard

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 5.1 → 5.2 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation + Capture Feasibility | 3/3 | Complete   | 2026-06-18 |
| 2. Device Registry + Discovery | 5/5 | Complete   | 2026-06-18 |
| 3. Live Traffic + Bandwidth | 4/4 | Complete    | 2026-06-20 |
| 4. Security | 4/4 | Complete    | 2026-06-20 |
| 5. Module Platform Foundation | 6/6 | Complete   | 2026-06-21 |
| 5.1. Improve Device Identity (INSERTED) | 0/TBD | Not started | - |
| 5.2. Notifications (INSERTED) | 0/TBD | Not started | - |
| 6. Dual-Mode + Control | 0/TBD | Not started | - |
| 7. UniFi + Integrations | 0/TBD | Not started | - |
| 8. Network Visualization | 0/TBD | Not started | - |

## Backlog

### Phase 999.2: Dashboard grouping for stale/unidentified devices (BACKLOG)

**Goal:** [Captured for future planning] — Dashboard device list needs activity-based grouping: keep active/recently-active devices as cards at the top; move devices not seen for 6+ hours into a separate, more compact table-style section; devices that remain unidentified after 24 hours should drop off the list entirely.
**Requirements**: TBD
**Plans**: 0 plans

Plans:

- [ ] TBD (promote with /gsd-review-backlog when ready)
