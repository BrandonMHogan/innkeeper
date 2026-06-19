import tldextract

# D-10: registered-domain grouping for the per-device destination breakdown
# (e.g. www.netflix.com / api.netflix.com both group under netflix.com).
#
# Offline mode only (suffix_list_urls=()) — zero outbound network calls, per
# D-09/CLAUDE.md's no-telemetry constraint. tldextract ships a bundled PSL
# snapshot so this works without ever fetching the suffix list at runtime.
_extractor = tldextract.TLDExtract(suffix_list_urls=())


def registered_domain(hostname: str) -> str:
    """Group a raw hostname under its registered (public-suffix-aware) domain.

    Called only at query/serialization time — never at capture/ingest time.
    TrafficFlow.dst_hostname always stores the raw, ungrouped hostname; this
    function is what groups subdomains for display.

    Falls back to returning the input unchanged for bare IPs or any
    unparseable/malformed hostname (covers D-09's IP-fallback path) — never
    raises, never mangles the input.
    """
    ext = _extractor(hostname)
    if ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    return hostname
