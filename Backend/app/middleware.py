"""
AEGIS Security Middleware (Backend/app/middleware.py)
Request ID tracing, strict security headers, body-size enforcement, and structured request logging (PRD Part 2c s7).
"""

import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from Backend.app.config import settings
from Backend.app.errors import format_error_response
from Backend.app.logging_setup import hash_user_id, logger
from Backend.app.security import verify_csrf_protection

MAX_BODY_SIZE_BYTES = 1_572_864  # 1.5 MB


class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Generate or extract X-Request-ID
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = req_id

        # 2. Body-size enforcement for streaming uploads
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE_BYTES:
            return format_error_response(
                "payload_too_large",
                "Total request payload exceeds maximum limit of 1.5 MB.",
                req_id,
                413,
            )

        # 3. CSRF Verification for state-changing requests
        try:
            verify_csrf_protection(request)
        except Exception as exc:
            from Backend.app.errors import ForbiddenError

            if isinstance(exc, ForbiddenError):
                return format_error_response(exc.code, exc.message, req_id, 403)
            raise exc

        start_time = time.time()
        response: Response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # 4. Attach X-Request-ID to response headers
        response.headers["X-Request-ID"] = req_id

        # 5. Attach Comprehensive Security Headers
        supabase_host = settings.SUPABASE_URL.rstrip("/")
        csp_header = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "font-src 'self'; "
            f"img-src 'self' data: {supabase_host}; "
            f"connect-src 'self' {supabase_host}; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        response.headers["Content-Security-Policy"] = csp_header
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
        )

        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

        # Prevent browser caching on sensitive dynamic API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        # 6. Structured Request Log
        user_id = getattr(getattr(request.state, "user", None), "id", None)
        logger.info(
            f"{request.method} {request.url.path} {response.status_code} ({duration_ms}ms)",
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_hash": hash_user_id(user_id),
            },
        )

        return response
