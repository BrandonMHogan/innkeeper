"""Phase 4 capture-side port scanning: a thin wrapper around the
home-assistant-libs `python-nmap` fork (D-04) for top-1000-port SYN scans,
a scan-trigger-listener thread that polls the backend's
`/api/capture/pending-scans` for on-demand scan requests, and a daily-rescan
thread that pings `/api/capture/queue-daily-scans` on a fixed schedule.

Per D-03, the capture container is the only component that ever runs nmap —
the backend stays unprivileged. Per D-01/Pitfall 2, all "registered devices
only" scoping logic for the daily rescan lives on the backend
(queue-daily-scans queries the `devices` table) — this module's daily loop
contains no device-selection logic at all, only a schedule and an HTTP call.

Mirrors capture/traffic_sniff.py's module shape and capture/capture.py's
existing POST-per-event, swallow-and-continue error handling convention.
"""

import datetime as dt
import ipaddress
import os
import threading

import httpx
import nmap

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
TOP_PORTS_ARGS = "-sS"  # SYN scan; no -p flag => nmap's own default top-1000 ports (D-02)
SCAN_POLL_INTERVAL = 3  # seconds between pending-scan polls
DAILY_RESCAN_HOUR = 3  # hour-of-day (local time) the daily-rescan trigger fires


def _run_and_post_scan(scanner: nmap.PortScanner, device_id: int, target_ip: str) -> None:
    """Runs a top-1000-port SYN scan against target_ip and POSTs the result
    to the backend. Swallows any exception (scan failure, host unreachable,
    network POST failure) so the calling loop never crashes — same
    swallow-and-continue philosophy as every other capture POST path."""
    try:
        try:
            ipaddress.ip_address(target_ip)  # raises ValueError on anything but a literal IP
        except ValueError:
            print(f"[capture] refusing to scan invalid target: {target_ip!r}")
            return
        scanner.scan(hosts=target_ip, arguments=TOP_PORTS_ARGS)
        if target_ip not in scanner.all_hosts():
            # Host did not respond — treat as "no open ports", not a crash.
            open_ports = []
        else:
            tcp_ports = scanner[target_ip].get("tcp", {})
            open_ports = [port for port, info in tcp_ports.items() if info["state"] == "open"]

        payload = {"device_id": device_id, "open_ports": open_ports}
        httpx.post(f"{API_URL}/api/capture/scan", json=payload, timeout=60.0)
    except Exception as exc:  # noqa: BLE001 - log and keep polling
        print(f"[capture] scan POST failed: {exc}")


def run_scan_listener(stop_event: threading.Event) -> None:
    """Polls the backend for pending on-demand scan requests and runs/POSTs
    each one. The backend's /pending-scans route already resolves each
    request's target IP from Device.last_known_ip — this module never needs
    its own MAC-to-IP resolution."""
    print("[capture] Starting scan listener...")
    scanner = nmap.PortScanner()
    while not stop_event.is_set():
        try:
            resp = httpx.get(f"{API_URL}/api/capture/pending-scans", timeout=5.0)
            for req in resp.json().get("pending", []):
                _run_and_post_scan(scanner, req["device_id"], req["ip"])
        except Exception as exc:  # noqa: BLE001 - log and keep polling
            print(f"[capture] scan-listener poll failed: {exc}")
        stop_event.wait(timeout=SCAN_POLL_INTERVAL)
    print("[capture] scan listener stopped.")


def run_daily_rescan_loop(stop_event: threading.Event) -> None:
    """Sleeps until DAILY_RESCAN_HOUR:00 local time, then pings the
    backend's queue-daily-scans trigger and repeats. Contains zero
    device-selection logic — all "registered devices only" scoping happens
    on the backend (Plan 04-02's queue-daily-scans route), per
    RESEARCH.md Pitfall 2."""
    print("[capture] Starting daily-rescan loop...")
    while not stop_event.is_set():
        now = dt.datetime.now()
        next_run = now.replace(hour=DAILY_RESCAN_HOUR, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += dt.timedelta(days=1)
        sleep_seconds = (next_run - now).total_seconds()

        # stop_event.wait (not time.sleep) so shutdown isn't blocked up to
        # 24h — same SIGTERM-responsiveness precedent as the sniff threads.
        if stop_event.wait(timeout=sleep_seconds):
            break

        try:
            httpx.post(f"{API_URL}/api/capture/queue-daily-scans", timeout=10.0)
        except Exception as exc:  # noqa: BLE001 - log and keep looping
            print(f"[capture] daily-rescan trigger failed: {exc}")
    print("[capture] daily-rescan loop stopped.")
