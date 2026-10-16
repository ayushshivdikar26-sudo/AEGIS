"""
Pytest Global Configuration & Path Initialization (tests/conftest.py).
Ensures repository root is available in sys.path for test discovery.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
