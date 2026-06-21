import socket
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, IPvAnyAddress
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.arp_event import ArpEvent
from src.models.dhcp_event import DhcpEvent
from src.models.mdns_event import MdnsEvent
from src.modules.device_identity.identity_resolver import MDNS_PLACEHOLDER_MAC, Observation
from src.modules.device_identity.models import Device
from src.modules.device_identity.service import record_observation
from src.modules.security.models import PendingScanRequest, PortScanResult, SecurityAlert, SecurityAlertType
from src.modules.traffic.models import TrafficFlow
from src.services.bandwidth_anomaly import check_bandwidth_anomaly
from src.services.bandwidth_source import PassiveCaptureBandwidthSource
from src.services.port_rules import evaluate_open_ports
from src.services.security_status import SecurityStatus, derive_status
from src.services.threat_intel_source import get_default_threat_intel_source

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


# Trust boundary: loopback always, plus the detected LAN default gateway.
# The gateway is included defensively for deployment topologies where the
# backend container is not on `network_mode: host` and the capture
# container's traffic can appear to originate from the gateway's address
# (NAT/hairpin routing, or a reverse proxy in front of the backend). In the
# common host-network deployment, all real capture traffic is loopback and
# the gateway branch is simply unused. Every route docstring below
# describes this boundary as "loopback or detected default gateway" to
# match this set exactly.
_default_gateway = _detect_default_gateway()
_TRUSTED_HOSTS = frozenset(
    {"127.0.0.1", "::1"} | ({_default_gateway} if _default_gateway else set())
)


class ArpEventPayload(BaseModel):
    src_mac: str
    src_ip: IPvAnyAddress
    dst_ip: IPvAnyAddress


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


class ScanResultPayload(BaseModel):
    device_id: int
    open_ports: list[int]


# Mirrors nmap's own top-1000 default scan scope (RESEARCH.md ASVS V5 finding).
_MAX_OPEN_PORTS = 1000


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
    """Capture ingest — loopback or detected default gateway only. Capture never writes directly to the DB."""
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback or detected default gateway only")

    event = ArpEvent(src_mac=payload.src_mac, src_ip=str(payload.src_ip), dst_ip=str(payload.dst_ip))
    db.add(event)
    await db.commit()

    await record_observation(
        db,
        Observation(mac=payload.src_mac, hostname=None, source="arp", observed_at=datetime.now(timezone.utc)),
    )

    # D-?: ARP is the only write path for Device.last_known_ip — gives the
    # capture container a scan target (Plan 04-03) sourced only from ARP
    # observations, never DHCP/mDNS.
    matched_device = (
        await db.execute(select(Device).where(Device.last_known_mac == payload.src_mac))
    ).scalar_one_or_none()
    if matched_device is not None:
        matched_device.last_known_ip = str(payload.src_ip)
        await db.commit()

    return {"ok": True}


@router.post("/dhcp", status_code=status.HTTP_201_CREATED)
async def ingest_dhcp(payload: DhcpEventPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """Capture ingest — loopback or detected default gateway only. Capture never writes directly to the DB."""
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback or detected default gateway only")

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
    """Capture ingest — loopback or detected default gateway only. Capture never writes directly to the DB."""
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback or detected default gateway only")

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
    """Capture ingest — loopback or detected default gateway only. Capture never writes directly to the DB.

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
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback or detected default gateway only")

    if len(payload.flows) > _MAX_FLOWS_PER_ROLLUP:
        raise HTTPException(status_code=413, detail="Rollup payload exceeds maximum flow count")

    bytes_by_mac: dict[str, float] = {}
    for flow in payload.flows:
        db.add(
            TrafficFlow(
                time=payload.interval_end,
                device_mac=flow.src_mac,
                dst_ip=flow.dst_ip,
                # traffic_flows' composite PK includes dst_port, and Postgres
                # forces NOT NULL on every PK column — protocols without a
                # port (ICMP, etc.) must use 0 (not a valid real port) as the
                # sentinel rather than None, regardless of which
                # BandwidthSource sent the rollup.
                dst_port=flow.dst_port if flow.dst_port is not None else 0,
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

    # SEC-03: malicious-IP check against every distinct dst_ip in this
    # rollup. Only registered devices get an alert/status flip — a flow
    # whose src_mac doesn't match any registered Device is skipped (out of
    # this phase's scope).
    threat_intel = get_default_threat_intel_source()
    seen_hits: set[tuple[int, str]] = set()
    for flow in payload.flows:
        if not threat_intel.is_malicious(flow.dst_ip):
            continue

        device = (
            await db.execute(select(Device).where(Device.last_known_mac == flow.src_mac))
        ).scalar_one_or_none()
        if device is None:
            continue

        hit_key = (device.id, flow.dst_ip)
        if hit_key in seen_hits:
            continue
        seen_hits.add(hit_key)

        db.add(
            SecurityAlert(
                device_id=device.id,
                type=SecurityAlertType.MALICIOUS_IP,
                severity=SecurityStatus.CRITICAL,
                message=f"{device.name} contacted a known-malicious address",
            )
        )
        device.security_status = SecurityStatus.CRITICAL.value

    if seen_hits:
        await db.commit()

    return {"ok": True}


@router.post("/scan", status_code=status.HTTP_201_CREATED)
async def ingest_scan_result(payload: ScanResultPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """Capture ingest — loopback or detected default gateway only. Persists a port-scan result and
    recomputes/persists Device.security_status (SEC-01/D-06)."""
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback or detected default gateway only")

    if len(payload.open_ports) > _MAX_OPEN_PORTS:
        raise HTTPException(status_code=413, detail="Scan payload exceeds maximum open-port count")

    device = (await db.execute(select(Device).where(Device.id == payload.device_id))).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    db.add(PortScanResult(device_id=device.id, open_ports=payload.open_ports))

    risky_open, unexpected_open = evaluate_open_ports(device.type, payload.open_ports)

    # D-07: each signal source independently contributes — a clean scan
    # result must not silently clear a prior malicious-IP/bandwidth-anomaly
    # signal still backed by an unacknowledged alert.
    has_malicious_ip_match = (
        await db.execute(
            select(SecurityAlert).where(
                SecurityAlert.device_id == device.id,
                SecurityAlert.type == SecurityAlertType.MALICIOUS_IP,
                SecurityAlert.acknowledged == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none() is not None
    has_bandwidth_anomaly = (
        await db.execute(
            select(SecurityAlert).where(
                SecurityAlert.device_id == device.id,
                SecurityAlert.type == SecurityAlertType.SUSPICIOUS_TRAFFIC,
                SecurityAlert.acknowledged == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none() is not None

    result = derive_status(
        risky_open_ports=risky_open,
        unexpected_open_ports=unexpected_open,
        has_malicious_ip_match=has_malicious_ip_match,
        has_bandwidth_anomaly=has_bandwidth_anomaly,
    )
    device.security_status = result.value
    device.last_scanned_at = datetime.now(timezone.utc)

    if unexpected_open:
        existing_unexpected_alert = (
            await db.execute(
                select(SecurityAlert).where(
                    SecurityAlert.device_id == device.id,
                    SecurityAlert.type == SecurityAlertType.UNEXPECTED_PORT,
                    SecurityAlert.acknowledged == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if existing_unexpected_alert is None:
            db.add(
                SecurityAlert(
                    device_id=device.id,
                    type=SecurityAlertType.UNEXPECTED_PORT,
                    severity=SecurityStatus.WARNING,
                    message=f"{device.name} has an unexpected open port",
                )
            )

    await db.commit()
    return {"ok": True}


@router.get("/pending-scans")
async def get_pending_scans(request: Request, db: AsyncSession = Depends(get_db)):
    """Capture ingest — loopback or detected default gateway only. Claim-on-read: every returned row's
    claimed_at is set to now, preventing duplicate delivery to a second poll
    before the result is POSTed back. Rows whose Device has no
    last_known_ip yet are left unclaimed so they can be retried once an
    ARP observation populates the IP."""
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback or detected default gateway only")

    rows = (
        (
            await db.execute(
                select(PendingScanRequest, Device)
                .join(Device, Device.id == PendingScanRequest.device_id)
                .where(PendingScanRequest.claimed_at.is_(None))
                .where(Device.last_known_ip.is_not(None))
            )
        )
        .all()
    )

    now = datetime.now(timezone.utc)
    pending = []
    for pending_request, device in rows:
        pending_request.claimed_at = now
        pending.append({"device_id": pending_request.device_id, "ip": device.last_known_ip})

    if rows:
        await db.commit()

    return {"pending": pending}


@router.post("/queue-daily-scans", status_code=status.HTTP_201_CREATED)
async def queue_daily_scans(request: Request, db: AsyncSession = Depends(get_db)):
    """Capture ingest — loopback or detected default gateway only. Queues one PendingScanRequest per
    registered Device (never discovered_identities/arp_events/etc —
    RESEARCH.md Pitfall 2), skipping devices that already have an unclaimed
    request. Independently evaluates check_bandwidth_anomaly() for every
    registered device and, on a True result with no existing unacknowledged
    suspicious_traffic alert, writes the alert and recomputes/persists
    Device.security_status — D-09's bandwidth-anomaly signal is reachable
    from a real execution path, not only from its own isolated unit test.
    """
    client_host = request.client.host if request.client else None
    if client_host not in _TRUSTED_HOSTS:
        raise HTTPException(status_code=403, detail="Forbidden — capture ingest is loopback or detected default gateway only")

    devices = (await db.execute(select(Device))).scalars().all()

    queued_count = 0
    for device in devices:
        existing_unclaimed = (
            await db.execute(
                select(PendingScanRequest).where(
                    PendingScanRequest.device_id == device.id,
                    PendingScanRequest.claimed_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing_unclaimed is None:
            db.add(PendingScanRequest(device_id=device.id))
            queued_count += 1

        anomaly_detected = await check_bandwidth_anomaly(db, device.id)
        if not anomaly_detected:
            continue

        existing_suspicious_alert = (
            await db.execute(
                select(SecurityAlert).where(
                    SecurityAlert.device_id == device.id,
                    SecurityAlert.type == SecurityAlertType.SUSPICIOUS_TRAFFIC,
                    SecurityAlert.acknowledged == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if existing_suspicious_alert is not None:
            continue

        db.add(
            SecurityAlert(
                device_id=device.id,
                type=SecurityAlertType.SUSPICIOUS_TRAFFIC,
                severity=SecurityStatus.WARNING,
                message=f"{device.name} shows unusually high traffic volume",
            )
        )

        latest_scan = (
            await db.execute(
                select(PortScanResult)
                .where(PortScanResult.device_id == device.id)
                .order_by(PortScanResult.scanned_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest_scan is not None:
            risky_open, unexpected_open = evaluate_open_ports(device.type, latest_scan.open_ports)
        else:
            risky_open, unexpected_open = [], []

        has_malicious_ip_match = (
            await db.execute(
                select(SecurityAlert).where(
                    SecurityAlert.device_id == device.id,
                    SecurityAlert.type == SecurityAlertType.MALICIOUS_IP,
                    SecurityAlert.acknowledged == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none() is not None

        new_status = derive_status(
            risky_open_ports=risky_open,
            unexpected_open_ports=unexpected_open,
            has_malicious_ip_match=has_malicious_ip_match,
            has_bandwidth_anomaly=True,
        )
        device.security_status = new_status.value

    await db.commit()
    return {"queued_count": queued_count}
