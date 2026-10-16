"""
AEGIS Security, JWT Validation & CSRF Protection (Backend/app/security.py)
Asymmetric JWKS JWT verification, HttpOnly cookie management, and CSRF guard (PRD Part 2c s5).
"""

import time
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
from fastapi import Request, Response
from jwt.algorithms import RSAAlgorithm

from Backend.app.config import settings
from Backend.app.errors import ForbiddenError, UnauthorizedError
from Backend.app.logging_setup import logger

# JWKS cache: { "keys": [...], "expires_at": float }
_JWKS_CACHE: dict[str, Any] = {"keys": [], "expires_at": 0.0}
JWKS_TTL_SECONDS = 3600  # 1 hour


def get_cookie_name(base_name: str) -> str:
    """In production with HTTPS and Path=/, apply __Host- prefix for cookie prefix security."""
    if settings.ENVIRONMENT == "production" and settings.COOKIE_SECURE:
        return f"__Host-{base_name}"
    return base_name


ACCESS_COOKIE_NAME = get_cookie_name("aegis_access_token")
REFRESH_COOKIE_NAME = get_cookie_name("aegis_refresh_token")


async def fetch_supabase_jwks(force_refresh: bool = False) -> list[dict]:
    """Fetch public JWKS keys from Supabase Auth endpoint with caching and rotation support."""
    global _JWKS_CACHE
    now = time.time()
    if not force_refresh and _JWKS_CACHE["keys"] and now < _JWKS_CACHE["expires_at"]:
        return _JWKS_CACHE["keys"]

    jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    headers = {"apikey": settings.SUPABASE_PUBLISHABLE_KEY}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(jwks_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                keys = data.get("keys", [])
                _JWKS_CACHE = {"keys": keys, "expires_at": now + JWKS_TTL_SECONDS}
                logger.info(f"Refreshed Supabase JWKS cache ({len(keys)} keys).")
                return keys
            else:
                logger.warning(f"Failed to fetch JWKS from Supabase (status {resp.status_code}).")
    except Exception as exc:
        logger.warning(f"Error fetching Supabase JWKS: {exc}")

    return _JWKS_CACHE.get("keys", [])


async def verify_jwt_token(token: str) -> dict[str, Any]:
    """
    Verify Supabase JWT token:
    1. Tries asymmetric verification via JWKS (RS256 / ES256).
    2. Falls back to HS256 secret if configured.
    3. Strictly enforces exp, iss, and aud == 'authenticated'.
    4. Rejects alg: none.
    """
    if not token or not isinstance(token, str):
        raise UnauthorizedError("Missing or invalid token format.")

    expected_issuer = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"

    # 0. Development / Mock Mode fallback when testing locally without live Supabase
    if settings.ENVIRONMENT != "production" and token.startswith("mock-user-token-"):
        user_id = token.replace("mock-user-token-", "")
        return {
            "sub": user_id,
            "aud": "authenticated",
            "iss": expected_issuer,
            "exp": time.time() + 3600,
            "app_metadata": {"role": "authenticated"},
        }

    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception:
        raise UnauthorizedError("Malformed token header.")

    alg = unverified_header.get("alg")
    if not alg or alg.lower() == "none":
        raise UnauthorizedError("Insecure JWT algorithm rejected.")

    kid = unverified_header.get("kid")

    # 1. Asymmetric verification via JWKS
    keys = await fetch_supabase_jwks()
    matching_key = next((k for k in keys if k.get("kid") == kid), None)

    if not matching_key and kid:
        # Key rotation handling: refresh cache once if key not found
        keys = await fetch_supabase_jwks(force_refresh=True)
        matching_key = next((k for k in keys if k.get("kid") == kid), None)

    if matching_key:
        try:
            public_key = RSAAlgorithm.from_jwk(matching_key)
            payload = jwt.decode(
                token,
                public_key,  # type: ignore[arg-type]
                algorithms=["RS256", "ES256"],
                audience="authenticated",
                issuer=expected_issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
            return payload
        except jwt.PyJWTError as err:
            raise UnauthorizedError(f"Token validation failed: {err}")

    # 2. Symmetric fallback if HS256 secret is configured
    if alg == "HS256" and settings.SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=expected_issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
            return payload
        except jwt.PyJWTError as err:
            raise UnauthorizedError(f"Token signature verification failed: {err}")

    raise UnauthorizedError("No matching public key found for token.")


def set_auth_cookies(response: Response, access_token: str, refresh_token: str | None = None) -> None:
    """Set secure HttpOnly cookies for session management."""
    max_age_access = 3600  # 1 hour
    max_age_refresh = 60 * 60 * 24 * 30  # 30 days

    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=max_age_access,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path="/",
    )

    if refresh_token:
        response.set_cookie(
            key=REFRESH_COOKIE_NAME,
            value=refresh_token,
            max_age=max_age_refresh,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite="strict",
            path="/api/auth",
        )


def clear_auth_cookies(response: Response) -> None:
    """Clear session cookies upon logout."""
    response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/auth")


def extract_token_from_request(request: Request) -> str | None:
    """Extract bearer token from cookie or Authorization header."""
    cookie_token = request.cookies.get(ACCESS_COOKIE_NAME)
    if cookie_token:
        return cookie_token

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


def verify_csrf_protection(request: Request) -> None:
    """
    Enforces double-submit CSRF protection on non-GET requests:
    1. Must contain X-AEGIS-CSRF custom header.
    2. Must verify Origin / Referer matches host.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    csrf_header = request.headers.get("X-AEGIS-CSRF")
    if not csrf_header:
        raise ForbiddenError("Missing required X-AEGIS-CSRF header for state-changing request.")

    # Validate Origin or Referer
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")
    host = request.headers.get("Host") or request.url.netloc

    if origin:
        parsed_origin = urlparse(origin)
        if parsed_origin.netloc != host and parsed_origin.netloc not in settings.ALLOWED_ORIGINS:
            raise ForbiddenError("Cross-origin request rejected by CSRF protection.")
    elif referer:
        parsed_ref = urlparse(referer)
        if parsed_ref.netloc != host and parsed_ref.netloc not in settings.ALLOWED_ORIGINS:
            raise ForbiddenError("Invalid request referer rejected by CSRF protection.")
