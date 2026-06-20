from src.services.threat_intel_source import StaticBlocklistSource


def _write_fixture_blocklist(tmp_path):
    """Small inline fixture file — NOT the full vendored file — for
    deterministic, fast unit tests (per 04-01-PLAN.md Test 9/10/11)."""
    blocklist_path = tmp_path / "fixture_blocklist.netset"
    blocklist_path.write_text(
        "# fixture blocklist for test_threat_intel.py\n"
        "\n"
        "203.0.113.0/24\n"
        "198.51.100.5/32\n"
        "2001:db8::/32\n"
    )
    return str(blocklist_path)


def test_ip_inside_fixture_cidr_is_malicious(tmp_path):
    source = StaticBlocklistSource(blocklist_path=_write_fixture_blocklist(tmp_path))
    assert source.is_malicious("203.0.113.42") is True


def test_ip_not_in_fixture_cidr_is_not_malicious(tmp_path):
    source = StaticBlocklistSource(blocklist_path=_write_fixture_blocklist(tmp_path))
    assert source.is_malicious("8.8.8.8") is False


def test_malformed_ip_never_raises_and_returns_false(tmp_path):
    source = StaticBlocklistSource(blocklist_path=_write_fixture_blocklist(tmp_path))
    assert source.is_malicious("not-an-ip") is False
