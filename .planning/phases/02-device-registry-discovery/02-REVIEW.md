---
phase: 02-device-registry-discovery
reviewed: 2026-06-18T00:00:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - backend/alembic/versions/0002_device_registry_discovery.py
  - backend/src/main.py
  - backend/src/models/__init__.py
  - backend/src/models/device.py
  - backend/src/models/dhcp_event.py
  - backend/src/models/discovered_identity.py
  - backend/src/models/mdns_event.py
  - backend/src/routes/capture.py
  - backend/src/routes/devices.py
  - backend/src/services/discovery.py
  - backend/src/services/identity_resolver.py
  - backend/tests/test_capture.py
  - backend/tests/test_devices.py
  - backend/tests/test_discovery.py
  - backend/tests/test_identity_resolver.py
  - capture/capture.py
  - capture/requirements.txt
  - frontend/src/lib/api.ts
  - frontend/src/lib/components/DeviceCard.svelte
  - frontend/src/lib/components/MergeDialog.svelte
  - frontend/src/lib/components/RegisterDialog.svelte
  - frontend/src/routes/dashboard/+page.svelte
findings:
  critical: 4
  warning: 7
  info: 4
  total: 15
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-06-18
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

This phase introduces the device registry + multi-source discovery pipeline: capture ingest routes (ARP/DHCP/mDNS), an identity resolver, a fused `discovered_identities` table, the `devices` registry, and frontend register/merge UI. The core upsert pattern (dialect-aware `ON CONFLICT DO UPDATE`) is sound and the loopback-trust mechanism for capture ingest is a reasonable design. However, there are real correctness gaps: a route-trailing-slash mismatch between frontend and backend that will silently break every device list/register/merge call path in certain client configurations, an mDNS placeholder MAC that causes multiple distinct mDNS-only devices to collide into a single identity/device, a TOCTOU race in `record_observation` between the Device lookup and the upsert that can leave a registered device's row stale, and a default-gateway trust check that can be defeated by IP spoofing on home networks where the host network mode is used. Several lower-severity robustness and quality issues are also present (unbounded MAC/hostname validation, missing `merge_device` identity_key handling commentary, broad exception swallowing in the capture proof-of-concept).

## Critical Issues

### CR-01: mDNS observations with no hostname collide onto a single placeholder-MAC identity

**File:** `backend/src/routes/capture.py:130-143`
**Issue:** Every mDNS event POST builds an `Observation` with `mac="00:00:00:00:00:00"`. When `payload.hostname` is also `None` (a valid input — the Pydantic model allows `hostname: str | None = None`), `HostnameFallbackResolver.resolve()` falls back to `mac:00:00:00:00:00:00` for every such device. This means any number of distinct, unrelated mDNS-only devices with no advertised hostname collapse into the exact same `discovered_identities` row (last-write-wins via the upsert), silently destroying device data and creating an incorrect single "unknown device" card on the dashboard regardless of how many physical devices were actually observed.
**Fix:** Skip identity resolution entirely (and skip the observation) when both the MAC is the placeholder and hostname is empty, since there's no usable identity signal:
```python
if not payload.hostname:
    return {"ok": True, "skipped": "no identity signal"}

await record_observation(
    db,
    Observation(mac="00:00:00:00:00:00", hostname=payload.hostname, source="mdns", observed_at=datetime.utcnow()),
)
```

### CR-02: Frontend calls `/api/devices` (no trailing slash) against a backend mounted at `/api/devices/`

**File:** `frontend/src/lib/api.ts:21,33`; `backend/src/routes/devices.py:53,60`
**Issue:** `listDevices()` calls `apiGet('/api/devices')` and `registerDevice()` calls `apiPost('/api/devices', payload)`, but the FastAPI router is mounted with `prefix="/api/devices"` and the route handlers are declared at `"/"` (i.e., the canonical path is `/api/devices/`). FastAPI's default `redirect_slashes=True` will issue a 307 redirect from `/api/devices` to `/api/devices/`. For the GET this mostly survives via fetch's automatic redirect-follow, but for the **POST** to `register_device`, a 307 redirect must replay the same method and body — this is only guaranteed by spec-compliant clients, and combined with `credentials: 'include'` cross-origin behavior (frontend dev server and backend run on different origins per CORS config in `main.py`) this is fragile and has historically broken in various browsers/proxies. It is also simply incorrect/wasteful to rely on a redirect round trip for every device-list/register call.
**Fix:** Match the path exactly to avoid the redirect hop:
```typescript
export async function listDevices(): Promise<unknown[]> {
  const res = await apiGet('/api/devices/');
  ...
}
export async function registerDevice(...): Promise<Response> {
  return apiPost('/api/devices/', payload);
}
```

### CR-03: TOCTOU race between Device lookup and DiscoveredIdentity upsert in `record_observation`

**File:** `backend/src/services/discovery.py:79-95`
**Issue:** `record_observation` first does a plain `SELECT` to check whether a `Device` already exists for `observation.mac`, and only if none is found does it fall through to `upsert_discovered_identity`. Between the `SELECT` and the eventual `commit()`, a concurrent request for the same MAC (e.g., near-simultaneous ARP + DHCP packets from the capture sidecar, which posts independently per packet type) can interleave: both requests see no Device row, both proceed to `upsert_discovered_identity`. The upsert itself is race-safe for the `discovered_identities` table (ON CONFLICT), so no duplicate row is created — but if a `Device` is registered for that MAC in between the SELECT and the second observation's commit, the second write goes to the wrong table/path. This is a narrower window than the "Pitfall 5" race the code explicitly addresses for `discovered_identities`, but the Device-vs-Identity branch itself is not given the same protection.
**Fix:** Either wrap the read+branch+write in a single transaction with `SELECT ... FOR UPDATE`, or accept the existing race as a known limitation but document it explicitly (the current docstring claims the Device branch prevents "phantom unknown card" issues without acknowledging the concurrent-write window). At minimum, add a regression test with two concurrent `record_observation` calls racing a `Device` registration.

### CR-04: Default-gateway trust source is attacker-controllable on the LAN the capture container monitors

**File:** `backend/src/routes/capture.py:20-52`
**Issue:** `_TRUSTED_HOSTS` is computed once at import time from `/proc/net/route` and includes the detected default gateway IP. The capture container runs with `network_mode: host` (per `capture/capture.py` docstring) on the same LAN it's sniffing. Any device on that LAN can spoof its source IP (via ARP spoofing or IP spoofing on networks without strict reverse-path filtering) to match the gateway's IP and successfully pass the `client_host in _TRUSTED_HOSTS` check, allowing an attacker to inject arbitrary forged ARP/DHCP/mDNS observations directly into the registry via `/api/capture/*` endpoints (no auth required on these routes — they rely solely on source-IP trust). Because `request.client.host` reflects the IP layer, not strong proof of identity, this is a meaningful authorization bypass beyond the loopback case the comments imply protection against ("Capture ingest is loopback-only" — but the code trusts more than loopback).
**Fix:** Either (a) restrict capture ingest to true loopback only (`127.0.0.1`/`::1`) and have the capture sidecar always run as a co-located process/container reachable only via loopback (drop the gateway-IP trust path entirely), or (b) authenticate the capture sidecar with a shared secret/token instead of relying on source IP, which is the standard mitigation for this exact spoofing class of bug.

## Warnings

### WR-01: `merge_device` discards the merged identity's `identity_key` and `hostname` without any handling

**File:** `backend/src/routes/devices.py:104-107`
**Issue:** When merging a `DiscoveredIdentity` into an existing `Device`, only `last_known_mac` and `last_seen` are copied onto the device; `identity.hostname` and `identity.identity_key` are dropped entirely (the identity row is deleted at line 106). If the merged identity had richer hostname/enrichment data than the existing device, that data is permanently lost with no audit trail and no way to recover it. There's also no check that `identity.identity_key` isn't already claimed by a *different* device (would silently coexist under stale data).
**Fix:** At minimum log/preserve the dropped hostname (e.g., update `device.name` if blank, or store the prior hostname in a notes/aliases field), and add a code comment documenting this is an intentional one-way data-loss operation if that's the accepted design.

### WR-02: `record_observation` device-branch update is not validated against `identity_key` collisions

**File:** `backend/src/services/discovery.py:82-87`
**Issue:** When an observation matches an existing `Device` by `last_known_mac`, the code blindly overwrites `device.identity_key = identity_key` without checking whether that `identity_key` is already in use by a *different* device or a `DiscoveredIdentity` row. Since `identity_key` has a `UniqueConstraint` (see migration `0002`, line 75), this can raise an `IntegrityError` on commit if two devices' hostnames coincidentally resolve to the same key (e.g., DHCP lease handed off between two devices both briefly reporting the same hostname), crashing the ingest request with an unhandled 500 instead of a graceful conflict resolution.
**Fix:** Catch `IntegrityError` around the commit and either skip the identity_key update or merge the conflicting rows, with a clear comment on the chosen policy.

### WR-03: `_detect_default_gateway` parses `/proc/net/route` with no upper bound on lines, and uses `bytes.fromhex` without verifying field length

**File:** `backend/src/routes/capture.py:28-46`
**Issue:** `gateway_hex = fields[gateway_idx]` is fed directly into `bytes.fromhex(...)[::-1]`. If the route table format ever differs (e.g., IPv6 routes mixed in non-standard kernels, or a malformed/truncated line), `bytes.fromhex` can produce a byte string of unexpected length, and `socket.inet_ntoa` will raise `socket.error`/`OSError` for anything other than exactly 4 bytes — this isn't in the caught exception tuple `(OSError, ValueError, IndexError)`. Actually `socket.error` is an alias for `OSError` in Python 3, so this particular case is covered, but the broader point stands: this is fragile low-level parsing for a security-relevant trust decision, executed once at import time with no logging when it silently fails to None.
**Fix:** Add a log statement (even just to stdout) when gateway detection fails, since this directly affects what's trusted at runtime, and operators have no visibility into why capture ingest is rejecting requests.

### WR-04: Capture proof-of-concept swallows all exceptions broadly in three different places

**File:** `capture/capture.py:55-58, 91-94, 116-118`
**Issue:** `except Exception as exc:` after every POST attempt catches everything including `KeyboardInterrupt`-adjacent issues is avoided (good, since `KeyboardInterrupt` derives from `BaseException` not `Exception`), but the catches mean any persistent backend outage (e.g., backend down for an extended deploy) is silently logged to stdout per-packet with no backoff, rate limiting, or circuit breaker — under any moderately busy LAN this could produce thousands of error lines per minute and mask the fact that no data is being captured at all.
**Fix:** Add basic exponential backoff / circuit-breaker logic, or at least rate-limit the log line (e.g., log once per N failures).

### WR-05: `DhcpEventPayload.src_mac` / `ArpEventPayload.src_mac` have no format validation

**File:** `backend/src/routes/capture.py:55-65`
**Issue:** `src_mac: str` accepts any string. Since `HostnameFallbackResolver.resolve()` does `f"mac:{observation.mac.lower()}"` with no format check, malformed MAC strings (wrong length, non-hex chars, or carrying injected characters) flow straight into `identity_key` and the `devices.last_known_mac` / `dhcp_events.src_mac` columns (`String(17)` — exactly fits `aa:bb:cc:dd:ee:ff`). A malformed but same-length string would pass DB constraints and corrupt the registry with a bogus identity that looks valid in the UI.
**Fix:** Add a Pydantic validator (regex `^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$`) to `ArpEventPayload.src_mac` and `DhcpEventPayload.src_mac`.

### WR-06: `register_device` does not verify the `DiscoveredIdentity.identity_key` doesn't already collide with an existing `Device.identity_key`

**File:** `backend/src/routes/devices.py:60-84`
**Issue:** `Device(identity_key=identity.identity_key, ...)` is inserted without checking for a pre-existing `Device` row sharing that `identity_key`. Given the `UniqueConstraint` on `devices.identity_key`, this will raise an unhandled `IntegrityError` → 500 response on conflict rather than a clean `409 Conflict` with an actionable message, which is a notably worse UX/debuggability outcome than the other 404 checks already present in the same function.
**Fix:**
```python
existing = await db.execute(select(Device).where(Device.identity_key == identity.identity_key))
if existing.scalar_one_or_none() is not None:
    raise HTTPException(status_code=409, detail="A device with this identity already exists")
```

### WR-07: `list_devices` returns an untyped, heterogeneous list mixing two different shapes with no pagination

**File:** `backend/src/routes/devices.py:53-57`
**Issue:** The endpoint concatenates serialized `Device` and `DiscoveredIdentity` rows into a single flat list distinguished only by the ad hoc `"unknown"` boolean key, with no `response_model` declared on the route, so FastAPI/OpenAPI consumers get no schema/type safety and the frontend (`frontend/src/lib/api.ts` `listDevices(): Promise<unknown[]>`) has to trust runtime shape entirely. There's also no limit/pagination, so this will not scale gracefully as the registry grows, though that aspect is out of scope per project policy (performance not in v1 review scope) — the type-safety gap is the quality issue being flagged here.
**Fix:** Add a `response_model=list[DeviceOrIdentityOut]` (a Pydantic discriminated union) so OpenAPI/clients get a real contract instead of `dict`.

## Info

### IN-01: `Observation.observed_at` uses `datetime.utcnow()` (deprecated, naive datetime)

**File:** `backend/src/routes/capture.py:87,110,141`
**Issue:** `datetime.utcnow()` is deprecated since Python 3.12 in favor of `datetime.now(datetime.UTC)`, and produces a naive datetime that gets stored against `TIMESTAMP(timezone=True)` columns — SQLAlchemy/asyncpg will implicitly assume it's in the session's local timezone unless explicitly configured, risking subtle timezone bugs in `first_seen`/`last_seen` comparisons (e.g., `merge_device`'s `max(identity.last_seen, device.last_seen)`).
**Fix:** Use `datetime.now(datetime.UTC)` consistently across all three capture routes.

### IN-02: Magic placeholder MAC string repeated as a literal

**File:** `backend/src/routes/capture.py:138`
**Issue:** `"00:00:00:00:00:00"` is a magic string with no named constant, making it easy to miss when grepping for "all MAC handling" logic or when this sentinel needs to change.
**Fix:** Extract to a module-level constant, e.g. `_MDNS_PLACEHOLDER_MAC = "00:00:00:00:00:00"`.

### IN-03: `DeviceCard.svelte` inline styling duplicated extensively instead of using shared CSS classes/utility classes

**File:** `frontend/src/lib/components/DeviceCard.svelte:63-111`
**Issue:** Nearly every element carries a long inline `style="..."` string repeating spacing/typography tokens already expressed as CSS custom properties elsewhere in the project. This is a maintainability cost (e.g., changing card padding requires touching N components) but is a style preference, not a correctness issue, so kept at Info severity.
**Fix:** Extract repeated style blocks into scoped `<style>` classes or a shared utility layer.

### IN-04: `test_devices.py` `_seed_device` omits `first_seen`/`last_seen` overrides used by other tests, relying entirely on server defaults

**File:** `backend/tests/test_devices.py:32-46`
**Issue:** Not a production bug, flagged for awareness only: this helper never sets `first_seen`/`last_seen`, relying on `server_default=sa.func.now()`. Under SQLite (the test backend) `server_default` for `TIMESTAMP` is evaluated, but the column lacks an explicit Python-side `default=` to match (compare `discovered_identities`/`devices` models, which only declare `server_default`). If a future test asserts ordering by `first_seen` across rows seeded via this helper and other helpers using explicit timestamps, the implicit "now" timestamp could sort unexpectedly relative to deliberately-dated fixtures like `_seed_identity`'s `datetime(2026, 1, 1)`.
**Fix:** No action required now; consider adding explicit timestamps if temporal-ordering tests are added later.

---

_Reviewed: 2026-06-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
