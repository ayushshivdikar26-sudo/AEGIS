"""
AEGIS Isolated Backend Admin Module (Backend/app/admin.py)
Uses SUPABASE_SECRET_KEY exclusively for administrative setup and test cleanup (PRD Part 2c s4).
CRITICAL: Never invoke this module in user-facing request flows.
"""

from Backend.app.config import settings
from Backend.app.logging_setup import logger
from supabase import Client, create_client

_admin_client: Client | None = None


def get_admin_client() -> Client:
    """Returns singleton Supabase client authenticated with service_role secret key."""
    global _admin_client
    if _admin_client is None:
        if not settings.SUPABASE_SECRET_KEY:
            raise RuntimeError("SUPABASE_SECRET_KEY is not configured.")

        logger.info("Initializing isolated Supabase admin client.")
        _admin_client = create_client(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_SECRET_KEY,
        )
    return _admin_client
