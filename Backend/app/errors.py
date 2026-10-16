"""
AEGIS Typed Exceptions & Error Handlers (Backend/app/errors.py)
Guarantees uniform {"error": {"code", "message", "request_id"}} responses with zero trace leakage (PRD Part 2c s7).
"""

from collections.abc import Mapping
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from Backend.app.logging_setup import logger


class AppError(Exception):
    def __init__(self, message: str, code: str = "app_error", status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", code: str = "not_found"):
        super().__init__(message, code=code, status_code=status.HTTP_404_NOT_FOUND)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required", code: str = "unauthorized"):
        super().__init__(message, code=code, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied", code: str = "forbidden"):
        super().__init__(message, code=code, status_code=status.HTTP_403_FORBIDDEN)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict", code: str = "conflict"):
        super().__init__(message, code=code, status_code=status.HTTP_409_CONFLICT)


class RateLimitExceededError(AppError):
    def __init__(self, message: str = "Too many requests", retry_after: int = 60):
        super().__init__(message, code="rate_limit_exceeded", status_code=status.HTTP_429_TOO_MANY_REQUESTS)
        self.retry_after = retry_after


def format_error_response(
    code: str, message: str, request_id: str, status_code: int, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }
    resp_headers = {"X-Request-ID": request_id}
    if headers:
        resp_headers.update(headers)
    return JSONResponse(status_code=status_code, content=payload, headers=resp_headers)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    req_id = getattr(request.state, "request_id", "unknown-req")
    extra: dict[str, Any] = {"request_id": req_id, "path": request.url.path, "code": exc.code}
    logger.warning(f"Application error: {exc.code} - {exc.message}", extra=extra)

    headers = {}
    if isinstance(exc, RateLimitExceededError):
        headers["Retry-After"] = str(exc.retry_after)

    return format_error_response(exc.code, exc.message, req_id, exc.status_code, headers=headers)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    req_id = getattr(request.state, "request_id", "unknown-req")
    code = f"http_{exc.status_code}"
    message = str(exc.detail) if exc.detail else "An HTTP error occurred"

    if exc.status_code == status.HTTP_404_NOT_FOUND:
        code = "not_found"
    elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
        code = "unauthorized"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        code = "forbidden"

    return format_error_response(code, message, req_id, exc.status_code, headers=exc.headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    req_id = getattr(request.state, "request_id", "unknown-req")
    # Redact sensitive input values; return only field names and error reasons
    field_errors = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
        msg = err.get("msg", "Invalid value")
        field_errors.append(f"{loc}: {msg}" if loc else msg)

    summary = "; ".join(field_errors) if field_errors else "Validation error in request"
    return format_error_response("validation_error", summary, req_id, status.HTTP_422_UNPROCESSABLE_ENTITY)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    req_id = getattr(request.state, "request_id", "unknown-req")
    # Log full traceback internally with request id; return generic 500 to client
    logger.error(
        f"Unhandled server exception: {exc}",
        exc_info=True,
        extra={"request_id": req_id, "path": request.url.path},
    )
    return format_error_response(
        "internal_server_error",
        "An internal server error occurred. Please quote the request ID when seeking assistance.",
        req_id,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
