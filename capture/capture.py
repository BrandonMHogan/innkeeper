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
from scapy.all import ARP, sniff

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


def main():
    print("[capture] Starting ARP sniff on all interfaces...")
    sniff(
        filter="arp",
        prn=on_arp_packet,
        store=False,
        stop_filter=lambda _pkt: stop_event.is_set(),
    )
    print("[capture] Stopped.")


if __name__ == "__main__":
    main()
