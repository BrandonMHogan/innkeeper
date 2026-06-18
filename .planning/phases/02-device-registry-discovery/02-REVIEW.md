---
phase: 02-device-registry-discovery
reviewed: 2026-06-18T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - backend/src/services/identity_resolver.py
  - backend/src/services/discovery.py
  - backend/src/routes/capture.py
  - backend/src/routes/devices.py
  - backend/src/models/device.py
  - backend/alembic/versions/0002_device_registry_discovery.py
  - backend/tests/test_discovery.py
  - backend/tests/test_devices.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 02: Code Review Report (gap-closure re-review, plan 02-05)

**Reviewed:** 2026-06-18
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

This re-review targets plan 02-05, which fixed CR-05 — the shared mDNS placeholder MAC (`00:00:00:00:00:00`) hijacking a registered device's identity once that device's `Device.last_known_mac` had ever been set to the placeholder. The fix has three parts: (1) hoist the constant to `identity_resolver.py` as `MDNS_PLACEHOLDER_MAC`, the single shared definition; (2) exclude placeholder-MAC observations from `discovery.py`'s `record_observation` Device-branch lookup, routing them to the hostname-keyed `DiscoveredIdentity` upsert instead; (3) guard `register_device`/`merge_device` in `devices.py` so the placeholder is never written into `Device.last_known_mac`, which required making the column nullable (model + in-place edit of the still-unreleased migration `0002`).

**CR-05 is confirmed resolved.** I traced every path that writes or reads `Device.last_known_mac` and every path that resolves an observation's identity, and found no remaining route by which the placeholder can match or overwrite an unrelated registered `Device`:

- `discovery.py:90-98` — placeholder-MAC observations now return immediately via `upsert_discovered_identity` (hostname-keyed `DiscoveredIdentity` upsert) and never reach the `select(Device).where(Device.last_known_mac == observation.mac)` lookup at line 100. Since `MDNS_PLACEHOLDER_MAC` is excluded up front, even a `Device` row that still has `last_known_mac == MDNS_PLACEHOLDER_MAC` (e.g., one registered before this fix shipped, or via a pre-fix data state) can no longer be matched by a subsequent placeholder-MAC observation — the lookup is skipped entirely for that MAC value, not just newly-prevented from being set.
- `devices.py:78` — `register_device` sets `last_known_mac=None if identity.mac == MDNS_PLACEHOLDER_MAC else identity.mac`, so a newly registered mDNS-only identity gets `last_known_mac=None`, not the placeholder.
- `devices.py:105-106` — `merge_device` only overwrites `device.last_known_mac` when `identity.mac != MDNS_PLACEHOLDER_MAC`, so merging a placeholder-MAC identity into an existing device leaves that device's real MAC untouched (and never sets it to the placeholder either).
- The nullable schema change (`Device.last_known_mac: str | None`, migration column `nullable=True`) is required for `register_device` to legally persist `None`, and is consistent end-to-end: model, migration, and the one INSERT path that uses it.
- Test coverage directly proves the closed loophole: `test_placeholder_mac_observation_does_not_hijack_registered_device` (`test_discovery.py:83-115`) seeds a registered `Device` with `last_known_mac=MDNS_PLACEHOLDER_MAC` (simulating a device that slipped through pre-fix, or any future regression) and asserts a second, unrelated mDNS observation does not rename it — this is the exact CR-05 reproduction scenario from the prior review's `Fix` recommendation. `test_register_device_with_placeholder_mac_does_not_persist_placeholder` and `test_merge_device_with_placeholder_mac_does_not_overwrite_last_known_mac` (`test_devices.py:114-158`) cover the two write paths.

CR-01 and CR-02 (resolved in earlier gap-closure passes, not touched by this diff) remain resolved — nothing in this diff reintroduces the original hostname-less mDNS collision or the trailing-slash mismatch.

Two warnings and one informational item remain; none block this fix, but one warning is new (the in-place migration edit) and is worth flagging given the project's general migration-immutability norms even though it's justified here by the migration being unreleased.

## Warnings

### WR-08: `test_arp_ingest_accepts_detected_gateway` monkeypatches the wrong abstraction layer, masking a real-world gap in gateway-trust testing

**File:** `backend/tests/test_capture.py:143-177` (not in this diff's file set, carried forward — unchanged since prior review)
**Issue:** This test monkeypatches `capture_module._TRUSTED_HOSTS` directly to inject a fake gateway IP, rather than exercising `_detect_default_gateway()` + the module-level `_TRUSTED_HOSTS` computation that actually runs at import time in production. The only test that exercises `_detect_default_gateway()` itself, `test_detect_default_gateway_fails_safe_on_bad_path`, only checks the failure path with a nonexistent file. A bug in the hex-to-IP byte-order conversion in `capture.py:42` would not be caught by either test.
**Fix:** Add a test that writes a synthetic `/proc/net/route`-formatted file (with a known gateway hex value) to a temp path, points `_PROC_NET_ROUTE_PATH` at it via monkeypatch, and asserts `_detect_default_gateway()` returns the expected dotted-quad IP.

### WR-09: In-place migration edit to make `last_known_mac` nullable relies entirely on the migration being unreleased — no test guards against this assumption breaking

**File:** `backend/alembic/versions/0002_device_registry_discovery.py:71`
**Issue:** This gap-closure plan edited `0002_device_registry_discovery.py` in place (`nullable=False` to `nullable=True` on `last_known_mac`, both in the migration and in `src/models/device.py`) rather than adding a new revision. This is the correct move only because `0002` has never shipped to a real deployment — editing an already-applied migration in place would silently desync any environment that already ran the old version (its `devices.last_known_mac` column would still be `NOT NULL` in the actual database, while the model and any fresh `alembic upgrade head` elsewhere would assume nullable, causing an `IntegrityError` the first time `register_device` tries to insert `last_known_mac=None`). There is no test or migration-state check anywhere in the suite that would catch a future regression of this kind (e.g., someone editing `0002` in place again after it has shipped), and nothing in the codebase documents "0002 is unreleased, in-place edits are safe until release X" as an explicit, enforced rule — it's tribal knowledge captured only in the plan/commit description, not in the migration file itself.
**Fix:** Add a one-line comment in the migration header noting the in-place-edit history and the cutoff (e.g., "edited in place 2026-06-18 to relax last_known_mac to nullable — safe only because this revision is unreleased; once released, future changes to this column MUST use a new revision"). Optionally, add a CI guard (e.g., a pre-commit/CI check that diffs already-tagged-as-released migration files against a frozen snapshot) if this project anticipates more pre-release gap-closure cycles that touch migrations.

## Info

### IN-06: `Device.last_known_mac` is now nullable for every device, not just mDNS-only ones, slightly widening the column's "unknown state" surface

**File:** `backend/src/models/device.py:35`
**Issue:** The nullability fix is correct and minimal, but it has the side effect of making `last_known_mac` nullable for *every* `Device` row, including ones registered from ARP/DHCP-derived identities that always carry a real MAC. There's no `CHECK` constraint or service-layer invariant stating "this column is only ever `NULL` when the device was registered/merged from a placeholder-MAC (mDNS-only) identity" — a future code path could set it to `None` for an unrelated reason without anything flagging that as suspicious. This is a minor schema-precision gap, not a functional bug, since no current code path sets it to `None` except the one intentional case.
**Fix:** Consider a brief model-level docstring note on `last_known_mac` clarifying that `None` specifically means "registered/merged from an mDNS-only (placeholder-MAC) identity, no real MAC observed yet" so future maintainers don't conflate it with "MAC unknown for some other reason."

---

_Reviewed: 2026-06-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
