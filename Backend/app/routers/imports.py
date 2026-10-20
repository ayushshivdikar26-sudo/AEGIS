"""
AEGIS Manifest & Icon Import Router (Backend/app/routers/imports.py)
Secure multipart manifest ingestion, magic-byte icon verification, and append-only snapshot deduplication (PRD Part 2c s6.1).
"""

import json

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Request,
    Response,
    UploadFile,
    status,
)

from Backend.app.cache import extension_list_cache
from Backend.app.config import settings
from Backend.app.deps import CurrentUser, get_optional_user, get_user_db_client
from Backend.app.errors import AppError, ConflictError, UnauthorizedError
from Backend.app.rate_limiter import enforce_critical_route_rate_limit
from Backend.app.repo import Repository
from Backend.app.schemas import ExtensionListItem, ImportResponse, ImportSnapshotResult
from Backend.app.services.assessment import compute_snapshot_assessment
from Backend.core.manifest_parser import ManifestError, parse_manifest

router = APIRouter(prefix="/api/extensions", tags=["imports"])

ALLOWED_ICON_TYPES = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
    "webp": b"RIFF",
}
MAX_MANIFEST_BYTES = 1_048_576  # 1 MB
MAX_ICON_BYTES = 262_144  # 256 KB


def validate_icon_magic_bytes(content: bytes) -> str:
    """Verifies that uploaded icon bytes strictly match PNG, JPEG, or WebP magic headers. Rejects SVG."""
    if len(content) > MAX_ICON_BYTES:
        raise AppError(
            "Icon file size exceeds 256 KB limit.",
            code="icon_too_large",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if content.startswith(b"<?xml") or b"<svg" in content[:256].lower():
        raise AppError(
            "SVG icons are prohibited for security.",
            code="svg_prohibited",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if content.startswith(ALLOWED_ICON_TYPES["png"]):
        return "png"
    if content.startswith(ALLOWED_ICON_TYPES["jpeg"]):
        return "jpeg"
    if content.startswith(b"RIFF") and b"WEBP" in content[8:16]:
        return "webp"

    raise AppError(
        "Invalid icon format. Only PNG, JPEG, and WebP are allowed.",
        code="invalid_icon_format",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@router.post("/import", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
async def import_manifest(
    request: Request,
    response: Response,
    manifest: UploadFile = File(...),
    browser: str = Form(...),
    store_id: str | None = Form(None),
    display_name: str | None = Form(None),
    messages: UploadFile | None = File(None),
    icon: UploadFile | None = File(None),
    user: CurrentUser | None = Depends(get_optional_user),
    client=Depends(get_user_db_client),
) -> ImportResponse:
    """Imports an extension manifest with magic-byte icon verification and deduplication."""
    enforce_critical_route_rate_limit(request, "import", max_requests=10, window_seconds=60)

    if user:
        effective_user_id = user.id
    elif settings.ENVIRONMENT != "production":
        effective_user_id = "00000000-0000-0000-0000-000000000001"
    else:
        raise UnauthorizedError("Authentication required.")

    # 1. Read and validate manifest payload
    manifest_bytes = await manifest.read()
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise AppError(
            "Manifest file exceeds 1 MB limit.",
            code="manifest_too_large",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # 2. Read optional messages.json
    messages_dict = None
    if messages:
        try:
            msg_bytes = await messages.read()
            messages_dict = json.loads(msg_bytes.decode("utf-8"))
        except Exception:
            messages_dict = None

    # 3. Parse manifest through core parser
    try:
        parsed = parse_manifest(
            manifest_bytes,
            messages=messages_dict,
        )
    except ManifestError as merr:
        raise AppError(
            f"Manifest parse error: {merr.message}", code=merr.code, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # 4. Handle placeholder name requiring user input
    effective_name = display_name if display_name else parsed.name
    if effective_name.startswith("__MSG_") and not display_name and not messages:
        raise AppError(
            f"Extension name '{parsed.name}' is an unresolved placeholder. Please provide a display name or messages.json.",
            code="name_unresolved",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # 5. Handle optional icon upload
    icon_path = None
    if icon:
        icon_bytes = await icon.read()
        if icon_bytes:
            ext_format = validate_icon_magic_bytes(icon_bytes)
            icon_path = f"{effective_user_id}/{store_id or effective_name[:32]}.{ext_format}"

    # 6. Database Operations (Centralized in Repository)
    repo = Repository(client=client)

    # Match existing extension or create new
    existing_ext = repo.find_extension_by_store_or_name(effective_user_id, browser, store_id, effective_name)
    matched_existing = existing_ext is not None

    if matched_existing and existing_ext:
        ext_id = existing_ext["id"]
    else:
        created_ext = repo.insert_extension(
            effective_user_id,
            browser=browser,
            store_id=store_id,
            name=effective_name,
            icon_path=icon_path,
        )
        ext_id = created_ext["id"]

    # 7. Append-only snapshot insertion
    try:
        snapshot_rec, created = repo.insert_snapshot(effective_user_id, ext_id, parsed)
    except ConflictError as cerr:
        raise ConflictError(str(cerr))

    assessment = compute_snapshot_assessment(snapshot_rec)

    if not created:
        response.status_code = status.HTTP_200_OK

    response_item = ExtensionListItem(
        id=ext_id,
        name=effective_name,
        browser=browser,
        version=parsed.version,
        icon_url=icon_path,
        risk_score=assessment.get("risk_score", 0),
        risk_level=assessment.get("risk_level", "low"),
    )

    extension_list_cache.invalidate(effective_user_id)

    return ImportResponse(
        extension=response_item,
        snapshot=ImportSnapshotResult(version=parsed.version, created=created),
        matched_existing=matched_existing,
        warnings=[],
    )
