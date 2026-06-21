# Phase 3: Live Traffic + Bandwidth - Pattern Map

**Mapped:** 2026-06-19
**Files analyzed:** 13 new/modified files
**Analogs found:** 11 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `capture/traffic_sniff.py` | utility (capture loop) | streaming (aggregated) | `capture/capture.py` | role-match (existing sniff loops are per-packet POST; this is the same shape, different cadence) |
| `capture/capture.py` (modified — add traffic thread) | utility (capture loop) | event-driven | `capture/capture.py` (self) | exact (extend existing thread-startup pattern) |
| `capture/requirements.txt` (modified — add dpkt) | config | — | n/a | n/a |
| `backend/src/models/traffic_flow.py` | model | CRUD (time-series insert) | `backend/src/models/bandwidth.py` | exact |
| `backend/src/routes/capture.py` (modified — add `/traffic`) | route | request-response | `backend/src/routes/capture.py` (self, `ingest_dhcp`) | exact |
| `backend/src/routes/traffic.py` | route | request-response + streaming (SSE) | `backend/src/routes/devices.py` (request-response) + new SSE pattern from research | role-match (no SSE analog exists yet) |
| `backend/src/services/bandwidth_source.py` | service (interface/protocol) | transform | `backend/src/services/identity_resolver.py` (`Protocol` + concrete impl pattern) | exact (structural — Protocol-based swappable strategy) |
| `backend/src/services/traffic_broadcaster.py` | service (shared state / fan-out) | pub-sub | none in codebase | no analog — follow RESEARCH.md Pattern 4 |
| `backend/src/services/domain_grouping.py` | service (pure transform) | transform | `backend/src/services/identity_resolver.py` (`HostnameFallbackResolver` — pure, stateless function-like class) | role-match |
| `backend/alembic/versions/0004_traffic_flows.py` | migration | batch (schema) | `backend/alembic/versions/0001_initial.py` | exact |
| `backend/tests/test_traffic_stream.py` | test | request-response (SSE) | `backend/tests/test_capture.py` | role-match (loopback-trust test patterns reusable; SSE assertions are new) |
| `backend/tests/test_bandwidth_query.py` | test | CRUD | `backend/tests/test_capture.py` + `backend/tests/test_devices.py` | role-match |
| `backend/tests/test_domain_grouping.py` | test | transform | `backend/tests/test_identity_resolver.py` (same shape — pure unit test of a resolver-style class) | role-match |

## Pattern Assignments

### `capture/traffic_sniff.py` (capture loop, streaming/aggregated)

**Analog:** `capture/capture.py`

**Module structure / SIGTERM handling** (lines 1-44 of `capture/capture.py`):
```python
import asyncio
import os
import signal
import threading

import httpx
from scapy.all import ARP, BOOTP, DHCP, Ether, sniff

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
stop_event = threading.Event()

def _handle_sigterm(*_args):
    stop_event.set()

signal.signal(signal.SIGTERM, _handle_sigterm)
```
Copy this exact shape but the new module imports `dpkt`/`socket` instead of `scapy`, and shares the *same* `stop_event` instance from `capture.py` (pass it in, don't create a second one) so SIGTERM still propagates cleanly across all threads (Pitfall 6 in capture.py's docstring).

**POST-per-unit pattern** (lines 47-58, `on_arp_packet`):
```python
def on_arp_packet(pkt):
    if ARP in pkt and pkt[ARP].op == 1:
        payload = {...}
        try:
            httpx.post(f"{API_URL}/api/capture/arp", json=payload, timeout=5.0)
        except Exception as exc:  # noqa: BLE001 - log and keep sniffing
            print(f"[capture] POST failed: {exc}")
```
Reuse this `try/except Exception ... print` swallow-and-continue pattern for the flush function, but trigger it on a timer (~7s, per RESEARCH.md Open Question 3) rather than per-packet — accumulate into the in-memory `flows: dict[tuple, int]` (RESEARCH.md Pattern 1) and only call `httpx.post` at flush time.

**Loop registration pattern** (lines 174-188, `main()`):
```python
def main():
    arp_thread = threading.Thread(target=run_arp_sniff, name="arp-sniff")
    dhcp_thread = threading.Thread(target=run_dhcp_sniff, name="dhcp-sniff")
    mdns_thread = threading.Thread(target=run_mdns_thread, name="mdns-browser")
    mdns_thread.start(); dhcp_thread.start(); arp_thread.start()
    arp_thread.join(); dhcp_thread.join(); mdns_thread.join()
```
Add a fourth `traffic_thread = threading.Thread(target=run_traffic_sniff, name="traffic-sniff")` following the identical start/join shape — modify `capture/capture.py`'s `main()` directly rather than duplicating the thread-management logic in the new file.

**Core dpkt parse + DNS cache pattern:** No codebase analog exists (first dpkt usage) — follow RESEARCH.md Pattern 1 (5-tuple flow aggregation) and Pattern 2 (passive DNS sniffing) verbatim; both are already concrete, tested-shape code blocks in `03-RESEARCH.md`.

---

### `backend/src/models/traffic_flow.py` (model, CRUD/time-series)

**Analog:** `backend/src/models/bandwidth.py` (full file, 27 lines — exact structural match)

```python
from datetime import datetime
from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base

class BandwidthMetric(Base):
    __tablename__ = "bandwidth_metrics"
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), primary_key=True,
    )
    device_mac: Mapped[str] = mapped_column(String(17), nullable=False, primary_key=True)
    bytes_rx: Mapped[float] = mapped_column(Float, default=0.0)
    bytes_tx: Mapped[float] = mapped_column(Float, default=0.0)
```

Copy this exact shape for `TrafficFlow`: composite primary key `(time, device_mac, dst_ip, dst_port, protocol)` per RESEARCH.md D-05/Open Question 2 (start with composite PK, matches existing convention), plus a `bytes: Mapped[float]` column and (per D-10's "keep raw hostname in storage") an optional `dst_hostname: Mapped[str | None]` column populated from the DNS cache — group-by-registered-domain happens at query time in `domain_grouping.py`, never written to this table.

---

### `backend/src/routes/capture.py` (modified — add `/traffic` ingest route)

**Analog:** same file, `ingest_dhcp` handler (lines 92-118) — exact match, same file being modified

```python
@router.post("/dhcp", status_code=status.HTTP_201_CREATED)
async def ingest_dhcp(payload: DhcpEventPayload, request: Request, db: AsyncSession = Depends(get_db)):
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback-only")

    event = DhcpEvent(...)
    db.add(event)
    await db.commit()

    await record_observation(db, Observation(...))
    return {"ok": True}
```

Copy this exact trust-check + Pydantic-payload + commit shape for `ingest_traffic`. The new payload model is a list of flow rollups (per RESEARCH.md's flush-and-POST batch), e.g.:
```python
class TrafficFlowPayload(BaseModel):
    src_mac: str
    dst_ip: str
    dst_port: int | None
    protocol: int
    bytes: int
    dst_hostname: str | None = None

class TrafficRollupPayload(BaseModel):
    interval_start: datetime
    interval_end: datetime
    flows: list[TrafficFlowPayload]
```
Reuse the existing `_TRUSTED_HOSTS` / `_detect_default_gateway()` module-level singletons already defined at the top of this file (lines 17-52) — do not redefine a second trust boundary. Writes `TrafficFlow` rows AND upserts `BandwidthMetric` rows from the same payload (D-05's "same in-memory per-interval flow table each cycle" maps to one route writing both tables in one transaction).

---

### `backend/src/routes/traffic.py` (route, request-response + SSE)

**Analog (request-response shape):** `backend/src/routes/devices.py` lines 1-13 (imports) and 65-69 (`list_devices`)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth import require_auth
from src.database import get_db

router = APIRouter()

@router.get("/")
async def list_devices(_: None = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    devices = (await db.execute(select(Device))).scalars().all()
    return [_serialize_device(d) for d in devices]
```
Copy the `Depends(require_auth)` + `Depends(get_db)` dependency-injection shape for every new GET endpoint (`/api/bandwidth/{device}`, `/api/bandwidth/network`, `/api/devices/{id}/destinations`) — all dashboard reads sit behind the existing session-cookie auth, per RESEARCH.md's ASVS V4 note ("Existing dashboard password auth already gates all new routes").

**SSE endpoint (no codebase analog — net-new infrastructure):** Use RESEARCH.md Pattern 4 verbatim:
```python
from sse_starlette.sse import EventSourceResponse

@router.get("/stream")
async def traffic_stream(request: Request, _: None = Depends(require_auth)):
    async def event_generator():
        last_sent = None
        while True:
            if await request.is_disconnected():
                break
            snapshot = get_latest_snapshot()  # from traffic_broadcaster.py
            if snapshot != last_sent:
                yield {"event": "snapshot", "data": json.dumps(snapshot)}
                last_sent = dict(snapshot)
            await asyncio.sleep(1)
    return EventSourceResponse(event_generator(), ping=15)
```
Note: still gate with `Depends(require_auth)` even though this is the first SSE route — every other route in the codebase enforces auth via this same dependency, and RESEARCH.md's ASVS table confirms no new auth surface is introduced.

---

### `backend/src/services/bandwidth_source.py` (service, swappable interface — D-07)

**Analog:** `backend/src/services/identity_resolver.py` (full file, 41 lines) — exact structural match for "Protocol interface + one concrete stateless implementation"

```python
from dataclasses import dataclass
from typing import Protocol

class IdentityResolver(Protocol):
    def resolve(self, observation: Observation) -> str:
        """Return the stable identity key this observation belongs to."""
        ...

class HostnameFallbackResolver:
    """Kept pure/stateless — registry-aware logic belongs elsewhere."""
    def resolve(self, observation: Observation) -> str:
        ...
```

Copy this exact `Protocol` + single concrete class shape for the bandwidth source interface:
```python
class BandwidthSource(Protocol):
    async def write_rollup(self, db: AsyncSession, payload: TrafficRollupPayload) -> None: ...

class PassiveCaptureBandwidthSource:
    """The only source today; Phase 7's UniFi adapter implements this same Protocol."""
    async def write_rollup(self, db, payload) -> None:
        ...
```
This directly satisfies D-07's "swappable source interface" requirement using the exact pattern already proven in this codebase (`identity_resolver.py`'s `Protocol` + concrete-impl-passed-as-default-arg, as seen in `discovery.py`'s `record_observation(db, observation, resolver: "IdentityResolver | None" = None)` — same default-injection idiom applies here).

---

### `backend/src/services/domain_grouping.py` (service, pure transform — D-10)

**Analog:** `backend/src/services/identity_resolver.py`, `HostnameFallbackResolver.resolve` (lines 29-40) — pure, stateless, single-method class pattern

```python
class HostnameFallbackResolver:
    def resolve(self, observation: Observation) -> str:
        hostname = observation.hostname.strip() if observation.hostname else ""
        if hostname:
            return f"host:{hostname.lower()}"
        return f"mac:{observation.mac.lower()}"
```
Copy this "stateless, no I/O, pure function wrapped in a class for testability" shape. Combine with RESEARCH.md Pattern 3's offline-mode `tldextract` usage:
```python
import tldextract

_extractor = tldextract.TLDExtract(suffix_list_urls=())  # offline-only, no network call

def registered_domain(hostname: str) -> str:
    ext = _extractor(hostname)
    return f"{ext.domain}.{ext.suffix}" if ext.suffix else hostname
```
Keep this as a module-level pure function (matching `HostnameFallbackResolver`'s no-constructor-args, no-DB-access style) — called only at serialization time in `routes/traffic.py`'s destinations endpoint, never at capture/ingest time (D-10).

---

### `backend/src/services/traffic_broadcaster.py` (service, pub-sub — no analog)

No existing pub-sub/broadcaster pattern exists in this codebase (RESEARCH.md confirms: "No SSE infrastructure exists yet anywhere"). Follow RESEARCH.md Pattern 4 directly:
```python
_latest_snapshot: dict = {}

def get_latest_snapshot() -> dict:
    return _latest_snapshot

async def update_snapshot_loop(stop_event: asyncio.Event):
    """Background task started in main.py's lifespan — recomputes the
    rolling top-talkers snapshot every ~7s from current bandwidth_metrics/
    traffic_flows rows (5-minute rolling window per D-12)."""
    while not stop_event.is_set():
        global _latest_snapshot
        _latest_snapshot = await _compute_snapshot()
        await asyncio.sleep(7)
```
Wire the background task into `backend/src/main.py`'s `lifespan` context manager (see Shared Patterns below) rather than spawning it ad hoc inside the route module — this matches the existing lifespan-managed resource pattern already used for `engine.dispose()`.

---

### `backend/alembic/versions/0004_traffic_flows.py` (migration, batch/schema)

**Analog:** `backend/alembic/versions/0001_initial.py` (full file, 64 lines) — exact match for hypertable migration shape

```python
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "bandwidth_metrics",
        sa.Column("time", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("device_mac", sa.String(17), nullable=False),
        sa.Column("bytes_rx", sa.Float(), nullable=False, server_default="0"),
        sa.Column("bytes_tx", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("time", "device_mac"),
    )
    op.execute(
        "SELECT create_hypertable('bandwidth_metrics', by_range('time', INTERVAL '1 week'))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS bandwidth_metrics_time_idx ON bandwidth_metrics (time)"
    )

def downgrade() -> None:
    op.drop_table("bandwidth_metrics")
```
Copy this exact `op.create_table` + `create_hypertable()` + `CREATE INDEX IF NOT EXISTS` (Pitfall: autogenerate would otherwise try to drop this index) shape for `traffic_flows`. Then layer on RESEARCH.md's Code Examples block for the continuous aggregates and compression policy (hourly/daily caggs + `add_compression_policy`, explicitly NO `add_retention_policy` call per D-06/Pitfall 3).

**Confirmed migration chain (verified against codebase):** Current head is `backend/alembic/versions/0003_identification_hints.py` with `revision = "0003"`, `down_revision = "0002"`. The new migration must use `revision = "0004"`, `down_revision = "0003"`.

---

### `backend/tests/test_traffic_stream.py` / `test_bandwidth_query.py` (tests, request-response/CRUD)

**Analog:** `backend/tests/test_capture.py` (full file, 185 lines) — loopback-trust test pattern, fixture usage pattern

```python
async def test_arp_ingest(client):
    """POST /api/capture/arp from loopback (httpx test client default) succeeds."""
    payload = {...}
    response = await client.post("/api/capture/arp", json=payload)
    assert response.status_code == 201
```

```python
async def test_arp_ingest_rejects_non_loopback(test_db):
    """Uses httpx's ASGITransport `client` tuple param to set a non-default
    peer address for this one test, exercising the real code path."""
    from src.database import get_db
    from src.main import app
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async def override_get_db():
        async with session_maker() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app, client=("203.0.113.5", 12345))
        async with AsyncClient(transport=transport, base_url="http://test") as non_loopback_client:
            response = await non_loopback_client.post("/api/capture/arp", json=payload)
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
```

Reuse the `client`/`test_db` fixtures from `backend/tests/conftest.py` (`test_db` is an in-memory SQLite async fixture, `client` wraps it in an `AsyncClient`) for `test_bandwidth_query.py` and the ingest half of `test_traffic_stream.py`. For the new ingest route's trust-boundary test, copy `test_arp_ingest_rejects_non_loopback`'s `ASGITransport(app=app, client=(ip, port))` technique verbatim.

For the SSE-specific assertions in `test_traffic_stream.py` (no analog exists for SSE testing in this codebase): test the `EventSourceResponse` generator function directly as a plain async generator (call `event_generator()` and `await anext(gen)` in a test, mocking `request.is_disconnected()` to return `True` after one iteration) rather than attempting a full streaming HTTP client test — this avoids flaky timing-dependent SSE-over-HTTP test infrastructure.

---

### `backend/tests/test_domain_grouping.py` (test, transform/unit)

**Analog:** Same fixture-free, no-DB unit-test shape implied by `HostnameFallbackResolver` being a pure class with no constructor args (see `identity_resolver.py`) — write plain `def test_...()` (not `async def`) functions exercising `registered_domain()` directly with input/output pairs (e.g. `"www.netflix.com" -> "netflix.com"`, `"foo.github.io" -> "github.io"` to prove PSL multi-part-suffix handling), no fixtures needed.

## Shared Patterns

### Loopback/Gateway Trust Boundary
**Source:** `backend/src/routes/capture.py` lines 17-52 (`_detect_default_gateway()`, `_TRUSTED_HOSTS`)
**Apply to:** The new `/api/capture/traffic` ingest route — reuse the exact same module-level `_TRUSTED_HOSTS` frozenset and `client_host not in _TRUSTED_HOSTS` check already used by `/arp`, `/dhcp`, `/mdns`. Do not introduce a second trust-boundary implementation.
```python
client_host = request.client.host if request.client else None
if client_host not in _TRUSTED_HOSTS:
    raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback-only")
```

### Session-Cookie Auth Gate
**Source:** `backend/src/routes/devices.py` line 66, `Depends(require_auth)` (from `backend/src/auth.py`)
**Apply to:** All new GET routes in `traffic.py` (`/stream`, `/bandwidth/{device}`, `/bandwidth/network`, `/devices/{id}/destinations`) — every authenticated read in the codebase uses this same dependency; the SSE route is no exception per RESEARCH.md's ASVS table.

### Capture-Never-Writes-DB-Directly
**Source:** `capture/capture.py` (entire file — every `on_*` handler POSTs via `httpx`, never imports `sqlalchemy`/`psycopg`)
**Apply to:** `capture/traffic_sniff.py` — the dpkt-based loop must also only POST aggregated rollups to `/api/capture/traffic`; it must never open a direct DB connection, preserving the existing container-trust-boundary architecture reaffirmed in CONTEXT.md ("Capture container never writes to the DB directly — always POSTs to the API").

### Lifespan-Managed Background Tasks
**Source:** `backend/src/main.py` lines 11-16 (`lifespan` context manager, `engine.dispose()` on shutdown)
**Apply to:** `traffic_broadcaster.py`'s `update_snapshot_loop` background task — start it in `lifespan`'s startup half (before `yield`) and signal it to stop in the shutdown half, following the same resource-lifecycle-tied-to-app-lifespan convention already established for the DB engine.
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from src.database import engine
    await engine.dispose()
```

### Dialect-Aware Upsert (if `traffic_flows`/`bandwidth_metrics` writes need ON CONFLICT semantics)
**Source:** `backend/src/services/discovery.py` lines 18-83 (`upsert_discovered_identity`)
**Apply to:** If the ingest route needs to upsert `BandwidthMetric` rows for an existing `(time, device_mac)` key rather than always inserting fresh rows, copy the `pg_insert(...).on_conflict_do_update(...)` / `sqlite_insert(...)` dialect-branch pattern — both Postgres (prod) and SQLite (test fixture) need working ON CONFLICT semantics.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/src/services/traffic_broadcaster.py` | service | pub-sub | No SSE/broadcaster infrastructure exists anywhere in the codebase yet (confirmed in RESEARCH.md) — follow RESEARCH.md Pattern 4 directly rather than adapting an existing file |
| `backend/src/routes/traffic.py` (`/stream` endpoint specifically) | route | streaming (SSE) | Same reason — first SSE route in the project; request-response sibling endpoints in the same file do have a direct analog (`devices.py`) |

## Metadata

**Analog search scope:** `capture/`, `backend/src/models/`, `backend/src/routes/`, `backend/src/services/`, `backend/alembic/versions/`, `backend/tests/`
**Files scanned:** 13 existing source files read in full (capture.py, routes/capture.py, routes/devices.py, models/bandwidth.py, models/device.py, services/identity_resolver.py, services/discovery.py, main.py, auth.py, alembic 0001/0003, tests/test_capture.py, tests/conftest.py)
**Pattern extraction date:** 2026-06-19
