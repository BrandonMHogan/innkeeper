from datetime import datetime

from src.services.identity_resolver import HostnameFallbackResolver, Observation


def test_hostname_fallback_resolver():
    resolver = HostnameFallbackResolver()
    observation = Observation(
        mac="aa:bb:cc:dd:ee:ff",
        hostname="Brandons-iPhone",
        source="mdns",
        observed_at=datetime.utcnow(),
    )
    assert resolver.resolve(observation) == "host:brandons-iphone"


def test_mac_fallback_when_no_hostname():
    resolver = HostnameFallbackResolver()
    observation = Observation(
        mac="AA:BB:CC:DD:EE:FF",
        hostname=None,
        source="arp",
        observed_at=datetime.utcnow(),
    )
    assert resolver.resolve(observation) == "mac:aa:bb:cc:dd:ee:ff"


def test_empty_hostname_treated_as_none():
    resolver = HostnameFallbackResolver()
    observation = Observation(
        mac="AA:BB:CC:DD:EE:FF",
        hostname="",
        source="dhcp",
        observed_at=datetime.utcnow(),
    )
    assert resolver.resolve(observation) == "mac:aa:bb:cc:dd:ee:ff"
