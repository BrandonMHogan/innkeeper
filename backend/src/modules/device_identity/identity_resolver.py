"""Observation/IdentityResolver/HostnameFallbackResolver/MDNS_PLACEHOLDER_MAC
— moved verbatim from src/services/identity_resolver.py into the
device_identity support module, per Plan 03 Task 1's action.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# Shared sentinel MAC used for hostname-bearing mDNS observations, which
# carry no real device-specific MAC. This value is identical across every
# such observation and must never be treated as a real device MAC for
# Device-table matching purposes (CR-05) — doing so would let any mDNS
# observation hijack any registered device that shares the same sentinel.
MDNS_PLACEHOLDER_MAC = "00:00:00:00:00:00"


@dataclass(frozen=True)
class Observation:
    mac: str
    hostname: str | None
    source: str  # "arp" | "dhcp" | "mdns"
    observed_at: datetime
    mdns_service_type: str | None = None
    dhcp_vendor_class: str | None = None


class IdentityResolver(Protocol):
    def resolve(self, observation: Observation) -> str:
        """Return the stable identity key this observation belongs to."""
        ...


class HostnameFallbackResolver:
    """D-02/D-03: hostname is the primary identity key, MAC is the fallback.

    Kept pure/stateless (Pitfall 2) — registry-aware identity-key-change
    logic belongs in service.py, not here.
    """

    def resolve(self, observation: Observation) -> str:
        hostname = observation.hostname.strip() if observation.hostname else ""
        if hostname:
            return f"host:{hostname.lower()}"
        return f"mac:{observation.mac.lower()}"
