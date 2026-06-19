---
phase: 02-device-registry-discovery
verified: 2026-06-18T01:00:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/6
  gaps_closed:
    - "ARP, DHCP, and mDNS observations fuse into one discovered_identities row keyed by hostname (primary) or MAC (fallback), not fragmented by MAC rotation (CR-01, closed by 02-04)"
    - "A user can register a discovered identity into the devices registry with name/owner/type/trusted (CR-02, closed by 02-04)"
  gaps_remaining: []
  regressions: []
---

# Phase 2: Device Registry + Discovery Verification Report

**Phase Goal:** A user can see every device on the network — automatically discovered with fused multi-source identity — register the ones they own with name/owner/type, and have unrecognized devices surface as unknown.
**Verified:** 2026-06-18
**Status:** human_needed
**Re-verification:** Yes — second pass, after gap-closure plans 02-04 (CR-01, CR-02) and 02-05 (CR-05, discovered during code review of 02-04)

## Summary of Re-Verification

The prior verification (02-VERIFICATION.md, now superseded) found 2 of 6 must-have truths FAILED: CR-01 (mDNS placeholder-MAC over-fusion of unrelated devices) and CR-02 (frontend/backend trailing-slash path mismatch causing 307 redirects). Plan 02-04 closed both. A subsequent code review of 02-04's diff (02-REVIEW.md, gap-closure re-review) discovered a third, more severe issue not previously caught: CR-05, a device-hijacking bug where the surviving hostname-bearing mDNS path still shared one placeholder MAC across devices, allowing any later mDNS observation to silently overwrite an unrelated *registered* device's `identity_key`/`last_known_mac` once that device had ever been registered/merged from an mDNS-only identity. Plan 02-05 closed CR-05.

This pass re-verifies all 6 original must-have truths via direct, independent reproduction (not SUMMARY.md narrative), with focused scrutiny on the three named reproduction scenarios in the verification brief, plus a full run of the backend test suite.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ARP, DHCP, and mDNS observations fuse into one discovered_identities row keyed by hostname (primary) or MAC (fallback), not fragmented by MAC rotation, and distinct hostname-less mDNS observations are never silently merged into one identity | ✓ VERIFIED | Reproduced live via the real HTTP ingest path (`POST /api/capture/mdns` twice, both with `hostname=None`, distinct `addresses`): both calls return `201 {"ok": true, "skipped": "no identity signal"}` and **0** `DiscoveredIdentity` rows are created (was 1 in the prior pass). Root-cause fix: `backend/src/routes/capture.py:138-139` skips `record_observation` entirely when `payload.hostname` is falsy, since a hostname-less mDNS observation carries no usable identity signal. Hostname-bearing mDNS fusion is unaffected — `test_mdns_ingest_with_hostname_still_resolves_identity` passes. |
| 2 | A user can register a discovered identity into the devices registry with name/owner/type/trusted | ✓ VERIFIED | Reproduced live: `GET /api/devices/` (the frontend's literal call path, `frontend/src/lib/api.ts:21`) returns `401` (auth-gated, normal response) — not `307`. The control case, `GET /api/devices` (old non-canonical path, no trailing slash) still returns `307` with `Location: http://test/api/devices/`, confirming the fix is the trailing slash, not a change in FastAPI's redirect behavior generally. `frontend/src/lib/api.ts:21,33` both target `/api/devices/`. `register_device` logic (devices.py:61-85) verified correct and now also guards against persisting the mDNS placeholder MAC (see truth re CR-05 below). |
| 3 | Every device and discovered-identity row carries first_seen and last_seen timestamps that update on new observations | ✓ VERIFIED | Unchanged from prior pass; re-ran `test_first_last_seen_tracking` directly — PASSED. No regression. |
| 4 | GET /api/devices returns both registered devices and unregistered (unknown) discovered identities, distinguishable by the caller | ✓ VERIFIED | `list_devices()` (`backend/src/routes/devices.py:54-58`) queries both tables and tags each `"unknown": bool`. The previously-flagged path-mismatch risk is now closed (truth #2) — `listDevices()` calls the canonical `/api/devices/` path directly, no redirect dependency. `test_unknown_device_listed` passes. |
| 5 | A registered device's identity-key change (e.g. hostname rename) updates the same devices row rather than spawning a phantom unknown card | ✓ VERIFIED | Re-ran `test_registered_identity_key_change_no_phantom` directly — PASSED. Also independently confirmed `test_record_observation_non_placeholder_mac_still_matches_device` (new in 02-05) proves the CR-05 fix's placeholder exclusion does not regress this behavior for real, non-placeholder MACs. |
| 6 | No automatic merging ever occurs — merge is only triggered by an explicit user-initiated API call, AND a registered device's identity can never be silently hijacked by an unrelated device's observation | ✓ VERIFIED (truth scope widened post-CR-05) | Grep confirms the only code path combining a `DiscoveredIdentity` into a `Device` is the explicit, auth-gated `POST /api/devices/{id}/merge`. Additionally, reproduced the CR-05 hijack scenario directly: seeded a registered `Device` (`identity_key="host:living-room-speaker"`, `last_known_mac=MDNS_PLACEHOLDER_MAC`), then called `record_observation` with an unrelated `Observation(mac=MDNS_PLACEHOLDER_MAC, hostname="someone-elses-phone", ...)`. Result: the registered Device's `identity_key`, `name`, and `last_known_mac` are all **unchanged**; the unrelated observation instead correctly created its own separate `DiscoveredIdentity` row (`host:someone-elses-phone`). Confirms `discovery.py:90-98`'s placeholder-MAC exclusion from the Device-branch lookup works as designed, and `devices.py:78,105` independently refuse to ever persist the placeholder into `Device.last_known_mac` (defense-in-depth, also verified via passing `test_register_device_with_placeholder_mac_does_not_persist_placeholder` and `test_merge_device_with_placeholder_mac_does_not_overwrite_last_known_mac`). |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/services/identity_resolver.py` | `MDNS_PLACEHOLDER_MAC` shared constant | ✓ VERIFIED | Defined once (line 10), single source of truth, imported by `capture.py`, `discovery.py`, `devices.py` — no duplicate local definitions remain (`capture.py`'s old `_MDNS_PLACEHOLDER_MAC` is gone per grep) |
| `backend/src/routes/capture.py` | Guard skipping `record_observation` when hostname absent | ✓ VERIFIED | Lines 138-139: `if not payload.hostname or not payload.hostname.strip(): return {"ok": True, "skipped": "no identity signal"}` — confirmed via direct HTTP reproduction above |
| `backend/src/services/discovery.py` | `record_observation` excludes placeholder MAC from Device-branch lookup | ✓ VERIFIED | Lines 90-98: placeholder-MAC observations route straight to `upsert_discovered_identity` and `return` before the `select(Device)` query at line 100 ever runs |
| `backend/src/routes/devices.py` | `register_device`/`merge_device` refuse to persist placeholder into `last_known_mac` | ✓ VERIFIED | Line 78 (`None if identity.mac == MDNS_PLACEHOLDER_MAC else identity.mac`), line 105 (`if identity.mac != MDNS_PLACEHOLDER_MAC: device.last_known_mac = identity.mac`) |
| `backend/src/models/device.py` | `last_known_mac` nullable to support the None-on-placeholder write | ✓ VERIFIED | `Mapped[str | None]`, `nullable=True` (line 35); migration `0002` matches (`nullable=True`, line 71) — consistent end-to-end |
| `frontend/src/lib/api.ts` | `listDevices`/`registerDevice` target canonical `/api/devices/` | ✓ VERIFIED | Lines 21, 33 — both call `/api/devices/` (trailing slash); `mergeDevice` correctly left unchanged (no trailing-slash ambiguity for that route) |
| `backend/tests/test_capture.py` | Regression tests for CR-01 | ✓ VERIFIED | `test_mdns_ingest_without_hostname_does_not_collide`, `test_mdns_ingest_with_hostname_still_resolves_identity` both present and PASS |
| `backend/tests/test_devices.py` | Regression tests for CR-02, CR-05 (write-path) | ✓ VERIFIED | `test_list_devices_canonical_path_no_redirect`, `test_register_device_with_placeholder_mac_does_not_persist_placeholder`, `test_merge_device_with_placeholder_mac_does_not_overwrite_last_known_mac` all present and PASS |
| `backend/tests/test_discovery.py` | Regression tests for CR-05 (match-path) | ✓ VERIFIED | `test_placeholder_mac_observation_does_not_hijack_registered_device`, `test_record_observation_non_placeholder_mac_still_matches_device` both present and PASS |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `backend/src/routes/capture.py` | `backend/src/services/discovery.py` | `record_observation()` call, now conditionally skipped | ✓ WIRED | mDNS path correctly skips the call when no identity signal; ARP/DHCP paths unaffected and still call it unconditionally |
| `backend/src/services/discovery.py` | `backend/src/services/identity_resolver.py` | Import of shared `MDNS_PLACEHOLDER_MAC` | ✓ WIRED | `discovery.py:10-15` imports it alongside `HostnameFallbackResolver`/`Observation` |
| `backend/src/routes/devices.py` | `backend/src/services/identity_resolver.py` | Import of shared `MDNS_PLACEHOLDER_MAC` | ✓ WIRED | `devices.py:10` |
| `frontend/src/routes/dashboard/+page.svelte` | `frontend/src/lib/api.ts` | `listDevices()` call in onMount | ✓ WIRED (no longer redirect-dependent) | Call targets canonical path directly |
| `frontend/src/lib/components/RegisterDialog.svelte` | `frontend/src/lib/api.ts` | `registerDevice()` call on submit | ✓ WIRED (no longer redirect-dependent) | Call targets canonical path directly |
| `frontend/src/lib/components/MergeDialog.svelte` | `frontend/src/lib/api.ts` | `mergeDevice()` call on submit | ✓ WIRED | Unchanged, already correct |

### Behavioral Spot-Checks (Direct Reproduction, Re-Verifier's Own Process)

| Behavior | Command/Method | Result | Status |
|----------|---------|--------|--------|
| Full backend test suite passes | `/private/tmp/innkeeper-venv313/bin/python -m pytest tests/ -q --ignore=tests/test_compose.py` (run directly by verifier, not trusted from SUMMARY.md) | `35 passed, 13 warnings` | ✓ PASS |
| CR-01 reproduction: two distinct hostname-less mDNS observations via real HTTP ingest path | `POST /api/capture/mdns` x2 with `hostname=None`, distinct addresses, then query `DiscoveredIdentity` | Both return `201 {"skipped": "no identity signal"}`; **0** `DiscoveredIdentity` rows created (was 1 in prior pass) | ✓ PASS — gap closed |
| CR-02 reproduction: GET canonical vs. non-canonical path | `follow_redirects=False` httpx call: `GET /api/devices/` and `GET /api/devices` | Canonical `/api/devices/` → `401` (no redirect); non-canonical `/api/devices` → `307, Location: http://test/api/devices/` (control case, confirms FastAPI's redirect_slashes still exists generally, just not on the path the frontend now uses) | ✓ PASS — gap closed |
| CR-05 reproduction: registered Device hijack via unrelated mDNS observation | Seed `Device(identity_key="host:living-room-speaker", last_known_mac=MDNS_PLACEHOLDER_MAC)`, then `record_observation(Observation(mac=MDNS_PLACEHOLDER_MAC, hostname="someone-elses-phone", ...))` | Device's `identity_key`/`name`/`last_known_mac` all unchanged; a separate `DiscoveredIdentity` row (`host:someone-elses-phone`) was created instead | ✓ PASS — gap closed |
| Direct `record_observation()` calls (not via HTTP/capture.py guard) with two hostname-less placeholder-MAC observations | Bypassing the capture.py guard, calling `record_observation` directly twice with `hostname=None` | 1 `DiscoveredIdentity` row (both resolve to `mac:00:00:00:00:00:00`) | ℹ️ Informational — see note below; not a gap, since the actual ingest path (capture.py) never calls `record_observation` in this case |

**Note on the informational spot-check above:** `record_observation()` itself, called directly with two hostname-less, placeholder-MAC observations (bypassing `capture.py`'s guard), still resolves both to the same `mac:00:00:00:00:00:00` identity key and collapses to 1 row — this is unsurprising, since `HostnameFallbackResolver.resolve()` is pure and has no knowledge of "skip" semantics; the actual fix is the **call-site guard in `capture.py`**, which is the only code path that ever produces an `Observation` with `mac=MDNS_PLACEHOLDER_MAC, hostname=None` in production (ARP/DHCP observations always carry a real MAC; only mDNS uses the placeholder, and the guard prevents `record_observation` from ever being invoked with a falsy hostname in that case). The HTTP-level reproduction above is the correct test of the user-facing behavior and confirms 0 rows are created. This is not a gap — it is documented here for completeness and to show the verifier checked the boundary case rather than assuming the fix at the wrong layer.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|--------------|--------|----------|
| DISC-01 | 02-01, 02-02, 02-04, 02-05 | System discovers all devices via ARP/mDNS/DHCP multi-source fingerprinting, handles MAC rotation, fusion must not corrupt unrelated devices | ✓ SATISFIED | CR-01 (over-fusion) and CR-05 (cross-device hijack) both closed and reproduced fixed; fusion logic now correctly distinguishes "no usable signal → skip" from "shared placeholder → never matches an unrelated registered Device" |
| DISC-02 | 02-01, 02-03, 02-04, 02-05 | User can register a device — name/owner/type/trusted | ✓ SATISFIED | CR-02 path mismatch closed (canonical path returns 200/401, not 307); register/merge write paths independently guard against placeholder-MAC corruption (CR-05 defense-in-depth) |
| DISC-03 | 02-01, 02-03 | System tracks/displays first_seen/last_seen | ✓ SATISFIED | Verified at data-model and test level; no regression across gap-closure plans |
| DISC-04 | 02-01, 02-03, 02-04, 02-05 | System detects unregistered device, marks unknown | ✓ SATISFIED | Backend list/tag logic correct and tested; path-mismatch risk closed; hijack risk closed |

No orphaned requirements — all four DISC IDs declared in REQUIREMENTS.md Phase 2 mapping are claimed across the five plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/alembic/versions/0002_device_registry_discovery.py` | (whole file, in-place edit history) | Migration `0002` edited in place twice (once in 02-04/02-05 context) to relax `last_known_mac` to nullable, with no in-file comment documenting the edit history or the "safe only because unreleased" assumption (WR-09 in 02-REVIEW.md) | ⚠️ Warning | Not a functional defect for this phase — `0002` has genuinely never shipped outside this branch — but no enforced guard exists against a future regression of this practice once the migration does ship. Tracked as WR-09, explicitly out of scope for the gap-closure plans' success criteria. |
| `backend/tests/test_capture.py` | (carried forward, unchanged) | `test_arp_ingest_accepts_detected_gateway` monkeypatches `_TRUSTED_HOSTS` directly rather than exercising `_detect_default_gateway()`'s hex-to-IP conversion end-to-end (WR-08 in 02-REVIEW.md) | ⚠️ Warning | Pre-existing test-coverage gap, unrelated to this phase's gap-closure plans, not introduced or worsened by 02-04/02-05 |
| `backend/src/routes/capture.py` | 20-52 | Default-gateway trust source spoofable on the monitored LAN (CR-04 in 02-REVIEW.md, unrelated to gap-closure) | ⚠️ Warning | Security-relevant but explicitly out of scope for this phase's functional must-haves; flagged for follow-up |

No unresolved `TBD`/`FIXME`/`XXX` markers found in any phase-modified file (only legitimate references to the `MDNS_PLACEHOLDER_MAC`/"placeholder" feature name, not debt markers).

All three blockers from the prior verification pass (the two anti-patterns tied to CR-01/CR-02) are resolved: the magic placeholder-MAC string is now a named constant (`MDNS_PLACEHOLDER_MAC`, single source of truth in `identity_resolver.py`), and the frontend path literal now matches the backend's canonical mount point.

### Human Verification Required

### 1. Manual LAN Verification (DHCP + mDNS reach the API)

**Test:** Run `docker compose up`, generate real DHCP and mDNS traffic on the LAN, confirm `DhcpEvent`/`MdnsEvent` rows are created from real packets (not synthetic test payloads).
**Expected:** At least one real DHCP lease observation and one real mDNS service observation reach `/api/capture/dhcp` and `/api/capture/mdns` respectively.
**Why human:** Requires a live LAN, a running container stack under `network_mode: host`, and observation of actual broadcast/multicast traffic — explicitly deferred by 02-02-PLAN.md's `<verification>` section, flagged again in 02-02-SUMMARY.md, and unchanged by the CR-01/CR-02/CR-05 gap-closure plans (none of which touched the capture container's network-level behavior). Still outstanding — no new evidence found that this was exercised.

### 2. Manual UAT — Dashboard Register/Merge Flow in a Real Browser

**Test:** Load `/dashboard` against the live backend in an actual browser, confirm unknown devices render with dashed border + badge sorted to top, and exercise Register and Merge end-to-end — including confirming that registering/merging an mDNS-only (placeholder-MAC) device behaves correctly in the UI (e.g. does not display a bogus MAC address for `last_known_mac=None`).
**Expected:** Cards render correctly; Register/Merge succeed and update the grid in place without a page reload; mDNS-only devices with `last_known_mac=None` render sensibly (no "None" or blank-MAC display bug).
**Why human:** Real browser fetch+CORS semantics, visual/UX correctness, and the newly-introduced `last_known_mac: null` rendering case cannot be fully proven by static analysis or the ASGITransport-based test client. No evidence found that this was exercised in any of the three execution passes (02-03, 02-04, 02-05) — all explicitly note no live browser session was used.

### Gaps Summary

No gaps remain. All three originally-identified critical issues are independently reproduced as fixed in this verification pass:

1. **CR-01 (mDNS over-fusion)** — confirmed closed via direct HTTP-level reproduction: two distinct hostname-less mDNS observations now produce 0 `DiscoveredIdentity` rows (not 1), because `capture.py`'s guard clause skips `record_observation` entirely when there is no usable identity signal.
2. **CR-02 (path mismatch / 307 redirect)** — confirmed closed via direct reproduction: `GET /api/devices/` (the frontend's literal call) now returns `401` (auth-gated, normal) rather than `307`; the control case (`GET /api/devices`, the old broken literal) still correctly 307-redirects, proving the fix is the path literal, not a change to FastAPI's general redirect behavior.
3. **CR-05 (cross-device hijack via shared placeholder MAC)** — discovered during code review of the CR-01 fix, confirmed closed via direct reproduction: a registered Device seeded with the placeholder MAC is NOT hijacked by an unrelated device's later mDNS observation; the unrelated observation correctly creates its own separate `DiscoveredIdentity` row instead.

The full backend test suite (35 tests) was run directly by the verifier (not trusted from SUMMARY.md) and passes with zero failures, zero regressions.

Two human-verification items remain outstanding from the original verification pass — a manual LAN test (real DHCP/mDNS traffic reaching the capture container) and a manual browser UAT pass (dashboard register/merge flow, now also including a check that the new `last_known_mac: null` case renders sensibly in the UI). Neither is a code-level gap; both require a live environment not available to static/automated verification. Per the status decision tree, the presence of these human-verification items routes this report to `human_needed` rather than `passed`, even though all 6 must-have truths are independently verified at the code level.

---

_Verified: 2026-06-18_
_Verifier: Claude (gsd-verifier)_
