from src.modules.device_identity.models import DeviceType

# D-01/D-02: curated friendly-name shortlist. Only vendors present here are
# ever shown as "vendor" on a device card or in the Register dialog pre-fill
# — the raw/legal OUI registrant string (e.g. "Sonos, Inc.") is never shown
# directly; it is only exposed inside the raw-signal popover (D-07/D-08).
# Keys are lowercase substrings matched against the raw OUI registrant
# string returned by mac-vendor-lookup.
FRIENDLY_NAMES: dict[str, str] = {
    "apple": "Apple",
    "samsung": "Samsung",
    "sonos": "Sonos",
    "google": "Google",
    "amazon": "Amazon",
    "roku": "Roku",
    "nest labs": "Nest",
    "microsoft": "Microsoft",
}

# D-03/D-05: single-category vendors — vendor alone is sufficient for a
# type guess, even with no corroborating mDNS/DHCP signal. Keyed by the
# curated friendly name (lowercased).
SINGLE_CATEGORY_VENDORS: dict[str, DeviceType] = {
    "sonos": DeviceType.IOT,
    "roku": DeviceType.TV,
    "nest": DeviceType.IOT,
}

# D-04/D-05: multi-category vendors — vendor alone is never sufficient for
# a type guess; a corroborating mDNS/DHCP signal is required. Vendor name
# may still be shown on its own per D-01.
MULTI_CATEGORY_VENDORS: set[str] = {"apple", "samsung", "google", "amazon", "microsoft"}

# D-06: mDNS service-type hints, checked before any vendor-derived guess.
# A match here always wins over a conflicting vendor-implied type. DHCP
# vendor class is intentionally not mapped here this phase (RESEARCH.md
# Pitfall 4 / Open Question 1) — those strings identify OS/client software,
# not device category, and a broad mapping risks confidently-wrong guesses.
MDNS_SERVICE_TYPE_HINTS: dict[str, DeviceType] = {
    "_googlecast._tcp": DeviceType.TV,
    "_airplay._tcp": DeviceType.TV,
    "_hap._tcp": DeviceType.IOT,
    "_ipp._tcp": DeviceType.OTHER,
}


def match_friendly_name(raw_oui: str) -> str | None:
    """Substring-match a raw OUI registrant string against the curated list (D-01)."""
    normalized = raw_oui.lower()
    for key, friendly in FRIENDLY_NAMES.items():
        if key in normalized:
            return friendly
    return None


def type_from_signal(mdns_service_type: str | None, dhcp_vendor_class: str | None) -> DeviceType | None:
    """D-06: protocol-level signal to DeviceType, checked before vendor-derived type.

    DHCP vendor class is treated as supplementary-only this phase (no
    mapping table) — see module docstring on MDNS_SERVICE_TYPE_HINTS.
    """
    if mdns_service_type:
        for hint, dtype in MDNS_SERVICE_TYPE_HINTS.items():
            if hint in mdns_service_type:
                return dtype
    return None


def type_from_vendor(friendly_name: str | None) -> DeviceType | None:
    """D-03/D-04: single-category vendor alone implies a type; multi-category does not."""
    if friendly_name is None:
        return None
    return SINGLE_CATEGORY_VENDORS.get(friendly_name.lower())
