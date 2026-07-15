"""Orchestrator error types.

The orchestrator stops immediately on any stage failure (no retries, no regeneration):
a stage exception is wrapped in :class:`StageExecutionError` and re-raised.
:class:`VerificationFailedError` is only raised when ``strict_verification`` is set — by
default a failing verification verdict is a normal terminal outcome carried in the response.
"""

from __future__ import annotations

from typing import Optional


class OrchestratorError(Exception):
    """Base class for all orchestrator errors."""


class ConfigurationError(OrchestratorError):
    """The engine cannot build a required component from the given configuration."""


class StageExecutionError(OrchestratorError):
    """A pipeline stage raised; the pipeline halts immediately (no retry)."""

    def __init__(self, stage: str, cause: BaseException) -> None:
        self.stage = stage
        self.cause = cause
        super().__init__(f"stage '{stage}' failed: {cause!r}")


class VerificationFailedError(OrchestratorError):
    """Raised only under strict_verification when the verification verdict is FAIL.

    Carries the fully-assembled response (including the failing ``VerificationReport`` and
    the execution trace) so callers can still inspect what happened.
    """

    def __init__(self, response: object, message: Optional[str] = None) -> None:
        self.response = response
        super().__init__(message or "verification verdict failed under strict_verification")
