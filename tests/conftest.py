"""
Pytest Global Configuration & Path Initialization (tests/conftest.py).
Ensures repository root is available in sys.path for test discovery.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from Backend.app.rate_limiter import reset_rate_limits


@pytest.fixture(autouse=True)
def clean_rate_limits():
    """Reset rate limiter state between all tests to prevent cascading 429s."""
    reset_rate_limits()
    yield
    reset_rate_limits()

