# Phase 2: Device Registry + Discovery - Context

**Gathered:** 2026-06-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace Phase 1's ARP-only capture proof-of-concept with real multi-source discovery (ARP + DHCP + mDNS, all passive), fuse rotating-MAC identities into stable device entries, let the user register devices with name/owner/type/trusted, and surface unregistered devices clearly as unknown on the dashboard. No router adapter, no active scanning, no bandwidth/traffic/security data yet — those are Phase 3+.

</domain>

<decisions>
## Implementation Decisions

### MAC-Randomization Identity Fusion
- **D-01:** Identity fusion logic MUST be isolated behind an interface/strategy abstraction (e.g. `IdentityResolver` with a `resolve(observation) -> device_identity_key` contract) — not inlined into the discovery pipeline. The goal is a drop-in replacement later without touching callers.
- **D-02:** Initial (Phase 2) strategy implementation: **hostname/mDNS as primary identity key**. If a device broadcasts a stable hostname via DHCP or mDNS, that hostname is the identity key regardless of MAC changes.
- **D-03:** **MAC address as fallback identity key** when no hostname/mDNS record exists (common for fixed-MAC IoT/smart-home devices).
- **D-04:** Fusion is **discovery-time only** — it only affects how unregistered observations are grouped into entries before registration. Once a device is registered, its identity is locked to that registry row; a later MAC/hostname change on a registered device updates the same row (matched by its stored identity key), it never creates or silently merges separate rows.
- **D-05:** **No automatic merging, ever** — not even for high-confidence matches (e.g. exact hostname match, MAC differing only in randomization bits). All merges of duplicate entries are user-initiated and manual.
- **D-06:** Manual merge UX: an unknown device's card has a "Merge with..." action (alongside "Register") letting the user pick another existing device entry to combine into. Not deferred to a later phase — ships in Phase 2.

### DHCP Lease Source
- **D-07:** DHCP-derived discovery data (hostname, requested IP) comes from **passive DHCP packet sniffing** in the capture service — same scapy + POST-to-API pattern Phase 1 established for ARP (`capture/capture.py`). No router adapter dependency; works in any deployment.
- **D-08:** Discovery stays **pure passive sniffing** — ARP + DHCP + mDNS, no active probing/scanning (no periodic ARP sweep, no nmap). Active scanning is a later-phase concern (security scans in Phase 4, travel-mode nmap in Phase 6).

### Device List & Unknown-Device UX
- **D-09:** Dashboard device list is a **card grid** (not a table) — one card per device, scales visually for household-sized device counts, leaves room for future per-card data (bandwidth sparkline, security badge).
- **D-10:** Unknown (unregistered) devices get **distinct visual styling** (dashed border / warning accent / "Unknown" badge) within the same grid, sorted to the top — not a separate page/section.
- **D-11:** Unknown device cards show an inline **"Register"** button that opens a quick form (name/owner/type/trusted) directly — no click-through to a separate page required for the common case.
- **D-12:** Registered device cards show, for Phase 2: name, type icon, last-seen timestamp, online/offline status dot. No IP/MAC on the card face (available on click-through/detail), no bandwidth or security data (not built yet).
- **D-13:** Dashboard shows a **summary banner** above the grid (e.g. "14 devices · 2 unknown") for at-a-glance status.

### Device Registry Fields & Type Taxonomy
- **D-14:** `type` is a **fixed dropdown enum**: Phone, Laptop, Desktop, Tablet, IoT/Smart Home, TV/Streaming, Game Console, Router/Network, Other. Closed set chosen deliberately so Phase 4's "unexpected port for this device type" security rules have something to key off of.
- **D-15:** `owner` is **freeform text** (e.g. "Brandon", "Guest", "Shared") — no separate household-members entity/CRUD this phase.
- **D-16:** `trusted` is a boolean that is **informational only in Phase 2** — shown on the registry form, no gating behavior yet, no extra visual treatment beyond the standard card. Future phases (travel-mode scope, security alerting) will read it; nothing consumes it yet.

### Claude's Discretion
- Exact card grid breakpoints/responsive layout
- Specific icon set for the type dropdown
- Internal schema/table design for device identity vs. registry rows (e.g. separate `discovered_identities` vs `devices` tables) — as long as D-01 through D-06 hold
- DHCP packet fields parsed beyond hostname + requested IP (e.g. vendor class) if useful for identity fusion
- Exact wording/placement of the "Merge with..." picker UI

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements & Roadmap
- `.planning/ROADMAP.md` — Phase 2 success criteria (4 items), requirements DISC-01..04, phase goal statement
- `.planning/REQUIREMENTS.md` — Full DISC-01..04 requirement text
- `.planning/PROJECT.md` — Key decisions table, constraints (portability, self-hosted, router-agnostic core)

### Prior Phase Context
- `.planning/phases/01-foundation-capture-feasibility/01-CONTEXT.md` — D-03/D-04/D-06: capture runs `network_mode: host` + CAP_NET_RAW/CAP_NET_ADMIN, POSTs to API (never writes DB directly), Phase 1 capture is explicitly proof-of-concept that Phase 2 replaces
- `.planning/STATE.md` — Blockers section flags "MAC-randomization identity model" as the central Phase 2 risk (addressed by D-01..D-06 above)

### Technology Stack
- `CLAUDE.md` — Scapy 2.7 for packet capture/discovery, python-zeroconf for mDNS, SQLAlchemy 2.0 async + asyncpg, Svelte 5 + SvelteKit 2

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `capture/capture.py` — Phase 1's ARP-sniff-and-POST pattern (scapy `sniff()` + `httpx.post()`, SIGTERM handling via `stop_event`). DHCP and mDNS sniffing should follow the same shape: capture container stays the single source of raw network observations, POSTs to API, never touches DB directly.
- `backend/src/routes/capture.py` — Existing `/api/capture/arp` ingest route pattern: loopback/gateway-trusted-only POST endpoint, Pydantic payload model, writes via SQLAlchemy async session. New DHCP/mDNS ingest routes (or a generalized ingest route) should follow this same trust-boundary and request/response shape.
- `backend/src/models/arp_event.py` — Existing raw-observation model shape (mac/ip/timestamp). New discovery models (device identity, registry) extend this pattern; raw ARP events likely become one input stream feeding the new fusion layer rather than being replaced.
- `frontend/src/routes/dashboard/+page.svelte` — Currently an empty protected shell (Phase 1 D-19). This phase fills it with the device card grid, summary banner, and register/merge interactions.
- `frontend/src/lib/api.ts` — Existing typed API client; extend with device list/register/merge endpoints.

### Established Patterns
- Capture container never writes to the DB directly — always POSTs to the API (Phase 1 D-06). Maintain this for DHCP/mDNS sources.
- Ingest routes trust only loopback + runtime-detected default gateway (Docker hairpin NAT pattern from `_detect_default_gateway()` in `capture.py`) — reuse this trust model for any new ingest routes rather than reinventing it.

### Integration Points
- New discovery sources (DHCP sniff, mDNS via python-zeroconf) plug into the same capture container and POST-to-API flow as ARP.
- The identity-fusion interface (D-01) sits in the backend, between raw ingest (ArpEvent-style tables) and the device registry table — this is the new architectural seam this phase introduces.

</code_context>

<specifics>
## Specific Ideas

- User explicitly wants the identity-fusion algorithm built as a swappable interface from day one — anticipates wanting a smarter fusion strategy later (e.g. the fingerprint-based approach considered and deferred) without rearchitecting callers.
- "Merge with..." manual-merge action ships now, attached to unknown device cards — not deferred.

</specifics>

<deferred>
## Deferred Ideas

- **Fingerprint-based identity fusion** (composite signal: hostname + mDNS service records + vendor OUI consistency + IP-lease continuity) — considered as the most accurate option but deferred in favor of simpler hostname/MAC-fallback fusion for Phase 2. Revisit if the simple strategy proves too lossy; the D-01 interface is designed to make this swap cheap.
- **Soft-prompt auto-merge suggestion** at discovery time for very high-confidence matches — rejected in favor of "always create new, manual merge only" (D-05), but could be reconsidered as a UX enhancement later.
- **Active periodic ARP scanning** to fill gaps between passive observations — deferred; pure passive sniffing only for Phase 2 (D-08). Active scanning concerns belong to Phase 4 (security scans) and Phase 6 (travel-mode nmap).
- **Structured household-member entity** for the `owner` field — deferred in favor of freeform text (D-15); revisit only if a future feature needs to reference owners as first-class entities.

</deferred>

---

*Phase: 2-Device Registry + Discovery*
*Context gathered: 2026-06-18*
