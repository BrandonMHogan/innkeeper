from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_auth
from src.database import get_db
from src.models.device import Device
from src.models.pending_scan_request import PendingScanRequest
from src.models.port_scan_result import PortScanResult
from src.models.security_alert import SecurityAlert
from src.services.port_rules import evaluate_open_ports

router = APIRouter()


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
    db: AsyncSession = Depends(get_db),
):
    """SEC-01: queue an on-demand port scan for a registered device. Never
    calls nmap itself — the capture container polls GET /api/capture/pending-scans
    and claims this row (D-03)."""
    device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    db.add(PendingScanRequest(device_id=device_id))
    await db.commit()
    return {"ok": True, "device_id": device_id}


@router.get("/scan/{device_id}")
async def get_scan_result(
    device_id: int,
    _: None = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Read-only — reuses evaluate_open_ports() (the same pure function the
    capture-ingest route calls) so the displayed flags always agree with
    whatever last set Device.security_status. Never triggers a scan."""
    device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one_or_none()
    if device is None:
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

    risky_open, unexpected_open = evaluate_open_ports(device.type, result.open_ports)
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


@router.post("/alerts/{alert_id}/ack")
async def ack_alert(
    alert_id: int,
    _: None = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    alert = (await db.execute(select(SecurityAlert).where(SecurityAlert.id == alert_id))).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.acknowledged = True
    await db.commit()
    return _serialize_alert(alert)


@router.post("/alerts/ack-all")
async def ack_all_alerts(_: None = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    alerts = (
        (await db.execute(select(SecurityAlert).where(SecurityAlert.acknowledged == False)))  # noqa: E712
        .scalars()
        .all()
    )
    for alert in alerts:
        alert.acknowledged = True
    await db.commit()
    return {"acknowledged_count": len(alerts)}
