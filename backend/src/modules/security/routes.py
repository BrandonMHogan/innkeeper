"""POST/GET /api/modules/security/* — on-demand port scan trigger/read
(SEC-01), security alert listing/acknowledgement. Every route is gated
behind Depends(require_auth) plus Depends(require_module_enabled("security"))
(T-05-15) — no new auth surface introduced.

Relocated from src/routes/security.py (Plan 05). The pre-retrofit join
against the Device table for alert serialization, and the pre-retrofit
Device existence-check queries, are both deleted entirely — every
device-name/device-existence resolution call site now goes through the
constructor-injected DeviceLookupInterface's lookup() (T-05-14), mirroring
Plan 04's traffic/routes.py retrofit pattern exactly.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_auth
from src.database import get_db
from src.host.dependencies import require_module_enabled
from src.modules.device_identity.interfaces import DeviceLookupInterface
from src.modules.security.models import PendingScanRequest, PortScanResult, SecurityAlert
from src.services.port_rules import evaluate_open_ports

router = APIRouter()

# Module-level accessor pair (mirrors traffic/routes.py's
# set_device_lookup()/get_device_lookup() pattern, Plan 04) — the
# constructor-injected DeviceLookupInterface instance the ModuleLoader
# resolved at startup is wired into route handlers here, since it's resolved
# once at load() time, not per-request.
_device_lookup: DeviceLookupInterface | None = None


def set_device_lookup(instance: DeviceLookupInterface) -> None:
    """Called once by SecurityModule's constructor at ModuleLoader wiring
    time (D-08) — injects the resolved DeviceLookupInterface instance for
    every route handler in this file to use."""
    global _device_lookup
    _device_lookup = instance


def get_device_lookup() -> DeviceLookupInterface:
    if _device_lookup is None:
        raise RuntimeError("DeviceLookupInterface not wired — ModuleLoader must run before requests are served")
    return _device_lookup


def _serialize_alert(alert: SecurityAlert, device_name: str | None = None) -> dict:
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


@router.post("/scan/{device_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    device_id: int,
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("security")),
    db: AsyncSession = Depends(get_db),
):
    """SEC-01: queue an on-demand port scan for a registered device. Never
    calls nmap itself — the capture container polls GET /api/capture/pending-scans
    and claims this row (D-03)."""
    device_info = await get_device_lookup().lookup(str(device_id))
    if device_info is None:
        raise HTTPException(status_code=404, detail="Device not found")

    db.add(PendingScanRequest(device_id=device_id))
    await db.commit()
    return {"ok": True, "device_id": device_id}


@router.get("/scan/{device_id}")
async def get_scan_result(
    device_id: int,
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("security")),
    db: AsyncSession = Depends(get_db),
):
    """Read-only — reuses evaluate_open_ports() (the same pure function the
    capture-ingest route calls) so the displayed flags always agree with
    whatever last set Device.security_status. Never triggers a scan."""
    device_info = await get_device_lookup().lookup(str(device_id))
    if device_info is None:
        raise HTTPException(status_code=404, detail="Device not found")

    result = (
        await db.execute(
            select(PortScanResult)
            .where(PortScanResult.device_id == device_id)
            .order_by(PortScanResult.scanned_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if result is None:
        return {"scanned_at": None, "ports": []}

    risky_open, unexpected_open = evaluate_open_ports(device_info.type, result.open_ports)
    ports = []
    for port in result.open_ports:
        if port in risky_open:
            flag = "risky"
        elif port in unexpected_open:
            flag = "unexpected"
        else:
            flag = "expected"
        ports.append({"port": port, "flag": flag})

    return {"scanned_at": result.scanned_at, "ports": ports}


@router.get("/alerts")
async def list_alerts(
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("security")),
    db: AsyncSession = Depends(get_db),
):
    alerts = (
        (
            await db.execute(
                select(SecurityAlert)
                .where(SecurityAlert.acknowledged == False)  # noqa: E712
                .order_by(SecurityAlert.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    serialized = []
    for alert in alerts:
        device_name = None
        if alert.device_id is not None:
            device_info = await get_device_lookup().lookup(str(alert.device_id))
            if device_info is not None:
                device_name = device_info.name
        serialized.append(_serialize_alert(alert, device_name))
    return serialized


@router.post("/alerts/{alert_id}/ack")
async def ack_alert(
    alert_id: int,
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("security")),
    db: AsyncSession = Depends(get_db),
):
    alert = (await db.execute(select(SecurityAlert).where(SecurityAlert.id == alert_id))).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.acknowledged = True
    await db.commit()
    return _serialize_alert(alert)


@router.post("/alerts/ack-all")
async def ack_all_alerts(
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("security")),
    db: AsyncSession = Depends(get_db),
):
    alerts = (
        (await db.execute(select(SecurityAlert).where(SecurityAlert.acknowledged == False)))  # noqa: E712
        .scalars()
        .all()
    )
    for alert in alerts:
        alert.acknowledged = True
    await db.commit()
    return {"acknowledged_count": len(alerts)}
