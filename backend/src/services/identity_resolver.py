from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Observation:
    mac: str
    hostname: str | None
    source: str  # "arp" | "dhcp" | "mdns"
    observed_at: datetime


class IdentityResolver(Protocol):
    def resolve(self, observation: Observation) -> str:
        """Return the stable identity key this observation belongs to."""
        ...


class HostnameFallbackResolver:
    """D-02/D-03: hostname is the primary identity key, MAC is the fallback.

    Kept pure/stateless (Pitfall 2) — registry-aware identity-key-change
    logic belongs in discovery.py, not here.
    """

    def resolve(self, observation: Observation) -> str:
        hostname = observation.hostname.strip() if observation.hostname else ""
        if hostname:
            return f"host:{hostname.lower()}"
        return f"mac:{observation.mac.lower()}"
