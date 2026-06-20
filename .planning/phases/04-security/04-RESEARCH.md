# Phase 4: Security - Research

**Researched:** 2026-06-20
**Domain:** Active port scanning (nmap), table-driven security rules, threat-intel matching, derived status computation, durable alerting
**Confidence:** MEDIUM-HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

User delegated all four gray areas to Claude's judgment ("pick your own recommended ideas... pick what is best for the product... while keeping up with our existing ideals of clean, easy to maintain, testable code"). Decisions below were chosen for product strength, maintainability, and consistency with prior-phase architecture — not for implementation ease.

**Port Scan Trigger, Scope & Engine**
- **D-01:** Two trigger paths: an on-demand "Scan" button per device (SEC-01's explicit ask) **and** a low-impact automatic background re-scan (daily) for *registered* devices only — keeps the security badge from going stale without the user remembering to click, while not scanning unknown/transient devices (e.g. guest phones) on a schedule.
- **D-02:** Scan scope is nmap's **top-1000 common ports**, not a full 1–65535 sweep — full-range scans are slow, CPU-heavy on a low-power always-on box, and add little signal for a home network. A "full scan" option is explicitly deferred (see Deferred Ideas), not built now.
- **D-03:** Scans run from the **capture container**, not the backend — the capture container already holds `CAP_NET_RAW`/`CAP_NET_ADMIN` (Phase 1 D-05) for a TCP SYN scan; this avoids granting new elevated capabilities to the backend and keeps the "backend stays unprivileged" boundary intact. Scan results are POSTed to the API via a new ingest route, following the same trust pattern as the existing `/api/capture/*` routes.
- **D-04:** Use the **home-assistant-libs/python-nmap fork** wrapping the system `nmap` binary, exactly per CLAUDE.md's stack guidance (the original `xael/python-nmap` on PyPI is unmaintained) — `nmap` gets added to the capture container's Dockerfile.

**Unexpected-Port Rule Baseline**
- **D-05:** Two-tier, table-driven rule (not a single allowlist) — chosen because it's testable as plain data and gives meaningfully different severities instead of one big "anything weird" bucket:
  - **Universal risky-ports set** (any device, any type): telnet (23), FTP (21), SMB (139/445), RDP (3389), VNC (5900), and other classic unauthenticated/legacy-remote-access ports. An open risky port is **always flagged**, regardless of device type.
  - **Per-device-type expected-ports allowlist** (keyed off `Device.type`, the closed enum locked in Phase 2 D-14 specifically for this purpose): e.g. `router_network` expects 53/80/443/22; `iot_smart_home` expects little to nothing; `phone`/`laptop`/`desktop`/`tablet` expect nothing by default. Any open port outside the type's allowlist *and* not in the risky set is "unexpected" (lower severity — e.g. a desktop running a Plex server on 32400 is informational, not alarming).

**Security Status Derivation (good/warning/critical)**
- **D-06:** Status is computed, table-driven, from two signal classes — no opaque scoring formula:
  - **critical:** device has an open *risky* port (D-05) **or** device has communicated with a known-malicious IP (SEC-03).
  - **warning:** device has an open *unexpected-but-not-risky* port (D-05) **or** a bandwidth-anomaly signal fires (D-09 below).
  - **good:** none of the above. A device that has never been scanned also defaults to **good** (not warning) — an unscanned device isn't assumed guilty; the UI surfaces "not yet scanned" separately via the scan button/timestamp, not via the badge color.
- **D-07:** Status is recomputed whenever new scan results land or a new traffic-pattern/malicious-IP match is recorded — it is a derived/cached field on the device (or a join at read time), not something the user sets.

**Malicious-IP / Suspicious-Traffic Detection**
- **D-08:** Default, zero-config detector is a **bundled static blocklist** (a vendored data file shipped in the backend image, updated via normal app releases) — satisfies the hard "no telemetry, no external calls unless user explicitly configures an integration" constraint out of the box. A `ThreatIntelSource` interface (mirroring the swappable-source pattern already used for bandwidth in Phase 3 D-07) has this `StaticBlocklistSource` as the only built-in implementation.
- **D-09 (suspicious traffic patterns):** Scoped narrowly and concretely for v1 — a **bandwidth-spike anomaly**: a device's traffic in the current window exceeds N× its own rolling historical average (reusing Phase 3's `bandwidth_metrics`/`traffic_flows` data, no new capture infra needed). This is a `warning`-level signal (more false-positive-prone than a malicious-IP hit — e.g. a video call or big download), not `critical`. No bespoke anomaly-detection ML — a simple, testable threshold comparison.
- **D-10:** A remote/updatable threat-feed source (e.g. Spamhaus DROP, FireHOL) is **explicitly an opt-in setting, off by default** — if/when built, it's the user "explicitly configuring an integration" the constraint already carves out. Building the remote-feed UI itself is not required this phase (see Deferred Ideas); the `ThreatIntelSource` interface should make adding it later a non-rewrite.

**Unknown-Device & Alert Surfacing (pre-notifications)**
- **D-11:** A durable **`security_alerts`** table (device_id nullable, type: `unknown_device` / `malicious_ip` / `suspicious_traffic` / `unexpected_port`, severity, message, created_at, acknowledged) is the canonical alert record. This is deliberately shaped so Phase 5's event bus (PLUG-03) can subscribe to/poll it directly — not throwaway work.
- **D-12:** Dashboard gets an **alerts feed/banner** (unacknowledged alerts, dismissible) above the device grid, alongside the existing Phase 2 D-13 summary banner — this is the "you need to act on this" view. The per-device good/warning/critical badge (D-06) remains the "at a glance" view on each card. Both are needed; neither replaces the other.
- **D-13:** SEC-02 (unknown device joins) and SEC-04 (status badge) both write into `security_alerts` for visibility now; actual push delivery is correctly deferred to Phase 5 per the roadmap — this phase's job stops at "detected, classified, and durably recorded."

### Claude's Discretion
- Exact daily-scan scheduling mechanism (cron-like loop vs APScheduler vs simple interval task) — implementation detail, not product-visible.
- Exact bandwidth-anomaly threshold multiplier (D-09) and rolling-average window length — tune during implementation/testing.
- Exact per-device-type expected-ports allowlist contents beyond the examples above (D-05) — researcher/planner should finalize the full table per `DeviceType` enum value.
- `security_alerts` schema details (indexes, exact column types) beyond the shape specified in D-11.
- Whether scan results themselves are persisted as a separate `port_scan_results` history table or only the latest result per device — left to planner, as long as the derived status (D-06/D-07) is always queryable.

### Deferred Ideas (OUT OF SCOPE)
- **Full 1–65535 port scan option** — deferred; top-1000 (D-02) is the v1 default. Could be a later opt-in "deep scan" if a user specifically needs it.
- **User-configurable remote threat-feed UI** (Spamhaus/FireHOL/etc.) — deferred; the `ThreatIntelSource` interface (D-08/D-10) is built to allow this later without rework, but the settings UI/fetch-scheduler itself is not built in Phase 4.
- **ML-based / statistical anomaly detection** beyond the simple bandwidth-spike threshold (D-09) — deferred; revisit only if the simple threshold proves insufficient in practice.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|--------------|----------------------|
| SEC-01 | System can run an open port scan against any device and display results, flagging ports that appear unexpected for that device type | Pattern 1 (scan-trigger), Pattern 2 (two-tier port rules + finalized `EXPECTED_PORTS` table), Package Legitimacy Audit (python-nmap fork sourcing) |
| SEC-02 | System sends a push notification when an unregistered (unknown) device joins the network (delivery deferred to Phase 5 per D-13 — this phase only detects/records) | `security_alerts` schema (D-11, locked), Architecture Diagram's alert-insert path |
| SEC-03 | System detects and alerts when a device connects to a known malicious IP or exhibits suspicious traffic patterns | Pattern 4 (`ThreatIntelSource`/`StaticBlocklistSource`), Pitfall 5 (bandwidth-anomaly baseline), Open Question 2 (threshold tuning) |
| SEC-04 | System assigns each device a security status (good/warning/critical) derived from scan results, displayed prominently on the device card | Pattern 3 (`derive_status`), Pitfall 3 (never-scanned-defaults-to-good), Architectural Responsibility Map |
</phase_requirements>

## Summary

Phase 4 adds Innkeeper's first **active** security capability on top of the passive discovery/traffic foundation built in Phases 1-3. The work is almost entirely "wire existing pieces together using established codebase patterns" rather than new technology adoption: the capture container already runs as root with `CAP_NET_RAW`/`CAP_NET_ADMIN` (no new privilege grant needed for nmap's SYN scan), the `/api/capture/*` ingest-route trust pattern already exists for the new scan-result route, and the `BandwidthSource` Protocol pattern from Phase 3 is the direct template for `ThreatIntelSource`.

The one real risk area is the **python-nmap package identity**: PyPI's published `python-nmap` (version 0.7.1) is confirmed to be the original unmaintained `xael.org` package, not the home-assistant-libs fork CLAUDE.md mandates. The fork is **not separately published to PyPI** — it must be installed directly from its GitHub repo via a `git+https://` pip requirement, which is an unusual-enough installation method that the planner must flag it for explicit human verification before locking the dependency.

Two-tier port-rule design (D-05), good/warning/critical derivation (D-06/D-07), and the `security_alerts` schema (D-11) are all plain-data/SQL problems with no external library needed — this research finalizes the per-`DeviceType` allowlist table and the derivation logic as concrete, ready-to-implement specs so the planner doesn't have to invent them. The bandwidth-anomaly check (D-09) reuses Phase 3's `bandwidth_metrics` table read-side with a new query, no new capture infrastructure.

**Primary recommendation:** Install the home-assistant-libs python-nmap fork via a `git+https://github.com/home-assistant-libs/python-nmap` pip requirement (not the PyPI name) behind a `checkpoint:human-verify` task; run scans from the capture container via a new scan-trigger listener + scheduled daily loop, POST results to a new `/api/capture/scan` ingest route; compute good/warning/critical via the table-driven rule sets below, cached on `Device` and recomputed on new scan/traffic-anomaly/threat-match events; ship a vendored FireHOL `firehol_level1.netset`-style flat CIDR list as the zero-config `StaticBlocklistSource`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Port scan execution (nmap SYN scan) | Capture container (privileged) | — | Only the capture container holds `CAP_NET_RAW`/`CAP_NET_ADMIN`; backend stays unprivileged (D-03) |
| Scan-result ingest | API / Backend | — | New `/api/capture/scan` route, same loopback/gateway-trust pattern as existing `/api/capture/*` routes |
| Port-rule evaluation (risky/unexpected) | API / Backend | — | Pure table-driven logic over scan results already in Postgres; no privilege or external I/O needed |
| Security status derivation (good/warning/critical) | API / Backend | Database / Storage (cached column) | Computed in a service function, persisted on `Device` as a cache (D-07) — read-heavy (every dashboard load), write-light (only on new signal) |
| Malicious-IP matching | API / Backend | Database / Storage (vendored blocklist file) | Static file lookup against `traffic_flows.dst_ip`, no capture-container involvement — purely a read-side correlation job |
| Bandwidth-anomaly detection | API / Backend | Database / Storage (`bandwidth_metrics` reads) | Reuses Phase 3's existing time-series table; pure SQL aggregation + threshold compare |
| Alert persistence (`security_alerts`) | Database / Storage | API / Backend (write path) | New plain relational table, not a hypertable (per STATE.md note: not time-series) |
| Alerts feed / banner UI | Browser / Client | Frontend Server (SSR is N/A — SPA) | New dashboard component reading `/api/security/alerts`, polling or page-load fetch (no SSE requirement stated for this phase) |
| DeviceCard security badge | Browser / Client | — | Reads cached `security_status` field already returned by `/api/devices` |
| Daily scheduled re-scan trigger | Capture container | — | Lives alongside existing ARP/DHCP/mDNS/traffic threads; triggers the same scan-and-POST code path as the on-demand button |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| nmap (system binary) | latest in `python:3.13-slim` + apt | Actual port-scanning engine | The only credible engine for SYN scans; python-nmap is a thin subprocess wrapper around it |
| python-nmap (home-assistant-libs fork) | git HEAD (no PyPI release) | Python wrapper around the `nmap` binary, parses XML output into dict | `[ASSUMED]` per CLAUDE.md mandate — **not separately versioned on PyPI**; see Package Legitimacy Audit |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none new for backend logic) | — | Port-rule eval, status derivation, threat matching, anomaly detection are all plain Python/SQL | Use stdlib + SQLAlchemy only — no new backend dependency required for this phase's core logic |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| home-assistant-libs python-nmap fork | Shell out to `nmap -oX -` directly via `subprocess` + `xml.etree` | Avoids the unusual git-install dependency entirely; loses the convenience dict-parsing API. Given the fork is unmaintained-feeling itself (GitHub-only, last meaningfully active years ago per its own README), this is a credible fallback if the checkpoint review rejects the git dependency |
| Simple `asyncio` daily interval loop (D-01's discretion item) | APScheduler 3.11.2 (`AsyncIOScheduler`) | APScheduler is the standard async-aware scheduler [VERIFIED: PyPI, confirmed legitimate `agronholm/apscheduler` source repo] but adds a dependency for a single fixed-cadence job; a sleep-until-next-run loop matches this codebase's existing thread-per-concern convention in `capture/capture.py` with zero new dependencies — **recommended: simple loop**, not APScheduler |
| Vendored FireHOL `firehol_level1.netset` flat file | Spamhaus DROP JSON feed directly | Spamhaus now distributes DROP as JSON requiring a parse step and carries Spamhaus's own re-distribution terms; FireHOL's `firehol_level1.netset` is a pre-aggregated, plain-text, one-CIDR-per-line file that already *includes* `spamhaus_drop` plus `dshield`/`feodo`/`fullbogons` — simpler to vendor, equivalent or broader coverage |

**Installation:**
```bash
# Capture container requirements.txt — add:
# nmap (system binary) via apt-get in Dockerfile, NOT pip
# python-nmap fork via git, NOT the PyPI name:
python-nmap @ git+https://github.com/home-assistant-libs/python-nmap
```

```dockerfile
# capture/Dockerfile — add to the existing apt-get install line:
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpcap-dev nmap \
    && rm -rf /var/lib/apt/lists/*
```

**Version verification:**
- `nmap` (apt package): not pinned to a specific version — relies on Debian slim's repo snapshot at build time, consistent with how `libpcap-dev` is already handled in this Dockerfile. `[VERIFIED: apt — confirmed via existing Dockerfile pattern, same unpinned convention]`
- `python-nmap` on PyPI: confirmed **0.7.1**, published by the original xael.org maintainer, last meaningfully updated years ago — this is explicitly the package CLAUDE.md says to avoid. `[VERIFIED: PyPI JSON API, fetched 2026-06-20]`
- home-assistant-libs fork: **no PyPI release exists** — GitHub-only, must be pip-installed via `git+https://` URL, pinned to a commit SHA (not just `master`) once a planner/implementor task selects one, to avoid silent drift. `[CITED: github.com/home-assistant-libs/python-nmap]`

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| python-nmap (PyPI, xael original) | PyPI | ~5 yrs (last release 2021) | unknown (seam: no metric) | xael.org (non-GitHub) | SUS | **REMOVED — do not install this PyPI package; CLAUDE.md explicitly prohibits it** |
| python-nmap (home-assistant-libs fork) | GitHub only, no registry entry | fork of a multi-year-old project, fork itself has commits but no independent release cadence | N/A — not on a registry | github.com/home-assistant-libs/python-nmap | Not registry-checkable | `[ASSUMED — flagged]` Planner MUST add `checkpoint:human-verify` before this dependency is added: verify the fork repo is still reachable, pin to a specific commit SHA (not `master`), and confirm the install command works inside the `python:3.13-slim` capture image before relying on it |
| APScheduler | PyPI | mature, active (agronholm/apscheduler) | unknown (seam: no metric) | github.com/agronholm/apscheduler | SUS (seam) → **OK on manual review** | Verified via PyPI project_urls: real GitHub source, real docs, real changelog. Recommended NOT to add (see Alternatives) but if planner chooses it anyway, no legitimacy concern — the seam's SUS verdict here is a metric-collection gap, not a real risk signal |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS] requiring human-verify checkpoint:** `python-nmap` (home-assistant-libs git fork) — non-registry git dependency, must be pinned to a SHA and manually smoke-tested in the capture image before being trusted as a build-time dependency.

*The PyPI-published `python-nmap` package itself is legitimate (publishes fine, has long history) but is the **wrong package** for this project's stated requirement — CLAUDE.md is explicit that it's unmaintained and the fork must be used instead. Do not let `pip install python-nmap` silently satisfy a "add python-nmap" task; the install line must reference the GitHub URL.*

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│  Capture container (CAP_NET_RAW + CAP_NET_ADMIN, root, no new caps) │
│                                                                       │
│  [existing] ARP/DHCP/mDNS/traffic threads ──POST──► API (unchanged) │
│                                                                       │
│  [NEW] scan-trigger listener ◄── poll/long-poll ──┐                 │
│        (checks API for pending on-demand requests) │                 │
│  [NEW] daily-rescan loop (sleep-until-next-run)     │                 │
│        │                                            │                 │
│        ▼                                            │                 │
│  nmap PortScanner.scan(ip, arguments='-sS')          │                 │
│  (top-1000 ports, one device at a time)              │                 │
│        │                                            │                 │
│        ▼                                            │                 │
│  POST scan result ──────────────────────────────────┘                 │
└─────────────────────┬─────────────────────────────────────────────────┘
                       │  POST /api/capture/scan  (loopback/gateway-trust,
                       │  same _TRUSTED_HOSTS check as /arp,/dhcp,/mdns,/traffic)
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  API / Backend (unprivileged)                                       │
│                                                                       │
│  ingest_scan() ─► persist scan result (latest-per-device or history) │
│        │                                                              │
│        ▼                                                              │
│  evaluate_port_rules(device.type, open_ports)                        │
│    - universal risky-ports set  (D-05)                               │
│    - per-DeviceType allowlist   (D-05)                               │
│        │                                                              │
│        ▼                                                              │
│  recompute_security_status(device) ─► writes Device.security_status  │
│        │                          ▲                                  │
│        │                          │ also triggered by:               │
│        │                          ├─ threat-intel match (new flow)   │
│        │                          └─ bandwidth-anomaly check (cron)  │
│        ▼                                                              │
│  security_alerts table ◄── insert on: unknown_device / malicious_ip  │
│        │                            / suspicious_traffic /            │
│        │                            unexpected_port                   │
│        ▼                                                              │
│  GET /api/devices        ──► includes security_status per device     │
│  GET /api/security/alerts──► unacknowledged alerts feed              │
└─────────────────────┬─────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Browser / Client (SPA)                                              │
│  Dashboard alerts banner (new) ── above device grid                  │
│  DeviceCard.svelte ── badge (good/warning/critical) + Scan button     │
└─────────────────────────────────────────────────────────────────────┘

Separately, on every /api/capture/traffic ingest (existing route):
  TrafficFlow.dst_ip ──► ThreatIntelSource.is_malicious(ip) ──► on hit:
      security_alerts insert (malicious_ip) + recompute_security_status
```

### Recommended Project Structure
```
backend/src/
├── models/
│   ├── device.py                  # existing — add security_status column (D-06/D-07)
│   ├── port_scan_result.py        # NEW — latest-or-history scan result rows
│   └── security_alert.py          # NEW — security_alerts table (D-11)
├── routes/
│   ├── capture.py                 # existing — add POST /scan ingest route
│   ├── security.py                # NEW — POST /scan/{device_id} trigger, GET /alerts, POST /alerts/{id}/ack
│   └── devices.py                 # existing — serializer gains security_status field
├── services/
│   ├── port_rules.py              # NEW — table-driven risky/expected-ports data + evaluate() (D-05)
│   ├── security_status.py         # NEW — derive/recompute good/warning/critical (D-06/D-07)
│   ├── threat_intel_source.py     # NEW — ThreatIntelSource Protocol + StaticBlocklistSource (D-08)
│   └── bandwidth_anomaly.py       # NEW — rolling-average threshold check (D-09)
└── data/
    └── firehol_level1.netset      # NEW — vendored static blocklist, bundled in backend image

capture/
├── capture.py                     # existing — add scan-trigger-listener thread + daily-rescan thread
├── port_scan.py                   # NEW — nmap PortScanner wrapper, mirrors traffic_sniff.py's module shape
└── requirements.txt                # existing — add python-nmap git dependency

frontend/src/lib/components/
├── DeviceCard.svelte               # existing — add badge + Scan button
└── SecurityAlertsBanner.svelte     # NEW — dashboard alerts feed (D-12)
```

### Pattern 1: Capture-Owns-Privilege Scan Trigger
**What:** The capture container cannot receive inbound HTTP (it only POSTs outbound), so an on-demand "Scan" button click from the browser must reach the capture container indirectly: the API records a pending-scan request (e.g. a row or in-memory queue), and the capture container's scan-trigger-listener thread polls a new lightweight `GET /api/capture/pending-scans` endpoint on a short interval (e.g. every 2-5s), claims the request, runs the scan, then POSTs the result back via the existing ingest pattern.
**When to use:** Any time the browser needs to cause an action in the privileged capture container, given capture never accepts inbound connections.
**Example:**
```python
# capture/port_scan.py — mirrors capture/traffic_sniff.py's module shape
import time
import httpx
import nmap

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
TOP_PORTS_ARGS = "-sS"  # no -p flag => nmap's default top-1000 TCP ports

def run_scan_listener(stop_event):
    scanner = nmap.PortScanner()
    while not stop_event.is_set():
        try:
            resp = httpx.get(f"{API_URL}/api/capture/pending-scans", timeout=5.0)
            for req in resp.json().get("pending", []):
                _run_and_post_scan(scanner, req["device_id"], req["ip"])
        except Exception as exc:  # noqa: BLE001 - log and keep polling
            print(f"[capture] scan-listener poll failed: {exc}")
        time.sleep(3)

def _run_and_post_scan(scanner, device_id, ip):
    scanner.scan(ip, arguments=TOP_PORTS_ARGS)
    open_ports = [
        p for p in scanner[ip].get("tcp", {})
        if scanner[ip]["tcp"][p]["state"] == "open"
    ] if ip in scanner.all_hosts() else []
    payload = {"device_id": device_id, "open_ports": open_ports}
    httpx.post(f"{API_URL}/api/capture/scan", json=payload, timeout=30.0)
```
*Source: pattern synthesized from capture/capture.py's existing POST-per-unit convention + [CITED: python-nmap README usage shape].*

### Pattern 2: Two-Tier Table-Driven Port Rules (D-05)
**What:** Plain Python data structures (a `frozenset` for risky ports, a `dict[DeviceType, frozenset[int]]` for expected ports) evaluated by a pure function — no ORM, no I/O, fully unit-testable.
**When to use:** Any time port-scan results need a severity classification.
**Example:**
```python
# backend/src/services/port_rules.py
from src.models.device import DeviceType

# D-05: universal risky ports — flagged regardless of device type.
# Classic unauthenticated/legacy-remote-access services.
RISKY_PORTS: frozenset[int] = frozenset({
    21,    # FTP — unauthenticated/plaintext
    23,    # Telnet — plaintext remote shell
    135,   # MS RPC
    139,   # NetBIOS / SMB
    445,   # SMB
    512, 513, 514,  # rexec/rlogin/rsh
    1433,  # MSSQL default
    3306,  # MySQL default — only risky if exposed beyond loopback, still flag
    3389,  # RDP
    5900,  # VNC
})

# D-05: per-DeviceType expected-ports allowlist. Anything open outside both
# this set AND RISKY_PORTS is "unexpected" (warning, not critical).
EXPECTED_PORTS: dict[DeviceType, frozenset[int]] = {
    DeviceType.ROUTER: frozenset({22, 53, 80, 443}),       # SSH/DNS/HTTP/HTTPS admin
    DeviceType.IOT: frozenset({80, 443, 1900}),            # HTTP/S + SSDP discovery
    DeviceType.TV: frozenset({80, 443, 7000, 8008, 8009}), # casting/streaming control ports
    DeviceType.CONSOLE: frozenset({80, 443}),
    DeviceType.PHONE: frozenset(),
    DeviceType.LAPTOP: frozenset(),
    DeviceType.DESKTOP: frozenset(),
    DeviceType.TABLET: frozenset(),
    DeviceType.OTHER: frozenset(),
}


def evaluate_open_ports(device_type: DeviceType, open_ports: list[int]) -> tuple[list[int], list[int]]:
    """Returns (risky_open, unexpected_open) — both empty lists if clean.

    risky_open: any open port in RISKY_PORTS (always flagged, any device).
    unexpected_open: open, not risky, and not in this device type's allowlist.
    """
    allowlist = EXPECTED_PORTS.get(device_type, frozenset())
    risky_open = [p for p in open_ports if p in RISKY_PORTS]
    unexpected_open = [p for p in open_ports if p not in RISKY_PORTS and p not in allowlist]
    return risky_open, unexpected_open
```
*Source: synthesized from D-05's explicit decision text + standard IANA well-known port assignments `[CITED: IANA Service Name and Transport Protocol Port Number Registry]`. Per-type allowlist contents beyond D-05's examples are `[ASSUMED]` — reasonable defaults, not externally verified against any device-fingerprinting database; flag in Assumptions Log for planner/user confirmation.*

### Pattern 3: Derived Status Cache, Recomputed on Signal (D-06/D-07)
**What:** A pure function takes the device's latest scan result + threat/anomaly flags and returns one of three enum values; callers persist the result onto `Device.security_status` whenever a new signal arrives. Mirrors the existing "compute then cache" idiom already used for `Device.last_seen` (set on every observation, not recomputed at read time).
**When to use:** Any value that's expensive or awkward to compute at every read but cheap to recompute on every write-triggering event.
**Example:**
```python
# backend/src/services/security_status.py
import enum

class SecurityStatus(str, enum.Enum):
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"


def derive_status(
    *, risky_open_ports: list[int], unexpected_open_ports: list[int],
    has_malicious_ip_match: bool, has_bandwidth_anomaly: bool,
) -> SecurityStatus:
    """D-06: table-driven, no opaque scoring. A never-scanned device passes
    empty lists/False here and correctly resolves to GOOD (D-06's explicit
    'not yet scanned defaults to good' rule) — callers surface 'not scanned'
    via a separate timestamp field, never via this enum."""
    if risky_open_ports or has_malicious_ip_match:
        return SecurityStatus.CRITICAL
    if unexpected_open_ports or has_bandwidth_anomaly:
        return SecurityStatus.WARNING
    return SecurityStatus.GOOD
```
Call `derive_status(...)` and persist the result to `Device.security_status` inside each of the three write paths: scan-ingest route, threat-intel-match check (in traffic ingest), bandwidth-anomaly cron job — never compute it lazily at `/api/devices` read time, to keep that route's cost flat regardless of scan/traffic volume.
*Source: directly synthesized from D-06/D-07's explicit decision text — this is locked product logic, not exploratory research.*

### Pattern 4: Swappable ThreatIntelSource (D-08/D-10)
**What:** A `Protocol` + one concrete implementation, exactly matching Phase 3's `BandwidthSource`/`PassiveCaptureBandwidthSource` shape.
**When to use:** Any pluggable backend where today there's exactly one implementation but a future one (remote feed) must slot in without changing callers.
**Example:**
```python
# backend/src/services/threat_intel_source.py
from typing import Protocol
import ipaddress

class ThreatIntelSource(Protocol):
    """D-08: swappable threat-data interface, mirrors BandwidthSource (D-07)."""
    def is_malicious(self, ip: str) -> bool: ...


class StaticBlocklistSource:
    """The only built-in source today (D-08) — loads a vendored flat CIDR
    file at startup, matches via ipaddress network containment. A future
    Phase opt-in RemoteFeedSource (D-10) implements the same Protocol."""

    def __init__(self, blocklist_path: str = "src/data/firehol_level1.netset"):
        self._networks: list[ipaddress.IPv4Network] = []
        with open(blocklist_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    self._networks.append(ipaddress.ip_network(line, strict=False))
                except ValueError:
                    continue  # skip malformed lines defensively

    def is_malicious(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(addr in net for net in self._networks)
```
**Performance note:** a linear scan over ~3,800 networks per lookup is adequate for a household's traffic-ingest volume (low hundreds of distinct dst_ips per rollup), but if profiling later shows it's hot, swap the list for a sorted-range binary-search structure (e.g. `bisect` over sorted network-start integers) — Protocol boundary makes this an internal `StaticBlocklistSource` optimization, not an interface change.
*Source: structural pattern from `backend/src/services/bandwidth_source.py` (read in full) `[VERIFIED: codebase]`; blocklist file format from FireHOL `[CITED: github.com/firehol/blocklist-ipsets]`.*

### Pattern 5: Capture-Container Daily Loop (D-01, Claude's Discretion)
**What:** A plain `threading.Thread` running a sleep-until-next-run loop, matching the existing ARP/DHCP/mDNS/traffic thread convention — no new dependency.
**When to use:** Single fixed-cadence background job inside a process that already manages its own threads with a shared `stop_event`.
**Example:**
```python
# capture/capture.py — add alongside existing thread definitions
import datetime as dt

def run_daily_rescan_loop(stop_event):
    while not stop_event.is_set():
        now = dt.datetime.now()
        next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += dt.timedelta(days=1)
        sleep_seconds = (next_run - now).total_seconds()
        # Wake early on stop_event so shutdown isn't blocked up to 24h (Pitfall 6 precedent).
        if stop_event.wait(timeout=sleep_seconds):
            break
        _trigger_rescan_of_registered_devices()
```
Register a fifth thread in `main()` alongside the existing four, same `start()`/`join()` shape.
*Source: synthesized from capture.py's existing SIGTERM/stop_event pattern `[VERIFIED: codebase]` + the Alternatives Considered analysis above recommending against APScheduler for this single-job use case.*

### Anti-Patterns to Avoid
- **Computing security_status lazily at `/api/devices` read time:** Defeats D-07's "derived/cached" requirement and couples dashboard latency to scan/traffic volume — always write the cached value at the point of the triggering event.
- **Letting `pip install python-nmap` (no git URL) satisfy the dependency:** Silently installs the unmaintained xael package CLAUDE.md explicitly prohibits — the install command must reference the GitHub fork URL, not the bare package name.
- **Scanning unregistered/unknown devices on the daily schedule:** D-01 explicitly scopes the automatic background re-scan to *registered* devices only — querying `Device` rows (not raw ARP/DHCP observations) for the daily loop's target list is required.
- **A single combined "risk score" number instead of two explicit lists:** D-06 explicitly rejects "opaque scoring formula" — keep `risky_open_ports` and `unexpected_open_ports` (and the two boolean flags) as separate, individually-inspectable signals all the way through to the alert message text.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Raw-socket SYN scanning | A custom Scapy-based port prober | nmap (system binary) via python-nmap fork | nmap's SYN-scan implementation handles OS-specific timing, retransmission, and firewall-evasion edge cases that a hand-rolled Scapy scanner would get wrong for years; D-04 already locks this choice |
| CIDR-range "is this IP malicious" matching | A custom trie/radix-tree IP-range matcher from scratch | Python's stdlib `ipaddress` module's `ip_network`/`in` containment check | stdlib already does this correctly and efficiently for a few thousand entries; no need for a third-party IP-range library at this scale |
| "Is this a malicious IP" data | A scraped/freshly-written-by-hand list of bad IPs | A maintained, already-aggregated open list (FireHOL `firehol_level1.netset`) | Threat-intel curation is an ongoing-maintenance problem (false positives, stale entries, coverage gaps) that existing community-maintained lists already solve; hand-rolling this list is a maintenance trap |
| Daily-cadence scheduling | A custom cron-string parser | Either APScheduler's `CronTrigger`/`IntervalTrigger` OR (recommended here) a plain sleep-until-next-run loop | Both are well-trodden; don't write a third option (e.g. parsing crontab syntax by hand) |

**Key insight:** Almost nothing in this phase requires hand-rolling beyond what's already explicitly decided in CONTEXT.md (D-04's nmap choice, D-08's static-blocklist choice). The risk in this phase is package-identity confusion (the PyPI/fork split), not algorithmic complexity.

## Runtime State Inventory

> Not applicable — this is a greenfield feature phase (new tables, new routes, new capture-container threads), not a rename/refactor/migration phase. Skipped per the trigger condition in the execution flow.

## Common Pitfalls

### Pitfall 1: Installing the wrong `python-nmap`
**What goes wrong:** `pip install python-nmap` silently succeeds and imports as `import nmap` either way — there is no error to signal you got the unmaintained xael package instead of the home-assistant-libs fork, because both publish the same top-level module name.
**Why it happens:** The fork has no separate PyPI release; a developer skimming "add python-nmap" without re-reading CLAUDE.md will reach for the obvious `pip install python-nmap`.
**How to avoid:** The requirements.txt line must literally read `python-nmap @ git+https://github.com/home-assistant-libs/python-nmap@<pinned-sha>` — never the bare package name. Add a comment in `capture/requirements.txt` (mirroring the comment style in `backend/pyproject.toml`) explaining why.
**Warning signs:** `pip show python-nmap` reporting a `Home-page` of `xael.org` instead of a GitHub URL is the signal something went wrong.

### Pitfall 2: Daily re-scan target list drifting from "registered only"
**What goes wrong:** If the daily loop's device list is built from the same discovery/observation tables used for the unregistered-device-detection pipeline instead of the `devices` table, transient guest devices get scanned automatically — explicitly out of scope per D-01.
**Why it happens:** Both the discovery pipeline and the registry share overlapping MAC/IP data; it's easy to query the wrong source table.
**How to avoid:** The daily-rescan query must be `SELECT * FROM devices` (or the ORM equivalent) — never a query against `arp_event`/`dhcp_event`/`discovered_identity`.
**Warning signs:** Seeing scan results for devices that were never registered, or seeing the alerts feed reference `device_id=NULL` scan rows.

### Pitfall 3: Treating "never scanned" as a security status
**What goes wrong:** A naive implementation defaults `security_status` to `WARNING` for any device with no scan history yet, which makes every freshly-registered device look "at risk" before the user has even clicked Scan once.
**Why it happens:** It feels intuitively cautious ("unknown = be careful"), but D-06 explicitly overrides this intuition.
**How to avoid:** `Device.security_status` should default to `GOOD` at the database level (or the derivation function should special-case empty/null scan history to `GOOD`), and a separate `last_scanned_at` (nullable) timestamp communicates "not yet scanned" in the UI — never conflate the two concerns in one field.
**Warning signs:** Every newly-registered device shows a yellow/warning badge immediately after registration, before any scan has run.

### Pitfall 4: Blocklist file going stale silently
**What goes wrong:** The vendored `firehol_level1.netset` is a point-in-time snapshot; if it's never refreshed across app releases, malicious-IP detection coverage quietly degrades over the product's lifetime.
**Why it happens:** D-08 deliberately ships it as a build-time-bundled file (not a runtime fetch) to satisfy the no-telemetry constraint — there's no automatic "it's stale" signal.
**How to avoid:** Note the snapshot date in a comment/header at the top of the vendored file (the FireHOL file already includes its own `# Date: ...` header — preserve it verbatim) and add a backlog reminder to refresh it on a regular release cadence. Not a blocker for this phase, but worth a one-line note in PROJECT.md decisions so it isn't forgotten.
**Warning signs:** None automatic — this is a process discipline gap, not a runtime bug, but the planner should still note the snapshot date in the migration/seed task's commit message for future traceability.

### Pitfall 5: Bandwidth-anomaly threshold computed against too-short a baseline
**What goes wrong:** A device with little history (e.g. registered yesterday) has a rolling average computed from 1-2 data points, making the "N× average" threshold trivially easy to trip (or impossible to trip, depending on the exact math) — producing noisy or absent warning signals for new devices.
**Why it happens:** The naive `avg(bytes) over last N days` query doesn't guard against a near-empty window.
**How to avoid:** Require a minimum sample count (e.g. at least 7 distinct prior days of `bandwidth_metrics` rows) before evaluating the anomaly check for a given device; skip (don't flag, don't clear) the check entirely below that threshold. Tune the exact minimum during implementation/testing per CONTEXT.md's "Claude's Discretion" note on this threshold.
**Warning signs:** Newly-registered devices immediately flagged `warning` on their very first day of traffic, or never flaggable at all due to a divide-by-near-zero baseline.

## Code Examples

### nmap top-1000-port scan and result parsing
```python
# Source: synthesized from python-nmap usage conventions [CITED: GeeksforGeeks
# "Port scanner using python-nmap", README.rst patterns] — no -p flag means
# nmap's own default port set (top 1000) is used.
import nmap

scanner = nmap.PortScanner()
scanner.scan(hosts="192.168.1.42", arguments="-sS")  # SYN scan, default top-1000 ports

if "192.168.1.42" in scanner.all_hosts():
    tcp_ports = scanner["192.168.1.42"].get("tcp", {})
    open_ports = [port for port, info in tcp_ports.items() if info["state"] == "open"]
else:
    open_ports = []  # host did not respond — treat as scan failure, not "no open ports"
```

### Vendored blocklist load-once-at-startup pattern
```python
# Source: synthesized from FireHOL's published format [CITED:
# github.com/firehol/blocklist-ipsets/blob/master/firehol_level1.netset]
# combined with backend/src/services/bandwidth_source.py's Protocol-impl shape
# [VERIFIED: codebase].
_DEFAULT_SOURCE: ThreatIntelSource | None = None

def get_default_threat_intel_source() -> ThreatIntelSource:
    global _DEFAULT_SOURCE
    if _DEFAULT_SOURCE is None:
        _DEFAULT_SOURCE = StaticBlocklistSource()
    return _DEFAULT_SOURCE
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| Spamhaus DROP as plain TXT | Spamhaus DROP as JSON (TXT still available but deprecated path) | Ongoing migration noted in Spamhaus's own docs | Irrelevant to this phase's recommendation — vendoring FireHOL's pre-aggregated `.netset` sidesteps needing to parse Spamhaus's format directly at all |
| python-nmap (xael, PyPI) | python-nmap (home-assistant-libs fork, GitHub-only) | Fork created because original went unmaintained | Directly drives this phase's Package Legitimacy Audit finding — the PyPI name no longer points at the maintained codebase |

**Deprecated/outdated:**
- `xael/python-nmap` on PyPI (0.7.1): functionally works but unmaintained; CLAUDE.md and this research both confirm avoiding it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | Full per-`DeviceType` expected-ports allowlist contents (beyond D-05's named examples: ROUTER=22/53/80/443, IOT≈nothing) — this research's `EXPECTED_PORTS` table for TV/CONSOLE/PHONE/LAPTOP/DESKTOP/TABLET/OTHER | Pattern 2 (Code) | If allowlist is too permissive, real risk goes undetected as `good`/`warning` instead of being surfaced; if too strict, false `warning` badges erode user trust in the feature. Low blast radius — easily tunable post-launch since it's plain data, not a schema change |
| A2 | Daily rescan time chosen as 03:00 local container time in Pattern 5's example | Pattern 5 (Code) | Cosmetic only — if the box is asleep/restarting at that hour, scan simply runs at next wake; no correctness impact, just a scheduling preference Claude's Discretion already delegates |
| A3 | home-assistant-libs fork is still functionally compatible with current `nmap` binary/XML output format (not independently re-verified beyond confirming the repo exists and is GitHub-reachable) | Package Legitimacy Audit / Standard Stack | If the fork's XML parser has drifted from current nmap's output schema, scan-result parsing could silently return empty/malformed data — mitigated by the mandatory `checkpoint:human-verify` gate already required for this dependency |
| A4 | Linear-scan `ipaddress` containment check is fast enough for vendoring at household traffic-ingest scale (no benchmark run this session) | Pattern 4 (Code) | If wrong, ingest latency could degrade under high distinct-destination-IP volume; low risk given the existing 7s flush-interval batching already used by traffic ingest, and an easy follow-up optimization path exists without an interface change |

## Open Questions

1. **Should `port_scan_results` be a history table or latest-only?**
   - What we know: D-11/D-05's "Claude's Discretion" section explicitly defers this to the planner.
   - What's unclear: Whether a future phase (e.g. VIZ or a "scan history" UI affordance) would want to show trend-over-time scan results.
   - Recommendation: Build a small history table (`port_scan_results` with `id`, `device_id`, `scanned_at`, `open_ports` as a JSON/array column) rather than overwriting a single row — it's a trivial cost difference at this data volume (one row per device per day, plus occasional on-demand clicks) and avoids a painful future migration if history ever becomes a feature. The *derived* `security_status` still only reads the latest row, so D-06/D-07's "no opaque history-dependent scoring" intent is preserved.

2. **Exact bandwidth-anomaly threshold multiplier and rolling-window length (D-09's discretion item)**
   - What we know: D-09 specifies "N× its own rolling historical average," explicitly deferring N and the window to tuning during implementation/testing.
   - What's unclear: No real household traffic data exists yet to calibrate against.
   - Recommendation: Start with a 14-day rolling average window and a 3x threshold multiplier as defaults (common starting points for simple anomaly thresholds), expose both as named constants (not magic numbers) in `bandwidth_anomaly.py` so they're trivially tunable without a code-structure change, and explicitly note in the PLAN that these are provisional pending real-world observation.

3. **Where does the scan-trigger "pending request" queue live?**
   - What we know: The capture container can't accept inbound HTTP; the existing architecture is capture-POSTs-out-only. Some mechanism must let the browser's "Scan" button reach the capture container.
   - What's unclear: Whether a simple DB-backed `pending_scan_requests` row (polled by capture) or a lighter in-memory queue on the API process is preferable.
   - Recommendation: Use a tiny DB-backed table (`pending_scan_requests`: `device_id`, `requested_at`, `claimed_at`) — it survives an API restart mid-request (an in-memory queue would silently drop a pending scan if the API process restarts between button-click and capture's next poll), and it's a trivial table to add given Alembic migrations are already the established schema-change path in this codebase.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|----------|
| `nmap` system binary | Port scan execution (D-03/D-04) | ✗ (not installed on this dev/research machine) | — | Installed via `apt-get install nmap` inside the `capture/Dockerfile` build — not a host-machine dependency at all; only the built Docker image needs it. No fallback needed since this always runs containerized per PLAT-03 |
| Docker | Build/run the capture container with the new `nmap` apt package | ✓ | confirmed running on this machine | — |
| `python-nmap` (home-assistant-libs fork) | Wraps `nmap` for the capture container's scan code | N/A (installed at image-build time, not host) | pinned commit SHA, to be selected by planner/implementor | Fallback: shell out to `nmap -oX -` + `subprocess` + stdlib `xml.etree.ElementTree` directly if the fork proves unusable during the human-verify checkpoint |
| FireHOL `firehol_level1.netset` | `StaticBlocklistSource` default blocklist | ✓ (fetched and inspected this session) | snapshot dated 2026-06-20 in this research session, ~3,851 CIDR entries | If the file becomes unreachable at implementation time, any equivalently-licensed flat CIDR list (e.g. Spamhaus DROP converted to plain CIDR-per-line) is an acceptable substitute — interface (`ThreatIntelSource`) is unaffected either way |

**Missing dependencies with no fallback:** none — `nmap`/`python-nmap` are container-build-time concerns, not blocking on this research/planning machine.
**Missing dependencies with fallback:** `python-nmap` fork (subprocess+XML fallback if the git dependency proves unworkable at the human-verify checkpoint).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto), in-memory SQLite via `test_db`/`client` fixtures |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend && python -m pytest tests/test_security_<area>.py -x` |
| Full suite command | `cd backend && python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| SEC-01 | On-demand scan trigger + result ingest + unexpected-port flagging | integration | `pytest tests/test_security_scan.py -x` | ❌ Wave 0 |
| SEC-01 | `evaluate_open_ports()` risky/unexpected classification (pure function) | unit | `pytest tests/test_port_rules.py -x` | ❌ Wave 0 |
| SEC-02 | Unregistered device join writes `security_alerts` row (type=unknown_device) | integration | `pytest tests/test_security_alerts.py -x` | ❌ Wave 0 |
| SEC-03 | Malicious-IP match on traffic ingest writes alert + flips status to critical | integration | `pytest tests/test_threat_intel.py -x` | ❌ Wave 0 |
| SEC-03 | Bandwidth-spike anomaly check (warning-level) | unit + integration | `pytest tests/test_bandwidth_anomaly.py -x` | ❌ Wave 0 |
| SEC-04 | `derive_status()` good/warning/critical table-driven logic (pure function) | unit | `pytest tests/test_security_status.py -x` | ❌ Wave 0 |
| SEC-04 | `/api/devices` response includes `security_status` field | integration | `pytest tests/test_devices.py -x` (extend existing file) | ✅ existing file, new test cases |
| (capture-side) | Trust-boundary rejection on `/api/capture/scan` for non-loopback callers | integration | `pytest tests/test_capture.py -x` (extend existing file, reuse `ASGITransport(client=...)` technique) | ✅ existing file, new test cases |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_<new_file>.py -x`
- **Per wave merge:** `cd backend && python -m pytest`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_port_rules.py` — covers SEC-01 (pure-function table-driven port classification, no DB fixture needed, follows `test_domain_grouping.py`'s fixture-free style)
- [ ] `backend/tests/test_security_status.py` — covers SEC-04 (pure-function status derivation, no DB fixture needed)
- [ ] `backend/tests/test_security_scan.py` — covers SEC-01 end-to-end ingest, reuses `client`/`test_db` fixtures from `conftest.py`
- [ ] `backend/tests/test_security_alerts.py` — covers SEC-02 (extend `test_discovery.py`'s unknown-device-join test path to also assert a `security_alerts` row is written)
- [ ] `backend/tests/test_threat_intel.py` — covers SEC-03 malicious-IP path, needs a small fixture blocklist (not the full vendored file) for deterministic test IPs
- [ ] `backend/tests/test_bandwidth_anomaly.py` — covers SEC-03 anomaly path, reuses `seeded_traffic_db`-style fixture pattern from `conftest.py`
- [ ] No new framework/config install needed — existing pytest + SQLite-fixture infrastructure fully covers all phase requirements structurally; only new test *files* are needed, matching every prior phase's pattern

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|---------------------|
| V2 Authentication | no (new) | Existing dashboard password auth (`Depends(require_auth)`) already gates all new GET routes (`/api/security/alerts`, scan-trigger endpoint) — no new auth surface |
| V3 Session Management | no (new) | Same existing session-cookie mechanism, unchanged |
| V4 Access Control | yes | The new `/api/capture/scan` ingest route MUST reuse the existing `_TRUSTED_HOSTS` loopback/gateway-only check from `backend/src/routes/capture.py` — do not introduce a second trust-boundary implementation |
| V5 Input Validation | yes | Pydantic payload models for the scan-result ingest route (mirroring `TrafficFlowPayload`/`ArpEventPayload` shape); `open_ports` list bounded to a sane max length (e.g. 1000, matching nmap's own top-1000 scope) to prevent a malformed/compromised capture payload from writing unbounded rows |
| V6 Cryptography | no | No new cryptographic operation introduced in this phase |
| V7 Error Handling / Logging | yes | Scan failures (host unreachable, nmap binary error) must not crash the capture loop — same `try/except Exception: print` swallow-and-continue convention already used for every other capture POST path |
| V11 Business Logic | yes | The "active scan only targets registered devices, on-demand or daily" boundary (D-01/MODE-02's "registered devices only" ethical/legal scoping) is a business-logic control, not just a UX nicety — port scanning unregistered third-party devices on a network without consent is the kind of action this constraint exists to prevent. The daily-loop's `SELECT * FROM devices` (never raw observation tables) enforces this technically |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|------------------------|
| Forged scan-result POST from a non-capture source (route spoofing) | Tampering / Spoofing | Existing loopback/gateway-trust check (`_TRUSTED_HOSTS`) — capture's results are only trusted from the Docker bridge gateway or loopback, never a LAN-routable address |
| Oversized/malformed `open_ports` payload (resource exhaustion via a compromised/buggy capture process) | Denial of Service | Bound the payload list length server-side (mirrors the existing `_MAX_FLOWS_PER_ROLLUP = 5000` precedent in `capture.py` for traffic rollups) |
| Vendored blocklist file tampering (image supply-chain) | Tampering | File is bundled at Docker build time from the backend repo (not fetched at runtime), so its provenance is whatever the backend image's build process already guarantees — no new runtime-fetch attack surface introduced (this is exactly what D-08's "zero external calls" constraint is protecting against) |
| Scanning a device outside the household's own network (legal/ethical exposure) | (business-logic, not strictly STRIDE) | Scans are always targeted at a specific `device_id`'s known IP from the local `devices` registry — never a user-supplied arbitrary target — eliminating the "scan any host" SSRF-adjacent risk entirely by construction |

## Sources

### Primary (HIGH confidence)
- `backend/src/services/bandwidth_source.py` (read in full) — `BandwidthSource` Protocol pattern directly templated for `ThreatIntelSource`
- `backend/src/routes/capture.py` (read in full) — loopback/gateway trust-boundary pattern for the new scan-ingest route
- `backend/src/models/device.py` (read in full) — `DeviceType` enum, confirms exact 9 enum values the port-rule allowlist must key off
- `capture/capture.py`, `capture/Dockerfile`, `capture/requirements.txt` (read in full) — existing thread/SIGTERM convention, Dockerfile apt-get pattern, pinned-dependency convention
- `backend/tests/conftest.py` (read in full) — fixture conventions for new test files
- PyPI JSON API (`pypi.org/pypi/python-nmap/json`, `pypi.org/pypi/APScheduler/json`) — fetched directly this session, confirms version numbers and source URLs

### Secondary (MEDIUM confidence)
- [home-assistant-libs/python-nmap GitHub repo](https://github.com/home-assistant-libs/python-nmap) — fork existence and GitHub-only distribution confirmed via WebFetch
- [FireHOL blocklist-ipsets firehol_level1.netset](https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level1.netset) — format and composition confirmed via WebFetch, fetched 2026-06-20
- [APScheduler PyPI / agronholm/apscheduler](https://pypi.org/project/APScheduler/) — version and source repo confirmed via PyPI JSON

### Tertiary (LOW confidence)
- WebSearch results on python-nmap usage examples (`-sS`, top-1000-ports default behavior) — consistent across multiple Medium/GeeksforGeeks articles but not independently verified against the home-assistant-libs fork's actual README; `[ASSUMED]` that the fork's API surface matches the long-standing python-nmap convention since it's a fork, not a rewrite
- WebSearch results on Spamhaus DROP JSON format — not directly used in the final recommendation (FireHOL chosen instead) but informs the Alternatives Considered table

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM — nmap/python-nmap choice is locked by CONTEXT.md/CLAUDE.md, but the fork's exact installability and API compatibility could not be fully verified (no PyPI release to inspect; GitHub README usage examples not independently confirmed for this specific fork)
- Architecture: HIGH — every pattern (trust boundary, Protocol-based swappable source, derived/cached status, table-driven rules) is either a direct extension of an existing, read-in-full codebase pattern or an explicit decision already locked in CONTEXT.md
- Pitfalls: MEDIUM-HIGH — package-identity and "registered-only" scoping pitfalls are high-confidence (directly observed/verified); bandwidth-anomaly threshold pitfall is reasoned from first principles, not observed in production data

**Research date:** 2026-06-20
**Valid until:** 30 days (stable domain — port-scanning/threat-intel patterns and the locked CONTEXT.md decisions are not fast-moving; re-verify python-nmap fork reachability if planning is delayed significantly past this window)
