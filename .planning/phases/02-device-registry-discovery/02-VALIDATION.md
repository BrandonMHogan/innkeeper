---
phase: 02
slug: device-registry-discovery
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| 02-TBD | TBD | TBD | DISC-01 | — | ARP/DHCP/mDNS observations fuse into one identity, not fragmented by MAC rotation | unit | `pytest tests/test_identity_resolver.py::test_hostname_fallback_resolver -x` | ❌ W0 | ⬜ pending |
| 02-TBD | TBD | TBD | DISC-01 | T-02-V4 | DHCP ingest endpoint accepts payload, applies same loopback-trust gate as ARP | integration | `pytest tests/test_capture.py::test_dhcp_ingest -x` | ❌ W0 | ⬜ pending |
| 02-TBD | TBD | TBD | DISC-01 | T-02-V4 | mDNS ingest endpoint accepts payload, applies same loopback-trust gate | integration | `pytest tests/test_capture.py::test_mdns_ingest -x` | ❌ W0 | ⬜ pending |
| 02-TBD | TBD | TBD | DISC-02 | T-02-V4/V5 | POST /api/devices registers a device with name/owner/type/trusted | integration | `pytest tests/test_devices.py::test_register_device -x` | ❌ W0 | ⬜ pending |
| 02-TBD | TBD | TBD | DISC-02 | — | Merge endpoint combines an unknown identity into an existing device | integration | `pytest tests/test_devices.py::test_merge_device -x` | ❌ W0 | ⬜ pending |
| 02-TBD | TBD | TBD | DISC-03 | — | first_seen/last_seen update correctly on repeated observations | unit | `pytest tests/test_discovery.py::test_first_last_seen_tracking -x` | ❌ W0 | ⬜ pending |
| 02-TBD | TBD | TBD | DISC-04 | — | Unregistered device appears as "unknown" via GET /api/devices | integration | `pytest tests/test_devices.py::test_unknown_device_listed -x` | ❌ W0 | ⬜ pending |
| 02-TBD | TBD | TBD | DISC-04 | — | Registered device's identity-key change updates same row, doesn't spawn phantom unknown (D-04 regression) | unit | `pytest tests/test_discovery.py::test_registered_identity_key_change_no_phantom -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_identity_resolver.py` — covers DISC-01 fusion logic (hostname primary, MAC fallback, no-hostname case)
- [ ] `backend/tests/test_devices.py` — covers DISC-02/DISC-04 registry CRUD + merge + unknown listing
- [ ] `backend/tests/test_discovery.py` — covers DISC-03 timestamp tracking + the D-04 locked-identity regression case
- [ ] Extend `backend/tests/test_capture.py` — DHCP and mDNS ingest endpoints (mirrors existing `test_arp_ingest*` tests)
- [ ] No new fixtures needed — existing `conftest.py` `test_db`/`client` fixtures (Phase 1) are sufficient

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Docker `network_mode: host` carries mDNS multicast traffic into the capture container the same way it carries ARP/DHCP broadcast | DISC-01 | Multicast-over-host-networking behavior is platform/network dependent and not reliably unit-testable; flagged in RESEARCH.md as an execution-time go/no-go spike | Start capture container on host network, run `python -c "from zeroconf import Zeroconf; ..."` browse on the dev LAN, confirm at least one mDNS service is discovered within 30s; if not, investigate `--network host` vs explicit multicast group join |
| Card grid / unknown-device visual styling matches UI-SPEC | DISC-04 | Visual/UX correctness is not automatable via pytest | Manually load dashboard, confirm unknown devices show dashed border + badge + sorted to top, confirm Register/Merge actions function |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
