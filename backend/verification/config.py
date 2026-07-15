"""Configuration for the Response Verification Engine."""

from __future__ import annotations

from pydantic import BaseModel


class VerificationConfig(BaseModel):
    """Thresholds and policy governing the overall verdict.

    Defaults are strict: the deterministic Echo pipeline must score perfect. Loosen
    ``min_grounding_coverage`` / ``min_completeness`` when verifying real providers that
    paraphrase more aggressively.
    """

    min_grounding_coverage: float = 1.0
    min_completeness: float = 1.0
    require_citation_order: bool = True
    require_section_order: bool = True
    fail_on_warning: bool = False
