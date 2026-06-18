# Requirements: Innkeeper

**Defined:** 2026-06-16
**Core Value:** See every device on your network and what it's doing, in real time — and be able to act on it.

## v1 Requirements

### Device Discovery (DISC)

- [ ] **DISC-01**: System discovers all devices on the network automatically via ARP, mDNS, and DHCP lease analysis using multi-source fingerprinting (not MAC address alone — handles iOS/Android MAC randomization)
- [ ] **DISC-02**: User can register a device in the device registry — assign a name, owner, type, and trusted flag
- [ ] **DISC-03**: System tracks and displays device history — first seen and last seen timestamps per device
- [ ] **DISC-04**: System detects when an unregistered device joins the network and marks it as unknown

### Traffic & Bandwidth (TRAF)

- [ ] **TRAF-01**: User can view a live real-time traffic feed — active connections and top talkers per device, updated via SSE without page refresh
- [ ] **TRAF-02**: User can view historical bandwidth consumption per device over any time range (data retention is configurable, never auto-deleted by default)
- [ ] **TRAF-03**: User can view a per-device breakdown of traffic by destination — which domains and IPs each device is communicating with
- [ ] **TRAF-04**: User can view network-wide bandwidth totals over time as a chart (daily, weekly, monthly views)

### Security (SEC)

- [ ] **SEC-01**: System can run an open port scan against any device and display results, flagging ports that appear unexpected for that device type
- [ ] **SEC-02**: System sends a push notification when an unregistered (unknown) device joins the network
- [ ] **SEC-03**: System detects and alerts when a device connects to a known malicious IP or exhibits suspicious traffic patterns
- [ ] **SEC-04**: System assigns each device a security status (good / warning / critical) derived from scan results, displayed prominently on the device card

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

### Plugin System (PLUG)

- [ ] **PLUG-01**: Plugin contract is defined and documented — a plugin consists of: a manifest (name, version, author, required capabilities), optional API routes, optional event subscriptions, optional data collectors, and an optional UI page route
- [ ] **PLUG-02**: User can view all available plugins, and enable, disable, or configure each one via the dashboard settings page
- [ ] **PLUG-03**: Plugins can subscribe to platform events — `new_device`, `device_lost`, `security_alert`, `traffic_spike`, `mode_change` — and react accordingly (send a notification, log, trigger a scan, etc.)
- [ ] **PLUG-04**: An enabled plugin with a UI page appears as a navigation entry in the dashboard at `/plugins/[plugin-name]`; the core platform requires no rebuild when plugins are toggled
- [ ] **PLUG-05**: Plugins can register data collectors — background tasks that feed new data (e.g. speedtest results, external threat feeds) into Innkeeper's storage and event stream

### First-Party Plugins (FPLG)

*These are plugins that use the plugin contract exactly as third-party plugins would — they prove the system works.*

- [ ] **FPLG-01**: UniFi router adapter plugin — connects to a UniFi controller, exposes capabilities: device list, per-client bandwidth counters, block device, unblock device; degrades gracefully when controller is unreachable
- [ ] **FPLG-02**: Pi-hole integration plugin — connects to a Pi-hole instance, exposes capabilities: block domain, unblock domain, query stats dashboard page
- [ ] **FPLG-03**: Grafana integration plugin — exposes Innkeeper's PostgreSQL as a Grafana data source; provides a plugin page with a link to the Grafana instance; requires no custom Grafana plugin
- [ ] **FPLG-04**: Notification plugin — delivers push alerts via ntfy.sh or Pushover; user configures the channel and topic in plugin settings; other plugins and the core platform send alerts through this plugin

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
| Plugin marketplace / registry | Config-based plugin management is sufficient for v1; a hosted registry is a future business decision |
| Automatic data deletion | User's choice is "never auto-delete" — retention is configurable but default is keep forever |
| `--privileged` Docker containers | Security tool must not be an attack surface; `CAP_NET_RAW` + `CAP_NET_ADMIN` only |
| Full DPI (deep packet inspection) | Per-payload inspection is legally complex, privacy-invasive, and high-performance-cost; flow-level accounting is sufficient |
| DHCP / DNS server (built-in) | Innkeeper reads from DHCP/DNS; it should not become the network's DHCP/DNS server — too much blast radius |
| Multi-network simultaneous management | One active network profile at a time; multi-network is a v2+ architectural extension |
| Module federation for plugin UI | Svelte compile-time constraint; dedicated routes are sufficient for v1 |
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
| DISC-01 | Phase 2 | Pending |
| DISC-02 | Phase 2 | Pending |
| DISC-03 | Phase 2 | Pending |
| DISC-04 | Phase 2 | Pending |
| TRAF-01 | Phase 3 | Pending |
| TRAF-02 | Phase 3 | Pending |
| TRAF-03 | Phase 3 | Pending |
| TRAF-04 | Phase 3 | Pending |
| SEC-01 | Phase 4 | Pending |
| SEC-02 | Phase 4 | Pending |
| SEC-03 | Phase 4 | Pending |
| SEC-04 | Phase 4 | Pending |
| PLUG-01 | Phase 5 | Pending |
| PLUG-02 | Phase 5 | Pending |
| PLUG-03 | Phase 5 | Pending |
| PLUG-04 | Phase 5 | Pending |
| PLUG-05 | Phase 5 | Pending |
| FPLG-04 | Phase 5 | Pending |
| MODE-02 | Phase 6 | Pending |
| MODE-03 | Phase 6 | Pending |
| MODE-04 | Phase 6 | Pending |
| CTRL-01 | Phase 6 | Pending |
| MODE-01 | Phase 7 | Pending |
| FPLG-01 | Phase 7 | Pending |
| FPLG-02 | Phase 7 | Pending |
| FPLG-03 | Phase 7 | Pending |
| CTRL-02 | Phase 7 | Pending |
| VIZ-01 | Phase 8 | Pending |
| VIZ-02 | Phase 8 | Pending |

**Coverage:**

- v1 requirements: 35 total
- Mapped to phases: 35 (100%) ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-16*
*Last updated: 2026-06-16 after roadmap creation (8 phases)*
