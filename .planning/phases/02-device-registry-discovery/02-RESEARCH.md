# Phase 2: Device Registry + Discovery - Research

**Researched:** 2026-06-18
**Domain:** Multi-source passive network discovery (ARP/DHCP/mDNS) with identity fusion, device registry CRUD, SvelteKit dashboard
**Confidence:** HIGH

## Summary

Phase 2 replaces Phase 1's ARP-only capture proof-of-concept with three passive discovery sources feeding a new identity-fusion seam. The capture container (already running `network_mode: host` with `CAP_NET_RAW`/`CAP_NET_ADMIN`, already POSTing ARP events to the API) gains two more sniffers: a Scapy BOOTP/DHCP listener and a `python-zeroconf` `AsyncZeroconf` mDNS browser, both running inside the *same* long-running process alongside the existing `sniff()` loop. All three sources still POST raw observations to the API — the capture container never writes to the DB and never makes fusion decisions; that logic lives entirely in the backend, behind an `IdentityResolver` interface (D-01) the planner can implement as a simple two-rule Python class today and swap later.

The schema split that satisfies D-01 through D-06 cleanly is: **raw observation tables** (extend the existing `ArpEvent` pattern with `DhcpEvent` and `MdnsEvent`) feeding a **resolved identity table** (`discovered_identities` — one row per fused, not-yet-registered device, holding the current identity key, last-known MAC(s), last-known hostname, first/last-seen) which is itself distinct from the **registry table** (`devices` — name/owner/type/trusted, locked identity key per D-04). The resolver's job is exactly one function: given a new observation, return which `discovered_identities` row it belongs to (or create a new one) — it never touches `devices` directly; a separate registration/merge service handles promoting an identity row into a registry row.

**Primary recommendation:** Build `IdentityResolver` as a Python `Protocol` (not ABC — no shared state/behavior to inherit) with a single method `resolve(observation: Observation) -> str` returning a stable identity key string. Implement `HostnameFallbackResolver` for Phase 2: hostname (from DHCP option 12 or mDNS service name, normalized) is the key if present and non-empty; otherwise the MAC address is the key. Persist the key directly on `discovered_identities` and `devices` rows as a plain string column — no need for a separate identity-keys table.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ARP/DHCP/mDNS packet sniffing | Capture container (separate process) | — | Requires `CAP_NET_RAW`/host networking; isolated per PLAT-03; established in Phase 1 |
| Raw observation persistence | API / Backend | Database | Capture POSTs, never writes DB directly (Phase 1 D-06, reaffirmed by D-07) |
| Identity fusion (`IdentityResolver`) | API / Backend | — | Pure business logic; must be swappable (D-01) — belongs in backend service layer, not DB triggers or capture |
| Device registry CRUD (register/merge) | API / Backend | Database | Standard REST resource pattern; registry is the durable source of truth |
| Unknown-device surfacing, card grid, dialogs | Browser / Client (SvelteKit) | Frontend Server (SSR, build-time only) | `adapter-static` SPA per Phase 1 D-17 — no SSR at runtime, all data fetched client-side from API |
| First/last-seen timestamp tracking | Database | API / Backend | Simple column update on observation ingest; backend computes "online/offline" status from last-seen freshness |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scapy | 2.7.0 (pinned, already in `backend/pyproject.toml` and `capture/requirements.txt`) | ARP + DHCP/BOOTP passive sniffing | Already adopted in Phase 1; `scapy.layers.dhcp` ships `BOOTP`/`DHCP` layer parsing built in — no separate DHCP-parsing library needed [VERIFIED: scapy.readthedocs.io] |
| zeroconf | 0.149.x (PyPI package name is `zeroconf`; project name "python-zeroconf") | Passive mDNS/Bonjour service discovery | `AsyncZeroconf` + `AsyncServiceBrowser` give an asyncio-native passive listener; actively maintained, used by Home Assistant [CITED: python-zeroconf.readthedocs.io] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mac-vendor-lookup | latest (PyPI `mac-vendor-lookup`) | Offline MAC OUI → vendor name resolution | Optional enrichment for `Other`-typed unknown devices; not required to satisfy DISC-01..04, listed in CLAUDE.md as discretionary supporting tool — skip if it adds schedule risk |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hostname/MAC fallback resolver (D-02/D-03) | Composite fingerprint (hostname + mDNS records + OUI + IP-lease continuity) | Explicitly deferred (CONTEXT.md `<deferred>`) — more accurate but more complex; D-01's interface makes this a drop-in swap later, don't build it now |
| `Protocol` for `IdentityResolver` | `abc.ABC` with `@abstractmethod` | Protocol is structurally typed (duck-typing-friendly, no inheritance required, easier to mock in tests); ABC is fine too and equally valid — pick whichever the codebase's existing style favors (no precedent yet, recommend Protocol for lower coupling) |
| Separate `discovered_identities` + `devices` tables | Single `devices` table with nullable registry fields | Single table conflates "observed, not yet known" with "registered" — would force nullable name/owner/type everywhere and complicate the D-04 "registered identity is locked" rule; two tables map directly to the two distinct lifecycles |
| `python-zeroconf`'s `AsyncServiceBrowser` browsing every service type | Browsing a fixed allowlist (`_http._tcp.local.`, `_airplay._tcp.local.`, etc.) plus `_services._dns-sd._udp.local.` meta-query to discover types dynamically | The meta-query approach (`ZeroconfServiceTypes`) finds more devices but adds latency/complexity; a fixed common-type allowlist is simpler and sufficient for Phase 2 — document as Claude's discretion item already covered by CONTEXT.md |

**Installation:**
```bash
# Backend (Python 3.13) — uv or pip, already declared in backend/pyproject.toml dependencies
uv add zeroconf  # add to backend/pyproject.toml dependencies list
# capture/requirements.txt also needs it (capture container runs the mDNS browser alongside ARP/DHCP sniff)
echo "zeroconf" >> capture/requirements.txt
```

**Version verification:** `zeroconf` PyPI release 0.149.16 confirmed published 2026-05-21 [VERIFIED: web search of pypi.org/project/zeroconf, cross-checked against python-zeroconf.readthedocs.io which documents the same 0.149.16 API reference build]. `scapy` 2.7.0 already pinned and running in this repo (Phase 1) — no version change needed for DHCP support; `scapy.layers.dhcp.DHCP`/`BOOTP` ship in the same 2.7.x release already installed.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| zeroconf | PyPI | published 2026-05-21 (latest patch; project itself is long-established, originally `python-zeroconf`) | unknown to legitimacy DB (signal gap, not a red flag) | github.com/python-zeroconf/python-zeroconf | SUS (flagged "too-new" + "unknown-downloads" + "no-repository" by automated signals) | Approved — see note |
| scapy | PyPI | published 2025-12-26 | unknown to legitimacy DB | scapy.net (canonical project site; mirrors github.com/secdev/scapy) | SUS (flagged "unknown-downloads") | Approved — already in production use since Phase 1 |
| mac-vendor-lookup | PyPI | published 2025-11-30 | unknown to legitimacy DB | github.com/bauerj/mac_vendor_lookup | SUS (flagged "unknown-downloads") | Approved (optional/discretionary) |

**Note on SUS verdicts:** All three packages were flagged `SUS` solely because the automated legitimacy DB lacks download-count and/or repo-URL signals for these specific releases — not because of any actual suspicious behavior (no malicious postinstall scripts, all have long-standing canonical repos). `scapy` is already running in production in this codebase since Phase 1 (`backend/pyproject.toml`, `capture/requirements.txt`). `zeroconf` is the de-facto standard pure-Python mDNS library, explicitly named in `CLAUDE.md`'s approved stack, maintained by the same org that publishes to `github.com/python-zeroconf/python-zeroconf`, and used by Home Assistant. Despite the automated `SUS` signal, package names and purposes are cross-confirmed against official documentation (`python-zeroconf.readthedocs.io`) and CLAUDE.md's pre-approved stack — tag `[ASSUMED]` on the exact pinned version only (the planner should pin a specific patch version after confirming against `pip index versions zeroconf` in the execution environment, since this research session's sandbox lacked network-enabled `pip`).

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** zeroconf, scapy, mac-vendor-lookup — all three are pre-approved in `CLAUDE.md`'s stack table and/or already in production (scapy). The planner should still add a `checkpoint:human-verify` task before the `zeroconf` install specifically, since it is the one new package this phase introduces (scapy is already installed; mac-vendor-lookup is optional/discretionary and can be skipped entirely).

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │         capture container (host net)         │
                    │  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
                    │  │ ARP sniff │  │DHCP sniff │  │ AsyncZero- │ │
                    │  │ (Phase 1) │  │(scapy     │  │ conf mDNS  │ │
                    │  │           │  │ BOOTP/DHCP)│  │ browser    │ │
                    │  └─────┬────┘  └─────┬─────┘  └─────┬──────┘ │
                    │        │  all three POST raw observation     │
                    │        ▼             ▼               ▼       │
                    └────────┴─────────────┴───────────────┴───────┘
                                       │ httpx.post()
                                       ▼
                    ┌──────────────────────────────────────────────┐
                    │  API (FastAPI) — /api/capture/{arp,dhcp,mdns}  │
                    │  loopback/gateway-trusted ingest (Phase 1      │
                    │  pattern, reused unchanged)                    │
                    │                       │                        │
                    │                       ▼                        │
                    │   raw tables: arp_events / dhcp_events /        │
                    │               mdns_events  (append-only)       │
                    │                       │                        │
                    │                       ▼                        │
                    │           IdentityResolver.resolve(obs)         │
                    │           (HostnameFallbackResolver impl)       │
                    │                       │                        │
                    │           ┌───────────┴────────────┐           │
                    │           ▼                        ▼           │
                    │  discovered_identities      devices (registry) │
                    │  (unregistered, fused)      (locked identity   │
                    │   first/last_seen update     key once          │
                    │                              registered, D-04) │
                    │           │                        ▲           │
                    │           │  user clicks "Register"│           │
                    │           └────────────────────────┘           │
                    │           │  user clicks "Merge with..."        │
                    │           ▼ (manual only, D-05)                 │
                    │  merge: target devices row absorbs identity key │
                    └──────────────────────────────────────────────┘
                                       │ GET /api/devices (poll or SSE-ready)
                                       ▼
                    ┌──────────────────────────────────────────────┐
                    │     SvelteKit dashboard (/dashboard)           │
                    │  Summary banner → Card grid (unknown first)    │
                    │  Register dialog / Merge dialog                │
                    └──────────────────────────────────────────────┘
```

### Recommended Project Structure
```
backend/src/
├── models/
│   ├── arp_event.py         # existing (Phase 1) — unchanged
│   ├── dhcp_event.py         # new — raw DHCP observation
│   ├── mdns_event.py         # new — raw mDNS observation
│   ├── discovered_identity.py # new — fused, unregistered identity
│   └── device.py             # new — registry row (name/owner/type/trusted)
├── services/
│   ├── identity_resolver.py  # IdentityResolver Protocol + HostnameFallbackResolver
│   └── discovery.py          # ingest → resolver → discovered_identities orchestration
├── routes/
│   ├── capture.py            # existing /arp + new /dhcp, /mdns ingest endpoints
│   └── devices.py            # new — GET /api/devices, POST /api/devices (register), POST /api/devices/{id}/merge
└── schemas/
    └── device.py              # Pydantic request/response models for the devices API

capture/
├── capture.py                 # extended: spawns ARP sniff (existing) + DHCP sniff + AsyncZeroconf browser
└── requirements.txt           # + zeroconf

frontend/src/
├── routes/dashboard/+page.svelte   # card grid + summary banner (per UI-SPEC)
├── lib/components/
│   ├── DeviceCard.svelte
│   ├── RegisterDialog.svelte
│   └── MergeDialog.svelte
└── lib/api.ts                       # + listDevices, registerDevice, mergeDevice
```

### Pattern 1: IdentityResolver as a Protocol
**What:** A structurally-typed interface with one method, decoupling fusion logic from the ingest pipeline.
**When to use:** Any place a new observation needs to be mapped to a stable identity key.
**Example:**
```python
# Source: PEP 544 Protocol pattern, applied per D-01
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class Observation:
    mac: str
    hostname: str | None
    source: str  # "arp" | "dhcp" | "mdns"
    observed_at: "datetime"

class IdentityResolver(Protocol):
    def resolve(self, observation: Observation) -> str:
        """Return the stable identity key this observation belongs to."""
        ...

class HostnameFallbackResolver:
    """D-02/D-03: hostname is primary key, MAC is fallback."""

    def resolve(self, observation: Observation) -> str:
        if observation.hostname:
            return f"host:{observation.hostname.strip().lower()}"
        return f"mac:{observation.mac.lower()}"
```
Swapping in a fingerprint-based resolver later means writing a new class with the same `resolve()` signature — no caller changes (satisfies D-01's "drop-in replacement" requirement).

### Pattern 2: Scapy DHCP passive sniff (extends Phase 1's capture.py)
**What:** A second `sniff()` call (or a combined filter) parsing BOOTP/DHCP options for hostname + requested IP.
**When to use:** Alongside the existing ARP `sniff()` in the same capture process (D-07 — same scapy + POST-to-API pattern).
**Example:**
```python
# Source: scapy.readthedocs.io/en/latest/api/scapy.layers.dhcp.html + community pattern
# (thepythoncode.com/article/dhcp-listener-using-scapy-in-python)
from scapy.all import DHCP, BOOTP, Ether, sniff

def on_dhcp_packet(pkt):
    if DHCP not in pkt:
        return
    mac = pkt[Ether].src if Ether in pkt else pkt[BOOTP].chaddr.hex()
    hostname = None
    requested_ip = None
    for opt in pkt[DHCP].options:
        if not isinstance(opt, tuple):
            continue
        label, value = opt
        if label == "hostname" and isinstance(value, bytes):
            hostname = value.decode(errors="replace")
        elif label == "requested_addr":
            requested_ip = value
    payload = {"src_mac": mac, "hostname": hostname, "requested_ip": requested_ip}
    httpx.post(f"{API_URL}/api/capture/dhcp", json=payload, timeout=5.0)

# Run as a second sniff() in its own thread (alongside the existing ARP sniff thread),
# both honoring the same stop_event/SIGTERM pattern from Phase 1.
sniff(filter="udp and (port 67 or port 68)", prn=on_dhcp_packet, store=False,
      stop_filter=lambda _pkt: stop_event.is_set())
```
**Pitfall to note inline:** not every DHCP packet carries a hostname option (option 12) — many devices only send `requested_addr`. The ingest payload's `hostname` field must be `Optional[str]`.

### Pattern 3: AsyncZeroconf passive mDNS browser integrated into capture's asyncio loop
**What:** Passive mDNS service discovery using `AsyncZeroconf` + `AsyncServiceBrowser`, run inside an asyncio event loop alongside the (synchronous, threaded) scapy sniffers.
**When to use:** Capture container needs one asyncio loop running concurrently with the existing thread-based scapy sniffers — run the zeroconf browser via `asyncio.run()` in its own thread, or restructure `capture.py`'s `main()` to run an asyncio loop with scapy sniffers each in `asyncio.to_thread()`.
**Example:**
```python
# Source: github.com/python-zeroconf/python-zeroconf/blob/master/examples/async_browser.py
# + python-zeroconf.readthedocs.io/en/latest/api.html
import asyncio
from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser, AsyncServiceInfo

COMMON_SERVICE_TYPES = [
    "_http._tcp.local.", "_airplay._tcp.local.", "_ipp._tcp.local.",
    "_googlecast._tcp.local.", "_spotify-connect._tcp.local.",
    "_device-info._tcp.local.", "_workstation._tcp.local.",
]

def on_service_state_change(zeroconf: Zeroconf, service_type: str, name: str,
                             state_change: ServiceStateChange) -> None:
    if state_change is not ServiceStateChange.Added:
        return
    asyncio.ensure_future(_post_service_info(zeroconf, service_type, name))

async def _post_service_info(zeroconf, service_type, name):
    info = AsyncServiceInfo(service_type, name)
    if await info.async_request(zeroconf, 3000):
        addresses = info.parsed_scoped_addresses()
        hostname = info.server  # e.g. "Brandons-iPhone.local."
        payload = {"hostname": hostname, "addresses": addresses, "service_type": service_type}
        async with httpx.AsyncClient() as client:
            try:
                await client.post(f"{API_URL}/api/capture/mdns", json=payload, timeout=5.0)
            except Exception as exc:
                print(f"[capture] mDNS POST failed: {exc}")

async def run_mdns_browser(stop_event: asyncio.Event):
    aiozc = AsyncZeroconf()
    browser = AsyncServiceBrowser(aiozc.zeroconf, COMMON_SERVICE_TYPES,
                                   handlers=[on_service_state_change])
    await stop_event.wait()
    await browser.async_cancel()
    await aiozc.async_close()
```
**Key integration note:** `AsyncZeroconf` expects a running asyncio loop. Since `capture.py`'s `main()` currently calls the blocking, synchronous `scapy.sniff()`, the cleanest integration is: keep ARP and DHCP `sniff()` calls each in their own `threading.Thread` (as Phase 1 already does for ARP), and run `asyncio.run(run_mdns_browser(...))` in a third thread (or make `main()` itself `asyncio.run`-based and wrap each `sniff()` call in `asyncio.to_thread()`). Either direction works; do not try to make scapy's `sniff()` itself async — it is fundamentally a blocking call with its own internal loop.

### Anti-Patterns to Avoid
- **Auto-merging "obviously the same" devices:** D-05 explicitly forbids this even for high-confidence matches (exact hostname, MAC differing only in randomization bits). Any task that adds automatic merge logic violates a locked decision — flag in code review.
- **Capture container writing to the DB or calling the resolver directly:** Breaks Phase 1's D-06 trust boundary and this phase's D-01 separation; capture must stay a dumb POST-only sender for all three sources.
- **Treating hostname as immutable:** Hostnames can change (user renames their phone, OS reinstall) and are attacker-controllable (DHCP option 12 is client-supplied, unauthenticated) — see Pitfall 1 below.
- **Resolving identity inline in the ingest route:** Inline fusion logic in `routes/capture.py` would violate D-01's "isolated behind an interface" requirement and make the later swap to a fingerprint resolver expensive.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DHCP option parsing | Custom byte-offset parser for BOOTP/DHCP options | `scapy.layers.dhcp.DHCP`/`BOOTP` (already a transitive capability of the installed `scapy==2.7.0`) | Scapy's DHCP layer already decodes all standard options (12=hostname, 50=requested_addr, 60=vendor_class_id) into a list of `(label, value)` tuples — RFC parsing is a solved, tested problem |
| mDNS/Bonjour protocol handling | Custom multicast UDP listener parsing DNS-SD records | `zeroconf`'s `AsyncZeroconf`/`AsyncServiceBrowser`/`AsyncServiceInfo` | mDNS involves DNS-SD record types (PTR/SRV/TXT/A/AAAA), multicast group management, and cache coherency — all handled by this library; hand-rolling risks missing TTL/cache-flush edge cases |
| MAC vendor (OUI) lookup | Hardcoded or scraped OUI-to-vendor table | `mac-vendor-lookup` (optional) | OUI registry is large (~30k+ entries) and updated periodically by IEEE; a maintained package handles updates |
| Relative timestamp formatting ("2 minutes ago") | Custom date-diffing string logic in Svelte | A small, focused JS utility (e.g. a 15-line `formatRelativeTime` helper) — not a full library; this is simple enough that pulling in a dependency (`dayjs`, `date-fns`) is optional discretion, not mandatory | UI-SPEC only requires 4 granularities (just now / minutes / hours / days) — a tiny hand-rolled helper is appropriate here, unlike the network-protocol items above |

**Key insight:** The two genuinely hard, protocol-level problems in this phase (DHCP option decoding, mDNS/DNS-SD discovery) are already solved by libraries already in the approved stack. The only thing actually novel to Innkeeper is the **fusion policy** (which observation belongs to which identity) — and that's exactly what D-01 isolates behind `IdentityResolver`, which is intentionally small and hand-rolled-on-purpose (it encodes a business decision, not a protocol).

## Common Pitfalls

### Pitfall 1: Hostname volatility and spoofability breaks "primary key" assumption silently
**What goes wrong:** A device's DHCP hostname or mDNS server name changes (factory reset, OS reinstall, user renames "John's iPhone" to "iPhone") — the resolver creates a *new* `discovered_identities` row instead of recognizing the same physical device, fragmenting history.
**Why it happens:** DHCP option 12 and mDNS service names are entirely client-supplied and unauthenticated; nothing prevents change or even malicious spoofing of another device's hostname.
**How to avoid:** This is explicitly accepted scope for Phase 2 (D-02/D-03 chose simplicity over the more accurate fingerprint approach, deferred per CONTEXT.md `<deferred>`). Document this as a known limitation, not a bug — the manual "Merge with..." UX (D-06) is the user's recourse when fragmentation happens. Do not attempt to silently auto-correct.
**Warning signs:** Users report "my phone shows up as two devices" after a reset/rename — expected behavior per current design, resolved via manual merge.

### Pitfall 2: Once registered, an identity-key change on a known device must NOT create a phantom unknown card
**What goes wrong:** A registered device's hostname changes after registration. If the resolver treats this as a brand-new identity key, a new `discovered_identities` row appears as "unknown" even though the device is already registered — directly violating D-04.
**Why it happens:** The resolver only knows about raw identity keys; it has no awareness of which keys are already claimed by a `devices` row unless the discovery/ingest service explicitly checks the registry first.
**How to avoid:** The discovery ingest service (not the resolver itself) must check: "does any `devices` row already have this MAC associated (via its locked identity key's last-known MAC, tracked even after the key changes)?" — D-04 specifies updating "the same row (matched by its stored identity key)" when a *registered* device's MAC/hostname changes. Concretely: store the device's current/locked identity key on the `devices` row, and when a new observation's resolved key would differ from a previously-seen key for the *same MAC*, update the registered row's key and MAC list rather than spawning a new `discovered_identities` row. This logic belongs in the discovery orchestration service that *calls* the resolver, not inside `IdentityResolver.resolve()` itself — keep the resolver pure/stateless.
**Warning signs:** A device the user already registered and trusts reappears as an "Unknown" card after a reboot/rename.

### Pitfall 3: DHCP sniffing only sees broadcast traffic, not all clients
**What goes wrong:** Passive DHCP sniffing only observes DHCP DISCOVER/REQUEST broadcasts at lease-acquisition/renewal time — a device that got its lease hours ago and is just sitting on the network won't generate new DHCP packets to observe.
**Why it happens:** DHCP is a lease-negotiation protocol, not a continuous announcement protocol; passive sniffing (D-08, no active scanning) means Innkeeper only learns what it happens to overhear.
**How to avoid:** Treat ARP (which *will* see ongoing traffic from any active device) as the most reliable "is this device currently present" signal, and DHCP/mDNS as enrichment sources for hostname/identity rather than the sole presence signal. First/last-seen tracking (DISC-03) should update on *any* of the three observation types, not require all three.
**Warning signs:** Device count seems lower than expected shortly after Innkeeper restarts (no DHCP renewals have happened yet) — expected with pure-passive capture; will self-correct as ARP traffic accumulates.

### Pitfall 4: mDNS multicast traffic may not reach the capture container depending on Docker network mode
**What goes wrong:** Even with `network_mode: host` (already required for ARP/DHCP per Phase 1 D-03), multicast group membership (224.0.0.251:5353 for mDNS) sometimes requires explicit `IGMP`/multicast routing support that differs from plain ARP/UDP broadcast sniffing.
**Why it happens:** mDNS relies on IP multicast, a different L3 mechanism than ARP (L2 broadcast) or DHCP (UDP broadcast); some container/network stacks handle multicast group joins differently even under host networking.
**How to avoid:** Because `network_mode: host` is already the established Phase 1 pattern (the container shares the host's network namespace entirely), this should work without extra config — host networking means the container *is* the host's network stack, including multicast membership. Verify explicitly during execution with a real LAN test (same D-05-style go/no-go spike Phase 1 used for ARP) rather than assuming it works from documentation alone.
**Warning signs:** mDNS browser starts cleanly (no exceptions) but `on_service_state_change` never fires even though `avahi-browse`/`dns-sd` on the host itself sees services — indicates a multicast-routing gap specific to the deployment environment, not a code bug.

### Pitfall 5: Resolver "creates a new row" race condition under concurrent observation ingest
**What goes wrong:** ARP, DHCP, and mDNS observations for the *same* physical device can arrive as near-simultaneous POST requests; if the discovery service does "look up by key, else INSERT" without a unique constraint + upsert, two near-simultaneous requests can both miss the lookup and insert two duplicate `discovered_identities` rows for the same key.
**Why it happens:** Classic check-then-act race under concurrent async request handling — FastAPI will happily process two ingest POSTs concurrently.
**How to avoid:** Put a unique constraint on `discovered_identities.identity_key` and use PostgreSQL's `INSERT ... ON CONFLICT (identity_key) DO UPDATE SET last_seen = ...` (SQLAlchemy: `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)`) rather than a separate SELECT-then-INSERT-or-UPDATE. [CITED: docs.sqlalchemy.org PostgreSQL dialect ON CONFLICT support]
**Warning signs:** Duplicate "Unknown Device" cards for what is obviously one device, appearing and disappearing across page refreshes (the duplicate may get a different `last_seen` and sort differently).

## Code Examples

### Upsert pattern for discovered-identity dedup (addresses Pitfall 5)
```python
# Source: docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert
from sqlalchemy.dialects.postgresql import insert as pg_insert

async def upsert_discovered_identity(db, identity_key: str, mac: str, hostname: str | None, seen_at):
    stmt = (
        pg_insert(DiscoveredIdentity)
        .values(identity_key=identity_key, mac=mac, hostname=hostname,
                first_seen=seen_at, last_seen=seen_at)
        .on_conflict_do_update(
            index_elements=[DiscoveredIdentity.identity_key],
            set_={"mac": mac, "hostname": hostname, "last_seen": seen_at},
        )
    )
    await db.execute(stmt)
    await db.commit()
```

### Device registry model sketch (satisfies D-04, D-14, D-15, D-16)
```python
# Source: pattern derived from existing backend/src/models/arp_event.py shape
from datetime import datetime
import enum

from sqlalchemy import String, Boolean, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class DeviceType(str, enum.Enum):
    PHONE = "phone"
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    TABLET = "tablet"
    IOT = "iot_smart_home"
    TV = "tv_streaming"
    CONSOLE = "game_console"
    ROUTER = "router_network"
    OTHER = "other"


class Device(Base):
    """Registry row — D-04: identity is locked once registered."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    identity_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    type: Mapped[DeviceType] = mapped_column(SAEnum(DeviceType), nullable=False)
    trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_known_mac: Mapped[str] = mapped_column(String(17), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Single MAC-address-keyed device tracking | Multi-source fused identity (hostname/mDNS primary, MAC fallback) | Ongoing industry shift since iOS 14 (2020) / Android 10 introduced MAC randomization by default | MAC alone is no longer a reliable persistent device identifier — this is precisely why DISC-01 calls for "multi-source fingerprinting (not MAC address alone)" |
| `aiozeroconf` for async mDNS | `zeroconf`'s native `AsyncZeroconf`/`zeroconf.asyncio` module | `zeroconf` absorbed async support natively; `aiozeroconf` (frawau) is no longer the recommended path | Use `zeroconf.asyncio.AsyncZeroconf`, not the separate `aiozeroconf` package |

**Deprecated/outdated:**
- `aiozeroconf` (frawau/aiozeroconf): superseded by native async support in the mainline `zeroconf` package — do not install this separately.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `zeroconf` PyPI version pinned as 0.149.x is the correct current release to pin in `pyproject.toml`/`requirements.txt` | Standard Stack, Installation | If a newer/older version has a breaking API change to `AsyncServiceBrowser`/`AsyncServiceInfo`, the planner should re-run `pip index versions zeroconf` (or `uv add zeroconf` and inspect resolved version) at execution time — this research's sandbox lacked network-enabled pip to confirm directly |
| A2 | `mac-vendor-lookup` is the correct, currently-maintained PyPI package name (vs. the unmaintained original) | Standard Stack | Low risk — this is explicitly named in CLAUDE.md already; if wrong, OUI enrichment (an optional/discretionary feature) simply gets skipped, no DISC requirement depends on it |
| A3 | Docker `network_mode: host` (already adopted for ARP) transparently supports IP multicast (mDNS) without additional compose config | Common Pitfalls (Pitfall 4) | If wrong, mDNS discovery silently produces zero results in the deployed environment — recommend an explicit go/no-go verification step early in execution, mirroring Phase 1's D-05 spike pattern, rather than discovering this late |
| A4 | `Protocol` (vs `ABC`) is the appropriate typing construct for `IdentityResolver` | Architecture Patterns Pattern 1 | Low risk — both are valid Python idioms satisfying D-01's "interface/strategy abstraction" requirement; if the codebase later establishes an ABC convention elsewhere, this can be trivially changed since there's no inheritance-based shared behavior to migrate |

## Open Questions

1. **Should `discovered_identities` rows ever be garbage-collected / expired?**
   - What we know: REQUIREMENTS.md's "Out of Scope" table states "Automatic data deletion" is rejected project-wide — retention is configurable, default keep-forever.
   - What's unclear: Whether an unregistered identity that hasn't been seen in months should still clutter the "unknown" section of the dashboard indefinitely.
   - Recommendation: For Phase 2, do not implement any expiry/cleanup — surface all discovered identities regardless of age (consistent with the project-wide no-auto-delete stance). Revisit only if UAT reveals dashboard clutter; defer to a later phase if so.

2. **What exact DHCP/mDNS fields, beyond hostname + requested IP, should be parsed and stored?**
   - What we know: CONTEXT.md explicitly leaves "DHCP packet fields parsed beyond hostname + requested IP (e.g. vendor class)" to Claude's discretion.
   - What's unclear: Whether `vendor_class_id` (DHCP option 60) or mDNS TXT records add enough fusion-accuracy value to justify the extra parsing/storage now, given D-02/D-03's deliberately simple hostname/MAC-fallback strategy doesn't use them yet.
   - Recommendation: Parse and store `vendor_class_id` from DHCP and the mDNS service `type`/`addresses` (not full TXT record dumps) since they're nearly free to capture alongside hostname and may inform the later fingerprint-resolver swap (deferred idea) — but do not build any fusion logic that consumes them yet (D-02/D-03 are locked).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| scapy (Python pkg) | ARP + DHCP sniffing | ✓ (already installed, Phase 1) | 2.7.0 | — |
| zeroconf (Python pkg) | mDNS discovery | ✗ (not yet installed) | — | Must be added to `backend/pyproject.toml` and `capture/requirements.txt`; no viable fallback for mDNS — it's the only approved library for this purpose |
| Docker `network_mode: host` + multicast | mDNS reception | ✓ (host networking already configured for capture container) | — | Verify multicast specifically works in deployment (Pitfall 4); if not, mDNS source degrades gracefully — fusion still works via hostname-from-DHCP and MAC fallback |
| PostgreSQL `ON CONFLICT` (native PG feature) | Dedup-safe upsert (Pitfall 5) | ✓ (PostgreSQL 17 + TimescaleDB 2.27, already the project's DB) | PG 17 | — |

**Missing dependencies with no fallback:**
- `zeroconf` package — must be installed; no fallback exists within the approved stack for mDNS discovery (DISC-01 explicitly requires mDNS as one of the three sources).

**Missing dependencies with fallback:**
- None beyond the above — all other dependencies are already present from Phase 1.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (already configured, `backend/pyproject.toml` `[tool.pytest.ini_options]` `asyncio_mode = "auto"`) |
| Config file | `backend/pyproject.toml` (`testpaths = ["tests"]`) |
| Quick run command | `cd backend && pytest tests/test_devices.py tests/test_identity_resolver.py -x` |
| Full suite command | `cd backend && pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DISC-01 | ARP/DHCP/mDNS observations fuse into one identity, not fragmented by MAC rotation | unit | `pytest tests/test_identity_resolver.py::test_hostname_fallback_resolver -x` | ❌ Wave 0 |
| DISC-01 | DHCP ingest endpoint accepts payload, applies same loopback-trust gate as ARP | integration | `pytest tests/test_capture.py::test_dhcp_ingest -x` | ❌ Wave 0 (extends existing `test_capture.py`) |
| DISC-01 | mDNS ingest endpoint accepts payload | integration | `pytest tests/test_capture.py::test_mdns_ingest -x` | ❌ Wave 0 |
| DISC-02 | POST /api/devices registers a device with name/owner/type/trusted | integration | `pytest tests/test_devices.py::test_register_device -x` | ❌ Wave 0 |
| DISC-02 | Merge endpoint combines an unknown identity into an existing device | integration | `pytest tests/test_devices.py::test_merge_device -x` | ❌ Wave 0 |
| DISC-03 | first_seen/last_seen update correctly on repeated observations | unit | `pytest tests/test_discovery.py::test_first_last_seen_tracking -x` | ❌ Wave 0 |
| DISC-04 | Unregistered device appears as "unknown" via GET /api/devices | integration | `pytest tests/test_devices.py::test_unknown_device_listed -x` | ❌ Wave 0 |
| DISC-04 (regression of D-04) | Registered device's identity-key change updates same row, doesn't spawn phantom unknown | unit | `pytest tests/test_discovery.py::test_registered_identity_key_change_no_phantom -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && pytest tests/test_devices.py tests/test_identity_resolver.py tests/test_discovery.py -x`
- **Per wave merge:** `cd backend && pytest` (full suite, includes Phase 1's `test_auth.py`/`test_capture.py`/`test_compose.py`/`test_models_scaffold.py`)
- **Phase gate:** Full suite green before `/gsd-verify-work`; frontend `npm run build && svelte-check` clean (per existing Phase 1 precedent in UI-SPEC notes)

### Wave 0 Gaps
- [ ] `backend/tests/test_identity_resolver.py` — covers DISC-01 fusion logic (hostname primary, MAC fallback, no-hostname case)
- [ ] `backend/tests/test_devices.py` — covers DISC-02/DISC-04 registry CRUD + merge + unknown listing
- [ ] `backend/tests/test_discovery.py` — covers DISC-03 timestamp tracking + the D-04 locked-identity regression case
- [ ] Extend `backend/tests/test_capture.py` — DHCP and mDNS ingest endpoints (mirrors existing `test_arp_ingest*` tests)
- [ ] No new fixtures needed — existing `conftest.py` `test_db`/`client` fixtures (Phase 1) are sufficient

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (new endpoints are behind existing session-cookie-gated dashboard, unchanged from Phase 1) | Phase 1's `itsdangerous` signed-cookie session, reused as-is |
| V3 Session Management | no | unchanged from Phase 1 |
| V4 Access Control | yes | New `/api/capture/dhcp` and `/api/capture/mdns` ingest routes MUST reuse the exact loopback/gateway-trust check (`_TRUSTED_HOSTS`/`_detect_default_gateway()`) already implemented in `backend/src/routes/capture.py` — do not weaken or duplicate-with-drift this logic; new `/api/devices` routes MUST require the existing authenticated session (same dependency as the dashboard) |
| V5 Input Validation | yes | Pydantic models for all new ingest payloads (`DhcpEventPayload`, `MdnsEventPayload`) and registry payloads (`DeviceRegisterPayload` with `type` constrained to the `DeviceType` enum, per D-14's closed set) — reject free-text `type` values at the schema layer, not just the DB enum layer |
| V6 Cryptography | no | no new crypto surface introduced this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| DHCP hostname/option spoofing (attacker on LAN sends a forged DHCP packet claiming another device's hostname) | Spoofing | Accepted residual risk for a passive, self-hosted, single-LAN tool (matches Pitfall 1) — not mitigated by Phase 2; the manual-merge-only policy (D-05) is itself a partial mitigation since it prevents an attacker-spoofed hostname from automatically absorbing a legitimate device's registry entry |
| Capture-ingest route abuse if trust boundary is misconfigured | Tampering | Reuse, do not reimplement, the existing `_detect_default_gateway()`/`_TRUSTED_HOSTS` pattern for every new ingest route — a second hand-rolled trust check is a drift risk (see Architecture Patterns "Don't Hand-Roll" framing) |
| Mass-registration / merge endpoint abuse (no rate limiting) | Denial of Service | Low severity for a single-user self-hosted LAN tool behind auth; explicitly out of scope per project's threat model (no internet-facing exposure) — no action needed this phase |
| `type` field injection via unconstrained free text | Tampering / data integrity | Enforce the D-14 closed enum at both the Pydantic schema layer and the SQLAlchemy `Enum` column type — never accept arbitrary strings for `type` |

## Sources

### Primary (HIGH confidence)
- `scapy.layers.dhcp` — Scapy 2.7.1 official docs (https://scapy.readthedocs.io/en/latest/api/scapy.layers.dhcp.html) — confirmed BOOTP/DHCP layer parsing built into the already-pinned scapy 2.7.0
- python-zeroconf official examples (https://github.com/python-zeroconf/python-zeroconf/blob/master/examples/async_browser.py) — confirmed `AsyncZeroconf`/`AsyncServiceBrowser`/`AsyncServiceInfo` async pattern
- python-zeroconf API reference (https://python-zeroconf.readthedocs.io/en/latest/api.html) — confirmed 0.149.16 current documented release
- Existing codebase: `backend/src/routes/capture.py`, `backend/src/models/arp_event.py`, `capture/capture.py`, `backend/tests/test_capture.py` — confirmed exact Phase 1 trust-boundary and POST-ingest patterns to extend

### Secondary (MEDIUM confidence)
- thepythoncode.com DHCP listener tutorial — cross-checked against official scapy docs, used to confirm exact option label strings (`'hostname'`, `'requested_addr'`, `'vendor_class_id'`)
- docs.sqlalchemy.org PostgreSQL dialect `insert().on_conflict_do_update()` — standard, well-documented SQLAlchemy 2.0 pattern for upsert/dedup

### Tertiary (LOW confidence)
- General web search results on MAC randomization / DHCP spoofing — used only to confirm the well-known, broadly-documented limitation described in Pitfall 1; not a novel or contested claim

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — both new libraries (`scapy`'s DHCP layer, `zeroconf`) are explicitly pre-approved in CLAUDE.md and confirmed via official docs/examples
- Architecture: HIGH — schema split and resolver interface design directly derive from locked CONTEXT.md decisions (D-01 through D-06) with no ambiguity left to resolve
- Pitfalls: MEDIUM-HIGH — DHCP/mDNS protocol pitfalls are well-documented; the Docker host-networking-multicast interaction (Pitfall 4 / Assumption A3) is the one item that genuinely needs an execution-time verification spike rather than research-time certainty

**Research date:** 2026-06-18
**Valid until:** 2026-07-18 (30 days — stable protocol-level libraries, low churn risk)
