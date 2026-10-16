"""
Unit tests for AEGIS Manifest Parser (FR-P1 to FR-P10).
"""

import json

import pytest

from Backend.core.manifest_parser import parse_manifest
from Backend.core.models import ManifestError


def test_valid_manifest_v3():
    raw = {
        "manifest_version": 3,
        "name": "Sample Extension",
        "version": "1.2.3.4",
        "description": "A sample extension for testing.",
        "permissions": ["storage", "alarms"],
        "host_permissions": ["https://example.com/*"],
        "optional_permissions": ["history"],
        "optional_host_permissions": ["*://*.google.com/*"],
        "background": {"service_worker": "bg.js"},
    }
    parsed = parse_manifest(raw)
    assert parsed.manifest_version == 3
    assert parsed.name == "Sample Extension"
    assert parsed.version == "1.2.3.4"
    assert parsed.version_key == [1, 2, 3, 4]
    assert parsed.api_permissions == ["alarms", "storage"]
    assert parsed.host_permissions == ["https://example.com/*"]
    assert parsed.optional_api_permissions == ["history"]
    assert parsed.optional_host_permissions == ["*://*.google.com/*"]
    assert "background" in parsed.features
    assert not parsed.name_is_placeholder
    assert parsed.sha256 is not None
    assert len(parsed.warnings) == 0


def test_valid_manifest_v2_mixed_permissions():
    raw = {
        "manifest_version": 2,
        "name": "Legacy V2 Extension",
        "version": "2.0",
        "permissions": [
            "storage",
            "https://api.github.com/*",
            "tabs",
            "*://*.example.org/*",
        ],
        "content_scripts": [
            {
                "matches": ["https://*.content.org/*"],
                "js": ["content.js"],
            }
        ],
    }
    parsed = parse_manifest(raw)
    assert parsed.manifest_version == 2
    assert parsed.api_permissions == ["storage", "tabs"]
    assert "https://api.github.com/*" in parsed.host_permissions
    assert "*://*.example.org/*" in parsed.host_permissions
    assert "https://*.content.org/*" in parsed.host_permissions
    assert parsed.content_script_matches == ["https://*.content.org/*"]


def test_host_pattern_in_v3_permissions():
    raw = {
        "manifest_version": 3,
        "name": "Misconfigured V3",
        "version": "1.0",
        "permissions": ["storage", "https://example.com/*"],
    }
    parsed = parse_manifest(raw)
    assert "storage" in parsed.api_permissions
    assert "https://example.com/*" in parsed.host_permissions
    assert any(w.code == "host_in_permissions" for w in parsed.warnings)


def test_placeholder_resolution():
    raw = {
        "manifest_version": 3,
        "name": "__MSG_appName__",
        "version": "1.0",
        "description": "__MSG_appDesc__",
    }
    messages = {
        "appname": {"message": "Resolved Name"},
        "appdesc": {"message": "Resolved Description"},
    }
    parsed = parse_manifest(raw, messages=messages)
    assert parsed.name == "Resolved Name"
    assert parsed.description == "Resolved Description"
    assert not parsed.name_is_placeholder
    assert not parsed.description_is_placeholder


def test_unresolved_placeholder():
    raw = {
        "manifest_version": 3,
        "name": "__MSG_missingName__",
        "version": "1.0",
    }
    parsed = parse_manifest(raw, messages={})
    assert parsed.name == "__MSG_missingName__"
    assert parsed.name_is_placeholder
    assert any(w.code == "unresolved_placeholder" for w in parsed.warnings)


def test_bidi_controls_removed():
    # \u202e is Right-to-Left Override
    raw = {
        "manifest_version": 3,
        "name": "Innocent\u202eExtension",
        "version": "1.0",
    }
    parsed = parse_manifest(raw)
    assert "\u202e" not in parsed.name
    assert parsed.name == "InnocentExtension"
    assert any(w.code == "bidi_controls_removed" for w in parsed.warnings)


def test_utf8_bom_handling():
    raw_str = json.dumps({"manifest_version": 3, "name": "BOM Test", "version": "1.0"})
    raw_bytes = b"\xef\xbb\xbf" + raw_str.encode("utf-8")
    parsed = parse_manifest(raw_bytes)
    assert parsed.name == "BOM Test"


def test_duplicate_key_rejection():
    raw_json = (
        '{"manifest_version": 3, "name": "Dup", "name": "Dup2", "version": "1.0"}'
    )
    with pytest.raises(ManifestError) as exc:
        parse_manifest(raw_json)
    assert exc.value.code == "duplicate_key"


def test_nan_infinity_rejection():
    raw_json = (
        '{"manifest_version": 3, "name": "NaN Test", "version": "1.0", "val": NaN}'
    )
    with pytest.raises(ManifestError) as exc:
        parse_manifest(raw_json)
    assert exc.value.code == "not_json"


def test_deeply_nested_rejection():
    # Generate 35 nested objects
    nested = {"a": 1}
    for _ in range(35):
        nested = {"sub": nested}
    raw = {"manifest_version": 3, "name": "Deep", "version": "1.0", "data": nested}
    with pytest.raises(ManifestError) as exc:
        parse_manifest(raw)
    assert exc.value.code == "too_deep"


def test_too_large_rejection():
    huge_bytes = b"{" + b" " * (1048576 + 10) + b"}"
    with pytest.raises(ManifestError) as exc:
        parse_manifest(huge_bytes)
    assert exc.value.code == "too_large"


def test_too_many_items_rejection():
    raw = {
        "manifest_version": 3,
        "name": "Many Items",
        "version": "1.0",
        "permissions": [f"perm_{i}" for i in range(505)],
    }
    with pytest.raises(ManifestError) as exc:
        parse_manifest(raw)
    assert exc.value.code == "too_many_items"


def test_string_too_long_rejection():
    raw = {
        "manifest_version": 3,
        "name": "A" * 2050,
        "version": "1.0",
    }
    with pytest.raises(ManifestError) as exc:
        parse_manifest(raw)
    assert exc.value.code == "string_too_long"


def test_missing_version_rejection():
    raw = {"manifest_version": 3, "name": "No Version"}
    with pytest.raises(ManifestError) as exc:
        parse_manifest(raw)
    assert exc.value.code == "missing_version"


def test_invalid_manifest_version():
    raw = {"manifest_version": 1, "name": "Old", "version": "1.0"}
    with pytest.raises(ManifestError) as exc:
        parse_manifest(raw)
    assert exc.value.code == "invalid_manifest_version"


def test_non_object_root():
    with pytest.raises(ManifestError) as exc:
        parse_manifest("[1, 2, 3]")
    assert exc.value.code == "not_object"


def test_invalid_field_types():
    with pytest.raises(ManifestError) as exc:
        parse_manifest({"manifest_version": 3, "name": 123, "version": "1.0"})
    assert exc.value.code == "invalid_field_type"

    with pytest.raises(ManifestError) as exc:
        parse_manifest(
            {
                "manifest_version": 3,
                "name": "Test",
                "version": "1.0",
                "description": 123,
            }
        )
    assert exc.value.code == "invalid_field_type"

    with pytest.raises(ManifestError) as exc:
        parse_manifest(
            {
                "manifest_version": 3,
                "name": "Test",
                "version": "1.0",
                "permissions": "not_list",
            }
        )
    assert exc.value.code == "invalid_field_type"

    with pytest.raises(ManifestError) as exc:
        parse_manifest(
            {
                "manifest_version": 3,
                "name": "Test",
                "version": "1.0",
                "permissions": [123],
            }
        )
    assert exc.value.code == "invalid_field_type"


def test_version_key_variations():
    m1 = parse_manifest(
        {"manifest_version": 3, "name": "VKey1", "version": "1.2.3.4.5"}
    )
    assert m1.version_key is None

    m2 = parse_manifest({"manifest_version": 3, "name": "VKey2", "version": "1.beta"})
    assert m2.version_key is None

    m3 = parse_manifest({"manifest_version": 3, "name": "VKey3", "version": "1.99999"})
    assert m3.version_key is None


def test_v2_optional_permissions_split():
    raw = {
        "manifest_version": 2,
        "name": "V2 Opt",
        "version": "1.0",
        "default_locale": "en",
        "optional_permissions": ["storage", "https://*.example.com/*"],
    }
    parsed = parse_manifest(raw)
    assert parsed.optional_api_permissions == ["storage"]
    assert parsed.optional_host_permissions == ["https://*.example.com/*"]
    assert parsed.default_locale == "en"


def test_dict_input_handling():
    raw = {"manifest_version": 3, "name": "Dict Input", "version": "1.0"}
    parsed = parse_manifest(raw)
    assert parsed.name == "Dict Input"
