"""
AEGIS Host Match Pattern Parser and Broadening Engine
Implements Chrome and MDN match pattern specifications with scope tiering and coverage logic.

References:
- Chrome Match Patterns: https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns
- MDN Match Patterns: https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Match_patterns
"""

import re

from publicsuffixlist import PublicSuffixList

from .models import MatchPattern, ScopeTier

# Bundled offline Public Suffix List instance
_PSL = PublicSuffixList()

# Valid match pattern schemes per Chrome & MDN docs
VALID_SCHEMES = {"*", "http", "https", "file", "ftp", "ws", "wss"}

# Pattern regex allowing optional port
# Scheme: * | http | https | file | ftp | ws | wss
# Host: * | *.domain | exact_host (or empty if scheme is file)
# Port: optional digits (1-65535)
# Path: must begin with /
_PATTERN_REGEX = re.compile(
    r"^(?P<scheme>\*|[a-z0-9]+)://"
    r"(?P<host>\*|(?:\*\.)?[a-z0-9_.-]+)?"
    r"(?::(?P<port>\d{1,5}))?"
    r"(?P<path>/.*)$",
    re.IGNORECASE,
)


def parse_match_pattern(raw: str) -> MatchPattern | None:
    """
    Parse a match pattern string into a structured MatchPattern object.
    Returns None if the pattern is invalid.
    """
    if not isinstance(raw, str):
        return None

    raw_clean = raw.strip()
    if not raw_clean:
        return None

    if raw_clean == "<all_urls>":
        return MatchPattern(
            raw="<all_urls>",
            scheme="*",
            host="*",
            port=None,
            path="/*",
            is_all_urls=True,
        )

    match = _PATTERN_REGEX.match(raw_clean)
    if not match:
        return None

    scheme = match.group("scheme").lower()
    host = match.group("host") or ""
    port_str = match.group("port")
    path = match.group("path")

    if scheme not in VALID_SCHEMES:
        return None

    # file:// scheme requires empty host (e.g. file:///* or file:///c:/...)
    if scheme == "file":
        if host != "":
            return None
        port = None
    else:
        if not host:
            return None
        # Host cannot contain invalid characters or stray wildcards
        if host != "*":
            if host.startswith("*."):
                domain_part = host[2:]
                if "*" in domain_part or not domain_part:
                    return None
            elif "*" in host:
                return None

        # Validate port range if present
        if port_str:
            port_val = int(port_str)
            if not (1 <= port_val <= 65535):
                return None
            port = port_val
        else:
            port = None

    return MatchPattern(
        raw=raw_clean,
        scheme=scheme,
        host=host.lower(),
        port=port,
        path=path,
        is_all_urls=False,
    )


def is_match_pattern(s: str) -> bool:
    """Returns True if the string is a valid Chrome/MDN match pattern."""
    return parse_match_pattern(s) is not None


def covers(
    a: str | MatchPattern,
    b: str | MatchPattern,
) -> bool:
    """
    Returns True only when every URL matched by pattern `b` is also matched by pattern `a`.
    Follows conservative safety principle: when unsure, return False.
    """
    pat_a = a if isinstance(a, MatchPattern) else parse_match_pattern(a)
    pat_b = b if isinstance(b, MatchPattern) else parse_match_pattern(b)

    if pat_a is None or pat_b is None:
        return False

    # Exact string match is always reflexive
    if pat_a.raw == pat_b.raw:
        return True

    # <all_urls> covers every valid match pattern
    if pat_a.is_all_urls:
        return True

    # If b is <all_urls> and a is not, a cannot cover b
    if pat_b.is_all_urls:
        return False

    # 1. Scheme coverage
    if pat_a.scheme == "*":
        # Wildcard scheme * matches only http and https
        if pat_b.scheme not in ("http", "https", "*"):
            return False
    elif pat_a.scheme != pat_b.scheme:
        return False

    # 2. Port coverage
    if pat_a.port is not None and pat_b.port != pat_a.port:
        return False

    # 3. Host coverage
    if pat_a.scheme == "file":
        # file schemes have no host; host is always empty
        pass
    elif pat_a.host == "*":
        # Host wildcard covers any host
        pass
    elif pat_a.host.startswith("*."):
        a_domain = pat_a.host[2:]
        if pat_b.host.startswith("*."):
            b_domain = pat_b.host[2:]
            # *.example.com covers *.example.com, and *.sub.example.com
            if b_domain != a_domain and not b_domain.endswith("." + a_domain):
                return False
        else:
            # *.example.com covers example.com, and sub.example.com
            if pat_b.host != a_domain and not pat_b.host.endswith("." + a_domain):
                return False
    else:
        # Exact host requires exact match
        if pat_b.host != pat_a.host:
            return False

    # 4. Path coverage
    if pat_a.path == "/*":
        # Matches all paths starting with /
        return True

    if pat_a.path.endswith("*"):
        prefix_a = pat_a.path[:-1]
        if not pat_b.path.startswith(prefix_a):
            return False
        # If pat_b also ends with *, pat_b prefix must be at least as specific
        if pat_b.path.endswith("*"):
            prefix_b = pat_b.path[:-1]
            return prefix_b.startswith(prefix_a)
        return True
    else:
        # Exact path requires exact match
        return pat_a.path == pat_b.path


def scope_tier(p: str | MatchPattern) -> ScopeTier:
    """
    Classify a match pattern into an exposure scope tier from narrow to wide:
    - single_host
    - domain_wide
    - suffix_wide
    - all_hosts_partial_path
    - file_access
    - all_sites
    """
    pat = p if isinstance(p, MatchPattern) else parse_match_pattern(p)
    if pat is None:
        return ScopeTier.SINGLE_HOST

    if pat.is_all_urls:
        return ScopeTier.ALL_SITES

    if pat.scheme == "file":
        return ScopeTier.FILE_ACCESS

    if pat.host == "*":
        if pat.path == "/*":
            return ScopeTier.ALL_SITES
        return ScopeTier.ALL_HOSTS_PARTIAL_PATH

    # Check wildcard subdomain patterns
    if pat.host.startswith("*."):
        domain = pat.host[2:]
        # Check if the domain itself is a public suffix (e.g. "com", "co.uk")
        if _PSL.is_public(domain):
            return ScopeTier.SUFFIX_WIDE
        return ScopeTier.DOMAIN_WIDE

    return ScopeTier.SINGLE_HOST


def describe(p: str | MatchPattern) -> str:
    """Returns a short, plain-language description of what the pattern allows."""
    pat = p if isinstance(p, MatchPattern) else parse_match_pattern(p)
    if pat is None:
        return f"Access URLs matching unrecognized pattern '{p}'"

    if pat.is_all_urls:
        return "Access all websites you visit"

    if pat.scheme == "file":
        if pat.path == "/*":
            return "Access all local files on your computer"
        return f"Access local files starting with {pat.path}"

    if pat.host == "*":
        if pat.path == "/*":
            return "Access all websites over HTTP and HTTPS"
        return f"Access web pages on any website matching path {pat.path}"

    if pat.host.startswith("*."):
        domain = pat.host[2:]
        if _PSL.is_public(domain):
            return f"Access all websites under the .{domain} domain registry"
        if pat.path == "/*":
            return f"Access {domain} and all its subdomains"
        return f"Access {domain} and all its subdomains on path {pat.path}"

    # Single host
    if pat.path == "/*":
        return f"Access {pat.host}"
    return f"Access {pat.host} on path {pat.path}"
