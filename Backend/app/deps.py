"""
AEGIS Dependencies & Authentication Injectors (Backend/app/deps.py)
Provides user-scoped database clients, authenticated user context, and rate limiting keys (PRD Part 2c s4).
"""

from dataclasses import dataclass

from fastapi import Depends, Request

from Backend.app.config import settings
from Backend.app.errors import UnauthorizedError
from Backend.app.security import extract_token_from_request, verify_jwt_token
from supabase import Client, create_client


@dataclass
class CurrentUser:
    id: str
    email: str | None = None
    role: str = "authenticated"


async def get_current_user(request: Request) -> CurrentUser:
    """Extracts and verifies JWT token from request; raises 401 if missing or invalid."""
    token = extract_token_from_request(request)
    if not token:
        raise UnauthorizedError("Authentication required.")

    payload = await verify_jwt_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid user token payload.")

    role = payload.get("app_metadata", {}).get("role", "authenticated")
    email = payload.get("email")
    user = CurrentUser(id=user_id, email=email, role=role)

    # Attach to request state
    request.state.user = user
    return user


async def get_optional_user(request: Request) -> CurrentUser | None:
    """Extracts user if valid session exists; returns None for unauthenticated visitors."""
    token = extract_token_from_request(request)
    if not token:
        return None

    try:
        payload = await verify_jwt_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        role = payload.get("app_metadata", {}).get("role", "authenticated")
        email = payload.get("email")
        user = CurrentUser(id=user_id, email=email, role=role)
        request.state.user = user
        return user
    except Exception:
        return None


def get_user_db_client(request: Request, user: CurrentUser | None = Depends(get_optional_user)) -> Client | None:
    """
    Builds a Supabase client carrying the user's access token, enforcing RLS on every query.
    In local development, if unauthenticated, falls back to admin client when secret key is provided.
    Returns None if Supabase is unconfigured or in mock development mode.
    """
    import sys
    if "pytest" in sys.modules and not getattr(request.state, "force_real_client", False):
        return None
    if (
        not settings.SUPABASE_URL
        or "localhost" in settings.SUPABASE_URL
        or "your-project" in settings.SUPABASE_URL
        or settings.SUPABASE_PUBLISHABLE_KEY.startswith("mock-")
        or "your-" in settings.SUPABASE_PUBLISHABLE_KEY
    ):
        return None

    token = extract_token_from_request(request)

    if token:
        try:
            from supabase.lib.client_options import ClientOptions

            client = create_client(
                supabase_url=settings.SUPABASE_URL,
                supabase_key=settings.SUPABASE_PUBLISHABLE_KEY,
                options=ClientOptions(headers={"Authorization": f"Bearer {token}"}),
            )
            client.postgrest.auth(token)
            return client
        except Exception as exc:
            from Backend.app.logging_setup import logger

            logger.warning(f"Error creating user-scoped Supabase client: {exc}")
            return None

    # In local development without user auth token, use admin client if configured
    if (
        settings.ENVIRONMENT != "production"
        and settings.SUPABASE_SECRET_KEY
        and not settings.SUPABASE_SECRET_KEY.startswith("mock-")
        and "your-" not in settings.SUPABASE_SECRET_KEY
    ):
        try:
            from Backend.app.admin import get_admin_client

            return get_admin_client()
        except Exception as exc:
            from Backend.app.logging_setup import logger

            logger.warning(f"Error getting admin Supabase client: {exc}")

    try:
        return create_client(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_PUBLISHABLE_KEY,
        )
    except Exception:
        return None


def get_client_ip(request: Request) -> str:
    """Extracts client IP, respecting TRUSTED_PROXY_COUNT for reverse proxies."""
    if settings.TRUSTED_PROXY_COUNT > 0:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ips = [ip.strip() for ip in forwarded_for.split(",")]
            if len(ips) >= settings.TRUSTED_PROXY_COUNT:
                return ips[-settings.TRUSTED_PROXY_COUNT]

    if request.client:
        return request.client.host
    return "127.0.0.1"


def get_rate_limit_key(request: Request) -> str:
    """Keys rate limits by authenticated user_id or remote client IP."""
    token = extract_token_from_request(request)
    if token and hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"
    return f"ip:{get_client_ip(request)}"
