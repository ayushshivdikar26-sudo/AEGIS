"""
AEGIS AI Analyzer Service (Backend/app/services/ai.py)
Stub service; AI is strictly disabled by default (deferred to Milestone M8) (PRD Part 2c s6).
"""

from typing import Any


def is_ai_available() -> bool:
    """Returns False for core release; AI is deferred and disabled by default."""
    return False


def get_ai_capabilities() -> dict[str, Any]:
    """Returns capabilities dictionary for API responses."""
    return {"ai_analysis": False}
