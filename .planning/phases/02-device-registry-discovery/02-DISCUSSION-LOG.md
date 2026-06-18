# Phase 2: Device Registry + Discovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-18
**Phase:** 2-Device Registry + Discovery
**Areas discussed:** MAC-randomization identity fusion, DHCP lease source, Device list & unknown-device UX, Device registry fields & type taxonomy

---

## MAC-Randomization Identity Fusion

| Option | Description | Selected |
|--------|-------------|----------|
| Fingerprint-based fusion | Composite fingerprint (hostname + mDNS + OUI consistency + IP-lease continuity) | |
| Hostname/mDNS as primary key | Trust self-reported hostname as stable identity, fall back to MAC | ✓ (modified) |
| Conservative — no auto-fusion | Each MAC its own entry, user manually merges related entries | |

**User's choice:** Hostname/mDNS as primary key, with the explicit requirement that the fusion logic be built behind a swappable interface so a better strategy (e.g. fingerprint-based) can be dropped in later without touching callers.
**Notes:** "go with 2 for now, but make sure how we develop this is isolated logic so that later on if we want to make it better, its more of a drop in feature."

Follow-up questions and answers:
- Fallback identity key when no hostname/mDNS exists → **MAC address as fallback** (over vendor+IP-continuity heuristic).
- Does fusion ever happen post-registration? → **Discovery-time only** — registered device identity is locked; no auto-merge after registration.
- Should the system ever soft-prompt a merge at discovery time for high-confidence matches? → **No — always create new, manual merge only.** Consistent with "no auto-merge."

---

## DHCP Lease Source

| Option | Description | Selected |
|--------|-------------|----------|
| Passive DHCP sniffing | Capture service sniffs DHCP DISCOVER/REQUEST via scapy, same pattern as ARP | ✓ |
| Defer DHCP to Phase 7 | Rely on ARP+mDNS only until router adapter lands | |

**User's choice:** Passive DHCP sniffing.
**Notes:** None.

Follow-up:
- Should discovery also do active scanning (e.g. periodic ARP sweep) to fill gaps between passive DHCP broadcasts? → **No — pure passive sniffing**, consistent with Phase 1's proof-of-concept pattern. Active scanning deferred to later phases (security scans, travel-mode nmap).

---

## Device List & Unknown-Device UX

| Option | Description | Selected |
|--------|-------------|----------|
| Card grid | One card per device, scales visually, room to grow | ✓ |
| Table/list | Dense sortable rows | |

**User's choice:** Card grid.

Follow-up questions and answers:
- How should unknown devices be visually called out? → **Distinct unknown styling** (dashed border/warning accent/badge) within the same grid, sorted to top — not a separate section.
- Primary action on an unknown device's card? → **Inline "Register" button** opening a quick form directly (over click-through to a detail page).
- Where does the manual-merge action (decided in the identity-fusion area) live? → **Merge action on each unknown card**, alongside Register — not deferred to a later phase.
- What does a registered device's card show day-to-day? → **Name, type icon, last-seen, online/offline dot.** No IP/MAC on the card face, no bandwidth/security data (not built yet).
- Summary banner above the grid? → **Yes** (e.g. "14 devices · 2 unknown").

---

## Device Registry Fields & Type Taxonomy

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed dropdown for `type` | Enum: Phone, Laptop, Desktop, Tablet, IoT/Smart Home, TV/Streaming, Game Console, Router/Network, Other | ✓ |
| Freeform text for `type` | User types whatever they want | |

**User's choice:** Fixed dropdown — needed as a closed set for Phase 4's port-expectation security rules.

Follow-up questions and answers:
- Is `owner` freeform or a structured household-member list? → **Freeform text** — no separate Person/household-member entity this phase.
- What does the `trusted` flag actually gate in Phase 2? → **Informational only** — shown on the form/registry, no gating behavior and no extra visual treatment yet. Future phases (travel-mode scope, security alerting) will read it.

---

## Claude's Discretion

- Exact card grid breakpoints/responsive layout
- Specific icon set for the type dropdown
- Internal schema/table design for device identity vs. registry rows (separate tables vs. one), as long as the identity-fusion decisions (interface-based, hostname-primary/MAC-fallback, discovery-time only, no auto-merge) hold
- DHCP packet fields parsed beyond hostname + requested IP
- Exact wording/placement of the "Merge with..." picker UI

## Deferred Ideas

- Fingerprint-based identity fusion (composite hostname + mDNS + OUI + IP-continuity signal) — deferred in favor of simpler hostname/MAC-fallback strategy; the swappable-interface requirement (D-01) is specifically designed to make this future swap cheap.
- Soft-prompt auto-merge suggestion at discovery time for very high-confidence matches — rejected in favor of always-manual merging.
- Active periodic ARP scanning to fill passive-sniffing gaps — deferred to Phase 4 (security scans) / Phase 6 (travel-mode nmap).
- Structured household-member entity for `owner` — deferred in favor of freeform text; revisit only if a future feature needs owners as first-class entities.
