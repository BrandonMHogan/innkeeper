from src.services.domain_grouping import registered_domain


def test_subdomain_groups_under_registered_domain():
    assert registered_domain("www.netflix.com") == "netflix.com"


def test_different_subdomain_groups_under_same_registered_domain():
    assert registered_domain("api.netflix.com") == "netflix.com"


def test_multi_part_psl_suffix_handled_correctly():
    """foo.github.io groups under github.io — proves tldextract offline mode
    loaded a real PSL snapshot, not a naive last-two-labels heuristic."""
    assert registered_domain("foo.github.io") == "github.io"


def test_bare_ip_passes_through_unchanged():
    """D-09: when no hostname is available (bare IP), return input unchanged
    rather than crashing or mangling the string."""
    assert registered_domain("17.253.1.1") == "17.253.1.1"
