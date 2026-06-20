---
phase: 04-security
verified: 2026-06-20T23:59:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 6/7 (3/4 truths fully verified, 1/4 partial)
  gaps_closed:
    - "The capture container can run an nmap top-1000-port SYN scan against a device's IP and POST the result to the backend (SEC-01, deployed via docker compose)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Confirm SEC-02's push notification delivery is genuinely out of scope for Phase 4 as currently worded in REQUIREMENTS.md"
    expected: "REQUIREMENTS.md's SEC-02 literally says 'sends a push notification' but Phase 4's roadmap success criterion explicitly scopes delivery to Phase 5 ('delivery handled once notifications exist'). This is a deliberate, documented deferral (verified against ROADMAP.md Phase 5 success criterion 4: 'receives a push alert ... when an unknown device joins'), not a phase-4 gap — but a human should confirm REQUIREMENTS.md's SEC-02 checkbox should remain unchecked until Phase 5 actually closes it."
    why_human: "This is a scope/requirements-traceability judgment call across two phases, not something a single phase's codebase state can resolve on its own. Carried forward unchanged from the previous verification pass — it was never a blocker."
---

# Phase 4: Security Verification Report (Re-Verification)

**Phase Goal:** A user can assess the security posture of each device at a glance and be alerted when something concerning happens — an unknown device appears or a device talks to a known-bad destination.
**Verified:** 2026-06-20T23:59:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (commit 3b88fcf)

## What Changed Since Previous Verification

Only one commit touched phase-4 code since the previous (gaps_found) verification pass: `3b88fcf fix(04): add git to capture image and copy port_scan.py/traffic_sniff.py`. It modifies exactly `capture/Dockerfile` (2 lines):

```diff
- && apt-get install -y --no-install-recommends libpcap-dev nmap \
+ && apt-get install -y --no-install-recommends libpcap-dev nmap git \
...
- COPY capture.py .
+ COPY capture.py port_scan.py traffic_sniff.py .
```

No other backend, frontend, or capture source files changed (`git status` confirms a clean tree besides untracked doc files; `git diff --stat` against the prior verification's HEAD shows only the Dockerfile). This re-verification therefore (a) independently reproduces the fix from a cold build, and (b) spot-checks regression on the previously-VERIFIED truths/artifacts, since nothing else in the codebase moved.

## Independent Reproduction of the Fix (not trusting the claim)

| Check | Command | Result |
|-------|---------|--------|
| Clean (no-cache) image build | `docker compose build --no-cache capture` | Succeeded. `git` installs via apt; `netmap` (python-nmap fork) wheel builds successfully from the git+https clone; pip install completes with all deps (scapy, zeroconf, dpkt, httpx, netmap) |
| All 3 required source files present in built image | `docker run --rm --entrypoint sh innkeeper-capture:latest -c "ls -la /app/"` | `capture.py`, `port_scan.py`, `traffic_sniff.py`, `requirements.txt` all present in `/app` |
| Deployment-health probe (de facto compose probe for this project) | `pytest tests/test_compose.py -v` (run directly with `/private/tmp/innkeeper-venv313/bin/python3 -m pytest`, not via SUMMARY narration) | `tests/test_compose.py::test_all_services_healthy PASSED` — 1 passed in 8.50s. The 4-service stack starts healthy via `docker compose up` |
| Full backend suite | `pytest -q` (full backend test directory) | `109 passed, 11 warnings in 19.13s` — matches the claimed 109/109, independently confirmed, includes `test_compose.py` passing as part of the count |

This directly falsifies the previous blocker. The root cause (missing `git` binary blocking the `git+https://` pip dependency clone, plus the missing `COPY` of `port_scan.py`/`traffic_sniff.py`) is fixed at the source: a real apt package addition and a real COPY directive change, verified by rebuilding from scratch (`--no-cache`) rather than relying on Docker layer cache or the executor's prior claim.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can run an open-port scan against any device and see results, with ports flagged as unexpected for that device type | ✓ VERIFIED | Backend/frontend wiring unchanged and re-confirmed (`POST /api/security/scan/{device_id}`, `GET /api/security/scan/{device_id}` in `backend/src/routes/security.py`; `ScanResultDialog.svelte` renders risky/unexpected/expected flags; `evaluate_open_ports()` tested). **The previously-blocking deploy path is now fixed**: `docker compose build --no-cache capture` succeeds, the capture container contains `port_scan.py` and can install `netmap` via `pip` because `git` is now in the image, and `test_compose.py::test_all_services_healthy` passes, confirming the full stack (including capture) starts healthy end-to-end. |
| 2 | Each device card prominently shows a security status of good, warning, or critical derived from scan results | ✓ VERIFIED | Unchanged since prior pass. `DeviceCard.svelte` renders `Badge` with text labels `Good`/`Warning`/`Critical` (re-confirmed at lines 56/59/61), colored via CSS custom properties, never color-only. `security_status`/`last_scanned_at` still serialized in `GET /api/devices` (`backend/src/routes/devices.py:40`). No regression — file untouched since prior verification. |
| 3 | System detects and alerts when a device connects to a known malicious IP or shows suspicious traffic patterns | ✓ VERIFIED | Unchanged since prior pass. `ingest_traffic` calls `is_malicious()` per distinct dst_ip and inserts `MALICIOUS_IP` alerts; `queue_daily_scans` calls `check_bandwidth_anomaly()` and writes `SUSPICIOUS_TRAFFIC` alerts. Both reachable from real execution paths, covered by integration tests, re-confirmed passing in the full 109-test run. |
| 4 | System raises an alert when an unregistered device joins the network (delivery deferred to Phase 5 per roadmap) | ✓ VERIFIED (scope-correct) | Unchanged since prior pass. `upsert_discovered_identity()` inserts exactly one `UNKNOWN_DEVICE` alert on genuinely new identities (`backend/src/services/discovery.py:101`), tested. Push-notification delivery remains an intentional, documented deferral to Phase 5 (carried forward as a human-verification item, not a gap). |

**Score:** 4/4 truths fully verified (up from 3/4 fully + 1/4 partial in the previous pass)

### Required Artifacts (Delta Since Prior Pass)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `capture/Dockerfile` | Installs `git` for git+https pip dep; COPYs all 3 capture-side `.py` files | ✓ VERIFIED | Confirmed via direct file read (lines 3-12) and reproduced via clean `--no-cache` build + in-container `ls /app` |
| `capture/port_scan.py` | nmap wrapper, scan-listener, daily-rescan loops | ✓ VERIFIED — now deployable | Present in built image; module-level unit tests still pass (unchanged) |
| All other artifacts from the previous pass (backend models/routes/services, frontend components) | — | ✓ VERIFIED (unchanged) | No source changes since prior pass besides Dockerfile; spot-checked `devices.py` security_status serialization, `DeviceCard.svelte` badge rendering, `security.py`/`SecurityAlertsBanner.svelte` device_name threading — all intact, `npx svelte-check` still reports 0 errors / 3 pre-existing warnings |

### Key Link Verification (Delta)

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `capture/capture.py` | `capture/port_scan.py` | thread registration | ✓ WIRED **and now reachable in production** | Both threads registered; container that runs this code now actually builds and starts (previously: code-correct but unreachable) |
| `capture/port_scan.py` | backend `/api/capture/*` | httpx calls | ✓ WIRED **and now reachable in production** | Code unchanged and correct; the container executing it now starts successfully via `docker compose up`, closing the previous "never reached in production" finding |
| All other links from prior pass | — | ✓ WIRED (unchanged) | No code changes to these paths; re-confirmed via grep spot-checks |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend test suite passes (full) | `pytest -q` (backend, via venv with installed deps) | `109 passed, 11 warnings in 19.13s` | ✓ PASS |
| `test_compose.py` deployment probe passes | `pytest tests/test_compose.py -v` | `1 passed in 8.50s` | ✓ PASS — this is the exact test that failed in the previous pass |
| Docker capture image builds clean (no cache) | `docker compose build --no-cache capture` | Succeeded; netmap wheel built from git clone, all deps installed | ✓ PASS |
| Capture image contains all 3 source files | `docker run --rm --entrypoint sh innkeeper-capture:latest -c "ls /app"` | `capture.py port_scan.py traffic_sniff.py requirements.txt` | ✓ PASS |
| Frontend type/template check | `npx svelte-check` | `0 ERRORS 3 WARNINGS` (same pre-existing warnings as before) | ✓ PASS — no regression |
| No new debt markers in touched file | `grep TBD\|FIXME\|XXX capture/Dockerfile` | No matches | ✓ PASS |

### Probe Execution

No dedicated `scripts/*/tests/probe-*.sh` probes exist for this phase. `backend/tests/test_compose.py` is the de facto deployment probe and was run directly above (PASSED, independently, not from cache-only `docker compose build`).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|--------------|--------|----------|
| SEC-01 | 04-01, 04-02, 04-03, 04-04 | Open port scan, results display, unexpected-port flagging | ✓ SATISFIED | Backend/frontend fully implemented and tested; capture-container execution path now builds and runs via `docker compose up` (gap closed) |
| SEC-02 | 04-02 | Push notification on unregistered device | ⚠️ PARTIAL BY DESIGN (unchanged, intentional) | Alert-recording half done and tested; push-delivery half explicitly deferred to Phase 5 per ROADMAP.md success criterion 4 — human verification item carried forward, not a phase-4 gap |
| SEC-03 | 04-01, 04-02 | Malicious-IP / suspicious-traffic detection and alerting | ✓ SATISFIED | Unchanged, both signal paths wired and tested |
| SEC-04 | 04-01, 04-02, 04-04 | Security status badge on device card | ✓ SATISFIED | Unchanged, fully verified |

No orphaned requirements.

### Anti-Patterns Found

None in the changed file (`capture/Dockerfile`). No TBD/FIXME/XXX markers. No placeholder/stub patterns introduced. The previous blocker (missing `git` binary breaking `docker compose build`) is resolved with a minimal, correctly-scoped fix — no new anti-patterns introduced by the fix itself.

### Human Verification Required

### 1. Confirm SEC-02 deferral framing (carried forward, unchanged)

**Test:** Review REQUIREMENTS.md's SEC-02 wording against ROADMAP.md Phase 5's success criterion 4.
**Expected:** Confirm this was a deliberate phase split (alert recording in Phase 4, push delivery in Phase 5), not an oversight, and decide whether REQUIREMENTS.md needs an annotation noting the split.
**Why human:** Cross-phase requirements-traceability judgment, not resolvable from Phase 4's codebase alone. This was never a phase-4 blocker and is unaffected by the Dockerfile fix.

### Gaps Summary

No gaps remain. The single blocker identified in the previous verification pass — `capture/Dockerfile` missing the `git` binary required by `python-nmap`'s `git+https://` pip dependency, plus a missing `COPY` of `port_scan.py`/`traffic_sniff.py` — has been fixed in commit `3b88fcf` and independently reproduced here via a clean (`--no-cache`) Docker rebuild, a direct file-presence check inside the built image, and a real `pytest` run of both the targeted `test_compose.py` probe and the full 109-test backend suite (all passing). No other code changed since the previous pass, and spot-checks confirm no regressions in the previously-verified truths, artifacts, or key links. The one remaining open item (SEC-02 push-delivery scope confirmation) is a documented, intentional cross-phase deferral, not a phase-4 gap, and is surfaced as a human-verification item per the original verification pass — it does not block phase completion.

---

_Verified: 2026-06-20T23:59:00Z_
_Verifier: Claude (gsd-verifier)_
