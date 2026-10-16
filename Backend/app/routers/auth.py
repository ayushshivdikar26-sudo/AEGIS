"""
AEGIS Authentication Router (Backend/app/routers/auth.py)
Backend-mediated cookie authentication with Supabase Auth, CSRF checks, and enumeration defense (PRD Part 2c s5).
"""

import httpx
from fastapi import APIRouter, Depends, Request, Response

from Backend.app.config import settings
from Backend.app.deps import CurrentUser, get_current_user
from Backend.app.errors import AppError, UnauthorizedError
from Backend.app.logging_setup import logger
from Backend.app.rate_limiter import enforce_critical_route_rate_limit
from Backend.app.schemas import (
    AuthLoginRequest,
    AuthMeResponse,
    AuthMessageResponse,
    AuthSignupRequest,
)
from Backend.app.security import clear_auth_cookies, set_auth_cookies

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=AuthMessageResponse)
async def signup(request: Request, body: AuthSignupRequest) -> AuthMessageResponse:
    """Sign up a new user via Supabase Auth with neutral enumeration-safe message."""
    enforce_critical_route_rate_limit(request, "signup", max_requests=3, window_seconds=60)

    # 1. Production / Live Supabase integration
    if settings.SUPABASE_URL and not settings.SUPABASE_URL.startswith("https://localhost"):
        try:
            signup_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/signup"
            headers = {"apikey": settings.SUPABASE_PUBLISHABLE_KEY, "Content-Type": "application/json"}
            payload = {"email": body.email, "password": body.password}

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(signup_url, json=payload, headers=headers)
                if resp.status_code not in (200, 201):
                    logger.warning(f"Supabase signup returned status {resp.status_code}")
        except Exception as exc:
            logger.error(f"Error during Supabase signup request: {exc}")

    # Always return neutral message to eliminate account enumeration attack vector
    return AuthMessageResponse(message="If this email can be used, check your inbox.")


@router.post("/login", response_model=AuthMessageResponse)
async def login(request: Request, response: Response, body: AuthLoginRequest) -> AuthMessageResponse:
    """Sign in user with Supabase Auth and establish HttpOnly session cookies."""
    enforce_critical_route_rate_limit(request, "login", max_requests=5, window_seconds=60)

    # 1. Live Supabase Auth
    if settings.SUPABASE_URL and not settings.SUPABASE_URL.startswith("https://localhost"):
        try:
            login_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password"
            headers = {"apikey": settings.SUPABASE_PUBLISHABLE_KEY, "Content-Type": "application/json"}
            payload = {"email": body.email, "password": body.password}

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(login_url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    access_token = data.get("access_token")
                    refresh_token = data.get("refresh_token")
                    if access_token:
                        set_auth_cookies(response, access_token, refresh_token)
                        return AuthMessageResponse(message="Login successful.")

                logger.warning(f"Supabase login failed with status {resp.status_code}")
                raise UnauthorizedError("Invalid email or password.")
        except UnauthorizedError:
            raise
        except Exception as exc:
            logger.error(f"Error connecting to Supabase Auth: {exc}")
            if settings.ENVIRONMENT == "production":
                raise AppError("Authentication service unavailable.", code="service_unavailable", status_code=503)

    # 2. Local / Mock Mode Fallback for Testing
    if settings.ENVIRONMENT != "production":
        mock_user_id = "00000000-0000-0000-0000-000000000002"
        mock_access = f"mock-user-token-{mock_user_id}"
        set_auth_cookies(response, mock_access, "mock-refresh-token")
        return AuthMessageResponse(message="Login successful.")

    raise UnauthorizedError("Invalid email or password.")


@router.post("/refresh", response_model=AuthMessageResponse)
async def refresh_session(request: Request, response: Response) -> AuthMessageResponse:
    """Rotate session token using HttpOnly refresh cookie."""
    refresh_token = request.cookies.get("aegis_refresh_token")
    if not refresh_token:
        raise UnauthorizedError("Refresh token missing.")

    if settings.SUPABASE_URL and not settings.SUPABASE_URL.startswith("https://localhost"):
        try:
            refresh_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=refresh_token"
            headers = {"apikey": settings.SUPABASE_PUBLISHABLE_KEY, "Content-Type": "application/json"}
            payload = {"refresh_token": refresh_token}

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(refresh_url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    new_access = data.get("access_token")
                    new_refresh = data.get("refresh_token")
                    set_auth_cookies(response, new_access, new_refresh)
                    return AuthMessageResponse(message="Session refreshed successfully.")
        except Exception as exc:
            logger.warning(f"Error refreshing session: {exc}")

    if settings.ENVIRONMENT != "production" and refresh_token == "mock-refresh-token":
        mock_user_id = "00000000-0000-0000-0000-000000000002"
        set_auth_cookies(response, f"mock-user-token-{mock_user_id}", "mock-refresh-token")
        return AuthMessageResponse(message="Session refreshed successfully.")

    raise UnauthorizedError("Could not refresh session.")


@router.post("/logout", response_model=AuthMessageResponse)
async def logout(response: Response) -> AuthMessageResponse:
    """Clear HttpOnly session cookies."""
    clear_auth_cookies(response)
    return AuthMessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=AuthMeResponse)
async def get_me(user: CurrentUser = Depends(get_current_user)) -> AuthMeResponse:
    """Return currently authenticated user identity."""
    return AuthMeResponse(id=user.id, email=user.email, role=user.role)
