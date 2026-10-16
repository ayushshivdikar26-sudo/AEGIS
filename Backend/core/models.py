"""
AEGIS Core Models
Pure Pydantic v2 immutable data models shared across all core analysis modules.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ManifestError(Exception):
    """Structured error raised during manifest parsing."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ScopeTier(str, Enum):
    """Host pattern scope tiers ordered from narrowest to widest."""

    SINGLE_HOST = "single_host"
    DOMAIN_WIDE = "domain_wide"
    SUFFIX_WIDE = "suffix_wide"
    ALL_HOSTS_PARTIAL_PATH = "all_hosts_partial_path"
    FILE_ACCESS = "file_access"
    ALL_SITES = "all_sites"


class MatchPattern(BaseModel):
    """Parsed representation of a Chrome/MDN match pattern."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw: str
    scheme: str
    host: str
    port: int | None = None
    path: str
    is_all_urls: bool = False


class WarningItem(BaseModel):
    """Warning emitted during manifest parsing or analysis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str


class ParsedManifest(BaseModel):
    """Normalized, sanitized output of manifest_parser.py."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_version: int
    name: str
    version: str
    version_key: list[int] | None = None
    description: str | None = None
    name_is_placeholder: bool = False
    description_is_placeholder: bool = False
    default_locale: str | None = None
    api_permissions: list[str] = Field(default_factory=list)
    host_permissions: list[str] = Field(default_factory=list)
    optional_api_permissions: list[str] = Field(default_factory=list)
    optional_host_permissions: list[str] = Field(default_factory=list)
    content_script_matches: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    sha256: str
    warnings: list[WarningItem] = Field(default_factory=list)


class PermissionInfo(BaseModel):
    """Evaluated metadata for an individual permission or host pattern."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    kind: str  # "api" | "host" | "optional_api" | "optional_host"
    weight: int
    risk_label: str  # "low" | "medium" | "high" | "critical"
    allows: str
    legitimate_use: str
    source_url: str | None = None
    known: bool = True
    tier: ScopeTier | None = None
    reviewed: bool = True
    narrower_alternative: str | None = None


class CalculationStep(BaseModel):
    """Step-by-step arithmetic trace for score explainability (FR-E2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step: str
    formula: str
    values: str
    result: str


class BreakdownItem(BaseModel):
    """Item contributing to the assessed risk score (FR-S7)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    contribution: float
    kind: str  # "api" | "host" | "floor"


class Assessment(BaseModel):
    """Output of risk_scoring.py providing explainable risk metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    formula_version: str
    knowledge_version: str
    risk_score: int
    risk_level: str  # "low" | "medium" | "high"
    thresholds: dict[str, int]
    api_score: float
    host_score: float
    max_weight: int
    critical_flags: list[str] = Field(default_factory=list)
    breakdown: list[BreakdownItem] = Field(default_factory=list)
    potential_score: int
    calculation: list[CalculationStep] = Field(default_factory=list)
    plain_summary: str
    notes: list[str] = Field(default_factory=list)
    unrecognized: list[str] = Field(default_factory=list)
    excess_score: float | None = None
    evidence_coverage: float | None = None


class ComparisonItem(BaseModel):
    """Individual permission item inside comparison diffs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    risk_label: str
    weight: int
    kind: str  # "api" | "host" | "optional_api" | "optional_host"
    source: str  # "permissions" | "host_permissions" | "content_scripts" | "optional_permissions"
    already_covered_by: str | None = None


class BroadenedItem(BaseModel):
    """Detected expansion of host scope across versions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_pattern: str
    to_pattern: str
    from_tier: str
    to_tier: str
    explanation: str


class ComparisonGroup(BaseModel):
    """Version diff for a specific permission category."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    added: list[ComparisonItem] = Field(default_factory=list)
    removed: list[ComparisonItem] = Field(default_factory=list)
    retained: list[ComparisonItem] = Field(default_factory=list)


class HostComparisonGroup(BaseModel):
    """Version diff for host permissions, including host broadening."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    added: list[ComparisonItem] = Field(default_factory=list)
    removed: list[ComparisonItem] = Field(default_factory=list)
    retained: list[ComparisonItem] = Field(default_factory=list)
    broadened: list[BroadenedItem] = Field(default_factory=list)


class Comparison(BaseModel):
    """Full side-by-side diff between two manifest snapshots."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_version: str
    to_version: str
    score_from: int
    score_to: int
    api: ComparisonGroup
    host: HostComparisonGroup
    optional: ComparisonGroup


class CreepTrigger(BaseModel):
    """Audit trigger recording why a specific creep outcome fired (FR-E3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: str
    observed: str
    threshold: str


class CreepAssessment(BaseModel):
    """Audited assessment of permission creep across versions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    reason: str | None = None
    outcome: str
    summary: str
    added: list[ComparisonItem] = Field(default_factory=list)
    removed: list[ComparisonItem] = Field(default_factory=list)
    broadened: list[BroadenedItem] = Field(default_factory=list)
    could_allow: list[str] = Field(default_factory=list)
    alignment: dict[str, str] = Field(default_factory=dict)
    triggers: list[CreepTrigger] = Field(default_factory=list)
    score_from: int | None = None
    score_to: int | None = None
    limitations: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    """Structured evidence element supporting a justification decision (FR-E1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str  # "structural" | "keyword" | "common" | "none"
    text: str


class PurposeMatch(BaseModel):
    """Recognized purpose tag and the triggering keyword/phrase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tag: str
    label: str
    matched_phrase: str


class JustifiedPermission(BaseModel):
    """Evaluated permission with complete rule provenance and explainability."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    kind: str  # "api" | "host" | "optional_api" | "optional_host"
    weight: int
    risk_label: str
    status: str  # "justified" | "needs_review" | "potentially_excessive" | "unknown"
    reason: str
    rule_id: str  # "R1".."R6" or "H1".."H3"
    evidence: list[EvidenceItem] = Field(default_factory=list)
    allows: str
    legitimate_use: str
    source_url: str | None = None
    reviewed: bool = True
    narrower_alternative: str | None = None


class JustificationReport(BaseModel):
    """Complete justification evaluation across API, Host, and Optional sets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    api: list[JustifiedPermission] = Field(default_factory=list)
    host: list[JustifiedPermission] = Field(default_factory=list)
    optional: list[JustifiedPermission] = Field(default_factory=list)
    purposes: list[PurposeMatch] = Field(default_factory=list)
    excess_score: float | None = None
    evidence_coverage: float
