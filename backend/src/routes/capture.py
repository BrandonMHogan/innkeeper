import socket

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.arp_event import ArpEvent

router = APIRouter()

_PROC_NET_ROUTE_PATH = "/proc/net/route"


def _detect_default_gateway() -> str | None:
    """Detect the default gateway IP from /proc/net/route.

    Returns the dotted-quad gateway IP for the default route (Destination
    00000000), or None if it can't be determined for any reason. Never
    raises — any failure (missing file, malformed data, wrong platform)
    falls back to None so callers can fail safe to loopback-only trust.
    """
    try:
        with open(_PROC_NET_ROUTE_PATH) as f:
            lines = f.readlines()
        if len(lines) < 2:
            return None
        header = lines[0].split()
        dest_idx = header.index("Destination")
        gateway_idx = header.index("Gateway")
        for line in lines[1:]:
            fields = line.split()
            if not fields:
                continue
            if fields[dest_idx] == "00000000":
                gateway_hex = fields[gateway_idx]
                gateway_bytes = bytes.fromhex(gateway_hex)[::-1]
                return socket.inet_ntoa(gateway_bytes)
        return None
    except (OSError, ValueError, IndexError):
        return None


_default_gateway = _detect_default_gateway()
_TRUSTED_HOSTS = frozenset(
    {"127.0.0.1", "::1"} | ({_default_gateway} if _default_gateway else set())
)


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
