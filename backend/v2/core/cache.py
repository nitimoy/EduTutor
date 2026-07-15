"""Lightweight in-memory caching, rate limiting, and session TTL for dev.

All state lives in process memory — no Redis/external deps needed.
Perfect for single-process dev servers. Survives restarts? No. That's fine.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class TTLCache:
    """Thread-safe in-memory cache with per-key TTL and LRU eviction.

    Usage:
        cache = TTLCache(max_size=1000, default_ttl=300)  # 5 min TTL
        cache.set("key", "value", ttl=60)  # custom TTL
        value = cache.get("key")  # returns None if expired/missing
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value if exists and not expired. Returns None on miss."""
        with self._lock:
            if key in self._cache:
                value, expires_at = self._cache[key]
                if time.time() < expires_at:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    return value
                else:
                    del self._cache[key]
            self._misses += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value with TTL. Evicts oldest if at capacity."""
        with self._lock:
            expires_at = time.time() + (ttl or self._default_ttl)
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (value, expires_at)

    def invalidate(self, key: str) -> bool:
        """Remove a key. Returns True if it existed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{self._hits / total * 100:.1f}%" if total > 0 else "N/A",
            }


class RateLimiter:
    """Simple sliding-window rate limiter per key (e.g., per session or IP).

    Usage:
        limiter = RateLimiter(max_requests=30, window_seconds=60)
        if limiter.allow("session-abc"):
            process_request()
        else:
            return 429
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self._max_requests = max_requests
        self._window = window_seconds
        self._requests: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Check if request is allowed. Returns True if under limit."""
        now = time.time()
        cutoff = now - self._window

        with self._lock:
            if key not in self._requests:
                self._requests[key] = []

            # Remove old timestamps outside the window
            self._requests[key] = [t for t in self._requests[key] if t > cutoff]

            if len(self._requests[key]) < self._max_requests:
                self._requests[key].append(now)
                return True
            return False

    def remaining(self, key: str) -> int:
        """How many requests remain in the current window."""
        now = time.time()
        cutoff = now - self._window

        with self._lock:
            if key not in self._requests:
                return self._max_requests
            recent = [t for t in self._requests[key] if t > cutoff]
            return max(0, self._max_requests - len(recent))

    def reset(self, key: str) -> None:
        """Reset the counter for a key."""
        with self._lock:
            self._requests.pop(key, None)

    def cleanup(self, max_age: float = 3600) -> int:
        """Remove stale keys older than max_age seconds. Returns count removed."""
        cutoff = time.time() - max_age
        removed = 0
        with self._lock:
            stale_keys = [
                k for k, timestamps in self._requests.items()
                if not timestamps or max(timestamps) < cutoff
            ]
            for k in stale_keys:
                del self._requests[k]
                removed += 1
        return removed


class SessionCleanup:
    """Periodic cleanup of expired sessions from SQLite.

    Runs as a background thread. Safe for dev — no external deps.
    """

    def __init__(
        self,
        db_path: str = "data/sessions.db",
        ttl_seconds: int = 86400,  # 24 hours
        cleanup_interval: int = 3600,  # check every hour
    ):
        self._db_path = db_path
        self._ttl = ttl_seconds
        self._interval = cleanup_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cleaned = 0

    def start(self) -> None:
        """Start the background cleanup thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the cleanup thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        """Background loop that cleans up expired sessions."""
        import sqlite3
        while self._running:
            try:
                cutoff = time.time() - self._ttl
                with sqlite3.connect(self._db_path) as conn:
                    cursor = conn.execute(
                        "DELETE FROM v2_sessions WHERE updated_at < datetime(?, 'unixepoch')",
                        (int(cutoff),)
                    )
                    self._cleaned += cursor.rowcount
            except Exception:
                pass  # DB might not exist yet
            time.sleep(self._interval)

    def cleanup_now(self) -> int:
        """Run cleanup immediately. Returns count of sessions removed."""
        import sqlite3
        try:
            cutoff = time.time() - self._ttl
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM v2_sessions WHERE updated_at < datetime(?, 'unixepoch')",
                    (int(cutoff),)
                )
                return cursor.rowcount
        except Exception:
            return 0

    def stats(self) -> dict:
        """Return cleanup statistics."""
        import sqlite3
        try:
            with sqlite3.connect(self._db_path) as conn:
                total = conn.execute("SELECT COUNT(*) FROM v2_sessions").fetchone()[0]
                return {
                    "total_sessions": total,
                    "total_cleaned": self._cleaned,
                    "ttl_hours": self._ttl // 3600,
                    "running": self._running,
                }
        except Exception:
            return {"error": "DB not available"}


def make_cache_key(query: str, subject: Optional[str] = None) -> str:
    """Generate a deterministic cache key for a query."""
    raw = f"{query.lower().strip()}|{subject or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
