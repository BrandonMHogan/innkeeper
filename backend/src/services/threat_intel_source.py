import ipaddress
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class ThreatIntelSource(Protocol):
    """D-08: swappable threat-data interface, mirrors BandwidthSource (D-07)."""

    def is_malicious(self, ip: str) -> bool: ...


class StaticBlocklistSource:
    """The only built-in source today (D-08) — loads a vendored flat CIDR
    file at startup, matches via ipaddress network containment. A future
    Phase opt-in RemoteFeedSource (D-10) implements the same Protocol.
    """

    # Defensive sanity caps against a corrupted/malicious feed entry that
    # parses successfully but is far too broad (e.g. an accidental 0.0.0.0/0
    # in an updated feed would otherwise silently match every IPv4 address
    # as malicious). Any parsed network wider than these prefix lengths is
    # rejected rather than loaded.
    _MAX_IPV4_PREFIXLEN = 8
    _MAX_IPV6_PREFIXLEN = 32

    def __init__(self, blocklist_path: str = "src/data/firehol_level1.netset"):
        self._networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        with open(blocklist_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    network = ipaddress.ip_network(line, strict=False)
                except ValueError:
                    logger.warning("Skipping malformed blocklist line: %r", line)
                    continue  # skip malformed lines defensively

                if isinstance(network, ipaddress.IPv4Network) and network.prefixlen < self._MAX_IPV4_PREFIXLEN:
                    logger.warning(
                        "Skipping overly broad IPv4 network in blocklist (wider than /%d): %r",
                        self._MAX_IPV4_PREFIXLEN,
                        line,
                    )
                    continue
                if isinstance(network, ipaddress.IPv6Network) and network.prefixlen < self._MAX_IPV6_PREFIXLEN:
                    logger.warning(
                        "Skipping overly broad IPv6 network in blocklist (wider than /%d): %r",
                        self._MAX_IPV6_PREFIXLEN,
                        line,
                    )
                    continue

                self._networks.append(network)

    def is_malicious(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(addr in net for net in self._networks)


# D-08: lazy singleton so the vendored blocklist file is parsed once per
# process, not on every is_malicious() call site.
_DEFAULT_SOURCE: ThreatIntelSource | None = None


def get_default_threat_intel_source() -> ThreatIntelSource:
    global _DEFAULT_SOURCE
    if _DEFAULT_SOURCE is None:
        _DEFAULT_SOURCE = StaticBlocklistSource()
    return _DEFAULT_SOURCE
