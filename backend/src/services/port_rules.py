from src.models.device import DeviceType

# D-05: universal risky ports — flagged regardless of device type.
# Classic unauthenticated/legacy-remote-access services.
RISKY_PORTS: frozenset[int] = frozenset(
    {
        21,  # FTP — unauthenticated/plaintext
        23,  # Telnet — plaintext remote shell
        135,  # MS RPC
        139,  # NetBIOS / SMB
        445,  # SMB
        512,
        513,
        514,  # rexec/rlogin/rsh
        1433,  # MSSQL default
        3306,  # MySQL default — only risky if exposed beyond loopback, still flag
        3389,  # RDP
        5900,  # VNC
    }
)

# D-05: per-DeviceType expected-ports allowlist. Anything open outside both
# this set AND RISKY_PORTS is "unexpected" (warning, not critical).
EXPECTED_PORTS: dict[DeviceType, frozenset[int]] = {
    DeviceType.ROUTER: frozenset({22, 53, 80, 443}),  # SSH/DNS/HTTP/HTTPS admin
    DeviceType.IOT: frozenset({80, 443, 1900}),  # HTTP/S + SSDP discovery
    DeviceType.TV: frozenset({80, 443, 7000, 8008, 8009}),  # casting/streaming control ports
    DeviceType.CONSOLE: frozenset({80, 443}),
    DeviceType.PHONE: frozenset(),
    DeviceType.LAPTOP: frozenset(),
    DeviceType.DESKTOP: frozenset(),
    DeviceType.TABLET: frozenset(),
    DeviceType.OTHER: frozenset(),
}


def evaluate_open_ports(device_type: DeviceType, open_ports: list[int]) -> tuple[list[int], list[int]]:
    """Returns (risky_open, unexpected_open) — both empty lists if clean.

    risky_open: any open port in RISKY_PORTS (always flagged, any device).
    unexpected_open: open, not risky, and not in this device type's allowlist.
    """
    allowlist = EXPECTED_PORTS.get(device_type, frozenset())
    risky_open = [p for p in open_ports if p in RISKY_PORTS]
    unexpected_open = [p for p in open_ports if p not in RISKY_PORTS and p not in allowlist]
    return risky_open, unexpected_open
