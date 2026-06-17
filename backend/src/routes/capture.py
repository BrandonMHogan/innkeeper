from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.arp_event import ArpEvent

router = APIRouter()

_LOOPBACK_HOSTS = ("127.0.0.1", "::1")


class ArpEventPayload(BaseModel):
    src_mac: str
    src_ip: str
    dst_ip: str


@router.post("/arp", status_code=status.HTTP_201_CREATED)
async def ingest_arp(payload: ArpEventPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """Capture ingest — loopback-only. Capture never writes directly to the DB."""
    client_host = request.client.host if request.client else None
    if client_host not in _LOOPBACK_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback-only")

    event = ArpEvent(src_mac=payload.src_mac, src_ip=payload.src_ip, dst_ip=payload.dst_ip)
    db.add(event)
    await db.commit()
    return {"ok": True}
