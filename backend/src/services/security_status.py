import enum


class SecurityStatus(str, enum.Enum):
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"


def derive_status(
    *,
    risky_open_ports: list[int],
    unexpected_open_ports: list[int],
    has_malicious_ip_match: bool,
    has_bandwidth_anomaly: bool,
) -> SecurityStatus:
    """D-06: table-driven, no opaque scoring. A never-scanned device passes
    empty lists/False here and correctly resolves to GOOD (D-06's explicit
    'not yet scanned defaults to good' rule) — callers surface 'not scanned'
    via a separate timestamp field, never via this enum.
    """
    if risky_open_ports or has_malicious_ip_match:
        return SecurityStatus.CRITICAL
    if unexpected_open_ports or has_bandwidth_anomaly:
        return SecurityStatus.WARNING
    return SecurityStatus.GOOD
