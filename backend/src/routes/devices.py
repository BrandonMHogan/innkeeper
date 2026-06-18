from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_auth
from src.database import get_db
from src.models.device import Device, DeviceType
from src.models.discovered_identity import DiscoveredIdentity
from src.services.identity_resolver import MDNS_PLACEHOLDER_MAC

router = APIRouter()


class DeviceRegisterPayload(BaseModel):
    identity_id: int
    name: str = Field(min_length=1)
    owner: str = ""
    type: DeviceType
    trusted: bool = False


class DeviceMergePayload(BaseModel):
    target_device_id: int


def _serialize_device(device: Device) -> dict:
    return {
        "id": device.id,
        "identity_key": device.identity_key,
        "name": device.name,
        "owner": device.owner,
        "type": device.type,
        "trusted": device.trusted,
        "last_known_mac": device.last_known_mac,
        "first_seen": device.first_seen,
        "last_seen": device.last_seen,
        "unknown": False,
    }


def _serialize_identity(identity: DiscoveredIdentity) -> dict:
    return {
        "id": identity.id,
        "identity_key": identity.identity_key,
        "mac": identity.mac,
        "hostname": identity.hostname,
        "first_seen": identity.first_seen,
        "last_seen": identity.last_seen,
        "unknown": True,
    }


@router.get("/")
async def list_devices(_: None = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    devices = (await db.execute(select(Device))).scalars().all()
    identities = (await db.execute(select(DiscoveredIdentity))).scalars().all()
    return [_serialize_device(d) for d in devices] + [_serialize_identity(i) for i in identities]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceRegisterPayload,
    _: None = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DiscoveredIdentity).where(DiscoveredIdentity.id == payload.identity_id))
    identity = result.scalar_one_or_none()
    if identity is None:
        raise HTTPException(status_code=404, detail="Discovered identity not found")

    device = Device(
        identity_key=identity.identity_key,
        name=payload.name,
        owner=payload.owner,
        type=payload.type,
        trusted=payload.trusted,
        last_known_mac=None if identity.mac == MDNS_PLACEHOLDER_MAC else identity.mac,
        first_seen=identity.first_seen,
        last_seen=identity.last_seen,
    )
    db.add(device)
    await db.delete(identity)
    await db.commit()
    return _serialize_device(device)


@router.post("/{identity_id}/merge")
async def merge_device(
    identity_id: int,
    payload: DeviceMergePayload,
    _: None = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    identity_result = await db.execute(select(DiscoveredIdentity).where(DiscoveredIdentity.id == identity_id))
    identity = identity_result.scalar_one_or_none()
    if identity is None:
        raise HTTPException(status_code=404, detail="Discovered identity not found")

    device_result = await db.execute(select(Device).where(Device.id == payload.target_device_id))
    device = device_result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Target device not found")

    if identity.mac != MDNS_PLACEHOLDER_MAC:
        device.last_known_mac = identity.mac
    device.last_seen = max(identity.last_seen, device.last_seen)
    await db.delete(identity)
    await db.commit()
    return _serialize_device(device)
