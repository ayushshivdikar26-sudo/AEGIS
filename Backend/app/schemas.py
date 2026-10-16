"""
AEGIS API Request & Response Schemas (Backend/app/schemas.py)
Strict Pydantic v2 contract models matching API Contract v1 (PRD Part 1 s10, Part 2c s6).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ============================================================================
# 1. Health & System
# ============================================================================
class HealthResponse(StrictBaseModel):
    status: Literal["ok"] = "ok"


# ============================================================================
# 2. Authentication
# ============================================================================
class AuthSignupRequest(StrictBaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


class AuthLoginRequest(StrictBaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class AuthMeResponse(StrictBaseModel):
    id: str
    email: str | None = None
    role: str = "authenticated"


class AuthMessageResponse(StrictBaseModel):
    message: str


# ============================================================================
# 3. Extensions List & Detail
# ============================================================================
class ExtensionListItem(StrictBaseModel):
    id: str
    name: str
    browser: str
    version: str
    icon_url: str | None = None
    risk_score: int
    risk_level: str


class ExtensionsListResponse(StrictBaseModel):
    source: str = "imported"
    extensions: list[ExtensionListItem]


class ExtensionDescription(StrictBaseModel):
    text: str | None = None
    origin: Literal["manifest", "unavailable"] = "manifest"


class ExtensionCapabilities(StrictBaseModel):
    ai_analysis: bool = False


class ExtensionDetailResponse(StrictBaseModel):
    id: str
    name: str
    browser: str
    version: str
    icon_url: str | None = None
    developer: str | None = None
    description: ExtensionDescription
    capabilities: ExtensionCapabilities = Field(default_factory=ExtensionCapabilities)
    assessment: dict[str, Any]


# ============================================================================
# 4. Permissions
# ============================================================================
class PermissionItem(StrictBaseModel):
    name: str
    kind: Literal["api", "host", "optional"]
    weight: int
    risk_label: str
    status: str
    allows: str
    legitimate_use: str
    source_url: str | None = None
    reviewed: bool = True
    evidence: list[str] = Field(default_factory=list)
    rule_id: str | None = None
    reason: str | None = None
    assessment: str | None = None


class PermissionsResponse(StrictBaseModel):
    api: list[PermissionItem] = Field(default_factory=list)
    host: list[PermissionItem] = Field(default_factory=list)
    optional: list[PermissionItem] = Field(default_factory=list)


# ============================================================================
# 5. Versions & Comparison
# ============================================================================
class VersionItem(StrictBaseModel):
    version: str
    released: str | None = None


class VersionsResponse(StrictBaseModel):
    versions: list[VersionItem]


class DiffBucket(StrictBaseModel):
    added: list[dict[str, Any]] = Field(default_factory=list)
    removed: list[dict[str, Any]] = Field(default_factory=list)
    retained: list[dict[str, Any]] = Field(default_factory=list)
    broadened: list[dict[str, Any]] | None = None


class ComparisonResponse(StrictBaseModel):
    from_version: str = Field(alias="from")
    to_version: str = Field(alias="to")
    score_from: int
    score_to: int
    api: DiffBucket
    host: DiffBucket
    optional: DiffBucket

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


# ============================================================================
# 6. Permission Creep
# ============================================================================
class CreepAlignment(StrictBaseModel):
    status: str | None = None
    text: str


class CreepResponse(StrictBaseModel):
    available: bool
    reason: str | None = None
    outcome: str | None = None
    score_from: int | None = None
    score_to: int | None = None
    summary: str | None = None
    limitations: list[str] | None = None
    added: list[dict[str, Any]] | None = None
    removed: list[dict[str, Any]] | None = None
    retained: list[dict[str, Any]] | None = None
    broadened: list[dict[str, Any]] | None = None
    alignment: CreepAlignment | None = None


# ============================================================================
# 7. Manifest Import
# ============================================================================
class ImportSnapshotResult(StrictBaseModel):
    version: str
    created: bool


class ImportResponse(StrictBaseModel):
    extension: ExtensionListItem
    snapshot: ImportSnapshotResult
    matched_existing: bool
    warnings: list[str] = Field(default_factory=list)
