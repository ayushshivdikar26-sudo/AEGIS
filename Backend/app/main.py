"""
AEGIS FastAPI Application Entrypoint (Backend/app/main.py)
Factory, middleware pipeline, routers mounting, and secure static frontend serving (PRD Part 2c s2, s7).
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from Backend.app.config import settings
from Backend.app.errors import (
    AppError,
    app_error_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from Backend.app.middleware import RequestTracingMiddleware
from Backend.app.rate_limiter import limiter
from Backend.app.routers import auth, extensions, health, imports

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "Frontend"

PROHIBITED_EXTENSIONS = {".env", ".py", ".pyc", ".db", ".sqlite", ".sql", ".sh", ".md", ".jsonl"}
PROHIBITED_DIRS = {".git", ".venv", "tests", "docs", "supabase", "dev", "PRD"}


class SecureStaticFiles(StaticFiles):
    """Custom static files handler that strictly denies access to source, tests, or config files."""

    async def get_response(self, path: str, scope) -> Response:
        p = Path(path)
        if any(part in PROHIBITED_DIRS for part in p.parts):
            return Response(status_code=404)
        if p.suffix.lower() in PROHIBITED_EXTENSIONS:
            return Response(status_code=404)
        return await super().get_response(path, scope)


def create_app() -> FastAPI:
    is_prod = settings.ENVIRONMENT.lower() == "production"

    app = FastAPI(
        title="AEGIS — Permission Creep Auditor API",
        version="1.0.0",
        debug=not is_prod,
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    # 1. State & Rate Limiter
    app.state.limiter = limiter

    # 2. Exception Handlers
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)

    # 3. Middleware Order:
    # Outer: CORS (if configured)
    if settings.ALLOWED_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

    # Core Security Middleware (Request ID, Headers, Body-Size Limit, CSRF, Logging)
    app.add_middleware(RequestTracingMiddleware)

    # 4. Mount API Routers
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(extensions.router)
    app.include_router(imports.router)

    # 5. Serve Single-Page Frontend at Root
    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_file = FRONTEND_DIR / "dashboard.html"
        if not index_file.exists():
            return Response(status_code=404)
        return FileResponse(index_file, media_type="text/html; charset=utf-8")

    if FRONTEND_DIR.exists():
        app.mount("/", SecureStaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    @app.on_event("startup")
    async def startup_seed():
        import sys

        from Backend.app.repo import seed_mock_store_from_fixtures

        if "pytest" not in sys.modules and settings.ENVIRONMENT != "production":
            seed_mock_store_from_fixtures()

    return app


app = create_app()
