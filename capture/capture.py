"""Phase 1 capture proof-of-concept: sniff ARP requests on the LAN and POST
each one to the FastAPI API. No real discovery pipeline exists yet (D-04) —
this only proves the LAN -> capture -> API -> PostgreSQL pipeline works
(D-05 go/no-go spike gate).

Runs as a Docker container with network_mode: host and only the
CAP_NET_RAW / CAP_NET_ADMIN capabilities (never --privileged, per D-03).
Must run as root inside the container because Python cannot receive
file-level capabilities — see 01-RESEARCH.md Pattern 8.
"""

import asyncio
import os
import signal
import threading

import httpx
from scapy.all import ARP, BOOTP, DHCP, Ether, sniff
from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

from traffic_sniff import run_traffic_sniff

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

COMMON_SERVICE_TYPES = [
    "_http._tcp.local.",
    "_airplay._tcp.local.",
    "_ipp._tcp.local.",
    "_googlecast._tcp.local.",
    "_spotify-connect._tcp.local.",
    "_device-info._tcp.local.",
    "_workstation._tcp.local.",
]

stop_event = threading.Event()


def _handle_sigterm(*_args):
    """Set the stop flag on SIGTERM so sniff()'s stop_filter can return True
    and the process exits promptly instead of blocking `docker compose down`
    (Pitfall 6)."""
    stop_event.set()


signal.signal(signal.SIGTERM, _handle_sigterm)


def on_arp_packet(pkt):
    """Called by Scapy for each captured ARP packet."""
    if ARP in pkt and pkt[ARP].op == 1:  # ARP request (who-has)
        payload = {
            "src_mac": pkt[ARP].hwsrc,
            "src_ip": pkt[ARP].psrc,
            "dst_ip": pkt[ARP].pdst,
        }
        try:
            httpx.post(f"{API_URL}/api/capture/arp", json=payload, timeout=5.0)
        except Exception as exc:  # noqa: BLE001 - log and keep sniffing
            print(f"[capture] POST failed: {exc}")


def on_dhcp_packet(pkt):
    """Called by Scapy for each captured DHCP/BOOTP packet. Passive only —
    no active DHCP probing (D-08). Not every DHCP packet carries a hostname
    option (option 12); many devices only send requested_addr, so hostname
    stays Optional."""
    if DHCP not in pkt:
        return

    mac = pkt[Ether].src if Ether in pkt else pkt[BOOTP].chaddr.hex()
    hostname = None
    requested_ip = None
    vendor_class_id = None

    for opt in pkt[DHCP].options:
        if not isinstance(opt, tuple):
            continue
        label, value = opt
        if label == "hostname":
            hostname = value.decode(errors="replace") if isinstance(value, bytes) else value
        elif label == "requested_addr":
            requested_ip = value
        elif label == "vendor_class_id":
            vendor_class_id = value.decode(errors="replace") if isinstance(value, bytes) else value

    payload = {
        "src_mac": mac,
        "hostname": hostname,
        "requested_ip": requested_ip,
        "vendor_class_id": vendor_class_id,
    }
    try:
        httpx.post(f"{API_URL}/api/capture/dhcp", json=payload, timeout=5.0)
    except Exception as exc:  # noqa: BLE001 - log and keep sniffing
        print(f"[capture] DHCP POST failed: {exc}")


def on_service_state_change(zeroconf, service_type, name, state_change):
    """Called by AsyncServiceBrowser whenever a matching mDNS service is
    seen. Passive only — browses the fixed COMMON_SERVICE_TYPES allowlist,
    no active probing beyond the standard mDNS query/response exchange."""
    if state_change is not ServiceStateChange.Added:
        return
    asyncio.ensure_future(_post_service_info(zeroconf, service_type, name))


async def _post_service_info(zeroconf, service_type, name):
    info = AsyncServiceInfo(service_type, name)
    if await info.async_request(zeroconf, 3000):
        payload = {
            "hostname": info.server,
            "addresses": ",".join(info.parsed_scoped_addresses()),
            "service_type": service_type,
        }
        async with httpx.AsyncClient() as client:
            try:
                await client.post(f"{API_URL}/api/capture/mdns", json=payload, timeout=5.0)
            except Exception as exc:  # noqa: BLE001 - log and keep browsing
                print(f"[capture] mDNS POST failed: {exc}")


async def run_mdns_browser(stop_event_async: asyncio.Event):
    aiozc = AsyncZeroconf()
    browser = AsyncServiceBrowser(
        aiozc.zeroconf, COMMON_SERVICE_TYPES, handlers=[on_service_state_change]
    )
    await stop_event_async.wait()
    await browser.async_cancel()
    await aiozc.async_close()


async def _mdns_main():
    """Bridges the module-level threading.Event (shared SIGTERM stop signal
    with ARP/DHCP) into a local asyncio.Event for run_mdns_browser, without
    introducing a second independent stop mechanism."""
    internal_event = asyncio.Event()

    async def _watch_stop_event():
        while not stop_event.is_set():
            await asyncio.sleep(0.5)
        internal_event.set()

    asyncio.ensure_future(_watch_stop_event())
    await run_mdns_browser(internal_event)


def run_mdns_thread():
    print("[capture] Starting mDNS browser...")
    asyncio.run(_mdns_main())
    print("[capture] mDNS browser stopped.")


def run_arp_sniff():
    print("[capture] Starting ARP sniff on all interfaces...")
    sniff(
        filter="arp",
        prn=on_arp_packet,
        store=False,
        stop_filter=lambda _pkt: stop_event.is_set(),
    )
    print("[capture] ARP sniff stopped.")


def run_dhcp_sniff():
    print("[capture] Starting DHCP sniff on all interfaces...")
    sniff(
        filter="udp and (port 67 or port 68)",
        prn=on_dhcp_packet,
        store=False,
        stop_filter=lambda _pkt: stop_event.is_set(),
    )
    print("[capture] DHCP sniff stopped.")


def main():
    arp_thread = threading.Thread(target=run_arp_sniff, name="arp-sniff")
    dhcp_thread = threading.Thread(target=run_dhcp_sniff, name="dhcp-sniff")
    mdns_thread = threading.Thread(target=run_mdns_thread, name="mdns-browser")
    traffic_thread = threading.Thread(
        target=run_traffic_sniff, args=(stop_event,), name="traffic-sniff"
    )

    mdns_thread.start()
    dhcp_thread.start()
    arp_thread.start()
    traffic_thread.start()

    arp_thread.join()
    dhcp_thread.join()
    mdns_thread.join()
    traffic_thread.join()

    print("[capture] Stopped.")


if __name__ == "__main__":
    main()
