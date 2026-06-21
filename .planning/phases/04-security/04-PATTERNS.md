# Phase 4: Security - Pattern Map

**Mapped:** 2026-06-20
**Files analyzed:** 16
**Analogs found:** 14 / 16

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `backend/src/models/port_scan_result.py` | model | CRUD | `backend/src/models/traffic_flow.py` | role-match (event-row model) |
| `backend/src/models/security_alert.py` | model | CRUD | `backend/src/models/arp_event.py` | role-match (simple event/log row) |
| `backend/src/models/pending_scan_request.py` | model | CRUD | `backend/src/models/arp_event.py` | role-match (simple queue-row) |
| `backend/src/models/device.py` (modify — add `security_status`, `last_scanned_at`) | model | CRUD | itself (existing) | exact (in-place extension) |
| `backend/src/services/port_rules.py` | utility/service | transform | `backend/src/services/domain_grouping.py` | role-match (pure-function table-driven transform) |
| `backend/src/services/security_status.py` | service | transform | `backend/src/services/domain_grouping.py` | role-match (pure derivation function) |
| `backend/src/services/threat_intel_source.py` | service | file-I/O + transform | `backend/src/services/bandwidth_source.py` | exact (Protocol + concrete impl swappable-source) |
| `backend/src/services/bandwidth_anomaly.py` | service | CRUD (read-only query) | `backend/src/routes/traffic.py` (`device_bandwidth`/`_resolve_device_macs`) | role-match (aggregation query over `bandwidth_metrics`) |
| `backend/src/routes/security.py` | route/controller | request-response | `backend/src/routes/traffic.py` | role-match (auth-gated GET/POST query routes) |
| `backend/src/routes/capture.py` (modify — add `/scan`, `/pending-scans`) | route/controller | event-driven (ingest) | itself (existing `/arp`,`/dhcp`,`/mdns`,`/traffic` routes) | exact (extend same file, same pattern) |
| `backend/src/routes/devices.py` (modify — serializer gains `security_status`) | route/controller | CRUD | itself (existing `_serialize_device`) | exact (in-place extension) |
| `backend/src/data/firehol_level1.netset` | config/data | file-I/O | (none — new data asset) | no analog (vendored static file) |
| `capture/port_scan.py` | utility | event-driven | `capture/traffic_sniff.py` | role-match (capture-module, POST-to-API discipline) |
| `capture/capture.py` (modify — add scan-listener + daily-rescan threads) | event-driven loop | event-driven | itself (existing ARP/DHCP/mDNS/traffic threads) | exact (extend same file, same thread convention) |
| `frontend/src/lib/components/DeviceCard.svelte` (modify — badge + Scan button) | component | request-response | itself (existing) | exact (in-place extension) |
| `frontend/src/lib/components/SecurityAlertsBanner.svelte` | component | request-response | `frontend/src/lib/components/DestinationsBreakdown.svelte` (not read but same shape) / `frontend/src/routes/dashboard/+page.svelte`'s inline summary banner | role-match |

## Pattern Assignments

### `backend/src/models/security_alert.py` (model, CRUD)

**Analog:** `backend/src/models/arp_event.py` (read in full, 19 lines) and `backend/src/models/device.py`'s `DeviceType` enum (lines 1-23)

**Imports pattern:**
```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
```

**Core model pattern** (mirrors `ArpEvent`, lines 9-18 of `arp_event.py`):
```python
class ArpEvent(Base):
    __tablename__ = "arp_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    src_mac: Mapped[str] = mapped_column(String(17), nullable=False)
    src_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    dst_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
```
Apply the same `id` autoincrement PK + `server_default=func.now()` timestamp idiom for `security_alerts.created_at`. Use the `SAEnum(..., values_callable=lambda enum_cls: [e.value for e in enum_cls])` idiom from `device.py` lines 34-37 for the `type`/`severity` enum columns — this is the established way to store a Python `str, enum.Enum` as a Postgres-native enum without leaking class names as values. `device_id` must be `nullable=True` per D-11 (unregistered/unknown-device alerts have no `Device` row to reference).

---

### `backend/src/models/port_scan_result.py` (model, CRUD/history)

**Analog:** `backend/src/models/traffic_flow.py` (read in full, 35 lines)

**Core pattern** — this is a plain relational history table (not a hypertable, per STATE.md note), so the **shape** to copy is `device_mac: Mapped[str]` row-per-event style, not the TimescaleDB composite-PK idiom:
```python
class TrafficFlow(Base):
    __tablename__ = "traffic_flows"
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), primary_key=True)
    device_mac: Mapped[str] = mapped_column(String(17), nullable=False, primary_key=True)
    ...
```
For `port_scan_results`, use a single autoincrement `id` PK (like `ArpEvent`) plus `device_id: Mapped[int]` (FK to `devices.id`, not `device_mac` — scans target a registered `Device`, not a raw MAC) plus `scanned_at`, `open_ports` (JSON/array column per Open Question 1's recommendation). Do **not** give this table a composite time+mac PK or register it as a hypertable — Research's Open Question 1 and STATE.md both confirm this is plain relational, not time-series.

---

### `backend/src/models/pending_scan_request.py` (model, CRUD/queue)

**Analog:** `backend/src/models/arp_event.py` — same minimal autoincrement-PK + timestamp shape. Columns: `id`, `device_id` (FK), `requested_at` (`server_default=func.now()`), `claimed_at` (nullable, set by the capture-side poll-and-claim).

---

### `backend/src/services/port_rules.py` (service, transform)

**Analog:** `backend/src/services/domain_grouping.py` (pure-function, table-driven transform pattern — not read in full this session, but its established shape is described in 03-CONTEXT.md/03-RESEARCH.md as a stateless pure function over a constant table; `DeviceType` enum import below is read in full).

**Imports pattern:**
```python
from src.models.device import DeviceType
```

**Core pattern** — directly copy from RESEARCH.md Pattern 2 (already vetted against the codebase's actual `DeviceType` enum values in `device.py` lines 13-22):
```python
RISKY_PORTS: frozenset[int] = frozenset({21, 23, 135, 139, 445, 512, 513, 514, 1433, 3306, 3389, 5900})

EXPECTED_PORTS: dict[DeviceType, frozenset[int]] = {
    DeviceType.ROUTER: frozenset({22, 53, 80, 443}),
    DeviceType.IOT: frozenset({80, 443, 1900}),
    DeviceType.TV: frozenset({80, 443, 7000, 8008, 8009}),
    DeviceType.CONSOLE: frozenset({80, 443}),
    DeviceType.PHONE: frozenset(),
    DeviceType.LAPTOP: frozenset(),
    DeviceType.DESKTOP: frozenset(),
    DeviceType.TABLET: frozenset(),
    DeviceType.OTHER: frozenset(),
}

def evaluate_open_ports(device_type: DeviceType, open_ports: list[int]) -> tuple[list[int], list[int]]:
    allowlist = EXPECTED_PORTS.get(device_type, frozenset())
    risky_open = [p for p in open_ports if p in RISKY_PORTS]
    unexpected_open = [p for p in open_ports if p not in RISKY_PORTS and p not in allowlist]
    return risky_open, unexpected_open
```
**Note:** `device.py`'s actual `DeviceType` member names are `PHONE/LAPTOP/DESKTOP/TABLET/IOT/TV/CONSOLE/ROUTER/OTHER` (confirmed by reading the enum directly) — exactly matching RESEARCH.md's table; no renaming needed.

**Testing pattern:** No DB fixture needed — pure function, unit-testable directly like `domain_grouping.py`'s tests. Mirrors the "fixture-free style" noted for `test_domain_grouping.py` in 04-RESEARCH.md's Wave 0 Gaps.

---

### `backend/src/services/security_status.py` (service, transform)

**Analog:** Pure-function derivation, same shape as `port_rules.py` above — no analog file needed beyond the locked logic already specified in RESEARCH.md Pattern 3. Copy verbatim:
```python
import enum

class SecurityStatus(str, enum.Enum):
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"

def derive_status(*, risky_open_ports, unexpected_open_ports, has_malicious_ip_match, has_bandwidth_anomaly) -> SecurityStatus:
    if risky_open_ports or has_malicious_ip_match:
        return SecurityStatus.CRITICAL
    if unexpected_open_ports or has_bandwidth_anomaly:
        return SecurityStatus.WARNING
    return SecurityStatus.GOOD
```
Use the same `str, enum.Enum` + `SAEnum(..., values_callable=...)` idiom as `DeviceType` (`device.py` lines 13-23, 34-37) when persisting this onto `Device.security_status`.

---

### `backend/src/services/threat_intel_source.py` (service, file-I/O + transform)

**Analog:** `backend/src/services/bandwidth_source.py` (read in full, 51 lines) — this IS the swappable-source Protocol pattern this file must mirror exactly.

**Full pattern to copy:**
```python
from typing import Protocol

class BandwidthSource(Protocol):
    """D-07: swappable bandwidth-writing interface.
    One source today (passive capture); a future Phase 7 UniFi adapter will
    implement this same Protocol without requiring changes to callers."""
    async def write_rollup(self, db, device_mac, bytes_rx, bytes_tx, observed_at) -> None: ...

class PassiveCaptureBandwidthSource:
    """The only source today; ... implements the same Protocol without
    requiring changes to callers — that is the swappability D-07 requires."""
    async def write_rollup(self, db, device_mac, bytes_rx, bytes_tx, observed_at) -> None:
        db.add(BandwidthMetric(time=observed_at, device_mac=device_mac, bytes_rx=bytes_rx, bytes_tx=bytes_tx))
        await db.commit()
```
Map directly to `ThreatIntelSource` Protocol (`is_malicious(ip: str) -> bool`) + `StaticBlocklistSource` concrete impl, per RESEARCH.md Pattern 4 — same docstring convention referencing the decision ID (D-08) and explicitly naming the future swap-in implementation (a remote-feed `RemoteFeedSource` per D-10), exactly as `bandwidth_source.py` names "a future Phase 7 UniFi adapter."

---

### `backend/src/services/bandwidth_anomaly.py` (service, CRUD read-only query)

**Analog:** `backend/src/routes/traffic.py`'s `_resolve_device_macs` + `device_bandwidth` (lines 46-67, 145-182, read in full)

**Query pattern to copy** (MAC-history resolution + time-bounded aggregation over `BandwidthMetric`):
```python
async def _resolve_device_macs(db: AsyncSession, device_id: int) -> set[str]:
    device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    history_macs = (await db.execute(select(DeviceMacHistory.mac).where(DeviceMacHistory.device_id == device_id))).scalars().all()
    macs = set(history_macs)
    if device.last_known_mac:
        macs.add(device.last_known_mac)
    return macs
```
Reuse `_resolve_device_macs` directly (import from `traffic.py`, don't duplicate) when computing a device's current-window vs rolling-average bandwidth. Follow `device_bandwidth`'s `select(BandwidthMetric).where(BandwidthMetric.device_mac.in_(macs)).where(BandwidthMetric.time >= start)...` filter-and-aggregate shape for both the current window and the historical baseline window. Per RESEARCH.md Pitfall 5, guard with a minimum sample count (≥7 distinct prior days) before evaluating — skip (don't flag) below that threshold.

---

### `backend/src/routes/security.py` (route, request-response)

**Analog:** `backend/src/routes/traffic.py` (read in full, 210 lines) — auth-gated query route shape, and `backend/src/routes/devices.py` (read in full) for the `_serialize_*` + 404-on-missing pattern.

**Imports pattern:**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_auth
from src.database import get_db
```

**Auth pattern** (every route gated, matches every existing route file):
```python
@router.get("/alerts")
async def list_alerts(_: None = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    ...
```

**404-on-missing pattern** (from `devices.py` lines 78-81 and `traffic.py` lines 55-57):
```python
result = await db.execute(select(Device).where(Device.id == payload.target_device_id))
device = result.scalar_one_or_none()
if device is None:
    raise HTTPException(status_code=404, detail="Target device not found")
```
Apply this exact shape for `POST /scan/{device_id}` (404 if device doesn't exist) and `POST /alerts/{id}/ack` (404 if alert doesn't exist).

**Scan-trigger insert pattern:** mirrors `register_device`'s `db.add(...)` + `await db.commit()` (devices.py lines 83-96) — `POST /scan/{device_id}` inserts a `PendingScanRequest` row, returns 202/201, does NOT call nmap itself (that's the capture container's job per D-03).

---

### `backend/src/routes/capture.py` (modify — add `POST /scan`, `GET /pending-scans`)

**Analog:** itself — the file's own existing 4 routes (read in full, 242 lines) define the exact pattern the new routes must follow, with zero deviation.

**Trust-boundary pattern (MUST reuse verbatim, lines 19-54, 100-113):**
```python
_default_gateway = _detect_default_gateway()
_TRUSTED_HOSTS = frozenset({"127.0.0.1", "::1"} | ({_default_gateway} if _default_gateway else set()))

@router.post("/arp", status_code=status.HTTP_201_CREATED)
async def ingest_arp(payload: ArpEventPayload, request: Request, db: AsyncSession = Depends(get_db)):
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback-only")
    ...
```
`POST /scan` (scan-result ingest) and `GET /pending-scans` (poll target) MUST use this exact `_TRUSTED_HOSTS` check — do not introduce a second trust-boundary implementation (ASVS V4 finding in RESEARCH.md).

**Payload bounding pattern** (lines 85-95, 206-208 — `_MAX_FLOWS_PER_ROLLUP` precedent):
```python
_MAX_FLOWS_PER_ROLLUP = 5000
...
if len(payload.flows) > _MAX_FLOWS_PER_ROLLUP:
    raise HTTPException(status_code=413, detail="Rollup payload exceeds maximum flow count")
```
Apply the same bound to the new `open_ports` list (e.g. `_MAX_OPEN_PORTS = 1000`, matching nmap's own top-1000 scope per RESEARCH.md's V5 finding).

**Pydantic payload pattern** (lines 57-82, `ArpEventPayload`/`TrafficFlowPayload` shape):
```python
class TrafficFlowPayload(BaseModel):
    src_mac: str
    dst_ip: str
    dst_port: int | None = None
    protocol: int
    bytes: int
    dst_hostname: str | None = None
```
Mirror this flat-field `BaseModel` shape for a new `ScanResultPayload(BaseModel)` (`device_id: int`, `open_ports: list[int]`).

---

### `backend/src/routes/devices.py` (modify — serializer extension)

**Analog:** itself, `_serialize_device` (lines 28-40, read in full)
```python
def _serialize_device(device: Device) -> dict:
    return {
        "id": device.id,
        ...
        "unknown": False,
    }
```
Add `"security_status": device.security_status` and `"last_scanned_at": device.last_scanned_at` as new keys in this same dict — no structural change, same flat-serialization convention as every other field here.

---

### `capture/port_scan.py` (capture-module, event-driven)

**Analog:** `capture/traffic_sniff.py` (not read in full this session, but its module shape — referenced directly in RESEARCH.md Pattern 1 and confirmed structurally via `capture/capture.py`'s `from traffic_sniff import run_traffic_sniff` import and thread-target usage, lines 22, 180-182) and `capture/capture.py`'s existing `on_arp_packet`/`on_dhcp_packet` POST pattern (read in full).

**POST-per-event pattern to copy** (capture.py lines 49-60):
```python
def on_arp_packet(pkt):
    if ARP in pkt and pkt[ARP].op == 1:
        payload = {"src_mac": pkt[ARP].hwsrc, "src_ip": pkt[ARP].psrc, "dst_ip": pkt[ARP].pdst}
        try:
            httpx.post(f"{API_URL}/api/capture/arp", json=payload, timeout=5.0)
        except Exception as exc:  # noqa: BLE001 - log and keep sniffing
            print(f"[capture] POST failed: {exc}")
```
This exact try/except-and-continue, `print(f"[capture] ... failed: {exc}")` swallow convention is the established error-handling idiom for every capture-side POST — `port_scan.py`'s scan-result POST and pending-scan poll MUST use the same shape (RESEARCH.md ASVS V7 finding: "same try/except Exception: print swallow-and-continue convention").

**Module-level constant pattern** (capture.py line 24):
```python
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
```

---

### `capture/capture.py` (modify — add scan-listener + daily-rescan threads)

**Analog:** itself — existing thread registration/SIGTERM convention (read in full, 199 lines)

**Thread + stop_event pattern** (lines 36-46, 154-195):
```python
stop_event = threading.Event()

def _handle_sigterm(*_args):
    stop_event.set()

signal.signal(signal.SIGTERM, _handle_sigterm)

def run_arp_sniff():
    sniff(filter="arp", prn=on_arp_packet, store=False, stop_filter=lambda _pkt: stop_event.is_set())

def main():
    arp_thread = threading.Thread(target=run_arp_sniff, name="arp-sniff")
    ...
    arp_thread.start()
    arp_thread.join()
```
Add a 5th and 6th thread (`scan-listener`, `daily-rescan`) following this exact `threading.Thread(target=..., name=..., args=(stop_event,))` + `.start()` + `.join()` registration shape in `main()`. For the daily-rescan loop specifically, use `stop_event.wait(timeout=sleep_seconds)` (not a plain `time.sleep`) so shutdown isn't blocked up to 24h — this directly extends the existing SIGTERM-responsiveness precedent already established by `stop_filter=lambda _pkt: stop_event.is_set()` in the sniff threads.

---

### `frontend/src/lib/components/DeviceCard.svelte` (modify — badge + Scan button)

**Analog:** itself (read in full, 212 lines)

**Badge pattern to copy** (lines 116-118, the "Unknown" badge):
```svelte
<Badge variant="outline" style="color: var(--color-warning); border-color: var(--color-warning);">
  Unknown
</Badge>
```
Use the same `<Badge variant="outline" style="color: var(--color-X); border-color: var(--color-X);">` shape for the good/warning/critical badge, swapping `--color-warning` for `--color-accent` (good — confirm this CSS var exists; the codebase uses `--color-accent` for "online" status at line 180-181) and a new `--color-critical`/red variant for critical.

**Button pattern to copy** (lines 161-164):
```svelte
<div style="display: flex; gap: 8px;">
  <Button onclick={() => onRegister(device.id)}>Register</Button>
  <Button variant="outline" onclick={() => onMerge(device.id)}>Merge with...</Button>
</div>
```
Add a "Scan" button in the registered-device branch (currently has no action buttons, lines 167-191) following this same `<Button onclick={() => onScan(device.id)}>Scan</Button>` shape, passed down as a new `onScan` prop alongside the existing `onRegister`/`onMerge` props (lines 36-42).

**Popover-for-detail pattern** (lines 128-159) — reuse for showing scan-result detail (open ports list) on click, exactly as currently used for raw signal data on unknown devices.

**Online-indicator dot pattern** (lines 177-183) — model the badge's color-swap logic the same way as `isOnline` (line 81, a `$derived` computing display state from a data field) rather than inline conditionals scattered through markup.

---

### `frontend/src/lib/components/SecurityAlertsBanner.svelte` (new component)

**Analog:** `frontend/src/routes/dashboard/+page.svelte`'s existing inline device-count summary banner (lines 130-136, read in full) — the closest existing "banner above the device grid" precedent (D-12 explicitly says "alongside the existing Phase 2 D-13 summary banner").
```svelte
<div style="background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 24px; margin-bottom: 24px; font-size: 14px; font-weight: 500; line-height: 1.4; color: var(--color-fg);">
  {devices.length} device{devices.length === 1 ? '' : 's'}{#if unknownCount > 0}
    {' '}· <span style="color: var(--color-warning);">{unknownCount} unknown</span>
  {/if}
</div>
```
Build `SecurityAlertsBanner.svelte` as its own component (not inline in `+page.svelte`, unlike the existing summary banner) that fetches `/api/security/alerts` on mount (same `onMount` + `apiGet` pattern as `+page.svelte` lines 55-73) and renders a dismiss-on-ack list using the same surface/border/radius/padding token values shown above, placed directly above the device grid in `+page.svelte` (insert between the existing summary `<div>` at line 130 and the device grid `<div>` at line 138).

**Data fetch pattern to copy** (`api.ts` lines 13-24, `listDevices`):
```typescript
export async function listDevices(): Promise<unknown[]> {
  const res = await apiGet('/api/devices/');
  if (!res.ok) throw new Error('Failed to load devices');
  return res.json();
}
```
Add `listAlerts()` / `ackAlert(id)` / `triggerScan(deviceId)` to `frontend/src/lib/api.ts` following this exact `apiGet`/`apiPost` wrapper shape (lines 1-18 define the shared helpers all of these reuse).

---

## Shared Patterns

### Capture-Ingest Trust Boundary
**Source:** `backend/src/routes/capture.py` lines 19-54, 100-113
**Apply to:** `POST /api/capture/scan`, `GET /api/capture/pending-scans` — the exact `_TRUSTED_HOSTS` loopback/gateway check, no second implementation.

### Auth-Gated Routes
**Source:** `backend/src/auth.py` (`require_auth`, read in full) + every route in `backend/src/routes/traffic.py`/`devices.py`
```python
async def require_auth(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")
```
**Apply to:** All new `backend/src/routes/security.py` GET/POST routes via `Depends(require_auth)` — no new auth surface, per RESEARCH.md's ASVS V2 finding.

### Swappable-Source Protocol Pattern
**Source:** `backend/src/services/bandwidth_source.py` (full file, 51 lines)
**Apply to:** `threat_intel_source.py`'s `ThreatIntelSource` Protocol + `StaticBlocklistSource` — same `Protocol` class + one concrete impl + docstring naming the future swap-in (`RemoteFeedSource`, D-10).

### Table-Driven Pure-Function Logic (no opaque scoring)
**Source:** RESEARCH.md Pattern 2/3, validated against `device.py`'s actual `DeviceType` enum
**Apply to:** `port_rules.py` (`evaluate_open_ports`) and `security_status.py` (`derive_status`) — both must stay framework-free (no DB/ORM imports), unit-testable with plain function calls, mirroring the fixture-free pure-function test style noted for `domain_grouping.py`.

### Payload Size Bounding on Untrusted Ingest
**Source:** `backend/src/routes/capture.py` lines 85-89, 206-208 (`_MAX_FLOWS_PER_ROLLUP = 5000`)
**Apply to:** New `ScanResultPayload.open_ports` — bound to e.g. 1000 entries to match nmap's own top-1000 scope (RESEARCH.md ASVS V5 finding).

### Capture-Side Swallow-and-Continue Error Handling
**Source:** `capture/capture.py` lines 56-60, 94-96, 118-120 (repeated 3x verbatim in the existing file)
```python
try:
    httpx.post(f"{API_URL}/api/capture/...", json=payload, timeout=5.0)
except Exception as exc:  # noqa: BLE001 - log and keep sniffing
    print(f"[capture] POST failed: {exc}")
```
**Apply to:** `capture/port_scan.py`'s scan-result POST and pending-scan poll GET — never let a single failed POST crash a capture thread.

### Thread Registration + SIGTERM Convention
**Source:** `capture/capture.py` lines 36-46, 176-195 (full `main()` function)
**Apply to:** The new scan-listener and daily-rescan threads — same `threading.Thread(target=..., name=...)` + `.start()`/`.join()` registration, same shared module-level `stop_event`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/src/data/firehol_level1.netset` | config/data | file-I/O | First vendored static data asset in the codebase — `backend/src/data/vendor_catalog.py` exists as a Python data module, not a flat external-format file, so there's no exact precedent for "vendored third-party flat-file asset." Follow RESEARCH.md's guidance directly: preserve the file's own `# Date:` header verbatim for staleness tracking (Pitfall 4). |
| Alembic migration for `security_status`/`last_scanned_at`/new tables | migration | batch | Not located/read this session (migrations dir not explored), but the established path is "Alembic migrations are the established schema-change path in this codebase" per RESEARCH.md Open Question 3 — planner should locate the most recent migration file (likely `backend/alembic/versions/0004_*` or later, referenced in `traffic.py` comments) as the structural analog when writing the new migration. |

## Metadata

**Analog search scope:** `backend/src/{models,routes,services}/`, `capture/`, `frontend/src/lib/`, `frontend/src/routes/dashboard/`
**Files scanned:** 16 read in full + directory listings of all four areas
**Pattern extraction date:** 2026-06-20
