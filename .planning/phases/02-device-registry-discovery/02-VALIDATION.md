---
phase: 02
slug: device-registry-discovery
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-18
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (already configured, `backend/pyproject.toml` `[tool.pytest.ini_options]` `asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` (`testpaths = ["tests"]`) |
| **Quick run command** | `cd backend && pytest tests/test_devices.py tests/test_identity_resolver.py tests/test_discovery.py -x` |
| **Full suite command** | `cd backend && pytest` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_devices.py tests/test_identity_resolver.py tests/test_discovery.py -x`
- **After every plan wave:** Run `cd backend && pytest` (full suite, includes Phase 1's `test_auth.py`/`test_capture.py`/`test_compose.py`/`test_models_scaffold.py`)
- **Before `/gsd-verify-work`:** Full suite must be green; frontend `npm run build && svelte-check` clean
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 02-01 | 1 | DISC-01 | — | `HostnameFallbackResolver` fuses hostname-primary/MAC-fallback identity (D-01/D-02/D-03) | unit | `pytest tests/test_identity_resolver.py::test_hostname_fallback_resolver -x` | ✅ | ⬜ pending |
| 02-01-T1 | 02-01 | 1 | DISC-01 | T-02-06 | Upsert path (not select-then-insert) prevents duplicate identities under concurrent same-key ingest | unit | `pytest tests/test_discovery.py::test_concurrent_same_identity_no_duplicate -x` | ✅ | ⬜ pending |
| 02-01-T1 | 02-01 | 1 | DISC-04 | — | Registered device's identity-key change updates same row, doesn't spawn phantom unknown (D-04/Pitfall 2 regression) | unit | `pytest tests/test_discovery.py::test_registered_identity_key_change_no_phantom -x` | ✅ | ⬜ pending |
| 02-01-T2 | 02-01 | 1 | DISC-01 | T-02-02 | DHCP ingest endpoint accepts payload, applies same loopback-trust gate as ARP | integration | `pytest tests/test_capture.py::test_dhcp_ingest -x` | ✅ | ⬜ pending |
| 02-01-T2 | 02-01 | 1 | DISC-01 | T-02-02 | mDNS ingest endpoint accepts payload, applies same loopback-trust gate | integration | `pytest tests/test_capture.py::test_mdns_ingest -x` | ✅ | ⬜ pending |
| 02-01-T2 | 02-01 | 1 | DISC-02 | T-02-03/T-02-05 | POST /api/devices registers a device with name/owner/type/trusted, rejects invalid type | integration | `pytest tests/test_devices.py::test_register_device tests/test_devices.py::test_register_device_rejects_invalid_type -x` | ✅ | ⬜ pending |
| 02-01-T2 | 02-01 | 1 | DISC-02 | T-02-05 | Merge endpoint combines an unknown identity into an existing device | integration | `pytest tests/test_devices.py::test_merge_device -x` | ✅ | ⬜ pending |
| 02-01-T1 | 02-01 | 1 | DISC-03 | — | first_seen/last_seen update correctly on repeated observations | unit | `pytest tests/test_discovery.py::test_first_last_seen_tracking -x` | ✅ | ⬜ pending |
| 02-01-T2 | 02-01 | 1 | DISC-04 | T-02-05 | Unregistered device appears as "unknown" via GET /api/devices, auth required | integration | `pytest tests/test_devices.py::test_unknown_device_listed tests/test_devices.py::test_devices_requires_auth -x` | ✅ | ⬜ pending |
| 02-02-T2/T3 | 02-02 | 2 | DISC-01 | T-02-SC (02-02) | Real passive DHCP sniff thread and AsyncZeroconf mDNS browser thread feed observations into capture.py's POST-to-API pipeline | manual + integration | See Manual-Only Verifications below (Docker host-network multicast spike) | ✅ | ⬜ pending |
| 02-03-T1/T2 | 02-03 | 2 | DISC-02/04 | — | Dashboard renders device card grid with unknown styling, Register/Merge dialogs wired to real `/api/devices` | manual (UI) | See Manual-Only Verifications below (UI-SPEC visual check) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is embedded inside Wave 1 (Plan 02-01, Tasks 1-2) rather than a separate Wave-0 plan — each item below is delivered as part of 02-01:

- [x] `backend/tests/test_identity_resolver.py` — covers DISC-01 fusion logic (hostname primary, MAC fallback, no-hostname case) — 02-01 Task 1
- [x] `backend/tests/test_devices.py` — covers DISC-02/DISC-04 registry CRUD + merge + unknown listing — 02-01 Task 2
- [x] `backend/tests/test_discovery.py` — covers DISC-03 timestamp tracking + the D-04 locked-identity regression case — 02-01 Task 1
- [x] Extend `backend/tests/test_capture.py` — DHCP and mDNS ingest endpoints (mirrors existing `test_arp_ingest*` tests) — 02-01 Task 2
- [x] No new fixtures needed — existing `conftest.py` `test_db`/`client` fixtures (Phase 1) are sufficient — confirmed in 02-01

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Docker `network_mode: host` carries mDNS multicast traffic into the capture container the same way it carries ARP/DHCP broadcast | DISC-01 | Multicast-over-host-networking behavior is platform/network dependent and not reliably unit-testable; flagged in RESEARCH.md as an execution-time go/no-go spike | Start capture container on host network, run `python -c "from zeroconf import Zeroconf; ..."` browse on the dev LAN, confirm at least one mDNS service is discovered within 30s; if not, investigate `--network host` vs explicit multicast group join |
| Card grid / unknown-device visual styling matches UI-SPEC | DISC-04 | Visual/UX correctness is not automatable via pytest | Manually load dashboard, confirm unknown devices show dashed border + badge + sorted to top, confirm Register/Merge actions function |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — 02-01's two tasks both have `<automated>` pytest verify; 02-02/02-03's UI/hardware-adjacent behaviors are covered under Manual-Only Verifications
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references — all four backend test files created in 02-01
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-18
