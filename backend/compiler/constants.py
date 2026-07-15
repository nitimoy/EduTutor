"""Compiler-wide constants."""

from __future__ import annotations

import hashlib
from typing import Any

# Bumped whenever the Educational IR schema changes shape.
IR_VERSION = "1.1.0"

DEFAULT_PARSER_VERSION = "unknown"


def compute_checksum(*parts: Any) -> str:
    """Deterministic content checksum used for change-detection and caching."""
    payload = "|".join(str(p) for p in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
