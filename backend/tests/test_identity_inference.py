from datetime import datetime

from mac_vendor_lookup import AsyncMacLookup

from src.modules.device_identity.identity_inference import infer
from src.modules.device_identity.identity_resolver import MDNS_PLACEHOLDER_MAC
from src.modules.device_identity.models import DeviceType, DiscoveredIdentity


def _identity(**overrides) -> DiscoveredIdentity:
    return DiscoveredIdentity(
        id=overrides.get("id", 1),
        identity_key=overrides.get("identity_key", "mac:aa:bb:cc:dd:ee:ff"),
        mac=overrides.get("mac", "aa:bb:cc:dd:ee:ff"),
        hostname=overrides.get("hostname"),
        mdns_service_type=overrides.get("mdns_service_type"),
        dhcp_vendor_class=overrides.get("dhcp_vendor_class"),
        first_seen=overrides.get("first_seen", datetime(2026, 1, 1)),
        last_seen=overrides.get("last_seen", datetime(2026, 1, 2)),
    )


async def test_vendor_inference():
    # Sonos OUI prefix -> curated friendly name
    sonos = _identity(mac="B8:E9:37:00:00:01")
    result = await infer(sonos)
    assert result.vendor == "Sonos"

    # An OUI that resolves to a raw registrant string with no curated match
    # ("Private", a real mac-vendor-lookup registrant string) -> no vendor.
    no_match = _identity(mac="AC:DE:48:00:00:01")
    result = await infer(no_match)
    assert result.vendor is None

    # Placeholder MAC never attempts vendor lookup.
    placeholder = _identity(mac=MDNS_PLACEHOLDER_MAC)
    result = await infer(placeholder)
    assert result.vendor is None

    # Locally-administered (U/L bit set) MAC never attempts vendor lookup.
    locally_administered = _identity(mac="02:00:00:00:00:01")
    result = await infer(locally_administered)
    assert result.vendor is None


async def test_vendor_inference_skips_lookup_for_excluded_macs(monkeypatch):
    calls = []

    async def fake_lookup(self, mac):
        calls.append(mac)
        raise AssertionError("lookup() must not be called for excluded MACs")

    monkeypatch.setattr(AsyncMacLookup, "lookup", fake_lookup)

    placeholder = _identity(mac=MDNS_PLACEHOLDER_MAC)
    await infer(placeholder)

    locally_administered = _identity(mac="02:00:00:00:00:01")
    await infer(locally_administered)

    assert calls == []


async def test_vendor_lookup_failure_handling():
    # Unassigned OUI prefix -> VendorNotFoundError, degrades to vendor=None.
    not_found = _identity(mac="FF:FF:FF:00:00:01")
    result = await infer(not_found)
    assert result.vendor is None
    assert result.raw.raw_vendor is None


async def test_vendor_category_classification():
    # Single-category vendor (Sonos) alone, no signal -> IOT.
    sonos = _identity(mac="B8:E9:37:00:00:01")
    result = await infer(sonos)
    assert result.vendor == "Sonos"
    assert result.type_guess == DeviceType.IOT

    # Multi-category vendor (Apple) alone, no signal -> vendor set, no type.
    apple = _identity(mac="00:1C:B3:00:00:01")
    result = await infer(apple)
    assert result.vendor == "Apple"
    assert result.type_guess is None


async def test_signal_overrides_vendor_type():
    # Sonos (single-category, implies IOT) + googlecast mDNS signal (implies TV)
    # -> mDNS wins per D-06.
    identity = _identity(mac="B8:E9:37:00:00:01", mdns_service_type="_googlecast._tcp")
    result = await infer(identity)
    assert result.vendor == "Sonos"
    assert result.type_guess == DeviceType.TV

    # Signal that doesn't map to any known type -> fall back to vendor-implied type.
    identity_unknown_signal = _identity(mac="B8:E9:37:00:00:01", mdns_service_type="_unknown._tcp")
    result = await infer(identity_unknown_signal)
    assert result.type_guess == DeviceType.IOT


async def test_no_signal_yields_no_guess():
    identity = _identity(mac="FF:FF:FF:00:00:01", hostname=None)
    result = await infer(identity)
    assert result.vendor is None
    assert result.type_guess is None
    assert result.name_guess is None

    identity_with_hostname = _identity(mac="FF:FF:FF:00:00:01", hostname="some-device")
    result = await infer(identity_with_hostname)
    assert result.name_guess == "some-device"
