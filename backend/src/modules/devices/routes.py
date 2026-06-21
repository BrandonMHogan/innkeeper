"""Devices feature module — thin client of DeviceIdentity. No direct
canonical-data ORM queries against Device/DiscoveredIdentity (T-05-07):
every read goes through the constructor-injected DeviceLookupInterface-
satisfying DeviceIdentityModule instance's list_all()/lookup(), every
write goes through its register()/merge() methods.

Moved from src/routes/devices.py per Plan 03 Task 2's action; every route
stacks Depends(require_module_enabled("devices")) alongside the existing
Depends(require_auth) (T-05-09 — disabled module routes 404).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_auth
from src.database import get_db
from src.host.dependencies import require_module_enabled
from src.modules.device_identity.identity_inference import infer
from src.modules.device_identity.models import Device, DeviceType, DiscoveredIdentity
from src.modules.device_identity.module import DeviceIdentityModule

router = APIRouter()

# Devices has requires=[DeviceLookupInterface] but no constructor-injection
# call site exists yet outside the ModuleLoader (main.py wires the real
# instance at startup via DevicesModule.create(deps)). Route handlers below
# call this module-level accessor so the same DeviceIdentityModule instance
# main.py's ModuleLoader run constructed is used, not a second one — see
# get_device_identity()/set_device_identity() below.
_device_identity_instance: DeviceIdentityModule | None = None


def set_device_identity(instance: DeviceIdentityModule) -> None:
    """Called once by DevicesModule's constructor at ModuleLoader wiring
    time (D-08) — injects the resolved DeviceIdentityModule instance for
    every route handler in this file to use."""
    global _device_identity_instance
    _device_identity_instance = instance


def get_device_identity() -> DeviceIdentityModule:
    if _device_identity_instance is None:
        raise RuntimeError("DeviceIdentity module not wired — ModuleLoader must run before requests are served")
    return _device_identity_instance


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
        "security_status": device.security_status,
        "last_scanned_at": device.last_scanned_at,
    }


async def _serialize_identity(identity: DiscoveredIdentity) -> dict:
    result = await infer(identity)
    return {
        "id": identity.id,
        "identity_key": identity.identity_key,
        "mac": identity.mac,
        "hostname": identity.hostname,
        "first_seen": identity.first_seen,
        "last_seen": identity.last_seen,
        "unknown": True,
        "vendor": result.vendor,
        "type_guess": result.type_guess.value if result.type_guess else None,
        "name_guess": result.name_guess,
        "raw_signals": {
            "mac": result.raw.mac,
            "raw_vendor": result.raw.raw_vendor,
            "mdns_service_type": result.raw.mdns_service_type,
            "dhcp_vendor_class": result.raw.dhcp_vendor_class,
        },
    }


@router.get("/")
async def list_devices(
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("devices")),
    db: AsyncSession = Depends(get_db),
):
    devices, identities = await get_device_identity().list_all(db)
    return [_serialize_device(d) for d in devices] + [await _serialize_identity(i) for i in identities]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceRegisterPayload,
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("devices")),
    db: AsyncSession = Depends(get_db),
):
    try:
        device = await get_device_identity().register(
            db,
            identity_id=payload.identity_id,
            name=payload.name,
            owner=payload.owner,
            device_type=payload.type,
            trusted=payload.trusted,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_device(device)


@router.post("/{identity_id}/merge")
async def merge_device(
    identity_id: int,
    payload: DeviceMergePayload,
    _: None = Depends(require_auth),
    __: None = Depends(require_module_enabled("devices")),
    db: AsyncSession = Depends(get_db),
):
    try:
        device = await get_device_identity().merge(db, identity_id, payload.target_device_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_device(device)
