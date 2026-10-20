"""
AEGIS In-Memory Cache (Backend/app/cache.py)
Thread-safe, bounded TTL cache for API responses (Milestone 1, Task 3).
"""

from collections import OrderedDict
import threading
import time
from typing import Any


class ExtensionListCache:
    """Thread-safe, bounded, in-memory TTL cache for extensions list responses."""

    def __init__(
        self,
        ttl_seconds: float = 60.0,
        max_size: int = 500,
        time_func=time.monotonic,
    ) -> None:
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._time_func = time_func
        # Map key -> (expires_at, cached_value)
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def _make_key(self, user_id: str, limit: int = 200) -> str:
        return f"{user_id}:{limit}"

    def get(self, user_id: str, limit: int = 200) -> Any | None:
        key = self._make_key(user_id, limit)
        with self._lock:
            if key not in self._cache:
                return None
            expires_at, val = self._cache[key]
            now = self._time_func()
            if now > expires_at:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return val

    def set(self, user_id: str, val: Any, limit: int = 200) -> None:
        key = self._make_key(user_id, limit)
        with self._lock:
            now = self._time_func()
            expires_at = now + self._ttl
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (expires_at, val)

    def invalidate(self, user_id: str) -> None:
        """Invalidate all cache entries associated with user_id."""
        with self._lock:
            prefix = f"{user_id}:"
            keys_to_del = [k for k in self._cache if k == user_id or k.startswith(prefix)]
            for k in keys_to_del:
                del self._cache[k]

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()


# Global singleton instance with 60-second TTL
extension_list_cache = ExtensionListCache(ttl_seconds=60.0, max_size=500)
