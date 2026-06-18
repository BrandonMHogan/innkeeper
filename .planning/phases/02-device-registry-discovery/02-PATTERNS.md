# Phase 2: Device Registry + Discovery - Pattern Map

**Mapped:** 2026-06-18
**Files analyzed:** 16
**Analogs found:** 14 / 16

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `backend/src/models/dhcp_event.py` | model | event-driven (append-only ingest) | `backend/src/models/arp_event.py` | exact |
| `backend/src/models/mdns_event.py` | model | event-driven (append-only ingest) | `backend/src/models/arp_event.py` | exact |
| `backend/src/models/discovered_identity.py` | model | CRUD (upsert) | `backend/src/models/arp_event.py` (shape) + `backend/src/models/app_settings.py` (singleton-row pattern) | role-match |
| `backend/src/models/device.py` | model | CRUD | `backend/src/models/app_settings.py` (enum/bool columns) | role-match |
| `backend/src/services/identity_resolver.py` | service | transform (pure function) | none in codebase — new architectural seam | no analog |
| `backend/src/services/discovery.py` | service | event-driven (ingest orchestration) | `backend/src/routes/capture.py` (ingest+trust logic, currently inline) | role-match |
| `backend/src/routes/capture.py` (extend: `/dhcp`, `/mdns`) | route | request-response (trusted ingest) | `backend/src/routes/capture.py` `/arp` handler (same file, existing pattern) | exact |
| `backend/src/routes/devices.py` | route | CRUD + request-response | `backend/src/routes/auth.py` (auth-gated CRUD-ish routes) | role-match |
| `backend/src/schemas/device.py` | schema/validation | request-response | `backend/src/routes/auth.py` `PasswordPayload` (inline Pydantic model pattern) | role-match |
| `capture/capture.py` (extend: DHCP sniff + mDNS browser) | utility (capture daemon) | streaming/event-driven | `capture/capture.py` (existing ARP sniff thread — same file) | exact |
| `capture/requirements.txt` (add `zeroconf`) | config | — | `capture/requirements.txt` (existing) | exact |
| `backend/tests/test_capture.py` (extend DHCP/mDNS ingest tests) | test | request-response | `backend/tests/test_capture.py::test_arp_ingest*` (same file) | exact |
| `backend/tests/test_devices.py` | test | CRUD | `backend/tests/test_capture.py` (client fixture usage pattern) | role-match |
| `backend/tests/test_identity_resolver.py` | test | transform | none — new pure-logic test, no existing unit-test-only file to mirror (closest shape: any pytest function in `test_capture.py`) | partial |
| `backend/tests/test_discovery.py` | test | event-driven | `backend/tests/test_capture.py` (fixture + DB-assertion pattern) | role-match |
| `frontend/src/routes/dashboard/+page.svelte` | component (page) | request-response (client fetch) | `frontend/src/routes/dashboard/+page.svelte` (existing shell, same file) + `frontend/src/routes/setup/+page.svelte` (form pattern for dialogs) | exact |
| `frontend/src/lib/components/DeviceCard.svelte` | component | request-response (render) | `frontend/src/lib/components/ui/badge/badge.svelte` (variant/styling pattern), `ui/card/*` (structure) | role-match |
| `frontend/src/lib/components/RegisterDialog.svelte` | component | request-response (form submit) | `frontend/src/lib/components/ui/dialog/dialog-content.svelte` (dialog shell) + `frontend/src/routes/setup/+page.svelte` (form/loading/error state pattern) | role-match |
| `frontend/src/lib/components/MergeDialog.svelte` | component | request-response (form submit) | same as `RegisterDialog.svelte` analogs | role-match |
| `frontend/src/lib/api.ts` (extend: `listDevices`, `registerDevice`, `mergeDevice`) | utility (API client) | request-response | `frontend/src/lib/api.ts` (existing `apiGet`/`apiPost`, same file) | exact |

## Pattern Assignments

### `backend/src/models/dhcp_event.py` and `mdns_event.py` (model, event-driven)

**Analog:** `backend/src/models/arp_event.py` (full file, 19 lines)

**Full pattern to copy:**
```python
from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ArpEvent(Base):
    """Capture ingest row — one ARP packet observation POSTed by the capture service."""

    __tablename__ = "arp_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    src_mac: Mapped[str] = mapped_column(String(17), nullable=False)
    src_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    dst_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    received_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
```

**Apply for `DhcpEvent`:** same shape, columns `src_mac`, `hostname: Mapped[str | None]`, `requested_ip: Mapped[str | None]`, `vendor_class_id: Mapped[str | None]` (RESEARCH.md Open Question #2 — parse but don't consume yet), `received_at`.

**Apply for `MdnsEvent`:** columns `hostname: Mapped[str | None]`, `service_type: Mapped[str]`, `addresses: Mapped[str]` (store as comma-joined or JSON string — no array column precedent in codebase, keep simple), `received_at`.

`__tablename__` must be `"dhcp_events"` / `"mdns_events"` respectively (plural, snake_case — matches `arp_events`).

---

### `backend/src/models/discovered_identity.py` and `device.py` (model, CRUD)

**Analog for column typing (enum/bool):** `backend/src/models/app_settings.py`

Read this file directly (not yet excerpted above) — confirm via Bash before planning: it establishes the project's convention for `Boolean`/server-default columns on a registry-like row. Combine with RESEARCH.md's `Device` model sketch (lines 332-370 of 02-RESEARCH.md), which already matches `arp_event.py`'s import/Base/Mapped style exactly:

```python
from datetime import datetime
import enum

from sqlalchemy import String, Boolean, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class DeviceType(str, enum.Enum):
    PHONE = "phone"
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    TABLET = "tablet"
    IOT = "iot_smart_home"
    TV = "tv_streaming"
    CONSOLE = "game_console"
    ROUTER = "router_network"
    OTHER = "other"


class Device(Base):
    """Registry row — D-04: identity is locked once registered."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    identity_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    type: Mapped[DeviceType] = mapped_column(SAEnum(DeviceType), nullable=False)
    trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_known_mac: Mapped[str] = mapped_column(String(17), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
```

`DiscoveredIdentity` follows the same import block, with `identity_key` unique-constrained for the upsert pattern (Pitfall 5), plus `mac`, `hostname`, `first_seen`, `last_seen`.

---

### `backend/src/services/identity_resolver.py` (service, transform — NO ANALOG, new seam)

No existing service-layer file exists in this codebase (`backend/src/services/` is empty). Use RESEARCH.md's `Protocol` pattern verbatim (D-01 requires interface isolation):

```python
from typing import Protocol
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Observation:
    mac: str
    hostname: str | None
    source: str  # "arp" | "dhcp" | "mdns"
    observed_at: datetime


class IdentityResolver(Protocol):
    def resolve(self, observation: Observation) -> str:
        """Return the stable identity key this observation belongs to."""
        ...


class HostnameFallbackResolver:
    """D-02/D-03: hostname is primary key, MAC is fallback."""

    def resolve(self, observation: Observation) -> str:
        if observation.hostname:
            return f"host:{observation.hostname.strip().lower()}"
        return f"mac:{observation.mac.lower()}"
```

Keep this resolver pure/stateless (Pitfall 2) — registry-aware identity-key-change logic belongs in `discovery.py`, not here.

---

### `backend/src/services/discovery.py` (service, event-driven orchestration)

**Analog:** `backend/src/routes/capture.py` — currently the route does DB writes inline (`db.add(event); await db.commit()`). The new ingest routes should instead call into `discovery.py`, which owns the upsert + resolver call.

**Upsert pattern to copy** (from RESEARCH.md, citing SQLAlchemy 2.0 PG dialect docs):
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

async def upsert_discovered_identity(db, identity_key: str, mac: str, hostname: str | None, seen_at):
    stmt = (
        pg_insert(DiscoveredIdentity)
        .values(identity_key=identity_key, mac=mac, hostname=hostname,
                first_seen=seen_at, last_seen=seen_at)
        .on_conflict_do_update(
            index_elements=[DiscoveredIdentity.identity_key],
            set_={"mac": mac, "hostname": hostname, "last_seen": seen_at},
        )
    )
    await db.execute(stmt)
    await db.commit()
```

**Note:** `test_db` fixture in `conftest.py` uses SQLite in-memory — `pg_insert`/`on_conflict_do_update` is Postgres-dialect-specific and will not work against SQLite in tests. The discovery service or its tests need a SQLite-compatible fallback path (e.g., `sqlalchemy.dialects.sqlite.insert` with `on_conflict_do_update`, which has equivalent syntax) or the test must run against a real Postgres fixture. Flag this for the planner — existing `conftest.py` (lines 13-25) only provides SQLite.

---

### `backend/src/routes/capture.py` (extend) and `backend/src/routes/devices.py` (route)

**Analog for trust boundary (MUST reuse, not reimplement):** `backend/src/routes/capture.py` lines 12-47 — `_detect_default_gateway()` + `_TRUSTED_HOSTS` frozenset. New `/dhcp` and `/mdns` handlers must check `client_host not in _TRUSTED_HOSTS` exactly as `/arp` does (lines 56-66):

```python
class ArpEventPayload(BaseModel):
    src_mac: str
    src_ip: str
    dst_ip: str


@router.post("/arp", status_code=status.HTTP_201_CREATED)
async def ingest_arp(payload: ArpEventPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """Capture ingest — loopback-only. Capture never writes directly to the DB."""
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback-only")

    event = ArpEvent(src_mac=payload.src_mac, src_ip=payload.src_ip, dst_ip=payload.dst_ip)
    db.add(event)
    await db.commit()
    return {"ok": True}
```

Add `DhcpEventPayload`/`MdnsEventPayload` Pydantic models + `/dhcp`, `/mdns` handlers in the **same file** (`capture.py`), reusing the module-level `_TRUSTED_HOSTS`.

**Analog for auth-gated CRUD routes:** `backend/src/routes/auth.py` — shows the `Depends(require_auth)` gate pattern (line 60: `_: None = Depends(require_auth)`) and `select(...).scalar_one_or_none()` query pattern (lines 18-19, 44-45). `devices.py`'s `GET /api/devices`, `POST /api/devices`, `POST /api/devices/{id}/merge` should all depend on `require_auth` from `src.auth`, matching `auth.py`'s `/me` route gating.

**Router registration:** `backend/src/main.py` lines 9, 31-32 — new routers must be imported and `app.include_router(devices.router, prefix="/api/devices")` added alongside the existing two.

---

### `backend/src/schemas/device.py` (schema, request-response)

**Analog:** `backend/src/routes/auth.py` lines 13-14 — the codebase currently inlines Pydantic payload models directly in the route file rather than a separate `schemas/` module (no `backend/src/schemas/` directory exists yet — RESEARCH.md's structure proposes creating one). Either follow RESEARCH.md's proposed split (new `schemas/device.py`) or match existing convention (inline in `routes/devices.py`) — RESEARCH.md's V5 Input Validation note requires the `type` field to be constrained to the `DeviceType` enum at the Pydantic layer:

```python
class PasswordPayload(BaseModel):
    password: str = Field(min_length=1)
```

Apply the same `Field(...)` constraint style for `DeviceRegisterPayload.name` (min_length=1) and use `DeviceType` enum directly as the Pydantic field type for `type` (Pydantic v2 validates enum membership automatically — rejects free text per V5).

---

### `capture/capture.py` (extend with DHCP sniff thread + mDNS asyncio browser)

**Analog:** same file, existing ARP sniff implementation (full file, 61 lines) — copy the `httpx.post` + `try/except Exception` + `stop_event` shape verbatim for DHCP:

```python
import os
import signal
import threading

import httpx
from scapy.all import ARP, sniff

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

stop_event = threading.Event()


def _handle_sigterm(*_args):
    stop_event.set()


signal.signal(signal.SIGTERM, _handle_sigterm)


def on_arp_packet(pkt):
    if ARP in pkt and pkt[ARP].op == 1:
        payload = {"src_mac": pkt[ARP].hwsrc, "src_ip": pkt[ARP].psrc, "dst_ip": pkt[ARP].pdst}
        try:
            httpx.post(f"{API_URL}/api/capture/arp", json=payload, timeout=5.0)
        except Exception as exc:  # noqa: BLE001 - log and keep sniffing
            print(f"[capture] POST failed: {exc}")
```

DHCP handler (`on_dhcp_packet`) must follow the identical try/except/print shape, POSTing to `/api/capture/dhcp`, and run in a second `threading.Thread` alongside the existing ARP `sniff()` call in `main()` — both honoring `stop_event`. mDNS browser runs via `asyncio.run()` in a third thread per RESEARCH.md Pattern 3 (lines 217-260 of 02-RESEARCH.md) — use the exact `AsyncZeroconf`/`AsyncServiceBrowser` code there, POSTing to `/api/capture/mdns`.

**SIGTERM handling:** all three sniff/browse loops must check the same `stop_event` — do not create a second stop mechanism.

---

### `backend/tests/test_capture.py` (extend) and new test files

**Analog:** `backend/tests/test_capture.py` (full file, 93 lines) — established pattern: loopback-success test, non-loopback-403 test (via `ASGITransport(client=(ip, port))`), gateway-trust test (via `monkeypatch.setattr(capture_module, "_TRUSTED_HOSTS", ...)`).

```python
async def test_arp_ingest(client):
    """POST /api/capture/arp from loopback (httpx test client default) succeeds."""
    payload = {"src_mac": "aa:bb:cc:dd:ee:ff", "src_ip": "192.168.1.50", "dst_ip": "192.168.1.1"}
    response = await client.post("/api/capture/arp", json=payload)
    assert response.status_code == 201
```

`test_dhcp_ingest`/`test_mdns_ingest` should mirror this exact `client` fixture usage and assert `201`. New non-loopback-403 case is optional per-endpoint since the trust check is shared module state (one regression test on the shared mechanism is likely sufficient — don't duplicate all three trust-boundary tests per endpoint, just one happy-path 201 test per new endpoint plus the existing shared 403/gateway tests already covering the mechanism).

**Analog for fixtures:** `backend/tests/conftest.py` — `test_db` (SQLite in-memory, `Base.metadata.create_all`) and `client` (dependency-override `AsyncClient`) fixtures are reused as-is for `test_devices.py`/`test_discovery.py`/`test_identity_resolver.py` — no new fixtures needed (confirmed by RESEARCH.md Wave 0 Gaps).

---

### `frontend/src/routes/dashboard/+page.svelte` (component, request-response)

**Analog:** same file, existing shell (full file, 39 lines) — keep the `onMount` auth-check + `goto('/login')` redirect pattern unchanged; replace only the placeholder `<p>` with the summary banner + card grid:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiGet } from '$lib/api';

  let authenticated = $state(false);
  let checking = $state(true);

  onMount(async () => {
    try {
      const res = await apiGet('/api/auth/me');
      if (!res.ok) {
        await goto('/login');
        return;
      }
      authenticated = true;
    } catch {
      await goto('/login');
      return;
    } finally {
      checking = false;
    }
  });
</script>
```

Fetch devices inside the same `onMount` (or a follow-up `$effect`) via a new `apiGet('/api/devices')` call, following this exact try/catch/finally shape.

---

### `frontend/src/lib/components/DeviceCard.svelte`, `RegisterDialog.svelte`, `MergeDialog.svelte`

**Analog for styling/variants:** `frontend/src/lib/components/ui/badge/badge.svelte` — `tv()` (tailwind-variants) pattern for the "Unknown" badge / dashed-border treatment (D-10). Reuse the existing `Badge` component with `variant="outline"` or `variant="destructive"` rather than hand-rolling new badge CSS.

**Analog for dialog shell:** `frontend/src/lib/components/ui/dialog/dialog-content.svelte` — `RegisterDialog`/`MergeDialog` should compose the existing `Dialog`/`DialogContent`/`DialogHeader`/`DialogFooter` primitives (already present under `ui/dialog/`), not build new modal markup.

**Analog for form/loading/error state:** `frontend/src/routes/setup/+page.svelte` lines 1-37 — the `$state` + `loading`/`errorMessage` + `apiPost` + try/catch/finally shape:

```svelte
let loading = $state(false);
let errorMessage = $state('');

async function handleSubmit(event: SubmitEvent) {
  event.preventDefault();
  errorMessage = '';
  loading = true;
  try {
    const res = await apiPost('/api/auth/setup', { password });
    if (!res.ok) {
      errorMessage = '...';
      loading = false;
      return;
    }
    await goto('/login');
  } catch {
    errorMessage = '...';
    loading = false;
  }
}
```

Apply identically for `RegisterDialog`'s submit handler (`apiPost('/api/devices', {...})`) and `MergeDialog`'s (`apiPost('/api/devices/{id}/merge', {...})`).

**Note:** existing inline `style="..."` strings (not Tailwind classes) are used in page-level `.svelte` files (`dashboard`, `setup`), while the shadcn-svelte `ui/` components use Tailwind + `tv()`. New custom components (`DeviceCard`, dialogs) should prefer composing existing `ui/` primitives (`Card`, `Badge`, `Button`, `Dialog`, `Select`, `Input`, `Label`) over hand-rolled inline styles, per the UI-SPEC's shadcn-svelte initialization (see `01-UI-SPEC.md`/`02-UI-SPEC.md` sign-off).

---

### `frontend/src/lib/api.ts` (extend)

**Analog:** same file, full existing content (18 lines) — add `listDevices`, `registerDevice`, `mergeDevice` following the exact `apiGet`/`apiPost` shape:

```typescript
const API_BASE = import.meta.env.PUBLIC_API_URL ?? '';

export async function apiPost(path: string, body: unknown): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  });
  return res;
}

export async function apiGet(path: string): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: 'include' });
  return res;
}
```

New functions can be thin wrappers (`listDevices = () => apiGet('/api/devices')`) or typed helpers returning parsed JSON — match whichever level of abstraction the planner picks consistently across all three new functions.

## Shared Patterns

### Ingest Trust Boundary (loopback/gateway-only)
**Source:** `backend/src/routes/capture.py` lines 12-47 (`_detect_default_gateway()`, `_TRUSTED_HOSTS`)
**Apply to:** `/api/capture/dhcp`, `/api/capture/mdns` — reuse the existing module-level `_TRUSTED_HOSTS` frozenset and the `client_host not in _TRUSTED_HOSTS` check verbatim. Do not write a second trust-check implementation (RESEARCH.md explicitly flags this as a drift risk).

### Session Auth Gate
**Source:** `backend/src/auth.py` (`require_auth` dependency) + `backend/src/routes/auth.py` line 60 usage
**Apply to:** All `backend/src/routes/devices.py` handlers (`GET /api/devices`, `POST /api/devices`, `POST /api/devices/{id}/merge`) — same `Depends(require_auth)` pattern, no new auth mechanism.

### Capture-Never-Writes-DB
**Source:** `capture/capture.py` (entire file) — `httpx.post()` only, no DB import, no SQLAlchemy
**Apply to:** New DHCP sniff and mDNS browser code added to `capture/capture.py` — must remain pure POST-senders; all fusion/persistence logic stays in `backend/src/services/discovery.py` and `identity_resolver.py`.

### SQLite-Compatible Test DB
**Source:** `backend/tests/conftest.py` lines 13-25 (`test_db` fixture using `Base.metadata.create_all`)
**Apply to:** All new models (`DhcpEvent`, `MdnsEvent`, `DiscoveredIdentity`, `Device`) — must use plain SQLAlchemy types (`String`, `Boolean`, `Enum`) that `Base.metadata.create_all` can render on SQLite; avoid Postgres-only column types. The upsert/`ON CONFLICT` logic in `discovery.py` is the one place this breaks down (see note under Pattern Assignments above) — planner must decide on a SQLite-compatible upsert path or a Postgres-only test fixture for that specific test.

### shadcn-svelte UI Primitives
**Source:** `frontend/src/lib/components/ui/{badge,card,dialog,button,select,input,label}/`
**Apply to:** `DeviceCard.svelte`, `RegisterDialog.svelte`, `MergeDialog.svelte` — compose existing primitives (already initialized per `02-UI-SPEC.md` sign-off) rather than hand-rolling new styled markup.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/src/services/identity_resolver.py` | service | transform | `backend/src/services/` directory is empty — this is the first service-layer file in the codebase; no precedent beyond RESEARCH.md's own Protocol example, which is authoritative here |
| `backend/tests/test_identity_resolver.py` | test | transform | First pure-unit-logic test file (no DB/HTTP fixtures needed) — existing tests are all integration-style against `client`/`test_db`; structure as plain `pytest` functions with no async/fixture dependency, following only the general file-naming convention of `backend/tests/test_*.py` |

## Metadata

**Analog search scope:** `backend/src/{models,routes,services,schemas}/`, `backend/tests/`, `capture/`, `frontend/src/{routes,lib}/`
**Files scanned:** 24 (5 models/routes files, 5 backend test files, 2 capture files, 12 frontend files including ui/ subcomponents)
**Pattern extraction date:** 2026-06-18
