"""Phase 1 capture proof-of-concept: sniff ARP requests on the LAN and POST
each one to the FastAPI API. No real discovery pipeline exists yet (D-04) —
this only proves the LAN -> capture -> API -> PostgreSQL pipeline works
(D-05 go/no-go spike gate).

Runs as a Docker container with network_mode: host and only the
CAP_NET_RAW / CAP_NET_ADMIN capabilities (never --privileged, per D-03).
Must run as root inside the container because Python cannot receive
file-level capabilities — see 01-RESEARCH.md Pattern 8.
"""

import os
import signal
import threading

import httpx
from scapy.all import ARP, BOOTP, DHCP, Ether, sniff

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

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

    dhcp_thread.start()
    arp_thread.start()

    arp_thread.join()
    dhcp_thread.join()

    print("[capture] Stopped.")


if __name__ == "__main__":
    main()
