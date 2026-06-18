---
phase: 02-device-registry-discovery
reviewed: 2026-06-18T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - backend/src/routes/capture.py
  - backend/tests/test_capture.py
  - frontend/src/lib/api.ts
  - backend/tests/test_devices.py
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 02: Code Review Report (gap-closure re-review, plan 02-04)

**Reviewed:** 2026-06-18
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

This re-review targets the gap-closure changes from plan 02-04, which addressed two previously-documented defects: CR-01 (mDNS placeholder-MAC over-fusion of distinct hostname-less devices) and CR-02 (frontend/backend trailing-slash path mismatch on `/api/devices`).

**Both CR-01 and CR-02 are confirmed resolved.**

- **CR-01 (resolved):** `backend/src/routes/capture.py:139-140` now returns early with `{"ok": True, "skipped": "no identity signal"}` whenever `payload.hostname` is `None` or blank, before `record_observation` is ever called. The placeholder MAC `00:00:00:00:00:00` (now named `_MDNS_PLACEHOLDER_MAC`) is only used for hostname-bearing mDNS events, where the resolver's primary hostname-keying path (`HostnameFallbackResolver.resolve`) takes over and the placeholder MAC is irrelevant to key derivation. `test_mdns_ingest_without_hostname_does_not_collide` directly reproduces the original bug scenario (two distinct hostname-less mDNS observations) and asserts zero `DiscoveredIdentity` rows are created, and `test_mdns_ingest_with_hostname_still_resolves_identity` proves the legitimate fusion path still works. Both tests pass per the diff and exercise the exact code path that previously collapsed unrelated devices.

- **CR-02 (resolved):** `frontend/src/lib/api.ts:21,33` now call `/api/devices/` (trailing slash) for both `listDevices()` and `registerDevice()`, matching the backend's canonical mount point. `test_list_devices_canonical_path_no_redirect` in `test_devices.py` proves the canonical path returns `200` with no redirect, while the old broken literal (`/api/devices`, no slash) still 307-redirects — confirming the frontend now hits the canonical path directly rather than relying on a redirect round-trip.

However, the CR-01 fix exposes a new cross-device data-corruption path that was previously masked by the bug it fixed (see CR-05 below), and a couple of smaller robustness/quality issues remain in the changed files.

## Critical Issues

### CR-05: Shared mDNS placeholder MAC still causes cross-device `identity_key` hijacking once any mDNS-derived identity is registered or merged

**File:** `backend/src/routes/capture.py:139-151`, `backend/src/services/discovery.py:79-87`, `backend/src/routes/devices.py:71-77,104`
**Issue:** The CR-01 fix correctly stops *hostname-less* mDNS observations from reaching `record_observation`, but every surviving (hostname-bearing) mDNS observation still calls `record_observation` with `mac=_MDNS_PLACEHOLDER_MAC` ("00:00:00:00:00:00") — by design, since mDNS browsing yields no real MAC. This is fine in isolation because `HostnameFallbackResolver.resolve()` keys hostname-bearing observations by hostname, not MAC.

The problem appears later: if a user registers (`POST /api/devices/`) or merges (`POST /api/devices/{id}/merge`) a `DiscoveredIdentity` that originated from an mDNS-only observation, `identity.mac` is the placeholder, and `register_device`/`merge_device` copy it verbatim into `Device.last_known_mac` (`devices.py:77` and `devices.py:104`). That `Device` row now permanently has `last_known_mac = "00:00:00:00:00:00"`.

From that point on, `record_observation`'s Device-branch fast path (`discovery.py:79`: `select(Device).where(Device.last_known_mac == observation.mac)`) matches **any** subsequent mDNS observation for **any other device**, because every hostname-bearing mDNS observation still carries the same placeholder MAC. The match is found regardless of whether the new observation's hostname has anything to do with the registered device, and the code unconditionally overwrites `device.identity_key`, `device.last_known_mac`, and `device.last_seen` (`discovery.py:82-86`) — silently renaming/corrupting an unrelated registered device's identity based on a completely different physical device's mDNS broadcast. This is a wider blast radius than the original CR-01 bug: instead of two unknown identities colliding, a single registered (named, owned, trusted) device can be silently hijacked by any other device on the network announcing itself over mDNS.
**Fix:** Exclude the placeholder MAC from the Device-branch lookup entirely, since it is never a real, device-specific MAC:
```python
async def record_observation(db, observation, resolver=None):
    resolver = resolver or HostnameFallbackResolver()
    identity_key = resolver.resolve(observation)

    if observation.mac == _MDNS_PLACEHOLDER_MAC:
        # Placeholder MAC is shared across all hostname-bearing mDNS
        # observations and must never be used to match an existing Device
        # by last_known_mac — fall through to the hostname-keyed upsert path.
        await upsert_discovered_identity(
            db, identity_key=identity_key, mac=observation.mac,
            hostname=observation.hostname, seen_at=observation.observed_at,
        )
        return

    result = await db.execute(select(Device).where(Device.last_known_mac == observation.mac))
    ...
```
(Import or pass `_MDNS_PLACEHOLDER_MAC` from `capture.py`, or better, hoist the constant to a shared module like `identity_resolver.py` so `discovery.py` doesn't need to import from a route module.) Additionally, `register_device`/`merge_device` should refuse to set `Device.last_known_mac` to the placeholder value in the first place — e.g., leave the device's existing `last_known_mac` unchanged (or null/sentinel it explicitly) when `identity.mac == _MDNS_PLACEHOLDER_MAC`, since a placeholder is not a real "last known MAC" for that device. Add a regression test: register an mDNS-only identity into a Device, then post a second, unrelated mDNS observation with a different hostname, and assert the first Device's `identity_key`/`name` are unaffected.

## Warnings

### WR-08: `test_arp_ingest_accepts_detected_gateway` monkeypatches the wrong abstraction layer, masking a real-world gap in gateway-trust testing

**File:** `backend/tests/test_capture.py:143-177`
**Issue:** This test monkeypatches `capture_module._TRUSTED_HOSTS` directly to inject a fake gateway IP, rather than exercising `_detect_default_gateway()` + the module-level `_TRUSTED_HOSTS` computation that actually runs at import time in production. This proves the membership-check `if client_host not in _TRUSTED_HOSTS` works, which is useful, but it provides no coverage at all for whether `_detect_default_gateway()` correctly parses a real `/proc/net/route`-shaped file and produces the expected dotted-quad IP (the only test for that function, `test_detect_default_gateway_fails_safe_on_bad_path`, only checks the failure path with a nonexistent file). A bug in the hex-to-IP conversion logic (e.g., wrong byte order) would not be caught by either test.
**Fix:** Add a test that writes a synthetic `/proc/net/route`-formatted file (with a known gateway hex value) to a temp path, points `_PROC_NET_ROUTE_PATH` at it via monkeypatch, and asserts `_detect_default_gateway()` returns the expected dotted-quad IP — exercising the real parsing logic end-to-end instead of only the membership-check consumer.

### WR-09: `ingest_mdns`'s early-return skip path produces no audit signal beyond the response body

**File:** `backend/src/routes/capture.py:139-140`
**Issue:** When an mDNS event is skipped for lack of identity signal, the function returns `{"ok": True, "skipped": "no identity signal"}` with no server-side logging. Since capture-sidecar responses aren't inspected by anything except (optionally) the sidecar's own log line on non-2xx, operators have no way to see how often mDNS events are being skipped (e.g., to gauge whether most devices on their LAN advertise mDNS without a hostname, which would be useful operational visibility into discovery effectiveness). This is a minor observability gap, not a correctness bug.
**Fix:** Add a debug-level log line (e.g., `logger.debug("mdns event skipped: no hostname", extra={"service_type": payload.service_type})`) alongside the early return.

## Info

### IN-05: `_MDNS_PLACEHOLDER_MAC` constant is now named but its single remaining consumer (`record_observation`'s Device-branch) still needs the literal re-derived independently in `discovery.py`

**File:** `backend/src/routes/capture.py:18`, `backend/src/services/discovery.py` (no reference)
**Issue:** The CR-01 fix correctly extracted `_MDNS_PLACEHOLDER_MAC` as a named constant in `capture.py`, addressing the old IN-02 finding. However, the fix for CR-05 above (if implemented) would need this same sentinel value inside `discovery.py`, which currently has no knowledge of "this MAC is a placeholder, not a real device fingerprint." Keeping the constant defined only in the route module creates a layering smell: a service module (`discovery.py`) would need to import a sentinel from a route module, or the value would have to be duplicated. This is purely a heads-up for whoever fixes CR-05, not a standalone defect in the currently-reviewed files.
**Fix:** When addressing CR-05, move `_MDNS_PLACEHOLDER_MAC` to a shared location (e.g., `identity_resolver.py`, which already owns MAC/hostname-keying concerns) so both `capture.py` and `discovery.py` can import the same constant.

---

_Reviewed: 2026-06-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
