# Phase 4: Security - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 4-Security
**Areas discussed:** Port scan trigger/scope/unexpected-port rules, Security status derivation, Malicious-IP/suspicious-traffic detection source, Unknown-device & alert surfacing

---

## Port Scan Trigger, Scope & Unexpected-Port Rules

User delegated this area to Claude with the instruction: optimize for product strength + maintainability/testability, not the easiest path.

**Claude's reasoning:**
- Trigger: on-demand button (SEC-01's literal ask) was the obvious baseline, but a pure on-demand-only design lets the security badge go stale indefinitely if the user never clicks it — undermines "at a glance" status. Added a daily background re-scan for *registered* devices only (not unknown/transient devices) as a low-noise freshness mechanism.
- Scope: full 1–65535 scan rejected — too slow/CPU-heavy for an always-on low-power box, low marginal signal for a home LAN. Top-1000 (nmap default) chosen as the v1 default; full-range scan noted as a future opt-in, not built now.
- Execution location: backend container could run a TCP-connect scan without new privileges, but a proper SYN scan needs `CAP_NET_RAW`, which the capture container already holds (Phase 1 D-05) and the backend deliberately does not. Running scans from the capture container avoids widening the backend's privilege surface and matches the existing "capture container owns anything requiring elevated network capability" pattern.
- Unexpected-port rule: a single flat allowlist was rejected in favor of a two-tier table (universal risky-ports set + per-`DeviceType` expected-ports allowlist) — gives meaningfully different severities (a Plex server port vs an open telnet port shouldn't be treated the same) and stays fully table-driven/testable rather than encoding judgment calls in branching logic.

**Selected:** On-demand + daily background scan (registered devices only); top-1000 ports via nmap; scan executes from the capture container; two-tier risky-port-set + per-type-allowlist rule (D-01..D-05).

---

## Security Status Derivation (good/warning/critical)

**Claude's reasoning:**
- Needed a rule that's explainable and table-driven, not an opaque weighted score that's hard to test or reason about.
- critical reserved for the two highest-confidence bad signals (risky port open, malicious-IP contact) since "critical" should mean "act now," not "something is slightly off."
- warning covers lower-confidence/lower-severity signals (unexpected-but-not-risky port, bandwidth anomaly) — both have legitimate explanations (Plex server, big download) so shouldn't escalate to critical.
- Unscanned devices default to good rather than warning/critical — avoids punishing a device the user simply hasn't gotten to yet; "not yet scanned" is surfaced separately (scan button/timestamp), not conflated with the security badge.

**Selected:** critical = risky port OR malicious-IP contact; warning = unexpected port OR bandwidth anomaly; good = neither, including not-yet-scanned (D-06/D-07).

---

## Malicious-IP / Suspicious-Traffic Detection Source

**Claude's reasoning:**
- The hard constraint (CLAUDE.md/PROJECT.md: "no telemetry, no external calls unless user explicitly configures an integration") rules out silently calling a live threat-feed API by default.
- A bundled static blocklist (vendored file, updated via app releases) is the only option that's both useful out-of-the-box and fully constraint-compliant with zero configuration.
- A remote/updatable feed (Spamhaus, FireHOL) is valuable for power users but is exactly the kind of thing the constraint says must be opt-in — so it's designed for (via a `ThreatIntelSource` interface mirroring Phase 3's swappable bandwidth-source pattern) but not built as a UI/scheduler in this phase, to avoid scope creep into Phase 5/settings territory.
- "Suspicious traffic patterns" (SEC-03's second clause) needed a concrete, narrow v1 definition rather than open-ended anomaly detection. A bandwidth-spike-vs-rolling-average threshold reuses Phase 3's existing traffic data with no new capture infrastructure and is simple to unit test — deliberately avoided building any ML/statistical model for v1.

**Selected:** Bundled static blocklist as default `ThreatIntelSource`; remote feed support designed-for via the interface but not built; bandwidth-spike threshold as the v1 "suspicious traffic pattern" signal, at warning (not critical) severity (D-08..D-10).

---

## Unknown-Device & Alert Surfacing (pre-notifications)

**Claude's reasoning:**
- SEC-02/SEC-04 explicitly defer push delivery to Phase 5, but Phase 4 still needs *some* durable, visible representation of "this happened" or the feature is invisible until Phase 5 ships.
- A `security_alerts` table shaped with device/type/severity/message/acknowledged fields is deliberately built so Phase 5's event bus (PLUG-03) can subscribe to or poll it directly later — avoids a second pass to retrofit an events shape once Phase 5 arrives.
- Decided both a dashboard alerts feed/banner (action-required view, mirrors the existing Phase 2 D-13 summary banner pattern) and the per-device badge (at-a-glance view) are needed — they serve different jobs (triage list vs status overview) and neither alone covers both.

**Selected:** `security_alerts` table feeding both a new dashboard alerts feed/banner and the existing per-device badge; push delivery explicitly deferred to Phase 5 (D-11..D-13).

---

## Claude's Discretion

- Daily-scan scheduling mechanism (cron-like loop vs APScheduler vs simple interval task)
- Bandwidth-anomaly threshold multiplier and rolling-average window length
- Full per-`DeviceType` expected-ports allowlist contents beyond the examples given
- `security_alerts` schema details (indexes, exact column types)
- Whether scan results get a history table or just a latest-result-per-device field

## Deferred Ideas

- Full 1–65535 "deep scan" option (top-1000 is the v1 default)
- User-configurable remote threat-feed UI (Spamhaus/FireHOL/etc.) — interface designed for it, UI not built
- ML-based/statistical anomaly detection beyond the simple bandwidth-spike threshold
