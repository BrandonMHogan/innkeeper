# Feature Landscape

**Domain:** Self-hosted home network monitoring & management platform (Innkeeper)
**Researched:** 2026-06-16
**Mode:** Ecosystem
**Overall confidence:** MEDIUM-HIGH (web sources cross-referenced across 8+ tools; vendor docs + independent reviews)

## Tools Compared

| Tool | Category | What it does best | Relevance to Innkeeper |
|------|----------|-------------------|------------------------|
| **ntopng** | Traffic/flow analysis | Per-host real-time flows, DPI, top talkers, behavioral alerts, host discovery (ARP/SSDP/mDNS/SNMP) | Closest functional analog to live-traffic + device-behavior goals |
| **Pi-hole** | DNS sinkhole | Network-wide ad/domain blocking, per-client groups, query log analytics | Direct integration target; reference for blocking UX |
| **UniFi Network** | Router/controller | Client management, block/unblock, DPI traffic ID, policy/firewall rules | First router adapter; the "home mode" gold standard |
| **Fing** | Device discovery | New-device alerts, device fingerprinting (largest device DB), per-device watch | Reference for device registry + new-device alerting UX |
| **Home Assistant** (network integrations) | Presence/discovery | nmap/ping device_tracker, known_devices.yaml registry | Reference for passive scan + known-device registry pattern |
| **Sniffnet** | Single-host traffic monitor | Per-app traffic, threshold/blacklist/favorite-host notifications, country/domain filters | Reference for notification model |
| **Netdata** | Metrics/observability | Real-time system + bandwidth dashboards | Reference for real-time dashboard expectations |
| **Prometheus + Grafana** | Metrics stack | Time-series storage + custom dashboards | Grafana is an integration target (expose metrics) |

---

## Table Stakes

Features users expect from a network monitor. Absence makes the product feel incomplete or broken. These map almost 1:1 to PROJECT.md's "Device Visibility," "Live Traffic," and core platform requirements — confirming those requirements are correctly scoped as baseline.

| Feature | Why Expected | Complexity | Notes / Dependencies |
|---------|--------------|------------|----------------------|
| Device discovery (IP, MAC, hostname, vendor, last-seen) | Every tool (ntopng, Fing, UniFi, HA) does this; it is the entry point of the entire category | Med | Foundation for everything. Passive: ARP/mDNS/nmap. Active (home): router client list. Vendor lookup = MAC OUI database (offline) |
| Live device list with online/offline state | Fing, UniFi, ntopng all show connected/disconnected at a glance | Low-Med | Depends on discovery + a presence/last-seen heartbeat. Offline detection needs a "grace period" to avoid flapping |
| Real-time dashboard (auto-updating) | Netdata/ntopng set the expectation that data is "now," not a refresh-button | Med | SSE per PROJECT.md decision. Drives architecture: backend must push deltas, not full re-renders |
| Per-device bandwidth (current + historical) | ntopng, UniFi, Netdata all show this; "who is using my bandwidth" is the #1 home use case | Med-High | Requires time-series storage (TimescaleDB). Sampling cadence + retention are real design questions |
| Top talkers / top destinations per device | ntopng's signature view; UniFi DPI; Sniffnet per-app | Med-High | In home mode from router DPI; in travel mode only for the host running the scan / own devices. Per-destination needs DNS resolution or DPI |
| Device fingerprinting / type identification | Fing's main differentiator is now expected baseline (phone vs IoT vs laptop) | Med | OUI vendor lookup is cheap; richer type detection (model/OS) needs heuristics or a device DB. Start with vendor + user-assigned type |
| Device registry / naming known devices | HA known_devices.yaml, Fing "named devices," UniFi client aliases — raw MAC lists are unusable | Low-Med | User assigns name/owner/type. **This is the keystone** that makes new-device alerts meaningful (known vs unknown) |
| New / unknown device alert | Fing, UniFi, all rogue-detection tools; the #1 security expectation for home users | Med | **Depends on device registry** — "unknown" is defined as "not in registry." Without registry, every device is noise |
| Notifications / alerts to a channel | Sniffnet, ntopng, Fing all alert; users won't watch a dashboard 24/7 | Low-Med | PROJECT.md picks ntfy/Pushover. Need an alert-rules engine even if minimal |
| Query/event/activity log | Pi-hole query log, ntopng flow history — users want to answer "what happened at 2am" | Med | Searchable history of device joins/leaves, alerts, and (where available) connections |
| Web dashboard accessible from any device | UniFi, Pi-hole, ntopng, Netdata all web-first | Med | Primary interface per PROJECT.md |
| Simple deployment | Pi-hole's one-line install is the category benchmark for adoption | Low-Med | Docker Compose per PROJECT.md. Critical for open-source adoption |

---

## Differentiators

Not strictly expected, but where a tool stands out. Innkeeper's stated value ("see every device AND act on it" + dual-mode) lives here. No single existing tool combines discovery + traffic + security + control + dual-mode — that combination IS the differentiator.

| Feature | Value Proposition | Complexity | Notes / Dependencies |
|---------|-------------------|------------|----------------------|
| **Dual-mode (home vs travel)** | No mainstream self-hosted tool reframes itself for untrusted networks. Unique positioning | High | See dedicated section below. Architecturally significant (capability gating) |
| **Unified visibility + control in one tool** | ntopng sees but can't block; Pi-hole blocks DNS but doesn't show devices; UniFi does both but only on UniFi gear. Innkeeper unifies via adapters | High | Depends on router adapter (control) + discovery (visibility). The "act on it" half is the moat |
| **Block device / block domain from the dashboard** | Fing/ntopng are read-only; acting requires jumping to the router. One-click block is high-value | Med-High | Device block = router adapter (home only). Domain block = Pi-hole integration. Clearly degrade in travel mode |
| **Per-device security scan (open ports + known vulns)** | Fing has basic port scan; most monitors have none. Pairing scan results with the device registry is distinctive | High | nmap for ports; vuln mapping needs a CVE/service-version source. Scope carefully (see anti-features) |
| **Suspicious-traffic / bad-IP alerting** | ntopng has behavioral checks + threat-intel ingestion; rare in home tools | Med-High | Needs a threat-intel feed (offline blocklist acceptable for v1). Keep signal-to-noise high |
| **Router-agnostic adapter architecture** | UniFi locks you to UniFi. Innkeeper's adapter pattern + passive fallback works on any network | Med (in arch), High (per adapter) | Core platform must function with zero adapters. Each adapter is incremental value |
| **Configurable retention, never auto-deleted** | Most tools roll off old data silently; PROJECT.md promises user-owned, durable history | Med | TimescaleDB retention policies that are opt-in, not default. A genuine privacy/ownership differentiator |
| **Pi-hole + Grafana curated integrations** | Pre-wired integrations beat "build your own Prometheus+Grafana" friction | Med | Pi-hole API for blocking/stats; expose metrics in Grafana-compatible form (Prometheus endpoint or direct Timescale datasource) |
| **CLI for power users / scripting** | ntopng/Pi-hole have CLIs; appeals to the self-hosting audience and aids automation | Med | Reuses the same backend API. Good for open-source credibility |

---

## Anti-Features

Things to deliberately NOT build in v1. Each either blows up scope, conflicts with PROJECT.md constraints, or has poor signal-to-noise for a single-household tool.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|--------------------|
| Full packet capture / Wireshark-style PCAP inspection | Massive storage, privacy minefield, niche use; ntopng/Wireshark already own this | Flow-level summaries (talkers, destinations, volume) only |
| Active vulnerability exploitation / pen-testing | Legal/ethical risk on untrusted networks; way out of scope | Passive port scan + version-based CVE flagging only, on user's own devices |
| Multi-network / multi-site management | PROJECT.md explicitly out of scope; doubles data model complexity | One active network profile at a time |
| Remote access from outside the LAN | PROJECT.md out of scope; security complexity | Document VPN usage; LAN-only by design |
| Cloud sync / cloud device database | Violates "no cloud dependencies" + privacy constraint | Local OUI/device DB shipped with the app |
| Open plugin marketplace | PROJECT.md defers to future; quality/security burden | Curated integrations (Pi-hole, Grafana) only |
| Mobile native app | PROJECT.md out of scope; web works on phone browsers | Responsive web dashboard |
| DHCP server / being the network's DNS | Pi-hole territory; turns Innkeeper into critical infra that breaks the whole network if it fails | Integrate with Pi-hole; observe/control, don't become the gateway |
| Deep DPI engine built from scratch | ntopng/nDPI took years; reinventing is a tar pit | Use router DPI (home mode) + DNS-based destination naming (travel mode) |
| Auto-blocking / NAC-style auto-quarantine | High blast radius (false positive locks out your own device); risky for a household tool | Alert + one-click manual block. Keep humans in the loop for v1 |
| Per-user accounts / RBAC / multi-tenant auth | PROJECT.md is single-user/household | Single admin auth; defer multi-user to commercial milestone |
| Wireless-specific features (AP management, channel/RF, rogue-AP) | Requires UniFi-specific WLAN data; out of core scope | Surface what the adapter provides; don't build RF tooling |

---

## Feature Dependencies

```
Device Discovery (ARP/mDNS/nmap | router client list)
        │
        ├──> Live Device List (online/offline state)
        │
        ├──> Device Registry (name/owner/type)  ◄── KEYSTONE
        │           │
        │           ├──> New/Unknown Device Alert  (unknown = not in registry)
        │           └──> Per-Device Security Scan   (scan registered/own devices)
        │
        ├──> Per-Device Bandwidth ──> Top Talkers/Destinations
        │           │                        │
        │           └──> TimescaleDB ◄────────┘ (time-series + retention)
        │                    │
        │                    └──> Grafana Integration (expose metrics)
        │
        └──> Control Layer (block device | block domain)
                     │
                     ├── block device  ──> Router Adapter (home mode ONLY)
                     └── block domain  ──> Pi-hole Integration

Alert Rules Engine ──> Notifications (ntfy/Pushover)
        ▲                    ▲
        └── feeds from: new-device, security scan, bandwidth threshold, bad-IP

Mode Switcher (home/travel) ──> gates: Control Layer, router-sourced traffic/DPI
SSE Layer ──> all real-time dashboard views
```

**Critical path insight:** Device Registry is the keystone. New-device alerts, security scans, and meaningful naming all depend on it. Build discovery → registry early; alerting/control layer on top. Bandwidth/traffic is a parallel track that depends on TimescaleDB but not on the registry.

---

## Dual-Mode (Home vs Travel) Feature Implications

This is Innkeeper's signature differentiator and has the deepest design implications. Research found **no mainstream self-hosted tool that explicitly models this split** — it is genuinely novel positioning.

### What changes between modes

| Capability | Home Mode (router adapter) | Travel Mode (passive scan) | Implication |
|------------|----------------------------|----------------------------|-------------|
| Device discovery | Full client list from router | ARP + mDNS + nmap sweep of the subnet | Travel sees only L2-reachable hosts; client isolation on hotel APs may hide devices |
| Scope of devices | All network devices | **Own registered devices only** (per PROJECT.md) | Travel mode is privacy/ethics-bound — don't profile strangers' devices on a shared network |
| Per-device traffic | Router DPI / flow export | Only traffic visible to the scanning host | Travel cannot see other devices' bandwidth (no client-isolation bypass; don't try) |
| Block device | Yes (router API) | **No** | Must clearly gray-out / explain unavailable controls |
| Block domain | Yes (Pi-hole on home net) | No (not your DNS) | Same gating |
| Security scan | Yes | Yes (own devices) | One of the few features fully available in travel mode — and arguably travel's primary value |
| New-device alert | "Unknown joined my network" | "Is this network hostile? Are my devices exposed?" | The *semantics* of alerts shift between modes |

### Design recommendations for dual-mode

1. **Capability model, not feature flags.** Each feature should declare required capabilities (e.g. `requires: router_control`). The active mode/adapter advertises capabilities; UI gates off that. This keeps the door open for partial-capability adapters (e.g. a router that lists clients but can't block).
2. **Explicit, honest degradation.** PROJECT.md already says features requiring home mode are "clearly indicated when unavailable." Do this as informative empty-states ("Blocking requires a connected router — you're in travel mode"), not hidden buttons.
3. **Travel mode = "defend yourself," not "police the network."** Reframe the entire UX: exposure of your own devices, open ports on your laptop, whether the network sniffs you (ARP/mDNS exposure per untrusted-network research), suspicious gateway behavior. This is where ntopng/Fing/UniFi have no answer.
4. **Travel mode threat surface.** Untrusted networks have no client isolation, no encryption between devices, and allow scanning/sniffing. Innkeeper's travel value is telling the user *they are on such a network* and what their own devices are leaking. Consider a "network trust assessment" view (encryption, isolation, captive portal, gateway fingerprint) as a travel-specific differentiator.
5. **Mode switch must be deliberate.** Travel mode should restrict scanning to the user's own registered devices to avoid scanning a shared network broadly (legal/ethical + courtesy). Make the registry the allow-list for travel scans.

**Complexity:** High. Dual-mode touches discovery, the capability/gating system, the UI, and the adapter contract. Recommend establishing the capability abstraction in an early foundational phase so later features inherit gating for free.

---

## Device Registry / Known-Device Management Patterns

Synthesized from Fing (named devices + watch), Home Assistant (`known_devices.yaml`), and UniFi (client aliases).

**Established patterns to adopt:**
- **MAC as stable identity** — name/owner/type attach to MAC, not IP (IPs churn via DHCP). Watch for MAC randomization on modern phones (iOS/Android private addresses) — a known v1 pain point; surface it rather than fighting it.
- **First-seen → unknown → user-promotes-to-known** lifecycle. New device appears as "unknown," user names/claims it, future appearances are "known." This is exactly what makes new-device alerts useful.
- **Rich attributes:** name, owner (household member), device type, vendor (auto from OUI), notes, first-seen, last-seen. PROJECT.md's (name, owner, type) is the right minimum.
- **Per-device watch/notify** (Fing): notify when *this specific* device joins/leaves — useful for "did the kids' tablet come online," "is grandma's phone here."
- **Registry as allow-list** doing double duty: defines "known" for alerts AND defines "own devices" for travel-mode scan scope.

**Complexity:** Low-Med for the registry itself; the MAC-randomization edge case is the main wrinkle.

---

## MVP Recommendation

Prioritize the dependency-critical foundation, then one differentiator:

1. **Device discovery + live device list** (table stakes, foundation)
2. **Device registry + new/unknown device alert** (keystone + highest-value security feature)
3. **Per-device bandwidth + top talkers** (the #1 home use case; validates TimescaleDB path)
4. **Real-time dashboard (SSE) + notifications** (table-stakes delivery layer)
5. **One differentiator: dual-mode capability gating with travel-mode passive scan** (the unique positioning — even minimal, it proves the concept)

**Defer to later phases:**
- **Block device / block domain (control layer):** Depends on the UniFi adapter + Pi-hole, both of which the user can't fully test until the planned UniFi purchase. High value but gated on hardware. *(Build the adapter contract early, the live UniFi adapter when hardware lands.)*
- **Per-device security scan with CVE mapping:** Valuable but high complexity; do basic open-port scan first, vuln mapping later.
- **Suspicious-traffic / bad-IP alerting:** Needs a threat-intel feed; layer on after core alerting works.
- **Grafana integration:** Straightforward once metrics exist; not on the critical path.
- **CLI:** After the API stabilizes (it reuses the same API).

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Table-stakes feature set | HIGH | Consistent across all 8 tools surveyed |
| Differentiators | MEDIUM-HIGH | Clear gaps in existing tools; "unified visibility+control" verified by feature comparison |
| Anti-features | MEDIUM-HIGH | Grounded in PROJECT.md constraints + known scope tar pits (DPI, PCAP) |
| Dual-mode implications | MEDIUM | Novel concept — little direct prior art; reasoned from untrusted-network security research + tool capabilities |
| Device registry patterns | HIGH | Well-established across Fing/HA/UniFi |

## Gaps / Open Questions for Later Research

- **MAC randomization handling:** How aggressively to dedupe/identify devices that rotate MACs — needs phase-specific design research.
- **Travel-mode "network trust assessment":** Worth scoping as a concrete feature set (what signals: client isolation test, captive portal, gateway fingerprint, encryption). No off-the-shelf reference found.
- **CVE/vuln data source:** Which offline-capable feed for the security scan (no-cloud constraint) — needs investigation when that phase is planned.
- **Threat-intel / bad-IP feed:** Offline-updatable blocklist source for suspicious-traffic alerts.
- **Per-destination naming in travel mode** without DPI: how far DNS-based resolution gets you.

## Sources

- [ntopng – ntop (official)](https://www.ntop.org/products/traffic-analysis/ntopng/) — HIGH
- [ntopng Flow Behavioural Checks docs](https://www.ntop.org/guides/ntopng/user_interface/shared/alerts/others/flow_checks.html) — HIGH
- [I monitor my home network by self-hosting ntopng (XDA)](https://www.xda-developers.com/ntopng-guide/) — MEDIUM
- [Pi-hole Query Log & DNS Management (DeepWiki)](https://deepwiki.com/pi-hole/web/3.1-query-log-and-dns-management) — MEDIUM
- [Pi-hole Domain List Management (DeepWiki)](https://deepwiki.com/pi-hole/pi-hole/4.1-domain-list-management) — MEDIUM
- [Pi-hole Per-client blocking docs](https://docs.pi-hole.net/group_management/example/) — HIGH
- [UniFi Traffic & Policy Management (Ubiquiti)](https://help.ui.com/hc/en-us/articles/5546542486551-Traffic-Policy-Management-in-UniFi) — HIGH
- [UniFi Gateway Traffic & Device Identification (Ubiquiti)](https://help.ui.com/hc/en-us/articles/12570783535383-UniFi-Gateway-Traffic-and-Device-Identification) — HIGH
- [Fing App Features](https://help.fing.com/hc/en-us/articles/4418790433426-Fing-App-Features) — MEDIUM
- [Fing Network Monitoring features](https://www.fing.com/news/network-monitoring-features/) — MEDIUM
- [Home Assistant Nmap Tracker](https://www.home-assistant.io/integrations/nmap_tracker/) — HIGH
- [Home Assistant Device Tracker](https://www.home-assistant.io/integrations/device_tracker/) — HIGH
- [Sniffnet review (Windows Central)](https://www.windowscentral.com/software-apps/sniffnet-network-monitor-app) — MEDIUM
- [Rogue Device Detection guide (Lansweeper)](https://www.lansweeper.com/blog/cybersecurity/rogue-device-detection-preventing-vulnerabilities-and-threats/) — MEDIUM
- [mDNS — Telling the world about you (LevelBlue/SpiderLabs)](https://levelblue.com/en-us/resources/blogs/spiderlabs-blog/mdns-telling-the-world-about-you-and-your-device/) — MEDIUM
- [NIST Mobile Threat Catalogue — LAN/PAN threats](https://pages.nist.gov/mobile-threat-catalogue/lan-pan-threats/LPN-0.html) — HIGH
