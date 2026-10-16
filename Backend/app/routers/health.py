"""
AEGIS Health Check Router (Backend/app/routers/health.py)
Public endpoint reporting service status (PRD Part 2c s6).
"""

from fastapi import APIRouter

from Backend.app.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Public health status check."""
    return HealthResponse(status="ok")
