from dataclasses import dataclass

from mac_vendor_lookup import AsyncMacLookup, InvalidMacError, VendorNotFoundError

from src.data.vendor_catalog import match_friendly_name, type_from_signal, type_from_vendor
from src.models.device import DeviceType
from src.models.discovered_identity import DiscoveredIdentity
from src.services.identity_resolver import MDNS_PLACEHOLDER_MAC

# Pitfall 3: AsyncMacLookup lazily loads its vendor-prefix table on first
# lookup() call. Instantiate once at module scope and reuse across every
# infer() call within the process lifetime — never per-call instantiation.
_mac_lookup = AsyncMacLookup()


@dataclass(frozen=True)
class RawSignals:
    mac: str | None
    raw_vendor: str | None
    mdns_service_type: str | None
    dhcp_vendor_class: str | None


@dataclass(frozen=True)
class InferenceResult:
    vendor: str | None
    type_guess: DeviceType | None
    name_guess: str | None
    raw: RawSignals


def _is_locally_administered(mac: str) -> bool:
    """U/L bit check (Pitfall 1) — randomized MACs must never reach vendor lookup."""
    first_octet = mac.split(":")[0]
    return int(first_octet, 16) & 0x02 != 0


async def infer(identity: DiscoveredIdentity) -> InferenceResult:
    """Pure, stateless DISC-05/06 inference over a DiscoveredIdentity-shaped input.

    No DB session parameter, no I/O beyond the in-memory AsyncMacLookup
    prefix-table read — mirrors identity_resolver.py's stateless style.
    """
    is_placeholder = identity.mac == MDNS_PLACEHOLDER_MAC
    is_locally_administered = _is_locally_administered(identity.mac)

    raw_vendor: str | None = None
    if not is_placeholder and not is_locally_administered:
        try:
            raw_vendor = await _mac_lookup.lookup(identity.mac)
        except (VendorNotFoundError, InvalidMacError):
            raw_vendor = None

    vendor = match_friendly_name(raw_vendor) if raw_vendor else None

    signal_type = type_from_signal(identity.mdns_service_type, identity.dhcp_vendor_class)
    vendor_type = type_from_vendor(vendor)
    type_guess = signal_type if signal_type is not None else vendor_type

    name_guess = identity.hostname.strip() if identity.hostname and identity.hostname.strip() else None

    raw = RawSignals(
        mac=None if is_placeholder else identity.mac,
        raw_vendor=raw_vendor,
        mdns_service_type=identity.mdns_service_type,
        dhcp_vendor_class=identity.dhcp_vendor_class,
    )

    return InferenceResult(vendor=vendor, type_guess=type_guess, name_guess=name_guess, raw=raw)
