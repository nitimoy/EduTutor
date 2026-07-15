"""Evaluation report model for the API layer."""

from pydantic import BaseModel


class ApiEvalReport(BaseModel):
    """Evaluation results for the Phase 8.0 API service layer."""

    health_endpoint: bool = False
    version_endpoint: bool = False
    ready_endpoint: bool = False
    root_endpoint: bool = False
    echo_round_trip: bool = False
    session_round_trip: bool = False
    error_mapping: bool = False
    determinism: bool = False
    chat_compatibility: bool = False
    offline_default: bool = False
    all_passed: bool = False
