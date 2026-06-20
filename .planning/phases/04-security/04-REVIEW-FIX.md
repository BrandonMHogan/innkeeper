---
phase: 04-security
fixed_at: 2026-06-20T23:31:56Z
review_path: .planning/phases/04-security/04-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-06-20T23:31:56Z
**Source review:** .planning/phases/04-security/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (3 critical, 5 warning — `fix_scope: critical_warning`, Info findings excluded)
- Fixed: 8
- Skipped: 0

**Post-fix verification note:** The fixer agent could not run pytest in its environment and verified CR-03 by manual trace only. Re-running the full backend suite (`/tmp/innkeeper-venv313`) after this fix pass surfaced a real regression in CR-03's `bandwidth_anomaly.py` change: SQLite (used in tests) returns naive datetimes for the `DateTime(timezone=True)` column, while the new trailing-24h logic compared `row.time` directly against an aware `now()`-derived window start, raising `TypeError` on every call. Fixed in commit b5ab6fe (normalize to aware UTC before comparing). Full suite is now 109/109 passing.

## Fixed Issues

### CR-01: `Device.last_known_ip` / ARP `src_ip` is never validated as an IP address before reaching the nmap subprocess

**Files modified:** `backend/src/routes/capture.py`, `capture/port_scan.py`
**Commit:** 682a299
**Applied fix:** Typed `ArpEventPayload.src_ip`/`dst_ip` as `pydantic.IPvAnyAddress` instead of bare `str`, closing the validation gap at the trust boundary; stringified the values at persistence sites (`ArpEvent`, `Device.last_known_ip`) since those columns are plain `String`. Added a defensive `ipaddress.ip_address(target_ip)` check in `port_scan.py`'s `_run_and_post_scan` immediately before the nmap subprocess invocation, refusing to scan and logging instead of passing an unvalidated string into `scanner.scan()`.

### CR-02: Security alert messages in the UI never include the actual device name

**Files modified:** `backend/src/routes/security.py`, `frontend/src/lib/components/SecurityAlertsBanner.svelte`
**Commit:** f09fdf8
**Applied fix:** `list_alerts()` now joins `Device.name` via `outerjoin` and `_serialize_alert()` includes `device_name` in the response. The frontend banner's `messageFor()` now renders the backend's pre-built `alert.message` field directly instead of reconstructing a generic message from `alert.type` with a hardcoded "A device" fallback.

### CR-03: `check_bandwidth_anomaly` compares a possibly-partial "most recent day" against a full-day rolling average

**Files modified:** `backend/src/services/bandwidth_anomaly.py`
**Commit:** 38d41ad
**Applied fix:** Replaced calendar-day bucketing (`row.time.date()`) for the "most recent" bucket with a trailing 24h window ending "now," so the comparison bucket is always a full day of traffic rather than a partial day relative to call time. Baseline days remain grouped by calendar day. Manually traced all three existing `test_bandwidth_anomaly.py` scenarios (below-minimum-sample, spike-after-history, steady) against the new bucketing logic and confirmed all three still produce the expected results.
**Note:** This is a logic/algorithm change to a statistical comparison — flagged per verification_strategy guidance as requiring human confirmation that the trailing-24h semantics are correct for production traffic patterns, beyond the unit-test-level trace performed here.

### WR-01: `/api/capture/*` loopback-only trust boundary also trusts the LAN default gateway

**Files modified:** `backend/src/routes/capture.py`
**Commit:** 9e0c576
**Applied fix:** Confirmed via `test_arp_ingest_accepts_detected_gateway` that the gateway-trust branch is intentional and already covered by a test (not dead/accidental code), so rather than removing it, updated every route docstring and the 403 error detail from "loopback-only" to "loopback or detected default gateway only," and added an explanatory comment above `_TRUSTED_HOSTS` describing the NAT/hairpin/reverse-proxy deployment scenario that motivates trusting the gateway.

### WR-02: `unexpected_port` alerts are never de-duplicated against existing unacknowledged alerts

**Files modified:** `backend/src/routes/capture.py`
**Commit:** 7be885b
**Applied fix:** Added the same existing-unacknowledged-alert guard already used for `MALICIOUS_IP` and `SUSPICIOUS_TRAFFIC` in the same module: before inserting a new `SecurityAlert(type=UNEXPECTED_PORT)`, query for an existing unacknowledged alert of that type for the device and skip the insert if one exists.

### WR-03: `_run_and_post_scan` unconditionally trusts `tcp_ports[port]["state"]` to be present

**Files modified:** `capture/port_scan.py`
**Commit:** 2c32125
**Applied fix:** Changed `info["state"]` to `info.get("state")` so a port-info dict missing the `"state"` key (e.g. from a partially-parsed/truncated nmap XML output) is skipped defensively instead of raising a `KeyError` that gets masked by the outer broad `except Exception`.

### WR-04: `derive_status` precedence is undocumented/untested for stale-alert-plus-clean-scan interaction

**Files modified:** `backend/tests/test_capture.py`
**Commit:** 2f334e0
**Applied fix:** Added `test_scan_ingest_clean_scan_keeps_status_elevated_with_old_unacked_alert`, an end-to-end integration test through the real `/api/capture/scan` ingest route. Seeds an old unacknowledged `MALICIOUS_IP` alert, then posts a fully-clean scan result (no risky/unexpected ports for the default `ROUTER` device type), and asserts `Device.security_status` remains `"critical"` — closing the test-coverage gap the review identified (previously only `derive_status`'s own unit tests exercised this interaction in isolation). The review's secondary suggestion (surfacing the *reason* for an elevated status in the UI) was left for a follow-up UI phase, as it is a UX feature addition rather than a defect fix.

### WR-05: `StaticBlocklistSource` has no size/sanity cap on parsed CIDR networks

**Files modified:** `backend/src/services/threat_intel_source.py`
**Commit:** f9442bf
**Applied fix:** Added `_MAX_IPV4_PREFIXLEN = 8` / `_MAX_IPV6_PREFIXLEN = 32` sanity caps; any parsed network wider than these is now rejected with a logged warning instead of silently loaded. Malformed lines also now log a warning instead of silently `continue`-ing. Verified against the vendored `firehol_level1.netset` file: one real entry (`224.0.0.0/3`, a multicast range) is now intentionally rejected by the new cap — an accepted trade-off per the review's explicit recommendation, favoring defense-in-depth against a corrupted feed over loading an overly-broad legitimate entry. Confirmed the unit-test fixture's three CIDRs (`/24`, `/32` IPv4, `/32` IPv6) all remain within the new caps.

## Skipped Issues

None — all 8 in-scope findings were fixed.

---

_Fixed: 2026-06-20T23:31:56Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
