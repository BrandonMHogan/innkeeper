from src.models.device import DeviceType
from src.services.port_rules import evaluate_open_ports


def test_router_flags_risky_telnet_but_not_allowlisted_ports():
    risky_open, unexpected_open = evaluate_open_ports(DeviceType.ROUTER, [22, 53, 23])
    assert risky_open == [23]
    assert unexpected_open == []


def test_phone_flags_unexpected_plex_port_as_unexpected_not_risky():
    risky_open, unexpected_open = evaluate_open_ports(DeviceType.PHONE, [32400])
    assert risky_open == []
    assert unexpected_open == [32400]


def test_iot_with_no_open_ports_returns_empty_lists():
    assert evaluate_open_ports(DeviceType.IOT, []) == ([], [])


def test_other_flags_rdp_as_risky_and_http_as_unexpected():
    risky_open, unexpected_open = evaluate_open_ports(DeviceType.OTHER, [3389, 80])
    assert risky_open == [3389]
    assert unexpected_open == [80]
