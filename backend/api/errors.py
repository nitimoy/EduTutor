"""Exception-to-HTTP mapping for orchestrator errors.

Registers FastAPI exception handlers that translate frozen orchestrator exceptions
into structured JSON error responses with appropriate HTTP status codes. The error
body shape is consistent: ``{"error": str, "code": str, "detail": dict | None}``.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.orchestrator.errors import (
    ConfigurationError,
    OrchestratorError,
    StageExecutionError,
    VerificationFailedError,
)


def _error_response(status: int, code: str, message: str, detail: dict | None = None) -> JSONResponse:
    body: dict[str, object] = {"error": message, "code": code}
    if detail is not None:
        body["detail"] = detail
    return JSONResponse(status_code=status, content=body)


async def _handle_configuration_error(_: Request, exc: ConfigurationError) -> JSONResponse:
    return _error_response(500, "CONFIGURATION_ERROR", str(exc))


async def _handle_stage_execution_error(_: Request, exc: StageExecutionError) -> JSONResponse:
    return _error_response(
        500, "STAGE_EXECUTION_ERROR", str(exc),
        detail={"stage": exc.stage, "cause": repr(exc.cause)},
    )


async def _handle_verification_failed_error(_: Request, exc: VerificationFailedError) -> JSONResponse:
    return _error_response(422, "VERIFICATION_FAILED", str(exc))


async def _handle_orchestrator_error(_: Request, exc: OrchestratorError) -> JSONResponse:
    return _error_response(500, "ORCHESTRATOR_ERROR", str(exc))


def register_exception_handlers(app: FastAPI) -> None:
    """Register all orchestrator exception handlers on the FastAPI app.

    Order matters: more specific exceptions must be registered before the base
    ``OrchestratorError`` so they are matched first.
    """
    app.add_exception_handler(ConfigurationError, _handle_configuration_error)
    app.add_exception_handler(StageExecutionError, _handle_stage_execution_error)
    app.add_exception_handler(VerificationFailedError, _handle_verification_failed_error)
    app.add_exception_handler(OrchestratorError, _handle_orchestrator_error)
