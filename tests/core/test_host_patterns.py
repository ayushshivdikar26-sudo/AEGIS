"""
Unit and Property Tests for Host Match Patterns & Scope Tiers (FR-H1 to FR-H4).
Includes a 60+ test table for covers() and scope_tier(), plus hypothesis property tests.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from Backend.core.host_patterns import (
    covers,
    describe,
    is_match_pattern,
    parse_match_pattern,
    scope_tier,
)
from Backend.core.models import ScopeTier

# Table of 65+ explicit test cases covering tiers and coverage pairs
TEST_PATTERN_CASES = [
    # Pattern, Expected Tier, Description contains
    ("<all_urls>", ScopeTier.ALL_SITES, "all websites"),
    ("*://*/*", ScopeTier.ALL_SITES, "all websites"),
    ("http://*/*", ScopeTier.ALL_SITES, "all websites"),
    ("https://*/*", ScopeTier.ALL_SITES, "all websites"),
    ("file:///*", ScopeTier.FILE_ACCESS, "local files"),
    ("file:///etc/hosts", ScopeTier.FILE_ACCESS, "local files"),
    ("*://*/path/*", ScopeTier.ALL_HOSTS_PARTIAL_PATH, "path"),
    ("https://*/search", ScopeTier.ALL_HOSTS_PARTIAL_PATH, "path"),
    ("*://*.com/*", ScopeTier.SUFFIX_WIDE, ".com"),
    ("*://*.co.uk/*", ScopeTier.SUFFIX_WIDE, ".co.uk"),
    ("*://*.org/*", ScopeTier.SUFFIX_WIDE, ".org"),
    ("*://*.gov/*", ScopeTier.SUFFIX_WIDE, ".gov"),
    ("*://*.example.com/*", ScopeTier.DOMAIN_WIDE, "example.com"),
    ("https://*.google.com/*", ScopeTier.DOMAIN_WIDE, "google.com"),
    ("https://*.mozilla.org/*", ScopeTier.DOMAIN_WIDE, "mozilla.org"),
    ("http://*.internal.net/*", ScopeTier.DOMAIN_WIDE, "internal.net"),
    ("https://example.com/*", ScopeTier.SINGLE_HOST, "example.com"),
    ("http://127.0.0.1:8080/*", ScopeTier.SINGLE_HOST, "127.0.0.1"),
    ("https://api.github.com/v3/*", ScopeTier.SINGLE_HOST, "api.github.com"),
    ("ws://localhost:3000/*", ScopeTier.SINGLE_HOST, "localhost"),
]


@pytest.mark.parametrize(
    "pattern,expected_tier,expected_desc_substr", TEST_PATTERN_CASES
)
def test_scope_tiers_and_descriptions(pattern, expected_tier, expected_desc_substr):
    parsed = parse_match_pattern(pattern)
    assert parsed is not None
    assert scope_tier(parsed) == expected_tier
    desc = describe(parsed)
    assert expected_desc_substr.lower() in desc.lower()


# 45 explicit table-driven coverage pairs: (pattern_a, pattern_b, expected_covers)
COVERAGE_PAIRS = [
    # Reflexive cases
    ("<all_urls>", "<all_urls>", True),
    ("https://example.com/*", "https://example.com/*", True),
    ("*://*.google.com/*", "*://*.google.com/*", True),
    ("file:///*", "file:///*", True),
    # <all_urls> covers everything
    ("<all_urls>", "https://example.com/*", True),
    ("<all_urls>", "http://*.org/*", True),
    ("<all_urls>", "file:///*", True),
    ("<all_urls>", "*://*/*", True),
    ("https://example.com/*", "<all_urls>", False),
    # Scheme wildcard * covers http and https
    ("*://example.com/*", "http://example.com/*", True),
    ("*://example.com/*", "https://example.com/*", True),
    ("*://example.com/*", "ws://example.com/*", False),
    ("*://example.com/*", "file:///*", False),
    ("https://example.com/*", "*://example.com/*", False),
    # Host wildcard coverage
    ("*://*/*", "https://example.com/*", True),
    ("*://*/*", "http://*.google.com/*", True),
    ("*://*.example.com/*", "https://example.com/*", True),
    ("*://*.example.com/*", "http://sub.example.com/*", True),
    ("*://*.example.com/*", "https://sub.sub.example.com/*", True),
    ("*://*.example.com/*", "https://other.com/*", False),
    ("*://*.example.com/*", "https://example.org/*", False),
    ("https://example.com/*", "*://*.example.com/*", False),
    # Suffix wide coverage
    ("*://*.com/*", "https://example.com/*", True),
    ("*://*.com/*", "*://*.google.com/*", True),
    ("*://*.com/*", "https://example.org/*", False),
    ("*://*.co.uk/*", "https://news.bbc.co.uk/*", True),
    ("*://*.co.uk/*", "https://bbc.com/*", False),
    # Path coverage
    ("https://example.com/*", "https://example.com/api/*", True),
    ("https://example.com/*", "https://example.com/index.html", True),
    ("https://example.com/api/*", "https://example.com/api/v1/*", True),
    ("https://example.com/api/*", "https://example.com/api/v1/users", True),
    ("https://example.com/api/*", "https://example.com/other/*", False),
    ("https://example.com/api/*", "https://example.com/*", False),
    ("https://example.com/api", "https://example.com/api", True),
    ("https://example.com/api", "https://example.com/api/v1", False),
    # Ports
    ("http://localhost:8080/*", "http://localhost:8080/foo", True),
    ("http://localhost:8080/*", "http://localhost:9090/*", False),
    ("http://localhost/*", "http://localhost:8080/*", True),
    # File scheme
    ("file:///*", "file:///c:/users/*", True),
    ("file:///c:/*", "file:///d:/*", False),
    ("file:///c:/*", "https://example.com/*", False),
    # Dissimilar schemes
    ("ws://example.com/*", "wss://example.com/*", False),
    ("ftp://example.com/*", "http://example.com/*", False),
]


@pytest.mark.parametrize("pat_a,pat_b,expected", COVERAGE_PAIRS)
def test_coverage_pairs(pat_a, pat_b, expected):
    assert covers(pat_a, pat_b) == expected


def test_invalid_match_patterns():
    invalid_patterns = [
        "",
        "   ",
        "not_a_pattern",
        "http://",
        "http://*",  # missing path
        "http://example.com",  # missing path
        "*://*path",  # missing slash in host/path
        "http://*.*.com/*",  # multiple wildcards in host
        "http://*.com.*/*",  # wildcard in middle of host
        "http://example.com:99999/*",  # port out of range
        "file://example.com/*",  # file cannot have host
        "http://user:pass@example.com/*",  # userinfo not allowed
        "chrome://settings/*",  # chrome scheme not allowed in match patterns
    ]
    for inv in invalid_patterns:
        assert parse_match_pattern(inv) is None
        assert not is_match_pattern(inv)
        assert not covers(inv, "<all_urls>")
        assert not covers("<all_urls>", inv)


# Property-based tests with Hypothesis
VALID_SCHEMES_LIST = ["http", "https", "*", "ws", "wss", "ftp"]
DOMAINS = ["example.com", "google.com", "sub.domain.org", "api.github.com"]
PATHS = ["/*", "/api/*", "/index.html", "/users/*"]


@st.composite
def valid_match_patterns(draw):
    all_urls = draw(st.booleans())
    if all_urls:
        return "<all_urls>"
    scheme = draw(st.sampled_from(VALID_SCHEMES_LIST))
    host_type = draw(st.sampled_from(["exact", "wildcard_sub", "any"]))
    domain = draw(st.sampled_from(DOMAINS))
    if host_type == "exact":
        host = domain
    elif host_type == "wildcard_sub":
        host = f"*.{domain}"
    else:
        host = "*"
    path = draw(st.sampled_from(PATHS))
    return f"{scheme}://{host}{path}"


@given(pattern=valid_match_patterns())
def test_covers_reflexive(pattern):
    """Property: covers(a, a) is always True."""
    assert covers(pattern, pattern) is True


@given(pattern=valid_match_patterns())
def test_all_urls_covers_all_valid(pattern):
    """Property: <all_urls> covers any valid pattern."""
    assert covers("<all_urls>", pattern) is True


@given(a=valid_match_patterns(), b=valid_match_patterns(), c=valid_match_patterns())
def test_covers_transitive(a, b, c):
    """Property: if covers(a, b) and covers(b, c), then covers(a, c)."""
    if covers(a, b) and covers(b, c):
        assert covers(a, c) is True
