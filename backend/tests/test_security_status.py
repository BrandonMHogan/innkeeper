from src.services.security_status import SecurityStatus, derive_status


def test_risky_open_port_is_critical():
    status = derive_status(
        risky_open_ports=[23],
        unexpected_open_ports=[],
        has_malicious_ip_match=False,
        has_bandwidth_anomaly=False,
    )
    assert status == SecurityStatus.CRITICAL


def test_unexpected_open_port_is_warning():
    status = derive_status(
        risky_open_ports=[],
        unexpected_open_ports=[8080],
        has_malicious_ip_match=False,
        has_bandwidth_anomaly=False,
    )
    assert status == SecurityStatus.WARNING


def test_never_scanned_defaults_to_good():
    """RESEARCH.md Pitfall 3: a device with no scan history yet (empty lists,
    no flags) must resolve to GOOD, not WARNING — never-scanned isn't guilty."""
    status = derive_status(
        risky_open_ports=[],
        unexpected_open_ports=[],
        has_malicious_ip_match=False,
        has_bandwidth_anomaly=False,
    )
    assert status == SecurityStatus.GOOD


def test_malicious_ip_match_alone_is_critical():
    status = derive_status(
        risky_open_ports=[],
        unexpected_open_ports=[],
        has_malicious_ip_match=True,
        has_bandwidth_anomaly=False,
    )
    assert status == SecurityStatus.CRITICAL
