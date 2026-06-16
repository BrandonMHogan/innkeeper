# Domain Pitfalls

**Domain:** Self-hosted home network monitoring & management platform
**Researched:** 2026-06-16
**Stack under review:** Python 3.12 / FastAPI, Svelte 5, PostgreSQL + TimescaleDB, Docker Compose
**Overall confidence:** MEDIUM-HIGH (core mechanics verified against vendor docs + community reports; some recommendations are domain experience tagged accordingly)

> Note on tooling: all GSD search providers were disabled in `config.json` and `gsd-tools` was unavailable on this run, so research used the built-in WebSearch/WebFetch. Confidence tiers below are assigned manually per the source hierarchy (vendor docs/standards = HIGH, community consensus = MEDIUM, single-source or experience = LOW/MEDIUM).

---

## TOP-OF-FUNNEL WARNING (read this first)

**The single highest-impact, most-likely-to-be-missed pitfall in this project is a hardware/platform mismatch:**

> The target hardware is a **Mac Mini running Docker Compose**, but the core value proposition (packet capture, live traffic, top-talkers, ARP/mDNS discovery) depends on the container *seeing real Layer-2 traffic*. On macOS, **Docker does not run containers natively — it runs them inside a Linux VM**, and `--network host`, `macvlan`, and promiscuous capture **do not work the way they do on Linux**. This can invalidate the headline features on the chosen hardware.

This is not a "be careful" item — it is a feasibility decision that must be made in Phase 0/1. It is expanded as **Critical Pitfall #1** below. Treat it as a gate before any capture code is written.

---

## Critical Pitfalls

Mistakes that cause rewrites, invalidate the architecture, or break the core value prop.

### Pitfall 1: Packet capture is fundamentally crippled on Docker Desktop for macOS (the target hardware)

**What goes wrong:** `network_mode: host` silently does nothing on Docker Desktop for Mac — `docker run` does not error, but the container is attached to the VM's network namespace, not the Mac's. There is no `docker0` on the host, the Linux bridge is unreachable from macOS, and a Scapy sniffer inside the container sees only VM-internal traffic, not your LAN. `macvlan` also depends on the host NIC entering promiscuous mode, which the macOS host networking stack does not expose to the VM the way a Linux host does.

**Why it happens:** The team reads "Docker Compose runs anywhere" and assumes Linux container networking semantics. On Linux they are correct; on macOS the VM boundary breaks them. The docs explicitly state the host driver is Linux-only and is silently accepted-but-ignored on Mac.

**Consequences:** Live traffic, per-device bandwidth, top-talkers, and "what is this device doing" — the headline features — return empty or VM-only data on the exact machine the user plans to deploy on. Discovered late, this forces either (a) a re-platform to a Linux host, or (b) re-architecting capture to live outside Docker.

**Prevention:**
- **Decide the capture topology in Phase 0/1, before writing capture code.** The realistic options:
  1. Run the *capture agent* (Scapy/sniffer) as a **native host process on the Mac** (launchd service or a small daemon), and run only the FastAPI/DB/UI in Docker. The agent feeds the API over a socket/HTTP. This is the most robust cross-platform answer and aligns with the open-source goal (the agent can be a Linux container on Linux hosts, a native process on macOS).
  2. Deploy the whole stack on a **Linux box** (the PROJECT.md "old PC" option) where `--network host` works, and treat the Mac Mini as a degraded/dev target.
  3. Get capture data from the **router (UniFi)** rather than from the host NIC — but this only works in home mode and not in travel mode.
- Document, in the deploy docs and the UI, that **packet-level features require either a Linux host or the native agent**; on macOS-Docker-only they degrade to router-sourced or scan-sourced data.
- Add a startup self-check: the app verifies it can actually see broadcast/ARP traffic on the expected interface and warns loudly if it cannot.

**Detection / warning signs:** Capture works on the developer's Linux CI but returns 0 packets on the Mac Mini; ARP table is empty; "top talkers" only shows container/localhost traffic.

**Phase:** Phase 0/1 (architecture & spike). This must be a spike with a go/no-go before the capture phase is planned.

**Confidence:** HIGH (Docker docs + roadmap issue #238 confirm host networking is unsupported on Mac and the VM architecture; macvlan promiscuous requirement confirmed).

---

### Pitfall 2: Capturing too much — unbounded packet capture and full-payload storage

**What goes wrong:** Scapy's pure-Python sniffer is not built for speed and drops packets under load; teams then try to "fix" it by storing everything, leading to memory blowups (`sniff()` with `store=1` keeps every packet in RAM) and disk bloat. At home-network scale a single 4K stream or a backup can be hundreds of Mbps — far more than a Python sniffer can parse per-packet in real time.

**Why it happens:** Default Scapy examples use `store=1`, no BPF filter, and parse every layer. Developers test on idle networks and never see the failure until real traffic hits.

**Consequences:** Dropped packets (silently inaccurate bandwidth/top-talker stats), runaway RAM, and a database full of per-packet rows that TimescaleDB then has to manage forever (compounding Pitfall 6).

**Prevention:**
- **Never store raw packets for analytics.** Aggregate at capture time into per-device/per-flow counters (bytes, packets, dest) over a fixed window (e.g. 5–10s), and write *aggregates* to the DB, not packets.
- Always `sniff(store=0, filter="<BPF>")` — push the filter into the kernel so Python never sees irrelevant traffic. Disable unused Scapy layers.
- For anything beyond modest home traffic, prefer **flow-level data over per-packet**: NetFlow/sFlow/IPFIX from the router, or `nfstream`/`pyshark` with a dumpcap backend, or simply consume the router's existing per-client stats (UniFi already aggregates this). Scapy is fine for ARP/discovery and light flow sampling; it is the wrong tool for "capture all bytes on a gigabit LAN."
- Cap memory and add backpressure: bounded queues between sniffer and writer, drop-and-count on overflow (and expose the drop counter as a health metric).

**Detection / warning signs:** RSS of the capture process climbing monotonically; bandwidth totals lower than the router reports (= drops); CPU pegged at 100% on one core.

**Phase:** Capture/Live-Traffic phase. Flag for deeper research — choice of capture backend (Scapy vs flow export vs router stats) is a load-bearing decision.

**Confidence:** HIGH (Scapy docs + community confirm sniffer is slow, `store=0`/kernel filter is the standard mitigation).

---

### Pitfall 3: Running the sniffer as root / over-broad privileges = the security tool becomes the attack surface

**What goes wrong:** Raw packet capture needs elevated privileges (`CAP_NET_RAW`/`CAP_NET_ADMIN` or root). The lazy path is "run the whole container as root with `--privileged`." Now a tool that holds your router admin credentials, your entire device inventory, and the ability to block devices is itself running with maximum privilege and a web UI.

**Why it happens:** `--privileged` or running as root is the fastest way to make capture "just work," so it ships and never gets revisited.

**Consequences:** A bug or RCE in the FastAPI app, a dependency, or the UI now means full host compromise. The irony: a security monitoring tool with the worst possible blast radius.

**Prevention:**
- **Split privilege from the web app.** The capture component gets exactly `CAP_NET_RAW` + `CAP_NET_ADMIN` (not `--privileged`, not root); the FastAPI/UI/DB run unprivileged. This pairs naturally with the "capture agent" split from Pitfall 1.
- Drop all other capabilities (`cap_drop: ALL`, then add back the two needed). Read-only root filesystem where possible.
- Never expose the dashboard to the WAN (PROJECT.md already scopes remote access out — enforce it: bind to LAN/localhost, require auth even on LAN).
- Treat stored router credentials and integration tokens as crown jewels — see Pitfall 7.

**Detection / warning signs:** `--privileged` or `user: root` in compose; capture and web app in the same process/container.

**Phase:** Architecture phase (privilege model) + every phase that adds capture or integrations. Security enforcement is already on in config — make this an explicit ASVS check.

**Confidence:** HIGH (standard least-privilege principle; capability set is documented Linux behavior).

---

### Pitfall 4: Device discovery built on ARP scanning alone is unreliable and over-counts modern devices

**What goes wrong:** ARP/active scanning misses devices that are asleep (phones, IoT), behind their own L3 segment, or that ignore unsolicited ARP; and **MAC randomization** (iOS 14+, Android 10+, per-network by default; iOS now rotates/per-connection) makes the same phone appear as multiple "new devices," firing false "unknown device joined" alerts and fragmenting per-device history.

**Why it happens:** ARP scan is the easiest thing to build and works great in a 2015-era test lab. The randomization and sleep-behavior problems only show up with real consumer devices.

**Consequences:** Missing devices (false sense of completeness), phantom devices, alert fatigue from a phone that "rejoins" with a new MAC every few days, and per-device bandwidth history that splits across MACs and looks wrong.

**Prevention:**
- **Use multiple discovery sources and reconcile them**, never ARP alone:
  - **DHCP lease data** (from the router/UniFi or Pi-hole/dnsmasq) — authoritative for who actually got an address, includes hostname.
  - **mDNS/Bonjour + DNS-SD** — surfaces Apple/IoT devices and friendly names/service types that ARP can't.
  - **Router client list (UniFi)** in home mode — the router already tracks association, signal, and (often) a stable identity even across randomized MACs.
  - ARP/`ping` sweep as a *supplement*, not the source of truth.
- **Identity = a fused fingerprint, not the MAC.** Combine MAC (with the locally-administered/randomization bit checked), hostname, mDNS name, DHCP fingerprint, and vendor OUI into a stable device record. Detect the LA bit (bit 1 of first octet) and label randomized MACs as such so the UI can explain "this looks like a private-address device."
- Let the user **merge/claim** devices manually; persist the merge so re-randomization re-attaches to the same logical device.
- Tune "new device" alerts to suppress known-randomized churn (e.g., correlate by hostname/mDNS before alerting).

**Detection / warning signs:** Device count fluctuating daily; the same phone appearing as several entries; IoT devices that show in the router app but not in Innkeeper.

**Phase:** Device Discovery phase. Flag for deeper research — the multi-source reconciliation/identity model is non-trivial and central to the product.

**Confidence:** HIGH (MAC randomization behavior confirmed across Apple/Android docs + academic study; mDNS/DHCP value is well established).

---

### Pitfall 5: Router integration brittleness — the UniFi API breaks on firmware updates

**What goes wrong:** UniFi has a documented history of breaking integrations on firmware/OS changes: the UDM moved the controller off port `8443` and changed the path from `/api/s/default/...` to `/proxy/network/api/s/default/...`; authentication shifted toward **API keys via `X-API-KEY`** with local user/pass auth being deprecated/limited. A hard-coded base URL, port, login flow, or response schema will break on the next firmware bump — and these are pushed automatically.

**Why it happens:** First integration is written against one controller version; the developer assumes the API is stable. UniFi (and most prosumer routers) treat the local API as semi-private and change it freely.

**Consequences:** Home mode silently dies after a router update — discovery, blocking, and bandwidth stats all fail at once, often while the user is away. Because it's the deepest integration, its failure looks like the whole product failing.

**Prevention:**
- **The adapter pattern (already a key decision) must be real isolation**, not a thin wrapper: define a stable internal interface (`discover_devices()`, `block_device()`, `get_client_stats()`) and keep *all* UniFi-version specifics (paths, auth, schema) behind it. Prefer the maintained `aiounifi` library over hand-rolled HTTP so version churn is absorbed upstream.
- Support **API-key auth** (the current direction) in addition to user/pass; don't bake in the legacy login flow as the only path.
- **Detect controller version/OS at connect time** and branch (UDM/UDM-Pro proxy path vs CloudKey legacy path).
- **Degrade gracefully, loudly:** when the adapter fails, fall back to passive/travel-mode capabilities for the affected functions and surface a clear "router integration unavailable — running in limited mode" banner + push alert, rather than showing stale/empty data as if real.
- Pin and test against known controller versions; keep an integration smoke test that runs on startup and on a schedule.

**Detection / warning signs:** 401/404 from the controller after a UniFi update; empty client list with no error in the UI; aiounifi version lagging current firmware.

**Phase:** Router Integration (Home Mode) phase. Flag for deeper research per router brand. The graceful-degradation contract should be designed in the Dual-Mode phase.

**Confidence:** HIGH (port 8443 → /proxy/network change and X-API-KEY shift are documented in vendor wiki + HA community reports).

---

### Pitfall 6: TimescaleDB schema mistakes that bloat and slow down over years (and "never auto-delete" makes it worse)

**What goes wrong:** PROJECT.md mandates **user-configurable retention with no automatic deletion** — meaning data grows forever. Combined with common TimescaleDB mistakes this is a slow-motion failure:
- **Wrong `chunk_time_interval`** for the ingest rate (default 7 days). Home-network aggregates are low-volume; tiny default chunks at low volume hurt compression, while too-coarse chunks hurt query pruning. Rule of thumb: aim for chunks containing ~10–100M rows / a chunk's worth of recent data fitting comfortably in memory.
- **Too many chunks → planning-time explosion.** With years of data and small chunks you get thousands of chunks; `LIMIT`/`ChunkAppend` query planning time balloons (documented issue).
- **High-cardinality `segmentby`** (e.g. segment by `device_id` *and* `dest_ip`) kills compression — >10k distinct values per chunk and you get <3x ratios, defeating the point.
- **One giant wide hypertable** for everything (raw flows + summaries + dimensional data) instead of separating high-cardinality time-series from low-cardinality config.
- **No continuous aggregates / no compression**, so the dashboard queries scan raw rows over multi-year ranges and time out.

**Why it happens:** Teams treat TimescaleDB as "Postgres that's automatically good at time-series." The defaults are fine for a demo and wrong for a years-long home dataset that never deletes.

**Consequences:** Dashboard gets slower every month; disk fills (especially nasty on a Mac Mini's SSD); per-device historical bandwidth — an explicit requirement — becomes the query that times out.

**Prevention:**
- **Separate concerns into different tables:** config/device-registry/alerts = plain Postgres tables; bandwidth/traffic = hypertables. Keep raw per-flow (if stored at all) separate from rolled-up summaries.
- **Set `chunk_time_interval` deliberately** for the actual aggregate write rate (likely 1–7 day chunks for home volume; size so a chunk fits memory and you don't accumulate thousands of them per year). Revisit after measuring real volume.
- **Enable compression** with a low-cardinality `segmentby` (e.g. `device_id`, not `dest_ip`); put high-entropy columns in `orderby`, not `segmentby`. Verify ratio ≥ ~3x.
- **Use continuous aggregates** for the dashboard: precompute hourly/daily per-device rollups; the UI queries the aggregate, raw stays for drill-down.
- **Reconcile "never auto-delete" with reality:** never *deleting* doesn't mean never *downsampling*. Keep raw/high-res for a window, then roll older data into compressed daily aggregates — data is retained (requirement met) but storage and query cost stay bounded. Make the high-res window the user-configurable knob, and be explicit in the UI that old data is downsampled, not deleted.
- Add a DB-size health metric and alert before the disk is a problem.

**Detection / warning signs:** Query planning time growing with history; compression ratio < 3x; chunk count in the thousands; disk usage climbing linearly with no plateau.

**Phase:** Data model phase (early — schema is expensive to change after years of data). Flag for deeper research: the downsampling-vs-"never delete" policy and the segmentby choice.

**Confidence:** HIGH (chunk sizing, cardinality/compression thresholds, continuous aggregates, and chunk-count planning issue all confirmed in TimescaleDB docs/community).

---

## Moderate Pitfalls

### Pitfall 7: Storing router credentials / integration tokens insecurely

**What goes wrong:** UniFi admin credentials or API keys, Pi-hole tokens, and Pushover/ntfy keys get written to `.env`, committed config, or a plaintext DB column. The DB and config are then the prize for any attacker — and `.env` files famously leak into git and Docker images.

**Prevention:** Store secrets encrypted at rest (e.g. app-level encryption with a key from an env var / Docker secret, not in the DB plaintext). Use Docker secrets or a host-protected env file, never commit `.env` (gitignore + a checked-in `.env.example`). Scope the UniFi account to least privilege; prefer a dedicated API key over the super-admin login. Provide a documented key-rotation path. Never log secrets.

**Phase:** Integrations + security hardening phase. (Security enforcement already enabled in config — make this an explicit ASVS item.)

**Confidence:** MEDIUM-HIGH (general API-key hygiene + standard secrets handling).

### Pitfall 8: Active scanning on untrusted networks (travel mode) gets you flagged or blocked

**What goes wrong:** Travel mode runs nmap/ARP/active probes on hotel/Airbnb/coffee-shop Wi-Fi. Aggressive scanning trips IDS/port-security, violates most public-Wi-Fi ToS, can get the user kicked off or banned, and behind a **captive portal** the scan results are meaningless (you're scanning the portal's walled garden, not the real network).

**Prevention:** In travel mode, **default to passive and own-device-only** (PROJECT.md already scopes travel mode to the user's registered devices — enforce it technically, don't just document it). Detect captive portals first (the standard "fetch a known URL, look for redirect" probe) and refuse/limit scanning until past the portal. Throttle scans hard (slow timing, small port sets), make active scanning opt-in with a clear ToS/legal warning, and never scan hosts the user hasn't claimed. Make the "I only scan my own devices" guarantee a real constraint in code.

**Phase:** Dual-Mode / Travel-Mode phase. Flag for deeper research on captive-portal detection and a safe-scan policy.

**Confidence:** MEDIUM (captive-portal detection method confirmed; ToS/IDS consequences are well-established operational knowledge).

### Pitfall 9: Network-control actions (block device / block domain) that don't persist or can't be undone

**What goes wrong:** "Block device" is implemented as a one-shot ARP-spoof or a router API call with no record. After a router reboot/firmware update the block silently lifts; or a block applied via the router can't be cleanly reverted from Innkeeper; or travel mode offers "block" when it physically can't enforce it (no router control on someone else's network).

**Prevention:** Model blocks as **declarative desired-state** stored in the DB, reconciled to the router on every connect/reboot (so blocks survive router restarts and Innkeeper restarts). Every control action is logged, attributable, and reversible from the UI. **Disable/grey-out control features in travel mode** (PROJECT.md says travel mode loses control — make the UI honest about it rather than offering buttons that no-op). Confirm enforcement by reading state back from the router, not by assuming the call worked.

**Phase:** Control phase.

**Confidence:** MEDIUM (domain experience; aligns with PROJECT's dual-mode constraints).

### Pitfall 10: SSE real-time pipeline that floods the client or leaks connections

**What goes wrong:** SSE (the chosen real-time transport) pushing every packet/flow event to the dashboard overwhelms the browser and the server; or each tab opens an SSE stream that the server never cleans up, exhausting FastAPI workers; or behind a reverse proxy the stream buffers and "real-time" lags by seconds.

**Prevention:** Push **throttled, pre-aggregated snapshots** (e.g. a top-talkers diff every 1–2s), not raw events. Cap concurrent SSE connections, implement heartbeats + server-side cleanup on disconnect, and test through whatever proxy ships in the compose stack (disable proxy buffering for the SSE route). FastAPI is async but a blocking call in the SSE generator stalls the event loop — keep generators non-blocking.

**Phase:** Live dashboard / real-time phase.

**Confidence:** MEDIUM (SSE + FastAPI async pitfalls are well documented; specifics depend on proxy choice).

---

## Minor Pitfalls

### Pitfall 11: Vendor/OUI lookup rot
**What goes wrong:** Hard-coding or shipping a stale IEEE OUI database means new vendors show as "Unknown," and randomized MACs (LA bit set) have no real OUI at all but get mislabeled.
**Prevention:** Use a maintained OUI dataset with a refresh path; explicitly handle locally-administered MACs as "private address" rather than guessing a vendor.

### Pitfall 12: Assuming a single, stable network interface name
**What goes wrong:** Hard-coding `eth0` breaks on machines using `en0`, `enp3s0`, predictable names, or multiple NICs — directly conflicts with the "no machine-specific assumptions" constraint.
**Prevention:** Auto-detect the active interface (or make it configurable) and validate it can see traffic at startup.

### Pitfall 13: Time zone / clock drift in time-series
**What goes wrong:** Storing local time instead of UTC, or container clock drift, corrupts bandwidth-over-time charts and retention math.
**Prevention:** Store everything in UTC (`timestamptz`), render local in the UI, sync container clock.

### Pitfall 14: Treating GeoIP / "known bad IP" feeds as ground truth
**What goes wrong:** "Alert on known bad IPs / suspicious traffic" using a stale or low-quality threat feed produces constant false positives (CDNs, shared cloud IPs) → alert fatigue.
**Prevention:** Use a maintained reputation feed, allow user allow-listing, and rank/aggregate rather than alerting on every hit.

---

## The Meta-Pitfall: Feature Creep / Scope Collapse

**What goes wrong:** Home-network tools (this is a recurring pattern across the ecosystem) start as "see my devices" and accrete: full IDS, VPN management, parental controls, ad-blocking, NAS dashboards, smart-home control, multi-network, plugin marketplaces. Each feature drags in capture depth, privilege, and integration brittleness. The project collapses under maintenance load and the core "see every device and what it's doing" never gets *good*.

**Why it happens:** Network data is fascinating and adjacent features feel "free." Open-source ambition amplifies it ("someone will want X").

**Why this project is already at risk:** The Active requirements list is broad (discovery, live traffic, security scanning, vuln detection, control, dual-mode, notifications, Pi-hole, Grafana, CLI, web UI). Several of these are each a product. PROJECT.md *has* good guardrails (Out of Scope: no remote access, no cloud, no mobile app, no plugin marketplace, single network) — the risk is the Active list, not the Out-of-Scope list.

**Prevention (actionable):**
- **Sequence by the capture-feasibility spine, not by excitement.** Discovery + a working capture topology (Pitfall 1) must be proven *before* security scanning, control, or integrations are planned — everything downstream depends on reliable device identity and traffic data.
- Treat **security scanning, vuln detection, Pi-hole, Grafana, CLI** as separate later phases that build on a stable core, each behind the adapter/integration boundary so they can fail or be deferred without touching the core.
- Hold the existing Out-of-Scope line hard; re-litigate scope only at milestone boundaries (PROJECT.md already defines this ritual).
- Prefer **consuming existing tools' data** (Pi-hole for DNS blocking, router for stats, Grafana for custom dashboards) over re-implementing them — the curated-integration decision is the right anti-creep move; honor it.

**Phase:** Roadmap structure overall. The roadmap should make the dependency spine explicit and gate later features on a proven core.

**Confidence:** MEDIUM (ecosystem pattern + direct read of this project's requirement breadth).

---

## Phase-Specific Warnings (summary for roadmap)

| Phase Topic | Likely Pitfall | Mitigation | Deeper research? |
|---|---|---|---|
| Phase 0/1 Architecture spike | #1 Docker-on-macOS capture is crippled | Decide capture topology (native agent vs Linux host vs router-sourced) **before** capture code | **Yes — gate** |
| Data model (early) | #6 TimescaleDB bloat; "never delete" forever-growth | Separate hypertables from config; deliberate chunk sizing; compression w/ low-card segmentby; continuous aggregates; downsample-not-delete | Yes |
| Device discovery | #4 ARP-only unreliable; MAC randomization over-counts | Fuse DHCP + mDNS + router client list; identity = fingerprint not MAC; manual merge; detect LA bit | Yes |
| Capture / live traffic | #2 capture-too-much, drops, RAM blowup; #3 root privilege | Aggregate at capture, `store=0`+BPF, prefer flow/router stats; split privileged capture from web app (`CAP_NET_RAW` only) | Yes (capture backend) |
| Real-time dashboard | #10 SSE flood / connection leak / proxy buffering | Throttled aggregated snapshots; heartbeats + cleanup; disable proxy buffering | No |
| Router integration (home) | #5 UniFi API breaks on firmware | Real adapter isolation; aiounifi; support X-API-KEY; version-detect path; degrade loudly | Yes (per brand) |
| Control (block) | #9 blocks don't persist / no-op in travel mode | Declarative desired-state reconciled on reconnect; grey-out control in travel mode | No |
| Dual / travel mode | #8 active scan on untrusted net flagged/blocked; captive portal | Passive + own-devices-only default; captive-portal detect; throttle; opt-in active w/ warning | Yes |
| Integrations + security | #3 / #7 tool is the attack surface; secret storage | Least privilege, LAN-only bind, encrypted secrets, Docker secrets, key rotation | No |
| Roadmap overall | Meta: feature creep / scope collapse | Sequence on capture-feasibility spine; gate later features on stable core; hold Out-of-Scope | n/a |

---

## Sources

- Docker host networking unsupported on Mac (VM architecture): https://docs.docker.com/desktop/features/networking/ , https://github.com/docker/roadmap/issues/238 , https://medium.com/@lailadahi/getting-around-dockers-host-network-limitation-on-mac-9e4e6bfee44b — HIGH
- Docker macvlan promiscuous-mode requirement & traffic-visibility issues: https://docs.docker.com/engine/network/drivers/macvlan/ , https://github.com/moby/libnetwork/issues/2008 — HIGH
- Scapy sniffer performance, `store=0`, kernel BPF filter, layer disabling: https://scapy.readthedocs.io/en/latest/usage.html , https://www.examcollection.com/blog/capturing-network-traffic-in-threads-using-scapy-and-python/ — HIGH
- MAC address randomization (iOS/Android per-network & rotation, LA bit): https://support.apple.com/guide/security/privacy-features-connecting-wireless-networks-secb9cb3140c/web , https://arxiv.org/pdf/1703.02874 , https://www.extremenetworks.com/extreme-networks-blog/wi-fi-mac-randomization-privacy-and-collateral-damage/ — HIGH
- UniFi API breaking changes (8443 → /proxy/network, X-API-KEY auth): https://ubntwiki.com/products/software/unifi-controller/api , https://community.home-assistant.io/t/unifi-integration-authentication-failing/435261 — HIGH
- TimescaleDB chunk sizing, compression cardinality, continuous aggregates, chunk-count planning: https://www.jusdb.com/blog/timescaledb-timescaledb-hypertables-continuous-aggregates-guide , https://dev.to/philip_mcclarence_2ef9475/why-your-timescaledb-compression-ratio-is-bad-and-how-to-fix-it-lb1 , https://github.com/timescale/timescaledb/issues/2897 , https://forum.tigerdata.com/forum/t/choosing-the-right-chunk-time-interval-value-for-timescaledb-hypertables/116 — HIGH
- Captive portal detection / untrusted-network scanning risk: https://arxiv.org/pdf/1907.02142 , https://forum.netgate.com/topic/810/nmap-scan-on-wan-reveals-captive-portal — MEDIUM
- API key / credential exposure hygiene: https://www.cycognito.com/learn/api-security/api-security-tools/ — MEDIUM
- Feature creep / scope, blocking persistence, SSE, OUI, interface naming: domain experience cross-referenced with PROJECT.md constraints — MEDIUM/LOW
