"""
AEGIS Permission Rules & Knowledge Base Loader
Loads version-controlled permission metadata, evaluates exposure weights, and formats explanations.
"""

import json
from pathlib import Path
from typing import Any

from .host_patterns import describe, parse_match_pattern, scope_tier
from .models import PermissionInfo

# Resolve data directories relative to this file
_BASE_DIR = Path(__file__).resolve().parent.parent
_KNOWLEDGE_PATH = _BASE_DIR / "data" / "permission_knowledge.json"
_CONFIG_PATH = _BASE_DIR / "data" / "scoring_config.json"


class PermissionKnowledgeBase:
    """Singleton loader for knowledge base and scoring configuration."""

    def __init__(
        self,
        knowledge_path: Path = _KNOWLEDGE_PATH,
        config_path: Path = _CONFIG_PATH,
    ) -> None:
        self.knowledge_path = knowledge_path
        self.config_path = config_path
        self.reload()

    def reload(self) -> None:
        """Load and validate knowledge base and scoring configuration."""
        if not self.knowledge_path.exists():
            raise FileNotFoundError(f"Knowledge base not found at {self.knowledge_path}")
        if not self.config_path.exists():
            raise FileNotFoundError(f"Scoring config not found at {self.config_path}")

        with open(self.knowledge_path, "r", encoding="utf-8") as f:
            raw_kb = json.load(f)

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw_cfg = json.load(f)

        # Validate knowledge base essentials
        if "api_permissions" not in raw_kb or "host_tiers" not in raw_kb:
            raise ValueError("Malformed permission knowledge base: missing required sections")

        self.knowledge_version: str = str(raw_kb.get("knowledge_version", "unknown"))
        self.schema_version: int = int(raw_kb.get("schema_version", 1))
        self.api_permissions: dict[str, dict[str, Any]] = raw_kb["api_permissions"]
        self.host_tiers: dict[str, dict[str, Any]] = raw_kb["host_tiers"]

        # Validate scoring config essentials
        self.formula_version: str = str(raw_cfg.get("formula_version", "1"))
        self.thresholds: dict[str, int] = raw_cfg.get("thresholds", {"low_max": 34, "mid_max": 69})
        self.default_unknown_weight: int = int(raw_cfg.get("default_unknown_weight", 3))
        self.weight_labels: dict[str, str] = raw_cfg.get(
            "weight_labels",
            {"1": "low", "2": "low", "3": "medium", "4": "high", "5": "critical"},
        )
        self.host_tier_weights: dict[str, int] = raw_cfg.get(
            "host_tier_weights",
            {
                "all_sites": 5,
                "file_access": 4,
                "suffix_wide": 4,
                "all_hosts_partial_path": 4,
                "domain_wide": 2,
                "single_host": 1,
            },
        )
        self.floors: dict[str, int] = raw_cfg.get("floors", {"critical_floor": 70, "high_floor": 40})
        self.creep_config: dict[str, int] = raw_cfg.get("creep", {"delta_review": 5, "delta_significant": 15})
        self.limits: dict[str, int] = raw_cfg.get("limits", {})

    def label_for_weight(self, weight: int) -> str:
        """Map numeric weight (1-5) to human-readable risk label."""
        return self.weight_labels.get(str(weight), "medium")

    def info_for_api(self, name: str, *, kind: str = "api") -> PermissionInfo:
        """Evaluate and format metadata for an API permission name."""
        entry = self.api_permissions.get(name)
        if entry is not None:
            weight = int(entry.get("weight", self.default_unknown_weight))
            return PermissionInfo(
                name=name,
                kind=kind,
                weight=weight,
                risk_label=self.label_for_weight(weight),
                allows=entry.get("allows", ""),
                legitimate_use=entry.get("legitimate_use", ""),
                source_url=entry.get("source"),
                known=True,
                tier=None,
                reviewed=bool(entry.get("reviewed", False)),
            )

        # Unknown permission fallback
        return PermissionInfo(
            name=name,
            kind=kind,
            weight=self.default_unknown_weight,
            risk_label=self.label_for_weight(self.default_unknown_weight),
            allows=f"Unknown capability: '{name}' is not documented in the AEGIS knowledge base.",
            legitimate_use="Consult the extension vendor or developer documentation.",
            source_url=None,
            known=False,
            tier=None,
            reviewed=False,
        )

    def info_for_host(self, pattern: str, *, kind: str = "host") -> PermissionInfo:
        """Evaluate and format metadata for a host pattern."""
        parsed = parse_match_pattern(pattern)
        if parsed is None:
            # Unrecognized host pattern
            return PermissionInfo(
                name=pattern,
                kind=kind,
                weight=self.default_unknown_weight,
                risk_label=self.label_for_weight(self.default_unknown_weight),
                allows=f"Unrecognized host pattern '{pattern}'.",
                legitimate_use="Verify match pattern syntax against Chrome/MDN documentation.",
                source_url=None,
                known=False,
                tier=None,
                reviewed=False,
            )

        tier = scope_tier(parsed)
        weight = self.host_tier_weights.get(tier.value, self.default_unknown_weight)
        tier_data = self.host_tiers.get(tier.value, {})

        # Use specific describe() summary if pattern is narrower than broad tier
        allows = describe(parsed)
        legitimate_use = tier_data.get("legitimate_use", "Website integration or content modification.")
        source_url = tier_data.get("source", "https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns")

        return PermissionInfo(
            name=pattern,
            kind=kind,
            weight=weight,
            risk_label=self.label_for_weight(weight),
            allows=allows,
            legitimate_use=legitimate_use,
            source_url=source_url,
            known=True,
            tier=tier,
            reviewed=bool(tier_data.get("reviewed", True)),
        )


# Global default knowledge base instance
_DEFAULT_KB = PermissionKnowledgeBase()


def get_knowledge_base() -> PermissionKnowledgeBase:
    """Retrieve the singleton knowledge base instance."""
    return _DEFAULT_KB
