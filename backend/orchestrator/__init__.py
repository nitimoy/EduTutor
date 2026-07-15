"""Educational Tutor Orchestrator — deterministic end-to-end pipeline (Phase 7.0).

Wires the frozen components (Retrieval → Tutor Brain → Student Model → Renderer →
Verification) into one public API, ``EducationalTutorEngine.answer(...)`` → ``TutorResponse``.
Coordination only: no new educational logic, no behavior change, no retries; every input is
left unmutated and execution is deterministic (timing aside).
"""

from backend.orchestrator.config import OrchestratorConfig
from backend.orchestrator.engine import STAGES, EducationalTutorEngine
from backend.orchestrator.errors import (
    ConfigurationError,
    OrchestratorError,
    StageExecutionError,
    VerificationFailedError,
)
from backend.orchestrator.models import (
    ExecutionMetadata,
    RetrievalMetadata,
    TimingInfo,
    TutorResponse,
)
from backend.orchestrator.tracing import ExecutionTrace, StageStatus, StageTrace, Tracer

__all__ = [
    "EducationalTutorEngine",
    "STAGES",
    "OrchestratorConfig",
    "TutorResponse",
    "RetrievalMetadata",
    "ExecutionMetadata",
    "TimingInfo",
    "ExecutionTrace",
    "StageTrace",
    "StageStatus",
    "Tracer",
    "OrchestratorError",
    "ConfigurationError",
    "StageExecutionError",
    "VerificationFailedError",
]
