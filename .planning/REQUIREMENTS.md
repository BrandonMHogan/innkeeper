# Requirements: Innkeeper

**Defined:** 2026-06-16
**Core Value:** See every device on your network and what it's doing, in real time — and be able to act on it.

## v1 Requirements

### Device Discovery (DISC)

- [x] **DISC-01**: System discovers all devices on the network automatically via ARP, mDNS, and DHCP lease analysis using multi-source fingerprinting (not MAC address alone — handles iOS/Android MAC randomization)
- [x] **DISC-02**: User can register a device in the device registry — assign a name, owner, type, and trusted flag
- [x] **DISC-03**: System tracks and displays device history — first seen and last seen timestamps per device
- [x] **DISC-04**: System detects when an unregistered device joins the network and marks it as unknown
- [x] **DISC-05**: System infers a likely vendor (e.g. "Apple", "Samsung", "Sonos") for an unknown device from its MAC OUI prefix, and displays it on the unknown-device card — a best-effort hint, not a registry field, since the user may override or ignore it
- [x] **DISC-06**: System infers a likely device type/category (e.g. phone, computer, TV/streaming, smart-home) for an unknown device from available signals (vendor, mDNS service type, DHCP vendor class) and pre-fills the register form's type/name fields with the best guess — the user can always change or reject the suggestion before registering
- [ ] **DISC-07**: DeviceIdentity uses DHCP vendor-class fingerprinting, hostname heuristics, and broader mDNS record parsing (beyond DISC-05/06's curated map) to materially raise the fraction of unknown devices that get a non-"Unknown" vendor/type guess
- [ ] **DISC-08**: DeviceIdentity has a documented strategy for randomized/private MAC addresses (iOS/macOS MAC randomization) — an alternate identifying signal, or an explicit "can't identify by MAC" state rather than a silent no-op

### Traffic & Bandwidth (TRAF)

- [x] **TRAF-01**: User can view a live real-time traffic feed — active connections and top talkers per device, updated via SSE without page refresh
- [x] **TRAF-02**: User can view historical bandwidth consumption per device over any time range (data retention is configurable, never auto-deleted by default)
- [x] **TRAF-03**: User can view a per-device breakdown of traffic by destination — which domains and IPs each device is communicating with
- [x] **TRAF-04**: User can view network-wide bandwidth totals over time as a chart (daily, weekly, monthly views)

### Security (SEC)

- [x] **SEC-01**: System can run an open port scan against any device and display results, flagging ports that appear unexpected for that device type
- [x] **SEC-02**: System sends a push notification when an unregistered (unknown) device joins the network
- [x] **SEC-03**: System detects and alerts when a device connects to a known malicious IP or exhibits suspicious traffic patterns
- [x] **SEC-04**: System assigns each device a security status (good / warning / critical) derived from scan results, displayed prominently on the device card

### Network Control (CTRL)

- [ ] **CTRL-01**: User can block a specific device from accessing the network (requires an active router adapter with block capability — clearly indicated when unavailable)
- [ ] **CTRL-02**: User can block a domain network-wide (executed via Pi-hole plugin or router adapter, whichever is active)

### Dual-Mode Operation (MODE)

- [ ] **MODE-01**: Home mode connects to a UniFi router via the UniFi plugin — provides full device list, bandwidth counters from router, and network control capabilities
- [ ] **MODE-02**: Travel mode uses passive scanning (ARP, mDNS, nmap) on untrusted networks — scoped to registered devices only for legal and ethical reasons
- [ ] **MODE-03**: User can switch between home and travel mode via the dashboard; UI clearly grays out or labels features that require capabilities the active mode doesn't provide
- [ ] **MODE-04**: System automatically detects when the configured router adapter is unreachable and degrades gracefully to travel mode, notifying the user

### Network Visualization (VIZ)

- [ ] **VIZ-01**: User can view an interactive network topology map — a visual graph showing all discovered devices, their connections, and security status
- [ ] **VIZ-02**: User can send a Wake-on-LAN magic packet to any registered device that supports it, directly from the dashboard

### Module Platform (MOD)

- [ ] **MOD-01**: Module contract is defined and documented — capability Protocols (HasAPIRoutes, HasUIPage, HasEventSubscriptions, HasCollector), a typed ModuleManifest (id, kind: feature/support/linked, provides, requires, db_schema), and a ModuleLoader that wires modules via constructor injection
- [ ] **MOD-02**: User can view all available modules, and enable, disable, or configure each one via the dashboard settings page
- [ ] **MOD-03**: Modules can subscribe to platform events — `new_device`, `device_lost`, `security_alert`, `traffic_spike`, `mode_change` — via the EventBus and react accordingly
- [ ] **MOD-04**: An enabled module with a UI page appears as a navigation entry in the dashboard at `/modules/[module-name]`; the core platform requires no rebuild when modules are toggled
- [ ] **MOD-05**: Modules can register data collectors — background tasks that feed new data into Innkeeper's storage and event stream
- [ ] **MOD-06**: A ModuleRegistry resolves support interfaces (e.g. DeviceLookupInterface) by Protocol type rather than module identity, so a provider can be replaced later without changing any consumer; the loader fails fast at startup if a `requires` is unsatisfied or two modules `provide` the same interface
- [ ] **MOD-07**: Devices, Traffic, and Security are retrofitted onto the module contract: DeviceIdentity becomes a support module (own Postgres schema, sole source of truth for device data/CRUD/merge/inference, exposes DeviceLookupInterface); Devices/Traffic/Security consume it instead of owning or duplicating device data
- [ ] **MOD-08**: A linked-module manifest format and dashboard "Linked Apps" section exist (data model + UI only — no real third-party module ships in v1)

### First-Party Modules (FMOD)

*These are modules that use the module contract exactly as third-party modules would — they prove the system works.*

- [ ] **FMOD-01**: UniFi router adapter module — connects to a UniFi controller, exposes capabilities: device list, per-client bandwidth counters, block device, unblock device; degrades gracefully when controller is unreachable
- [ ] **FMOD-02**: Pi-hole integration module — connects to a Pi-hole instance, exposes capabilities: block domain, unblock domain, query stats dashboard page
- [ ] **FMOD-03**: Grafana integration module — exposes Innkeeper's PostgreSQL as a Grafana data source; provides a module page with a link to the Grafana instance; requires no custom Grafana plugin
- [ ] **FMOD-04**: Notification module — delivers push alerts via ntfy.sh or Pushover; user configures the channel and topic in module settings; other modules and the core platform send alerts through it

### Authentication (AUTH)

- [x] **AUTH-01**: A first-run setup wizard prompts the user to set a dashboard password before the UI is accessible
- [x] **AUTH-02**: User must authenticate with the dashboard password to access any page of the Innkeeper UI
- [x] **AUTH-03**: User session persists across browser refresh (JWT or session cookie) so the password is not required on every visit

### Platform (PLAT)

- [x] **PLAT-01**: User accesses Innkeeper via a web dashboard from any device on the home network without installing anything on that device
- [ ] **PLAT-02**: The full Innkeeper stack (API, frontend, database, capture engine) is deployable via a single `docker compose up` command on any Docker-capable machine
- [x] **PLAT-03**: The capture engine runs as a separate, isolated Docker service with only `CAP_NET_RAW` and `CAP_NET_ADMIN` capabilities — never `--privileged` — and can be replaced with a native host agent on macOS where Docker host networking is unavailable

---

## v2 Requirements

### CLI

- **CLI-01**: User can query device list, network status, and trigger scans from the command line
- **CLI-02**: CLI is scriptable — machine-readable JSON output mode
- **CLI-03**: CLI can trigger plugin actions (e.g. `innkeeper block device <mac>`)

### Plugin Distribution

- **PDST-01**: User can install a plugin from a URL via the dashboard (download, validate manifest, register)
- **PDST-02**: Plugin sandbox mode — plugins run in isolated processes rather than in-process with the API

### Access Control

- **AUTH-01**: Multiple users can log in with separate credentials and role-based access (admin vs. read-only viewer)
- **AUTH-02**: Admin user is created during first-run setup

### Extended Integrations

- **INT-01**: Speedtest plugin — scheduled internet speed tests with historical chart
- **INT-02**: Tailscale / WireGuard plugin — VPN tunnel status and connected peer visibility
- **INT-03**: Home Assistant integration — expose Innkeeper device data as HA entities

### Network Management

- **NET-01**: User can manage VLAN assignments per device (requires UniFi router adapter)
- **NET-02**: User can configure time-based access rules for devices (parental controls)
- **NET-03**: User can manage router port forwards from the Innkeeper dashboard

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Remote access from outside home network | Adds significant security surface; users should use a VPN (e.g. Tailscale) for remote access — potential v2 integration |
| Cloud sync / telemetry | All data stays local; no cloud dependencies for any core feature — non-negotiable for self-hosted trust |
| Native mobile app | Web dashboard works from any phone browser on the network; native app is a separate product |
| Module marketplace / registry | Config-based module management is sufficient for v1; a hosted registry is a future business decision |
| Automatic data deletion | User's choice is "never auto-delete" — retention is configurable but default is keep forever |
| `--privileged` Docker containers | Security tool must not be an attack surface; `CAP_NET_RAW` + `CAP_NET_ADMIN` only |
| Full DPI (deep packet inspection) | Per-payload inspection is legally complex, privacy-invasive, and high-performance-cost; flow-level accounting is sufficient |
| DHCP / DNS server (built-in) | Innkeeper reads from DHCP/DNS; it should not become the network's DHCP/DNS server — too much blast radius |
| Multi-network simultaneous management | One active network profile at a time; multi-network is a v2+ architectural extension |
| Module federation for module UI | Svelte compile-time constraint; dedicated routes are sufficient for v1 |
| Multiple user accounts / RBAC | Single shared password is sufficient for v1 personal use; multi-user with role-based access is v2 |
| Auto-quarantine / NAC | Network Access Control is complex, error-prone, and high blast radius; manual block is sufficient for v1 |

---

## Traceability

*Populated during roadmap creation — each requirement maps to exactly one phase.*

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLAT-01 | Phase 1 | Complete |
| PLAT-02 | Phase 1 | Pending |
| PLAT-03 | Phase 1 | Complete |
| AUTH-01 | Phase 1 | Complete |
| AUTH-02 | Phase 1 | Complete |
| AUTH-03 | Phase 1 | Complete |
| DISC-01 | Phase 2 | Complete |
| DISC-02 | Phase 2 | Complete |
| DISC-03 | Phase 2 | Complete |
| DISC-04 | Phase 2 | Complete |
| TRAF-01 | Phase 3 | Complete |
| TRAF-02 | Phase 3 | Complete |
| TRAF-03 | Phase 3 | Complete |
| TRAF-04 | Phase 3 | Complete |
| SEC-01 | Phase 4 | Complete |
| SEC-02 | Phase 4 | Complete |
| SEC-03 | Phase 4 | Complete |
| SEC-04 | Phase 4 | Complete |
| MOD-01 | Phase 5 | Pending |
| MOD-02 | Phase 5 | Pending |
| MOD-03 | Phase 5 | Pending |
| MOD-04 | Phase 5 | Pending |
| MOD-05 | Phase 5 | Pending |
| MOD-06 | Phase 5 | Pending |
| MOD-07 | Phase 5 | Pending |
| MOD-08 | Phase 5 | Pending |
| DISC-07 | Phase 5.1 | Pending |
| DISC-08 | Phase 5.1 | Pending |
| FMOD-04 | Phase 5.2 | Pending |
| MODE-02 | Phase 6 | Pending |
| MODE-03 | Phase 6 | Pending |
| MODE-04 | Phase 6 | Pending |
| CTRL-01 | Phase 6 | Pending |
| MODE-01 | Phase 7 | Pending |
| FMOD-01 | Phase 7 | Pending |
| FMOD-02 | Phase 7 | Pending |
| FMOD-03 | Phase 7 | Pending |
| CTRL-02 | Phase 7 | Pending |
| VIZ-01 | Phase 8 | Pending |
| VIZ-02 | Phase 8 | Pending |

**Coverage:**

- v1 requirements: 40 total
- Mapped to phases: 40 (100%) ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-16*
*Last updated: 2026-06-21 — module platform pivot: PLUG/FPLG renamed to MOD/FMOD, MOD-06/07/08 and DISC-07/08 added, Notifications demoted to Phase 5.2 (see docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md)*
