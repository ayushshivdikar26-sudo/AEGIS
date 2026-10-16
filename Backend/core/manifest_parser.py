"""
AEGIS Manifest Parser
Strict parser for WebExtension Manifest V2 and V3 specifications.
Enforces size limits, strict JSON syntax, normalization, and feature extraction.
"""

import hashlib
import json
import re
import unicodedata
from typing import Any

from .host_patterns import is_match_pattern
from .models import ManifestError, ParsedManifest, WarningItem

MAX_BYTES = 1048576  # 1 MB
MAX_DEPTH = 32
MAX_STRING_LEN = 2048
MAX_ARRAY_ITEMS = 500

STRUCTURAL_FEATURES = {
    "background",
    "action",
    "browser_action",
    "page_action",
    "side_panel",
    "devtools_page",
    "omnibox",
    "commands",
    "options_page",
    "options_ui",
    "content_scripts",
    "declarative_net_request",
    "chrome_url_overrides",
    "web_accessible_resources",
    "externally_connectable",
    "storage",
    "sidebar_action",
}

# Bidirectional control code points: U+202A to U+202E, U+2066 to U+2069
BIDI_CODEPOINTS = {
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,
    0x2066,
    0x2067,
    0x2068,
    0x2069,
}

PLACEHOLDER_REGEX = re.compile(r"^__MSG_(.+)__$", re.IGNORECASE)


def _check_depth(val: Any, current_depth: int = 1) -> None:
    """Recursively ensure JSON nesting does not exceed MAX_DEPTH."""
    if current_depth > MAX_DEPTH:
        raise ManifestError(
            "too_deep",
            f"Manifest JSON structure exceeds maximum nesting depth of {MAX_DEPTH}",
        )
    if isinstance(val, dict):
        for v in val.values():
            _check_depth(v, current_depth + 1)
    elif isinstance(val, list):
        for item in val:
            _check_depth(item, current_depth + 1)


def _check_limits(val: Any) -> None:
    """Ensure all strings and arrays comply with size constraints."""
    if isinstance(val, str):
        if len(val) > MAX_STRING_LEN:
            raise ManifestError(
                "string_too_long",
                f"String value exceeds maximum allowed length of {MAX_STRING_LEN} characters",
            )
    elif isinstance(val, list):
        if len(val) > MAX_ARRAY_ITEMS:
            raise ManifestError(
                "too_many_items",
                f"Array exceeds maximum allowed item count of {MAX_ARRAY_ITEMS}",
            )
        for item in val:
            _check_limits(item)
    elif isinstance(val, dict):
        for v in val.values():
            _check_limits(v)


def _sanitize_text(text: str) -> tuple[str, bool]:
    """
    NFC normalizes string, strips leading/trailing whitespace, and removes
    bidirectional controls and unwanted C0/C1 control characters.
    Returns (sanitized_string, bidi_removed_flag).
    """
    normalized = unicodedata.normalize("NFC", text).strip()
    clean_chars = []
    bidi_removed = False

    for char in normalized:
        cp = ord(char)
        if cp in BIDI_CODEPOINTS:
            bidi_removed = True
            continue
        category = unicodedata.category(char)
        # Drop Cc and Cf controls except common whitespace
        if category in ("Cc", "Cf") and char not in ("\t", "\n", "\r"):
            continue
        clean_chars.append(char)

    return "".join(clean_chars), bidi_removed


def _parse_version_key(version_str: str) -> list[int] | None:
    """Parse Chrome-style version string (1-4 integers between 0 and 65535)."""
    parts = version_str.split(".")
    if not (1 <= len(parts) <= 4):
        return None
    key = []
    for part in parts:
        if not part.isdigit():
            return None
        num = int(part)
        if not (0 <= num <= 65535):
            return None
        key.append(num)
    return key


def parse_manifest(
    raw: bytes | str | dict[str, Any],
    *,
    messages: dict[str, Any] | None = None,
) -> ParsedManifest:
    """
    Parse, validate, and normalize an untrusted browser extension manifest.
    Accepts raw bytes, JSON string, or parsed dictionary.
    """
    warnings: list[WarningItem] = []

    # 1. Determine raw bytes & SHA-256
    if isinstance(raw, bytes):
        raw_bytes = raw
        if len(raw_bytes) > MAX_BYTES:
            raise ManifestError(
                "too_large",
                f"Manifest exceeds maximum allowed size of {MAX_BYTES} bytes",
            )
        # Handle UTF-8 BOM if present
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            raw_text = raw_bytes[3:].decode("utf-8", errors="replace")
        else:
            raw_text = raw_bytes.decode("utf-8", errors="replace")
    elif isinstance(raw, str):
        raw_bytes = raw.encode("utf-8")
        if len(raw_bytes) > MAX_BYTES:
            raise ManifestError(
                "too_large",
                f"Manifest exceeds maximum allowed size of {MAX_BYTES} bytes",
            )
        raw_text = raw
    elif isinstance(raw, dict):
        raw_bytes = json.dumps(raw, sort_keys=True).encode("utf-8")
        if len(raw_bytes) > MAX_BYTES:
            raise ManifestError(
                "too_large",
                f"Manifest exceeds maximum allowed size of {MAX_BYTES} bytes",
            )
        raw_text = None
    else:
        raise ManifestError("not_object", "Manifest input must be bytes, string, or JSON dictionary")

    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    # 2. Strict JSON parsing with duplicate key and NaN/Infinity rejection
    if raw_text is not None:

        def _reject_constant(c: str) -> None:
            raise ManifestError("not_json", f"Invalid numeric token '{c}' in JSON")

        def _check_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            seen: set[str] = set()
            d: dict[str, Any] = {}
            for k, v in pairs:
                if k in seen:
                    raise ManifestError("duplicate_key", f"Duplicate key found in JSON object: {k}")
                seen.add(k)
                d[k] = v
            return d

        try:
            data = json.loads(
                raw_text,
                object_pairs_hook=_check_pairs,
                parse_constant=_reject_constant,
            )
        except json.JSONDecodeError as exc:
            raise ManifestError("not_json", f"Manifest is not valid JSON: {exc.msg}")
        except RecursionError:
            raise ManifestError("too_deep", "Manifest JSON structure caused recursion limit")
    else:
        data = raw

    if not isinstance(data, dict):
        raise ManifestError("not_object", "Manifest top-level entity must be a JSON object")

    # 3. Depth and string/array boundary checks
    _check_depth(data)
    _check_limits(data)

    # 4. Required fields validation
    manifest_version = data.get("manifest_version")
    if manifest_version not in (2, 3):
        raise ManifestError(
            "invalid_manifest_version",
            "Manifest field 'manifest_version' must be either 2 or 3",
        )

    raw_version = data.get("version")
    if not isinstance(raw_version, str) or not raw_version.strip():
        raise ManifestError("missing_version", "Manifest field 'version' must be a non-empty string")
    version = raw_version.strip()
    version_key = _parse_version_key(version)

    # 5. Extract structural features (FR-P3)
    features = sorted([k for k in STRUCTURAL_FEATURES if k in data])

    # 6. Name and description resolution and sanitization
    raw_name = data.get("name", "")
    if not isinstance(raw_name, str):
        raise ManifestError("invalid_field_type", "Manifest field 'name' must be a string")

    raw_desc = data.get("description")
    if raw_desc is not None and not isinstance(raw_desc, str):
        raise ManifestError("invalid_field_type", "Manifest field 'description' must be a string")

    name_is_placeholder = False
    desc_is_placeholder = False

    # Normalized lookup dict for messages (case-insensitive keys)
    msg_lookup: dict[str, str] = {}
    if messages and isinstance(messages, dict):
        for mk, mv in messages.items():
            if isinstance(mv, dict) and "message" in mv:
                msg_lookup[mk.lower()] = str(mv["message"])
            elif isinstance(mv, str):
                msg_lookup[mk.lower()] = mv

    # Resolve name
    name_match = PLACEHOLDER_REGEX.match(raw_name.strip())
    if name_match:
        key = name_match.group(1).lower()
        if key in msg_lookup:
            raw_name = msg_lookup[key]
        else:
            name_is_placeholder = True
            warnings.append(
                WarningItem(
                    code="unresolved_placeholder",
                    message=f"Unresolved localization placeholder in name: {raw_name}",
                )
            )

    # Resolve description
    if raw_desc:
        desc_match = PLACEHOLDER_REGEX.match(raw_desc.strip())
        if desc_match:
            key = desc_match.group(1).lower()
            if key in msg_lookup:
                raw_desc = msg_lookup[key]
            else:
                desc_is_placeholder = True
                warnings.append(
                    WarningItem(
                        code="unresolved_placeholder",
                        message=f"Unresolved localization placeholder in description: {raw_desc}",
                    )
                )

    sanitized_name, name_bidi = _sanitize_text(raw_name)
    sanitized_desc, desc_bidi = _sanitize_text(raw_desc) if raw_desc else (None, False)

    if name_bidi or desc_bidi:
        warnings.append(
            WarningItem(
                code="bidi_controls_removed",
                message="Bidirectional formatting control characters were removed from text fields",
            )
        )

    default_locale = data.get("default_locale")
    if default_locale is not None and not isinstance(default_locale, str):
        default_locale = None

    # 7. Permissions extraction and splitting
    api_perms: set[str] = set()
    host_perms: set[str] = set()
    opt_api_perms: set[str] = set()
    opt_host_perms: set[str] = set()
    cs_matches: set[str] = set()

    def _extract_list(field_name: str) -> list[str]:
        raw_list = data.get(field_name, [])
        if not isinstance(raw_list, list):
            raise ManifestError("invalid_field_type", f"Manifest field '{field_name}' must be an array")
        if len(raw_list) > MAX_ARRAY_ITEMS:
            raise ManifestError(
                "too_many_items",
                f"Array '{field_name}' exceeds maximum allowed item count of {MAX_ARRAY_ITEMS}",
            )
        items = []
        for x in raw_list:
            if not isinstance(x, str):
                raise ManifestError("invalid_field_type", f"Items in '{field_name}' must be strings")
            item = x.strip()
            if item:
                items.append(item)
        return items

    raw_permissions = _extract_list("permissions")
    raw_opt_permissions = _extract_list("optional_permissions")
    raw_host_permissions = _extract_list("host_permissions") if manifest_version == 3 else []
    raw_opt_host_permissions = _extract_list("optional_host_permissions") if manifest_version == 3 else []

    # Manifest V3 handling
    if manifest_version == 3:
        for p in raw_permissions:
            if is_match_pattern(p):
                host_perms.add(p)
                warnings.append(
                    WarningItem(
                        code="host_in_permissions",
                        message=f"Host match pattern found in V3 permissions array: {p}",
                    )
                )
            else:
                api_perms.add(p)

        for hp in raw_host_permissions:
            host_perms.add(hp)

        for op in raw_opt_permissions:
            if is_match_pattern(op):
                opt_host_perms.add(op)
            else:
                opt_api_perms.add(op)

        for ohp in raw_opt_host_permissions:
            opt_host_perms.add(ohp)

    else:
        # Manifest V2 handling
        for p in raw_permissions:
            if is_match_pattern(p):
                host_perms.add(p)
            else:
                api_perms.add(p)

        for op in raw_opt_permissions:
            if is_match_pattern(op):
                opt_host_perms.add(op)
            else:
                opt_api_perms.add(op)

    # Content scripts matches (FR-P2)
    content_scripts = data.get("content_scripts", [])
    if isinstance(content_scripts, list):
        for cs in content_scripts:
            if isinstance(cs, dict):
                matches = cs.get("matches", [])
                if isinstance(matches, list):
                    for m in matches:
                        if isinstance(m, str):
                            m_clean = m.strip()
                            if m_clean:
                                cs_matches.add(m_clean)
                                host_perms.add(m_clean)

    return ParsedManifest(
        manifest_version=manifest_version,
        name=sanitized_name,
        version=version,
        version_key=version_key,
        description=sanitized_desc,
        name_is_placeholder=name_is_placeholder,
        description_is_placeholder=desc_is_placeholder,
        default_locale=default_locale.strip() if default_locale else None,
        api_permissions=sorted(api_perms),
        host_permissions=sorted(host_perms),
        optional_api_permissions=sorted(opt_api_perms),
        optional_host_permissions=sorted(opt_host_perms),
        content_script_matches=sorted(cs_matches),
        features=features,
        sha256=sha256,
        warnings=warnings,
    )
