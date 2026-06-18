---
phase: 02-device-registry-discovery
verified: 2026-06-18T00:00:00Z
status: gaps_found
score: 4/6 must-haves verified
overrides_applied: 0
gaps:
  - truth: "ARP, DHCP, and mDNS observations fuse into one discovered_identities row keyed by hostname (primary) or MAC (fallback), not fragmented by MAC rotation"
    status: failed
    reason: "Confirmed via direct spot-check: two distinct, unrelated mDNS-only devices (both with no advertised hostname) collapse into a single discovered_identities row because record_observation() is called with a hardcoded placeholder MAC (00:00:00:00:00:00) whenever hostname is absent. This is the opposite failure of the must-have — instead of fusing observations that genuinely belong to the same device, it erroneously merges unrelated devices, silently destroying device data. Reproduced live: 2 separate record_observation() calls for distinct hostname-less mDNS observations produced exactly 1 DiscoveredIdentity row, not 2. Documented as CR-01 in 02-REVIEW.md."
    artifacts:
      - path: "backend/src/routes/capture.py"
        issue: "Lines 130-143: ingest_mdns always builds an Observation with mac='00:00:00:00:00:00' regardless of whether hostname is present; when hostname is also None, HostnameFallbackResolver falls back to mac:00:00:00:00:00:00 for every such device, causing distinct devices to alias onto one identity row."
    missing:
      - "Skip identity resolution (and the record_observation call) when both the MAC is the placeholder and hostname is empty/None, since there is no usable identity signal in that case (per CR-01's suggested fix in 02-REVIEW.md)"
      - "A regression test proving two distinct hostname-less mDNS observations do NOT collapse into one identity"
  - truth: "A user can register a discovered identity into the devices registry with name/owner/type/trusted"
    status: failed
    reason: "The deployed topology is genuinely cross-origin (frontend on port 9999, backend on port 8000, explicit CORS config in backend/src/main.py allowing only settings.frontend_url). frontend/src/lib/api.ts calls GET '/api/devices' and POST '/api/devices' (no trailing slash), but the backend router is mounted with prefix='/api/devices' and handlers declared at '/' — making the canonical path '/api/devices/'. Reproduced live: a direct GET to '/api/devices' (no auth, no redirect-follow) returns HTTP 307 with Location '/api/devices/', not the actual response. Every list/register call from the real frontend therefore round-trips through a same-origin-assuming redirect that is fragile across browsers/proxies for the POST case (method+body replay on 307 is spec-compliant but historically inconsistent), and is simply unnecessary overhead for the GET case. This was already raised as CR-02 in 02-REVIEW.md and is unfixed in the current codebase — pytest's test suite does not catch it because the AsyncClient/ASGITransport test fixture auto-follows redirects and is not exercising real browser fetch+CORS semantics."
    artifacts:
      - path: "frontend/src/lib/api.ts"
        issue: "listDevices() and registerDevice() call apiGet/apiPost with path '/api/devices' (no trailing slash) against a backend canonically mounted at '/api/devices/' — verified to produce an HTTP 307 redirect, not a direct 200/201 response."
    missing:
      - "Match the literal request path to the backend's canonical mount point (e.g. '/api/devices/') in frontend/src/lib/api.ts's listDevices() and registerDevice(), per CR-02's suggested fix in 02-REVIEW.md"
deferred: []
human_verification:
  - test: "Manual LAN verification — confirm at least one real DHCP packet and one real mDNS service observation reach the API end-to-end through the capture container under network_mode: host on macOS/Linux"
    expected: "DhcpEvent and MdnsEvent rows appear in the database from real LAN traffic, not just synthetic payloads"
    why_human: "Requires a live LAN, a running docker compose stack, and observation of actual broadcast/multicast traffic reaching the capture container — not verifiable via static code inspection. Explicitly flagged as deferred-but-required by both 02-02-PLAN.md's <verification> section and 02-02-SUMMARY.md's Next Phase Readiness note ('Manual LAN verification...should happen during phase-level execution per VALIDATION.md before Phase 2 is considered fully done — not blocking, but flagged for the phase verifier')."
  - test: "Manual UAT — load /dashboard against a live backend, confirm unknown devices show dashed border + badge + sorted to top, and confirm Register/Merge actions function end-to-end in a real browser"
    expected: "Dashboard renders correctly, Register and Merge dialogs successfully transition cards in place without a page reload"
    why_human: "Visual/UX correctness and real browser fetch+CORS+redirect behavior (relevant to the CR-02 gap above) cannot be fully proven by static grep/unit tests. 02-03-SUMMARY.md explicitly states this UAT checkpoint 'was not exercised in this automated execution pass (no live backend/browser session available)'."
---

# Phase 2: Device Registry + Discovery Verification Report

**Phase Goal:** A user can see every device on the network — automatically discovered with fused multi-source identity — register the ones they own with name/owner/type, and have unrecognized devices surface as unknown.
**Verified:** 2026-06-18
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ARP, DHCP, and mDNS observations fuse into one discovered_identities row keyed by hostname (primary) or MAC (fallback), not fragmented by MAC rotation | ✗ FAILED | Spot-check reproduced: two distinct hostname-less mDNS observations collapse into 1 DiscoveredIdentity row (should be 2 distinct unknowns, or at minimum not silently merged). Root cause: hardcoded mDNS placeholder MAC `00:00:00:00:00:00` combined with `hostname=None` always resolves to the same identity key. See `backend/src/routes/capture.py:130-143`, `backend/src/services/discovery.py`. Matches 02-REVIEW.md CR-01. |
| 2 | A user can register a discovered identity into the devices registry with name/owner/type/trusted | ✗ FAILED | `POST /api/devices` (frontend literal path, no trailing slash) returns an HTTP 307 redirect rather than the actual response — reproduced live against the real app object. Backend route is canonically `/api/devices/` (`backend/src/routes/devices.py:53,60` mounted with `prefix="/api/devices"`, handlers at `"/"`); frontend calls `/api/devices` (`frontend/src/lib/api.ts:21,33`). Confirmed cross-origin deployment (frontend:9999, backend:8000, explicit CORS allowlist) makes this a real risk, not theoretical. Matches 02-REVIEW.md CR-02. The backend logic for registration itself (when reached directly, bypassing the path mismatch) is correct and covered by passing tests. |
| 3 | Every device and discovered-identity row carries first_seen and last_seen timestamps that update on new observations | ✓ VERIFIED | `Device`/`DiscoveredIdentity` models declare `first_seen`/`last_seen` with `server_default=func.now()` (`backend/src/models/device.py`, `backend/src/models/discovered_identity.py`); `record_observation()`/`upsert_discovered_identity()` update `last_seen` on every observation; `test_first_last_seen_tracking` passes, proving `last_seen` updates while `first_seen` stays fixed across repeated observations. |
| 4 | GET /api/devices returns both registered devices and unregistered (unknown) discovered identities, distinguishable by the caller | ✓ VERIFIED (logic) / ⚠️ at risk via gap #2's path mismatch | `list_devices()` in `backend/src/routes/devices.py:53-57` queries both tables and tags each row `"unknown": bool`; `test_unknown_device_listed` passes. However the same trailing-slash mismatch from gap #2 applies to `listDevices()`'s GET call — browsers auto-follow 307 on GET so this is lower severity than the POST case, but it is the same root defect and is not actually fixed. |
| 5 | A registered device's identity-key change (e.g. hostname rename) updates the same devices row rather than spawning a phantom unknown card | ✓ VERIFIED | `record_observation()` in `backend/src/services/discovery.py:79-87` checks for an existing `Device` row by `last_known_mac` before falling through to the `DiscoveredIdentity` upsert path, updating in place and returning early. `test_registered_identity_key_change_no_phantom` passes, proving no phantom `DiscoveredIdentity` row is created on rename. |
| 6 | No automatic merging ever occurs — merge is only triggered by an explicit user-initiated API call | ✓ VERIFIED | Grep across all phase-modified backend files confirms the only code path that combines a `DiscoveredIdentity` into a `Device` is `POST /api/devices/{id}/merge` (`backend/src/routes/devices.py:87-108`), which requires `Depends(require_auth)` and an explicit `target_device_id` in the request body. `record_observation()`'s Device-branch update (truth #5) updates the existing device's own row in place — it does not combine two separate registry entries, consistent with D-05. `test_merge_device` passes. |

**Score:** 4/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/services/identity_resolver.py` | `class HostnameFallbackResolver` | ✓ VERIFIED | Present, implements D-01/D-02/D-03 hostname-primary/MAC-fallback resolution exactly per plan; `test_identity_resolver.py` (3 tests) passes |
| `backend/src/services/discovery.py` | `async def record_observation` | ✓ VERIFIED (with caveat) | Present, implements orchestration + dialect-aware upsert; correct for the cases tested but does not guard the mDNS placeholder-MAC collision case (gap #1) |
| `backend/src/models/device.py` | `class Device(Base)` | ✓ VERIFIED | 9 `DeviceType` enum members exactly matching plan spec; `identity_key` unique, `trusted` bool present |
| `backend/src/models/discovered_identity.py` | `class DiscoveredIdentity(Base)` | ✓ VERIFIED | Present, `identity_key` unique constraint backs the dialect-aware upsert |
| `backend/src/models/dhcp_event.py` | `class DhcpEvent(Base)` | ✓ VERIFIED | Present, matches plan field spec |
| `backend/src/models/mdns_event.py` | `class MdnsEvent(Base)` | ✓ VERIFIED | Present, matches plan field spec |
| `backend/src/routes/devices.py` | `GET/POST /api/devices`, `POST /api/devices/{id}/merge` | ⚠️ WIRED BUT MISMATCHED | All three handlers exist and are auth-gated, but the canonical path (`/api/devices/`) does not match what the frontend client calls (`/api/devices`) — see gap #2 |
| `backend/alembic/versions/0002_device_registry_discovery.py` | `def upgrade` creating 4 tables | ✓ VERIFIED | All four tables (`dhcp_events`, `mdns_events`, `discovered_identities`, `devices`) created with correct unique constraints and enum; chains off `0001` |
| `capture/capture.py` | DHCP sniff + AsyncZeroconf mDNS browser threads | ✓ VERIFIED | `on_dhcp_packet`, `AsyncZeroconf`, `COMMON_SERVICE_TYPES` all present; single `stop_event` definition confirmed (no second stop mechanism) |
| `capture/requirements.txt` | `zeroconf` pinned | ✓ VERIFIED | `zeroconf==0.148.0` pinned (deviates from orchestrator's stated 0.149.16, corrected by executor against the real PyPI index — documented deviation, not a gap) |
| `frontend/src/lib/components/DeviceCard.svelte` | Registered/unknown card variants | ✓ VERIFIED | 126 lines, both branches present, `HelpCircle`, `formatRelativeTime`, `sr-only` all present per acceptance criteria |
| `frontend/src/lib/components/RegisterDialog.svelte` | Register form dialog | ✓ VERIFIED | 154 lines, calls `registerDevice` (subject to gap #2's path mismatch) |
| `frontend/src/lib/components/MergeDialog.svelte` | Merge picker dialog | ✓ VERIFIED | 116 lines, calls `mergeDevice` (subject to gap #2's path mismatch) |
| `frontend/src/routes/dashboard/+page.svelte` | Summary banner + card grid wired to `listDevices` | ✓ VERIFIED | 117 lines, contains `listDevices`, unknown-first sort logic present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `backend/src/routes/capture.py` | `backend/src/services/discovery.py` | `record_observation()` call from `/dhcp`/`/mdns`/`/arp` | ✓ WIRED | All three ingest handlers call `record_observation` after inserting their raw event row |
| `backend/src/services/discovery.py` | `backend/src/services/identity_resolver.py` | `HostnameFallbackResolver().resolve(observation)` | ✓ WIRED | `record_observation` resolves identity_key via the default resolver each call |
| `backend/src/routes/devices.py` | `backend/src/models/device.py` | `select(Device)` / `Device(...)` | ✓ WIRED | Confirmed in `list_devices`, `register_device`, `merge_device` |
| `frontend/src/routes/dashboard/+page.svelte` | `frontend/src/lib/api.ts` | `listDevices()` call in onMount | ⚠️ WIRED BUT BROKEN AT RUNTIME | Call exists, but the underlying HTTP request targets a mismatched path (gap #2) — link code-level wired, runtime behavior degraded |
| `frontend/src/lib/components/RegisterDialog.svelte` | `frontend/src/lib/api.ts` | `registerDevice()` call on submit | ⚠️ WIRED BUT BROKEN AT RUNTIME | Same path-mismatch issue — POST redirect is the higher-risk case per 02-REVIEW.md CR-02 |
| `frontend/src/lib/components/MergeDialog.svelte` | `frontend/src/lib/api.ts` | `mergeDevice()` call on submit | ✓ WIRED | `mergeDevice` targets `/api/devices/{identityId}/merge` which already includes the correct path shape relative to the router's `{identity_id}/merge` route (no trailing-slash ambiguity for this specific endpoint, since it has a path segment after the prefix) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full backend test suite passes | `pytest backend/tests/ -q --ignore=tests/test_compose.py` | `28 passed, 10 warnings` | ✓ PASS |
| GET /api/devices path-mismatch reproduction | Direct httpx ASGITransport call with `follow_redirects=False` to `/api/devices` | `307, Location: http://test/api/devices/` | ✗ FAIL (confirms gap #2) |
| mDNS placeholder-MAC collision reproduction | Two sequential `record_observation()` calls for distinct hostname-less mDNS observations | `1 DiscoveredIdentity row created (expected 2 distinct identities, or at minimum non-collision)` | ✗ FAIL (confirms gap #1) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|--------------|--------|----------|
| DISC-01 | 02-01, 02-02 | System discovers all devices via ARP/mDNS/DHCP multi-source fingerprinting, handles MAC rotation | ⚠️ PARTIAL | Fusion seam and capture observers exist and are wired, but the mDNS placeholder-MAC collision (gap #1) causes incorrect over-fusion of unrelated devices — directly undermines the "multi-source fingerprinting... not MAC alone" intent |
| DISC-02 | 02-01, 02-03 | User can register a device — name/owner/type/trusted | ⚠️ PARTIAL | Backend logic correct and tested; frontend↔backend path mismatch (gap #2) means the real browser-driven registration flow is unverified/at-risk |
| DISC-03 | 02-01, 02-03 | System tracks/displays first_seen/last_seen | ✓ SATISFIED | Verified at both data-model and test level (truth #3) |
| DISC-04 | 02-01, 02-03 | System detects unregistered device, marks unknown | ⚠️ PARTIAL | Backend list/tag logic correct and tested; same path-mismatch risk as DISC-02 for the live dashboard fetch |

No orphaned requirements — all four DISC IDs declared in REQUIREMENTS.md Phase 2 mapping are claimed across the three plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/src/routes/capture.py` | 138 | Magic placeholder MAC string with no named constant, root-causing gap #1 | 🛑 Blocker (tied to CR-01) | Makes the collision bug harder to spot/fix and easy to reintroduce |
| `frontend/src/lib/api.ts` | 21, 33 | Hardcoded path string mismatched against backend's canonical mount | 🛑 Blocker (tied to CR-02) | Breaks/degrades the primary user-facing register and list flows |
| `backend/src/services/discovery.py` | 82-87 | Device-branch `identity_key` update has no `IntegrityError` handling for collision with another device/identity's key (WR-02 in 02-REVIEW.md) | ⚠️ Warning | Could surface as an unhandled 500 in a rare race; not reproduced here, lower priority than the two blockers above |
| `backend/src/routes/devices.py` | 71-81 | `register_device` has no pre-check for `identity_key` collision before insert (WR-06 in 02-REVIEW.md) | ⚠️ Warning | Same risk class as above — unhandled 500 instead of clean 409 |
| `backend/src/routes/capture.py` | 20-52 | Default-gateway trust source spoofable on the monitored LAN (CR-04 in 02-REVIEW.md) | ⚠️ Warning | Security-relevant but does not block this phase's functional must-haves; flagged for follow-up, not gating Phase 2 completion |

No unresolved `TBD`/`FIXME`/`XXX` markers found in any phase-modified file.

### Human Verification Required

### 1. Manual LAN Verification (DHCP + mDNS reach the API)

**Test:** Run `docker compose up`, generate real DHCP and mDNS traffic on the LAN, confirm `DhcpEvent`/`MdnsEvent` rows are created from real packets (not synthetic test payloads).
**Expected:** At least one real DHCP lease observation and one real mDNS service observation reach `/api/capture/dhcp` and `/api/capture/mdns` respectively.
**Why human:** Requires a live LAN, a running container stack under `network_mode: host`, and observation of actual broadcast/multicast traffic — explicitly deferred by 02-02-PLAN.md's `<verification>` section and flagged again in 02-02-SUMMARY.md as "not blocking, but flagged for the phase verifier."

### 2. Manual UAT — Dashboard Register/Merge Flow in a Real Browser

**Test:** Load `/dashboard` against the live backend in an actual browser, confirm unknown devices render with dashed border + badge sorted to top, and exercise Register and Merge end-to-end.
**Expected:** Cards render correctly; Register/Merge succeed and update the grid in place without a page reload.
**Why human:** Real browser fetch+CORS+redirect semantics (directly relevant to gap #2 above) and visual/UX correctness cannot be fully proven by static analysis or the ASGITransport-based test client. 02-03-SUMMARY.md explicitly states this was "not exercised in this automated execution pass."

### Gaps Summary

Two of six must-haves fail under direct reproduction, both already identified independently by `02-REVIEW.md` (CR-01, CR-02) and confirmed here via live spot-checks against the actual codebase rather than relying on SUMMARY.md claims:

1. **Multi-source fusion produces incorrect over-merging (CR-01).** The mDNS ingest path's hardcoded placeholder MAC, combined with the common real-world case of an mDNS service advertising no hostname, causes unrelated physical devices to alias onto the same `discovered_identities` row. This is a direct violation of the phase goal's "fused multi-source identity" promise — fusion is supposed to consolidate observations of the *same* device, not silently merge *different* devices.

2. **Register/list calls from the real frontend hit a redirect due to a path mismatch (CR-02).** The frontend calls `/api/devices` while the backend's canonical route is `/api/devices/`. This is reproducible today (confirmed via a direct, redirect-disabled HTTP call returning 307) and is a real risk in the actual deployed topology, which is genuinely cross-origin (frontend:9999, backend:8000). The backend's registration/listing logic is itself correct and fully tested — the defect is purely in the literal path string used by the frontend API client, but it sits squarely on the path a user takes to register a device, one of the phase's core promises.

Both gaps were already documented with root cause and fix in `02-REVIEW.md` before this verification ran; this report independently reproduces and confirms them against the current state of the codebase (not the SUMMARY.md narrative, which described the phase as fully complete with "no blockers").

The remaining four must-haves (timestamp tracking, identity-key-change handling, distinguishable list serialization at the backend logic level, and no-automatic-merge) are verified and pass both static and dynamic checks.

These are narrow, well-scoped fixes (a guard clause in `capture.py` and a path string fix in `api.ts`) — not a sign of an unsound architecture. The underlying fusion/registry design is sound; these are implementation bugs in the seams between layers.

---

_Verified: 2026-06-18_
_Verifier: Claude (gsd-verifier)_
