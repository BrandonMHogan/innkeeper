import socket
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.arp_event import ArpEvent
from src.models.dhcp_event import DhcpEvent
from src.models.mdns_event import MdnsEvent
from src.models.traffic_flow import TrafficFlow
from src.services.bandwidth_source import PassiveCaptureBandwidthSource
from src.services.discovery import record_observation
from src.services.identity_resolver import MDNS_PLACEHOLDER_MAC, Observation

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


class DhcpEventPayload(BaseModel):
    src_mac: str
    hostname: str | None = None
    requested_ip: str | None = None
    vendor_class_id: str | None = None


class MdnsEventPayload(BaseModel):
    hostname: str | None = None
    addresses: str
    service_type: str


class TrafficFlowPayload(BaseModel):
    src_mac: str
    dst_ip: str
    dst_port: int | None = None
    protocol: int
    bytes: int
    dst_hostname: str | None = None


# T-03-08: bound the worst-case write volume a single rollup can cause, in
# case a misbehaving/compromised capture process sends a pathologically
# large flow list. Several thousand distinct 5-tuples in one ~7s window is
# already an extreme outlier for a single household's WAN traffic.
_MAX_FLOWS_PER_ROLLUP = 5000


class TrafficRollupPayload(BaseModel):
    interval_start: datetime
    interval_end: datetime
    flows: list[TrafficFlowPayload]


@router.post("/arp", status_code=status.HTTP_201_CREATED)
async def ingest_arp(payload: ArpEventPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """Capture ingest — loopback-only. Capture never writes directly to the DB."""
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback-only")

    event = ArpEvent(src_mac=payload.src_mac, src_ip=payload.src_ip, dst_ip=payload.dst_ip)
    db.add(event)
    await db.commit()

    await record_observation(
        db,
        Observation(mac=payload.src_mac, hostname=None, source="arp", observed_at=datetime.now(timezone.utc)),
    )
    return {"ok": True}


@router.post("/dhcp", status_code=status.HTTP_201_CREATED)
async def ingest_dhcp(payload: DhcpEventPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """Capture ingest — loopback-only. Capture never writes directly to the DB."""
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback-only")

    event = DhcpEvent(
        src_mac=payload.src_mac,
        hostname=payload.hostname,
        requested_ip=payload.requested_ip,
        vendor_class_id=payload.vendor_class_id,
    )
    db.add(event)
    await db.commit()

    await record_observation(
        db,
        Observation(
            mac=payload.src_mac,
            hostname=payload.hostname,
            source="dhcp",
            observed_at=datetime.now(timezone.utc),
            dhcp_vendor_class=payload.vendor_class_id,
        ),
    )
    return {"ok": True}


@router.post("/mdns", status_code=status.HTTP_201_CREATED)
async def ingest_mdns(payload: MdnsEventPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """Capture ingest — loopback-only. Capture never writes directly to the DB."""
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback-only")

    event = MdnsEvent(
        hostname=payload.hostname,
        service_type=payload.service_type,
        addresses=payload.addresses,
    )
    db.add(event)
    await db.commit()

    # mDNS browsing alone yields no MAC address. A hostname-less mDNS
    # observation carries no usable identity signal at all (the placeholder
    # MAC is shared across every hostname-less mDNS event, so resolving an
    # identity from it would collide distinct physical devices onto one
    # row) — skip identity resolution entirely in that case. ARP/DHCP
    # observations for the same physical device will independently resolve
    # the real MAC-keyed identity; only hostname-bearing mDNS observations
    # contribute to fusion (D-02), via the shared placeholder MAC.
    if not payload.hostname or not payload.hostname.strip():
        return {"ok": True, "skipped": "no identity signal"}

    await record_observation(
        db,
        Observation(
            mac=MDNS_PLACEHOLDER_MAC,
            hostname=payload.hostname,
            source="mdns",
            observed_at=datetime.now(timezone.utc),
            mdns_service_type=payload.service_type,
        ),
    )
    return {"ok": True}


@router.post("/traffic", status_code=status.HTTP_201_CREATED)
async def ingest_traffic(payload: TrafficRollupPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """Capture ingest — loopback-only. Capture never writes directly to the DB.

    Writes one TrafficFlow row per distinct 5-tuple in the rollup and one
    summed BandwidthMetric row per distinct src_mac, via the swappable
    BandwidthSource (D-07).

    Known v1 limitation: bytes_rx is hardcoded to 0.0 for every rollup this
    route writes. A single-point passive capture sniffing WAN-bound traffic
    cannot reliably observe a device's inbound return traffic with the same
    5-tuple fidelity used here — correlating egress frames with inbound
    responses would require full bidirectional flow tracking/connection-state
    matching, explicitly out of scope for D-04's flow-level, non-DPI capture
    design. TRAF-02 is still satisfied (bytes_tx is real, captured data);
    full bidirectional accounting is a candidate backlog item once a
    router-side counter source (e.g. a future UniFi adapter) exists.
    """
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback-only")

    if len(payload.flows) > _MAX_FLOWS_PER_ROLLUP:
        raise HTTPException(status_code=413, detail="Rollup payload exceeds maximum flow count")

    bytes_by_mac: dict[str, float] = {}
    for flow in payload.flows:
        db.add(
            TrafficFlow(
                time=payload.interval_end,
                device_mac=flow.src_mac,
                dst_ip=flow.dst_ip,
                dst_port=flow.dst_port,
                protocol=flow.protocol,
                bytes=flow.bytes,
                dst_hostname=flow.dst_hostname,
            )
        )
        bytes_by_mac[flow.src_mac] = bytes_by_mac.get(flow.src_mac, 0.0) + flow.bytes

    await db.commit()

    bandwidth_source = PassiveCaptureBandwidthSource()
    for device_mac, summed_bytes in bytes_by_mac.items():
        await bandwidth_source.write_rollup(
            db,
            device_mac=device_mac,
            bytes_rx=0.0,
            bytes_tx=summed_bytes,
            observed_at=payload.interval_end,
        )

    return {"ok": True}
