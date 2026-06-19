"""Phase 3 traffic-sniff loop: a dpkt-based raw-socket capture loop that
observes WAN-bound packets (D-03), aggregates bytes in-process by 5-tuple
over a ~5-10s window (D-01/D-02), and maintains a passive DNS-sniffed
IP-to-hostname cache (D-08). Posts one rollup batch per window to the API
— never one POST per packet.

Runs as a fourth thread inside the existing capture container alongside
the ARP/DHCP/mDNS sniff loops in capture.py, sharing the same module-level
stop_event for SIGTERM propagation (Pitfall 6 in capture.py's docstring).
"""

import ipaddress
import os
import socket
import threading
import time

import dpkt
import httpx

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
FLUSH_INTERVAL = 7  # seconds — midpoint of the locked 5-10s range (D-01/D-11)

ETH_P_ALL = 3


def _is_wan_bound(src_ip: str, dst_ip: str) -> bool:
    """Returns True only when the packet crosses from a private RFC1918
    range to a non-private destination (or vice versa) — D-03's WAN-only
    scope. Drops any packet where both src and dst are private (LAN-to-LAN
    traffic) or both are non-private (shouldn't normally happen on this
    capture point, but treated as non-WAN to be safe)."""
    try:
        src_private = ipaddress.ip_address(src_ip).is_private
        dst_private = ipaddress.ip_address(dst_ip).is_private
    except ValueError:
        return False
    return src_private != dst_private


def _mac_str(raw_mac: bytes) -> str:
    """Format a raw 6-byte MAC as a colon-joined hex string, matching
    capture.py's existing pkt[ARP].hwsrc-style string MACs."""
    return ":".join(f"{b:02x}" for b in raw_mac)


def _flush_and_post(flows: dict, dns_cache: dict, interval_start: float, interval_end: float) -> None:
    """Builds the rollup payload from the current flow table and POSTs it
    to the API, swallowing any exception so the sniff loop never crashes
    on a POST failure (mirrors capture.py's on_arp_packet/on_dhcp_packet
    try/except style)."""
    if not flows:
        return

    flow_entries = []
    for (src_mac, dst_ip, dst_port, protocol), num_bytes in flows.items():
        flow_entries.append(
            {
                "src_mac": src_mac,
                "dst_ip": dst_ip,
                "dst_port": dst_port,
                "protocol": protocol,
                "bytes": num_bytes,
                "dst_hostname": dns_cache.get(dst_ip),
            }
        )

    payload = {
        "interval_start": _iso8601(interval_start),
        "interval_end": _iso8601(interval_end),
        "flows": flow_entries,
    }

    try:
        httpx.post(f"{API_URL}/api/capture/traffic", json=payload, timeout=5.0)
    except Exception as exc:  # noqa: BLE001 - log and keep sniffing
        print(f"[capture] traffic POST failed: {exc}")


def _iso8601(monotonic_time: float) -> str:
    """Converts a time.monotonic() reading to an ISO8601 wall-clock string
    by combining it with the current time.time() offset at call time."""
    wall_clock = time.time() - (time.monotonic() - monotonic_time)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(wall_clock))


def run_traffic_sniff(stop_event: threading.Event) -> None:
    """Public entry point capture.py's main() calls as a thread target,
    accepting the shared stop_event (not creating its own)."""
    print("[capture] Starting traffic sniff on all interfaces...")

    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
    sock.settimeout(1.0)

    flows: dict[tuple, int] = {}
    dns_cache: dict[str, str] = {}
    interval_start = time.monotonic()
    last_flush = interval_start

    while not stop_event.is_set():
        try:
            raw, _ = sock.recvfrom(65536)
        except socket.timeout:
            pass
        except Exception as exc:  # noqa: BLE001 - log and keep sniffing
            print(f"[capture] traffic sniff recv failed: {exc}")
        else:
            try:
                eth = dpkt.ethernet.Ethernet(raw)
                if not isinstance(eth.data, dpkt.ip.IP):
                    continue
                ip = eth.data

                src_ip = socket.inet_ntoa(ip.src)
                dst_ip = socket.inet_ntoa(ip.dst)

                if not _is_wan_bound(src_ip, dst_ip):
                    continue

                sport = getattr(ip.data, "sport", None)
                dport = getattr(ip.data, "dport", None)

                if ip.p == dpkt.ip.IP_PROTO_UDP and (sport == 53 or dport == 53):
                    try:
                        dns = dpkt.dns.DNS(ip.data.data)
                    except dpkt.dpkt.UnpackError:
                        pass
                    else:
                        if dns.qr == dpkt.dns.DNS_R and dns.qd:
                            qname = dns.qd[0].name
                            for rr in dns.an:
                                if rr.type == dpkt.dns.DNS_A:
                                    dns_cache[socket.inet_ntoa(rr.rdata)] = qname
                    continue

                key = (_mac_str(eth.src), dst_ip, dport, ip.p)
                flows[key] = flows.get(key, 0) + len(raw)
            except Exception as exc:  # noqa: BLE001 - a single malformed frame
                # must never crash the whole sniff thread.
                print(f"[capture] traffic sniff parse failed: {exc}")

        now = time.monotonic()
        if now - last_flush >= FLUSH_INTERVAL:
            _flush_and_post(flows, dns_cache, last_flush, now)
            flows.clear()
            last_flush = now

    sock.close()
    print("[capture] traffic sniff stopped.")
