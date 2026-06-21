---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Roadmap updated; ready to re-plan
stopped_at: Phase 5 UI-SPEC approved
last_updated: "2026-06-21T17:41:49.040Z"
last_activity: 2026-06-21 -- module platform pivot applied to ROADMAP.md/REQUIREMENTS.md/PROJECT.md
progress:
  total_phases: 12
  completed_phases: 5
  total_plans: 18
  completed_plans: 18
  percent: 42
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-21)

**Core value:** See every device on your network and what it's doing, in real time — and be able to act on it.
**Current focus:** Phase 5 — Module Platform Foundation (pivot applied, awaiting re-plan)

## Current Position

Phase: 5
Plan: Not started — original 05-01..05-04 plans superseded, new scope needs `/gsd-plan-phase 5`
Status: Roadmap updated; ready to re-plan
Last activity: 2026-06-21 -- module platform pivot applied to ROADMAP.md/REQUIREMENTS.md/PROJECT.md

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 10
- Average duration: 24 min
- Total execution time: 0.8 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 2 | 47min | 24min |
| 3 | 4 | - | - |
| 04 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: 35min, 12min
- Trend: decreasing

*Updated after each plan completion*

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 01 | 01 | 35min | 2 | 20 |
| 01 | 03 | 12min | 2 | 16 |
| 01 | 02 | ~3h (incl. live debugging) | 2 | 5 |
| Phase 02 P01 | 25min | 2 tasks | 15 files |
| Phase 02 P02 | 12min | 2 tasks | 2 files |
| Phase 02 P03 | 18min | 2 tasks | 5 files |
| Phase 02 P04 | 18min | 2 tasks | 4 files |
| Phase 02 P05 | 25min | 2 tasks | 8 files |
| Phase 02.1 P01 | 55min | 2 tasks | 12 files |
| Phase 03 P01 | 25min | 2 tasks | 7 files |
| Phase 03 P02 | 20min | 2 tasks | 3 files |
| Phase 03 P03 | 45min | 3 tasks | 10 files |
| Phase 03 P04 | 102min | 3 tasks (+2 deviation fix commits) | 16 files |

## Accumulated Context

### Roadmap Evolution

- [2026-06-21] Phase 5 edited: "Plugin System + Notifications" replaced with "Module Platform Foundation" — host infra (ModuleRegistry/EventBus/ModuleLoader/capability Protocols) + retrofit of Devices/Traffic/Security onto isolated, swappable modules. See docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md.
- [2026-06-21] Phase 5.1 inserted after Phase 5 (URGENT): "Improve Device Identity" — promotes backlog item 999.1, moved ahead of Notifications.
- [2026-06-21] Phase 5.2 inserted after Phase 5.1 (URGENT): "Notifications" — demoted from the original Phase 5 scope; now built clean on the new module contract with no retrofit baggage.
- [2026-06-21] Original Phase 5 plans (05-01..05-04-PLAN.md) and 05-PATTERNS.md/05-CONTEXT.md marked superseded in place — built against the retired bolt-on plugin contract.

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [2026-06-21]: Module platform pivot — capability-Protocol module contracts, ModuleRegistry resolving support interfaces by type (not module identity) for swappable implementations, per-module Postgres schema isolation, DeviceIdentity as sole source of truth for device data with Devices as a thin UI client. Full rationale in docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md.
- [Roadmap]: Python 3.13 baseline (aiounifi v91 requires >=3.13)
- [Roadmap]: Capture engine is a separable component — topology (native macOS agent vs Linux host networking) resolved by a Phase 1 go/no-go spike before any capture code
- [Roadmap]: Device Registry is the keystone — built in Phase 2 before everything that derives meaning from it
- [Roadmap]: Plugin contract defined (Phase 5) before any first-party plugins; UniFi adapter (Phase 7) gated on user's planned hardware
- [Phase 1]: database.py only passes pool_size/max_overflow (QueuePool-only kwargs) when the URL is not sqlite, so the same engine factory works for both production Postgres and the in-memory SQLite test fixture
- [Phase 1]: greenlet added as an explicit dependency — SQLAlchemy's async extension requires it at runtime but does not declare it as a hard dependency
- [Phase 1]: Settings.model_config uses env_file=None — config is injected entirely via Docker Compose's env_file: directive
- [Phase 1]: Added frontend/.gitignore (node_modules, build/, .svelte-kit) — required for any Node project, not explicitly listed in plan files_modified
- [Phase 1]: svelte:head must be a top-level element, not nested inside an {#if} block — moved dashboard's title tag outside the auth-gated conditional
- [Phase 1]: Frontend and API must be same-origin (nginx reverse-proxies /api/) — cross-port + CORS breaks SameSite=Lax session cookies on every fetch()-based client, invisible to unit tests
- [Phase 1]: Capture's loopback-only ingest check must trust the runtime-detected Docker bridge gateway (via /proc/net/route), not just literal 127.0.0.1 — Docker hairpin NAT rewrites the source IP for any container using network_mode: host talking to a bridge-networked service via the host's published port
- [Phase 1]: macOS local dev requires a bridged-network Lima VM (Docker Desktop's NAT isolation can't see real LAN traffic) — Mac-only tooling, irrelevant to the real Linux deployment target; see docs/dev/mac_setup.md
- [Phase ?]: Phase 2: mDNS observations use placeholder MAC 00:00:00:00:00:00 since mDNS alone carries no MAC; documented as known limitation, ARP/DHCP independently resolve real identity
- [Phase ?]: Phase 2: used a throwaway /tmp venv with Python 3.13 (homebrew) to run pytest since project requires >=3.13 and no project venv existed yet
- [Phase ?]: Pinned zeroconf==0.148.0 (not 0.149.16) — live pip index confirmed 0.148.0 as latest actually-published version; package identity already verified
- [Phase 02]: Phase 2: bits-ui Select.Value imported directly (not re-exported via ui/select/index.ts) for placeholder/selected-label display in Register/Merge dialog Select triggers
- [Phase 02 P04]: ingest_mdns guard depends only on hostname presence (not a combined MAC+hostname check) since mDNS observations always carry the same placeholder MAC today — closes CR-01 over-fusion bug
- [Phase 02 P04]: Frontend listDevices()/registerDevice() now call the canonical /api/devices/ (trailing slash) path to avoid the 307-redirect hop on POST — closes CR-02 path mismatch
- [Phase ?]: Phase 02 P05: hoisted MDNS_PLACEHOLDER_MAC to identity_resolver.py as single source of truth; record_observation excludes placeholder MAC from Device-branch matching entirely (CR-05 fix)
- [Phase ?]: Phase 02 P05: register_device/merge_device refuse to persist placeholder MAC into Device.last_known_mac; column made nullable (migration 0002 edited in place, not yet shipped outside this branch)
- [Phase ?]: Phase 02.1 P01: mac-vendor-lookup's AsyncMacLookup resolves its OUI snapshot from a build-time-populated cache path, not a runtime network call
- [Phase ?]: Phase 02.1 P01: Docker api image required a rebuild after adding mac-vendor-lookup dependency - stale image caused ModuleNotFoundError, caught by test_compose.py
- [Phase 02.1 P02]: Task 3's human-verify checkpoint (all six UI-SPEC Checker Sign-Off checks: inference line presence/absence, info-icon popover open/close/keyboard, touch tap-to-toggle, Register dialog pre-fill with/without guess) approved by user 2026-06-19 — phase 02.1 complete, DISC-05/DISC-06 fully satisfied
- [Phase 03]: Added upsert_device_mac_history() to discovery.py reusing the dialect-aware pg_insert/sqlite_insert upsert pattern already established by upsert_discovered_identity
- [Phase 03]: Phase 03 P02: FLUSH_INTERVAL=7s (midpoint of locked 5-10s range per D-01/D-11); dpkt==1.9.8 pinned for the traffic-sniff loop after package-legitimacy checkpoint approval
- [Phase ?]: Phase 03 P03: sse-starlette pinned at 3.4.4 (Task 0 checkpoint approved by user after independent PyPI verification)
- [Phase ?]: Phase 03 P03: GET /bandwidth/network registered before GET /bandwidth/{device_id} — FastAPI route matching is declaration-order-sensitive
- [Phase ?]: Phase 03 P03: conftest.py now explicitly imports every model module before Base.metadata.create_all so test_db is self-sufficient regardless of which other fixtures a test uses
- [Phase 03 P04]: Any table with a composite primary key that includes an optional/nullable business field must coerce that field to a sentinel value before insert — Postgres enforces NOT NULL on PK columns regardless of the SQLAlchemy model's nullable declaration; surfaced when dpkt's portless-protocol (ICMP/IGMP) packets carried a null dst_port straight into traffic_flows' composite PK, fixed at both capture/traffic_sniff.py and backend/src/routes/capture.py
- [Phase 03 P04]: Svelte {#each} block keys must never rely on implicit string-concat of a possibly-undefined field plus a number — `undefined + number` evaluates to NaN (JS numeric addition, not string concatenation) in JS, collapsing every row to the same key and crashing with each_key_duplicate; build keys from explicit template-literal composites of verified-present fields instead. Also: SSE/API payload field names must be verified against the actual backend response shape during live testing, not assumed from plan prose — svelte-check's static typing cannot catch a runtime field-name mismatch against an untyped fetch/EventSource payload
- [Phase 03]: Phase 03 P04 (03-04) complete — manual verification checkpoint (live SSE behavior, device-picker navigation, tab switching, EventSource reconnect) confirmed passing by user against the real Lima-VM docker-compose stack with live WAN traffic, including after two live-verification bug-fix commits. Phase 3 (TRAF-01..04) fully complete.
- [Phase 04 P01]: Plan 04-01 complete — pure-function services (port_rules.py, security_status.py, threat_intel_source.py), vendored FireHOL firehol_level1.netset blocklist (4558 CIDR entries), and the security data layer (Device gains security_status/last_scanned_at/last_known_ip; new port_scan_results/security_alerts/pending_scan_requests tables; migration 0005) all shipped with zero regressions (80/80 backend tests passing). Ran pytest via the pre-existing /tmp/innkeeper-venv313 Python 3.13 venv since no project-local venv exists yet. Device.last_known_ip is schema-only here — Plan 04-02 wires discovery.py's record_observation() to populate it from ARP's src_ip.
- [Phase 04 P02]: Plan 04-02 complete — new /api/security/* route file (scan-trigger, scan-result read, alerts list/ack/ack-all, all auth-gated), bandwidth_anomaly.py's check_bandwidth_anomaly() (D-09, reused as-is from a prior interrupted attempt after verifying it matched the plan spec exactly), and capture.py extensions (POST /scan ingest, GET /pending-scans claim-on-read poll, POST /queue-daily-scans which both queues PendingScanRequests AND evaluates check_bandwidth_anomaly() per device — closing the gap where D-09's signal was previously unreachable from production). ingest_arp now persists Device.last_known_ip from ARP src_ip; ingest_traffic now checks every dst_ip against the threat-intel blocklist and writes a malicious_ip alert + critical status flip on a hit. discovery.py's upsert_discovered_identity() fires exactly one unknown_device alert per genuinely-new identity (SEC-02). devices.py's serializer gained security_status/last_scanned_at. 108/108 backend tests passing, zero regressions. Plans 04-03 (capture container) and 04-04 (frontend) can now build against this stable API contract.
- [Phase 04 P03]: Plan 04-03 complete — Task 0 checkpoint (python-nmap dependency source) resolved by orchestrator/user: home-assistant-libs/python-nmap verified legitimate via GitHub API, pinned to commit 9ac822b56ebbdbf8816e592a1cdb071a2b808f11. capture/port_scan.py adds _run_and_post_scan() (top-1000-port -sS SYN scan, swallow-and-continue POST to /api/capture/scan), run_scan_listener() (polls /api/capture/pending-scans every 3s), run_daily_rescan_loop() (sleeps until 03:00 local, pings /api/capture/queue-daily-scans, zero device-selection logic). capture.py now runs six threads total sharing the same stop_event. **Deviation found and fixed**: the plan's literal `python-nmap @ git+https://...` requirements.txt syntax does not install — the fork's own package metadata declares its distribution name as "netmap", not "python-nmap", so pip rejects the named requirement as a mismatch (confirmed live via `pip install` into a venv). Fixed to a bare `git+https://...@<sha>` line with no name prefix; `import nmap` still resolves PortScanner identically. 3/3 new capture-side tests passing (capture/test_port_scan.py, first test infra in capture/); backend full suite re-verified at 108/108, zero regressions (capture is a separate, unaffected runtime). Plan 04-04 (frontend) can proceed independently.
- [Phase 04 P04]: Plan 04-04 complete — Phase 4 (Security) fully implemented. Frontend gains: DeviceCard's good/warning/critical security badge (never color-only, defaults to "Good" when security_status is null/undefined per D-06) + Scan/Re-scan button (aria-live="polite" "Scanning…" state, inline "Scan couldn't complete" recovery on failure) + a new "View results" affordance; ScanResultDialog (new) sourcing per-port risky/unexpected/expected detail exclusively from getScanResult() -> GET /api/security/scan/{device_id}, never from the device list's rolled-up security_status; SecurityAlertsBanner (new) reading /api/security/alerts, per-row dismiss with no confirmation, "Dismiss all" (2+ alerts) gated behind an AlertDialog confirmation, rendering no DOM when zero alerts exist. Installed shadcn-svelte's first tooltip/alert/alert-dialog components and the project's first --color-good token (green-500, brand-alias-only, distinct from --color-accent's online/live teal-green). Dashboard now renders the alerts banner above the existing Phase 2 summary banner and polls for scan-result freshness after triggering a scan. **Deviation**: added an undocumented-by-plan `onShowResults` prop on DeviceCard — the plan specifies ScanResultDialog and its open/close state but left the "view results" open affordance to executor discretion per the UI-SPEC; without it, a user would have no way to view an existing scan result (only to trigger a brand-new one). svelte-check: 0 errors (3 pre-existing warnings, unrelated). No frontend test runner exists in this project (no vitest/jest) — TDD behavior cases verified via code inspection + svelte-check, consistent with prior phases. Phase 4 (SEC-01..04) is now complete across all 4 plans.

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- [Phase 1/3]: TimescaleDB schema (hypertable vs config separation, chunk sizing, downsample-not-delete policy) is expensive to change later — settle during early planning.
- [Phase 2]: MAC-randomization identity model — how aggressively to dedupe rotating MACs is non-trivial and central.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260618-bmk | Add a scripted Lima VM dev environment so the Phase 1 docker-compose stack can be verified on a real Linux network namespace from any Mac | 2026-06-18 | fefb67c | [260618-bmk-add-a-scripted-lima-vm-dev-environment-s](./quick/260618-bmk-add-a-scripted-lima-vm-dev-environment-s/) |
| 260618-coa | Fix cross-origin session-cookie bug (SameSite=Lax + cross-port frontend/API) via same-origin nginx proxy; also fixed the underlying api.ts fallback that defeated it | 2026-06-18 | 455e8d4 | [260618-coa-fix-cross-origin-session-cookie-bug-fron](./quick/260618-coa-fix-cross-origin-session-cookie-bug-fron/) |
| 260618-dcc | Fix capture.py loopback-only check (Docker hairpin NAT rewrites source to bridge gateway) — unblocked the D-05 go/no-go gate, confirmed PASS with a real captured ARP packet | 2026-06-18 | 8054f07 | [260618-dcc-fix-capture-py-loopback-only-security-ch](./quick/260618-dcc-fix-capture-py-loopback-only-security-ch/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-21T17:15:20.460Z
Stopped at: Phase 5 UI-SPEC approved
Resume file:

.planning/phases/05-plugin-system-notifications/05-UI-SPEC.md
