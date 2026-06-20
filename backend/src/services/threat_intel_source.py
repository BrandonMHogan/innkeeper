import ipaddress
from typing import Protocol


class ThreatIntelSource(Protocol):
    """D-08: swappable threat-data interface, mirrors BandwidthSource (D-07)."""

    def is_malicious(self, ip: str) -> bool: ...


class StaticBlocklistSource:
    """The only built-in source today (D-08) — loads a vendored flat CIDR
    file at startup, matches via ipaddress network containment. A future
    Phase opt-in RemoteFeedSource (D-10) implements the same Protocol.
    """

    def __init__(self, blocklist_path: str = "src/data/firehol_level1.netset"):
        self._networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        with open(blocklist_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    self._networks.append(ipaddress.ip_network(line, strict=False))
                except ValueError:
                    continue  # skip malformed lines defensively

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
