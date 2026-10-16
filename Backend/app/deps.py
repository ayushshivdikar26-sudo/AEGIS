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
    Returns None if Supabase is unconfigured or in mock development mode.
    """
    if (
        not settings.SUPABASE_URL
        or "localhost" in settings.SUPABASE_URL
        or settings.SUPABASE_PUBLISHABLE_KEY.startswith("mock-")
    ):
        return None

    token = extract_token_from_request(request)
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        client = create_client(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_PUBLISHABLE_KEY,
            options={"headers": headers} if hasattr(create_client, "options") else None,  # type: ignore[arg-type,call-arg]
        )
        if token:
            # Set auth token on postgrest client
            client.postgrest.auth(token)
        return client
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
