---
phase: 04-security
reviewed: 2026-06-20T00:00:00Z
depth: standard
files_reviewed: 30
files_reviewed_list:
  - backend/alembic/versions/0005_security.py
  - backend/src/data/firehol_level1.netset
  - backend/src/main.py
  - backend/src/models/device.py
  - backend/src/models/pending_scan_request.py
  - backend/src/models/port_scan_result.py
  - backend/src/models/security_alert.py
  - backend/src/routes/capture.py
  - backend/src/routes/devices.py
  - backend/src/routes/security.py
  - backend/src/services/bandwidth_anomaly.py
  - backend/src/services/discovery.py
  - backend/src/services/port_rules.py
  - backend/src/services/security_status.py
  - backend/src/services/threat_intel_source.py
  - backend/tests/conftest.py
  - backend/tests/test_bandwidth_anomaly.py
  - backend/tests/test_capture.py
  - backend/tests/test_devices.py
  - backend/tests/test_port_rules.py
  - backend/tests/test_security_alerts.py
  - backend/tests/test_security_scan.py
  - backend/tests/test_security_status.py
  - backend/tests/test_threat_intel.py
  - capture/Dockerfile
  - capture/capture.py
  - capture/port_scan.py
  - capture/requirements-dev.txt
  - capture/requirements.txt
  - capture/test_port_scan.py
  - frontend/src/lib/api.ts
  - frontend/src/lib/components/DeviceCard.svelte
  - frontend/src/lib/components/ScanResultDialog.svelte
  - frontend/src/lib/components/SecurityAlertsBanner.svelte
  - frontend/src/lib/styles/theme.css
  - frontend/src/routes/dashboard/+page.svelte
findings:
  critical: 3
  warning: 5
  info: 4
  total: 12
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-06-20
**Depth:** standard
**Files Reviewed:** 30 (excluding vendored shadcn-svelte UI primitives per review scope note)
**Status:** issues_found

## Summary

Reviewed the Phase 4 (Security) implementation: new `port_scan_results` / `security_alerts` /
`pending_scan_requests` tables, the pure-function security services
(`port_rules.evaluate_open_ports`, `security_status.derive_status`,
`threat_intel_source.StaticBlocklistSource`), the extended `/api/capture/*` ingest routes and new
`/api/security/*` routes, the capture-container `port_scan.py` module wrapping the
`home-assistant-libs/python-nmap` fork, and the frontend security-status badge / scan-result
dialog / alerts banner.

The pure-function services (`derive_status`, `evaluate_open_ports`, `StaticBlocklistSource`) are
correctly table-driven and well-tested. However, the review surfaced a real input-validation gap
on the data that ultimately reaches the capture container's `nmap` subprocess invocation, a broken
end-to-end feature (security alert messages never show the actual device name in the UI), and a
statistical correctness bug in the bandwidth-anomaly comparison that can produce false negatives
on legitimate spike days. The `/api/capture/*` loopback-only trust boundary is also broader than
its own docstrings claim, because it additionally trusts the LAN gateway IP.

## Critical Issues

### CR-01: `Device.last_known_ip` / ARP `src_ip` is never validated as an IP address before reaching the nmap subprocess

**File:** `backend/src/routes/capture.py:66-69,123,139` and `capture/port_scan.py:36`
**Issue:** `ArpEventPayload.src_ip` is typed as a bare `str` (no `pydantic.IPvAnyAddress`, no regex,
no length/charset check). That value is persisted verbatim into `Device.last_known_ip` (a plain
`String(45)` column, also unvalidated), is later returned unmodified by `GET
/api/capture/pending-scans` as `{"ip": device.last_known_ip}`, and is finally passed straight into
`capture/port_scan.py`'s `scanner.scan(hosts=target_ip, arguments=TOP_PORTS_ARGS)`.

The vendored `home-assistant-libs/python-nmap` fork's `scan()` method does:
```python
h_args = shlex.split(hosts)
f_args = shlex.split(arguments)
...
subprocess.Popen([nmap_path, ...] + h_args + f_args + [...], ...)
```
Because `hosts` is `shlex.split()` before being concatenated into the `Popen` argv list, a `src_ip`
string containing spaces (e.g. `"10.0.0.5 --script=vuln 10.0.0.1/24"`, or any string starting with
`-`) is split into *multiple separate argv tokens* and handed to the real `nmap` binary's own
argument parser. No shell is invoked (so classic `;`/`` ` `` shell-injection is not possible), but
this is still nmap CLI **flag/argument injection**: a value flowing from the network into a
privileged scanning subprocess can append arbitrary nmap flags (e.g. additional targets, output
file flags, alternate scan techniques) with no validation anywhere in the pipeline.

While today's real `capture.py` parses the wire ARP packet via Scapy (`pkt[ARP].psrc`), which
yields a dotted-quad string, nothing enforces that invariant at the trust boundary itself — the
`/api/capture/arp` route accepts and persists *any* string from any loopback-trusted caller, and
the model column accepts any string up to 45 chars. This is a real defense-in-depth gap: a bug in a
future capture-side parser, a compromised/buggy loopback-trusted process, or a regression in the
Scapy parsing path would have no fallback containment at the API/DB layer before reaching a
privileged subprocess invocation.

**Fix:** Validate `src_ip` as an actual IP address at the Pydantic boundary, and validate
`target_ip` again immediately before scanning in `port_scan.py`:
```python
# backend/src/routes/capture.py
from pydantic import IPvAnyAddress

class ArpEventPayload(BaseModel):
    src_mac: str
    src_ip: IPvAnyAddress
    dst_ip: IPvAnyAddress
```
```python
# capture/port_scan.py
import ipaddress

def _run_and_post_scan(scanner: nmap.PortScanner, device_id: int, target_ip: str) -> None:
    try:
        ipaddress.ip_address(target_ip)  # raises ValueError on anything but a literal IP
    except ValueError:
        print(f"[capture] refusing to scan invalid target: {target_ip!r}")
        return
    ...
```

### CR-02: Security alert messages in the UI never include the actual device name

**File:** `backend/src/routes/security.py:16-25` and `frontend/src/lib/components/SecurityAlertsBanner.svelte:21-51`
**Issue:** The backend writes fully-formed, device-specific messages into `SecurityAlert.message`
(e.g. `f"{device.name} contacted a known-malicious address"` in `capture.py:296`, `f"{device.name}
has an unexpected open port"` in `capture.py:363`, `f"{device.name} shows unusually high traffic
volume"` in `capture.py:458`). However:

1. `security.py::_serialize_alert()` never includes `device_name` (or the raw `message` field's
   already-correct text) in a form the frontend reads.
2. `SecurityAlertsBanner.svelte` defines `messageFor(alert)` which reconstructs a *generic*
   message from `alert.type`, using `alert.device_name ?? 'A device'` — but `device_name` is never
   sent by the API, so every alert in the UI literally renders as "A device contacted a
   known-malicious address" / "A device has an unexpected open port" / "A device shows unusual
   traffic activity," regardless of which device actually triggered it.
3. The backend's real `alert.message` field (which already says e.g. "Bedroom Camera contacted a
   known-malicious address") is fetched by the frontend (`SecurityAlert` interface even has no
   `message` field declared) but is **never read or rendered anywhere**.

This means the single most useful piece of information in a security alert — which device
triggered it — is silently dropped end-to-end, despite the backend doing the work to compute it.
This is a functional regression in the core "see every device and what it's doing" value
proposition for exactly the surface (security alerts) where it matters most.

**Fix:** Either serialize and render the backend's pre-built `message` directly, or join
`Device.name` in `list_alerts()` and add `device_name` to the response:
```python
# backend/src/routes/security.py
def _serialize_alert(alert: SecurityAlert, device_name: str | None) -> dict:
    return {
        "id": alert.id,
        "device_id": alert.device_id,
        "device_name": device_name,
        "type": alert.type,
        "severity": alert.severity,
        "message": alert.message,
        "created_at": alert.created_at,
        "acknowledged": alert.acknowledged,
    }

@router.get("/alerts")
async def list_alerts(_: None = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(SecurityAlert, Device.name)
            .outerjoin(Device, Device.id == SecurityAlert.device_id)
            .where(SecurityAlert.acknowledged == False)  # noqa: E712
            .order_by(SecurityAlert.created_at.desc())
        )
    ).all()
    return [_serialize_alert(alert, device_name) for alert, device_name in rows]
```
And simplify the frontend to just render `alert.message` (the backend already has the correct
text) instead of re-deriving it from `alert.type`.

### CR-03: `check_bandwidth_anomaly` compares a possibly-partial "most recent day" against a full-day rolling average, producing both false negatives and false positives depending on time-of-day

**File:** `backend/src/services/bandwidth_anomaly.py:46-62`
**Issue:** `daily_totals` is built by grouping `BandwidthMetric` rows by `row.time.date()` over a
14-day window, then the **single most-recent calendar day** (which, at the time this function is
called — e.g. by `queue-daily-scans` at `DAILY_RESCAN_HOUR = 3` local time — is "today," a day that
has only accumulated ~3 hours of traffic so far) is compared against the average of all *other*
(complete) days:
```python
most_recent_day = max(daily_totals.keys())
most_recent_total = daily_totals.pop(most_recent_day)
...
rolling_average = sum(daily_totals.values()) / len(daily_totals)
return most_recent_total > rolling_average * ANOMALY_THRESHOLD_MULTIPLIER
```
Since `queue-daily-scans` (the only real caller) runs once daily at a fixed hour, "today" at that
point has accumulated only a partial day of data relative to the full prior days in the baseline.
This systematically biases the comparison toward **under-counting** anomalies that occur early in a
day relative to the scan time (false negative — a genuine spike late in "yesterday" that rolled
into a new calendar day right before the scan would be diluted), and conversely a device that is
unusually active in just the few hours before the 3am scan could trigger a comparison against a
multi-day average computed from full days, which is not an apples-to-apples comparison either way.
The existing unit tests in `test_bandwidth_anomaly.py` only seed complete daily rows and never
exercise a partial "today" bucket, so this asymmetry is untested.

**Fix:** Either restrict "most recent day" comparison to complete prior 24h windows (rolling
24-hour buckets, not calendar-day buckets keyed off `time.date()`), or explicitly document/test the
partial-day skew and adjust the threshold accordingly:
```python
# Use a trailing 24h window ending "now" instead of calendar-day grouping,
# so the "most recent" bucket is never partial relative to the baseline buckets.
now = datetime.now(timezone.utc)
most_recent_window_start = now - timedelta(hours=24)
...
```

## Warnings

### WR-01: `/api/capture/*` loopback-only trust boundary also trusts the LAN default gateway, broadening the claimed boundary

**File:** `backend/src/routes/capture.py:31-63`
**Issue:** Every docstring on the `/api/capture/*` routes claims "loopback-only" (e.g. `"""Capture
ingest — loopback-only. Capture never writes directly to the DB."""`), but `_TRUSTED_HOSTS` also
includes the auto-detected default gateway IP:
```python
_TRUSTED_HOSTS = frozenset(
    {"127.0.0.1", "::1"} | ({_default_gateway} if _default_gateway else set())
)
```
This means any request whose observed peer address equals the gateway's IP is trusted as if it were
the capture container, even though the comment in `ingest_arp`/`ingest_scan_result`/etc. all say
"loopback-only." In most home-router topologies the gateway never originates HTTP requests to the
backend, so this is unlikely to be exploitable today, but it is a real expansion of the trust
boundary beyond what every route's own docstring promises, and depending on deployment topology
(e.g. backend container not on `network_mode: host`, NAT/hairpin routing scenarios, or a
misconfigured reverse proxy that causes `request.client.host` to reflect the gateway) it could let
an unauthenticated LAN actor reach these endpoints. There is no comment in `capture.py` itself
explaining *why* the gateway needs to be trusted at all (no code path appears to require it — all
ingest traffic in this codebase originates from the capture container on loopback).

**Fix:** Either remove the gateway-trust branch if it isn't actually needed (the capture container
appears to always call the API at `127.0.0.1`/`API_URL` defaulting to loopback per
`capture/port_scan.py:24`), or update every route docstring to accurately describe "loopback or
detected default gateway" and explain the deployment scenario that requires it.

### WR-02: `evaluate_open_ports` / `derive_status` re-derive risk status using only the *latest* scan, silently discarding multiple unacknowledged `unexpected_port` alerts across scans

**File:** `backend/src/routes/capture.py:307-368`
**Issue:** `ingest_scan_result` always inserts a new `SecurityAlert(type=UNEXPECTED_PORT, ...)` row
whenever `unexpected_open` is non-empty, with no de-duplication check against an existing
unacknowledged `UNEXPECTED_PORT` alert for the same device — unlike the `MALICIOUS_IP` and
`SUSPICIOUS_TRAFFIC` alert types, which both have explicit existing-unacknowledged-alert guards
elsewhere in this same file (`capture.py:329-346` and the `queue-daily-scans` dedup check at
`capture.py:441-451`). Every re-scan of a device that still has the same unexpected port open
(e.g. a daily rescan of a device whose owner hasn't acted on the warning yet) creates a brand-new
duplicate `unexpected_port` alert row, unbounded, forever. This is inconsistent with the explicit
de-dup pattern already established for the other two alert types in the same module and will flood
`security_alerts`/the alerts banner with duplicate noise over time.

**Fix:** Apply the same existing-unacknowledged-alert guard used for `MALICIOUS_IP`/`SUSPICIOUS_TRAFFIC`:
```python
existing_unexpected_alert = (
    await db.execute(
        select(SecurityAlert).where(
            SecurityAlert.device_id == device.id,
            SecurityAlert.type == SecurityAlertType.UNEXPECTED_PORT,
            SecurityAlert.acknowledged == False,  # noqa: E712
        )
    )
).scalar_one_or_none()
if unexpected_open and existing_unexpected_alert is None:
    db.add(SecurityAlert(...))
```

### WR-03: `_run_and_post_scan` unconditionally trusts `tcp_ports[port]["state"]` to be a string key without checking for malformed/partial nmap XML output

**File:** `capture/port_scan.py:41-42`
**Issue:**
```python
tcp_ports = scanner[target_ip].get("tcp", {})
open_ports = [port for port, info in tcp_ports.items() if info["state"] == "open"]
```
`info["state"]` is accessed with a plain `[]` index rather than `.get("state")`. If `python-nmap`
ever returns a port-info dict missing the `"state"` key (e.g. a partially-parsed/truncated nmap XML
output, which the wrapped library's own docs note can happen on scan timeout or malformed output),
this raises a `KeyError` from inside the broad `try/except Exception` in the caller — which *is*
caught by the existing handler, so this won't crash the process, but it means the entire scan
result for that host is silently discarded (not even a partial port list is posted), and the
generic exception log line gives no indication that this was a malformed-output issue versus a
network failure. This degrades observability of a real failure mode.

**Fix:** Use `.get("state")` and skip entries defensively rather than relying on the outer
catch-all to mask a more specific failure:
```python
open_ports = [port for port, info in tcp_ports.items() if info.get("state") == "open"]
```

### WR-04: `derive_status` precedence is undocumented/untested for the case where `risky_open_ports` is empty but stale unacknowledged malicious-IP/bandwidth signals coexist with a now-clean scan

**File:** `backend/src/services/security_status.py:10-26`, exercised by `backend/src/routes/capture.py:324-354`
**Issue:** `derive_status` itself is a clean pure function and well covered by
`test_security_status.py`. However, the *caller* in `ingest_scan_result` recomputes
`has_malicious_ip_match`/`has_bandwidth_anomaly` from "any unacknowledged alert of that type still
exists" each time a new scan result arrives — meaning a device's security status can flip back to
`CRITICAL`/`WARNING` purely because of an old, already-detected-and-alerted issue from days ago that
the user simply hasn't acknowledged yet, even though the *new* scan itself is completely clean. This
is plausibly intentional per the D-07 comment ("each signal source independently contributes — a
clean scan result must not silently clear a prior...signal"), but there's no test exercising this
specific interaction (an old unacknowledged alert + a fresh clean scan → status stays
elevated), and the UI gives no indication *why* a device shows critical/warning when its latest
scan is shown as fully "expected" in `ScanResultDialog.svelte` — a user inspecting scan results for
a device flagged Critical, after a malicious-IP contact days ago that they haven't acknowledged,
will see an all-green/expected port list with no explanation for the Critical badge.

**Fix:** Add an integration test for "old unacknowledged alert + new clean scan keeps elevated
status," and consider surfacing the *reason* for an elevated status in the UI (e.g. the scan dialog
or device card showing "Critical: unacknowledged malicious-IP alert" rather than just a bare
"Critical" badge with no scan-port explanation).

### WR-05: `StaticBlocklistSource.__init__` reads the entire 4591-line blocklist file and builds an `ipaddress.ip_network` list with no size/sanity cap, and `is_malicious` is O(n) over that list per call

**File:** `backend/src/services/threat_intel_source.py:17-34`
**Issue:** Not a performance defect per the v1 scope exclusion, but worth flagging as a
maintainability/robustness gap: there is no upper bound on how large the vendored
`firehol_level1.netset` file can grow before this becomes a problem, and a malformed but
"successfully parsed" huge CIDR (e.g. `0.0.0.0/0` accidentally present in an updated feed) would
silently match every single IP as malicious with no validation/sanity check on network size. Given
`get_default_threat_intel_source()` is a process-lifetime singleton, a future remote-feed source
update mechanism (mentioned in the D-10 docstring) inheriting this same lack-of-bounds-checking
pattern could silently degrade `is_malicious()` into "always true."

**Fix:** Add a basic sanity check rejecting overly broad networks (e.g. reject any parsed network
wider than `/8` for IPv4 or `/32` for IPv6 as defensive validation against a corrupted feed), and
log a warning when skipping malformed lines instead of silently `continue`-ing.

## Info

### IN-01: `_MAX_OPEN_PORTS = 1000` magic-number comment claims to "mirror nmap's own top-1000 default scan scope" but the actual nmap invocation passes no `-p` flag and no explicit limit is enforced on the capture side

**File:** `backend/src/routes/capture.py:99-100` and `capture/port_scan.py:25`
**Issue:** `TOP_PORTS_ARGS = "-sS"` (capture/port_scan.py) relies entirely on nmap's own internal
default of scanning its top 1000 ports — there is no `-p` flag, no `--top-ports 1000` passed
explicitly. If a future nmap version changes its default top-ports count, or if `TOP_PORTS_ARGS` is
ever edited to add `-p-` (all 65535 ports) without remembering to also bump
`_MAX_OPEN_PORTS` on the backend, the two constants will silently drift out of sync and the backend
will start rejecting legitimate scan results with a 413.
**Fix:** Pass `--top-ports 1000` explicitly in `TOP_PORTS_ARGS` so the relationship between the two
constants is enforced by the actual scan command, not by an implicit assumption about nmap's
default.

### IN-02: `evaluate_open_ports`'s docstring says "any device" for `RISKY_PORTS` but `3306`/`1433` comments single out "exposed beyond loopback" as a caveat that the function cannot actually evaluate

**File:** `backend/src/services/port_rules.py:16`
**Issue:** The comment on port 3306 says `# MySQL default — only risky if exposed beyond loopback,
still flag` — but `evaluate_open_ports` has no concept of loopback-vs-LAN exposure; it only
receives a flat list of open ports from an nmap scan run *against* the device's LAN IP, so any port
in this list is by definition already externally reachable from the scanning host. The comment
describes a distinction the function cannot make and may confuse future maintainers into thinking
there's a loopback-detection branch that doesn't exist.
**Fix:** Simplify the comment to state plainly that any port reported "open" by the nmap scan is, by
construction, reachable from the LAN (not loopback-local), removing the misleading caveat.

### IN-03: `_serialize_device` in `devices.py` and `_serialize_alert` in `security.py` duplicate the same dict-construction pattern with no shared serializer helper

**File:** `backend/src/routes/devices.py:28-42`, `backend/src/routes/security.py:16-25`
**Issue:** Minor duplication; not a defect, but both modules hand-roll near-identical
dict-serialization boilerplate (id/timestamps/etc.) that could be a shared Pydantic response model
instead of an ad hoc dict, which would also have caught CR-02 above at type-checking time (a
`SecurityAlertResponse` Pydantic model with a required `device_name: str | None` field would force
every code path constructing the response to supply it).
**Fix:** Consider introducing Pydantic response models for these routes in a follow-up phase.

### IN-04: `port_scan.py`'s `run_daily_rescan_loop` computes `next_run` using naive local time (`dt.datetime.now()`) with no timezone handling, while the rest of the security subsystem is consistently UTC-aware

**File:** `capture/port_scan.py:68-91`
**Issue:** Every other timestamp in this phase's code (`datetime.now(timezone.utc)` throughout
`capture.py`/`bandwidth_anomaly.py`/etc.) is explicitly UTC-aware, but `run_daily_rescan_loop` uses
naive `dt.datetime.now()` to compute "3am local time." This is likely intentional (the docstring
says "hour-of-day (local time)"), but it means the daily-rescan trigger's exact wall-clock moment is
dependent on the container's configured timezone (which Docker containers default to UTC unless
explicitly configured otherwise) — on a default UTC container, "3am local" is just "3am UTC," which
may not match the household's actual local night-time, defeating the apparent intent of running
scans during low-usage hours.
**Fix:** Either explicitly document that `DAILY_RESCAN_HOUR` is UTC (and rename the constant/docstring
accordingly), or read a `TZ` environment variable explicitly rather than relying on implicit
container-timezone configuration.

---

_Reviewed: 2026-06-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
