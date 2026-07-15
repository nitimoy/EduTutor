"""Architectural evaluation of the Phase 8.0 API service layer.

Fully offline: uses TestClient with injected FakeStrategy + Echo (no compiled data,
no network). Checks endpoint availability, error mapping, determinism, legacy
compatibility, and the offline-by-default guarantee.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.config import ServiceConfig
from backend.api.deps import get_factory
from backend.api.factory import EngineFactory
from backend.evaluation.api_models import ApiEvalReport
from backend.evaluation.orchestrator_eval import FakeStrategy, _FailVerifier
from backend.generation.language_model import EchoLanguageModel
from backend.orchestrator.config import OrchestratorConfig
from backend.orchestrator.engine import EducationalTutorEngine
from backend.session.engine import LearningSessionEngine


class _EvalFactory(EngineFactory):
    """Factory for evaluation: offline, no compiled data."""

    def __init__(self, strict: bool = False, verifier=None) -> None:
        super().__init__(ServiceConfig())
        config = OrchestratorConfig(
            use_repository=False, strict_verification=strict,
        )
        self._tutor_engine = EducationalTutorEngine(
            config, strategy=FakeStrategy(), language_model=EchoLanguageModel(),
            verification_engine=verifier,
        )
        self._session_engine = LearningSessionEngine()


def _client(strict: bool = False, verifier=None) -> TestClient:
    factory = _EvalFactory(strict=strict, verifier=verifier)
    app.dependency_overrides[get_factory] = lambda: factory
    return TestClient(app)


class ApiEvaluationEngine:
    """Evaluate the Phase 8.0 API service layer for architectural correctness."""

    def evaluate(self) -> ApiEvalReport:
        c = _client()
        report = ApiEvalReport(
            health_endpoint=self._check_health(c),
            version_endpoint=self._check_version(c),
            ready_endpoint=self._check_ready(c),
            root_endpoint=self._check_root(c),
            echo_round_trip=self._check_echo_round_trip(c),
            session_round_trip=self._check_session_round_trip(c),
            error_mapping=self._check_error_mapping(),
            determinism=self._check_determinism(c),
            chat_compatibility=self._check_chat_compat(c),
            offline_default=self._check_offline_default(),
        )
        report.all_passed = all([
            report.health_endpoint, report.version_endpoint, report.ready_endpoint,
            report.root_endpoint, report.echo_round_trip, report.session_round_trip,
            report.error_mapping, report.determinism, report.chat_compatibility,
            report.offline_default,
        ])
        return report

    def _check_health(self, c: TestClient) -> bool:
        return c.get("/api/v1/health").json() == {"status": "ok"}

    def _check_version(self, c: TestClient) -> bool:
        data = c.get("/api/v1/version").json()
        return "version" in data and data["phase"] == "8.0"

    def _check_ready(self, c: TestClient) -> bool:
        data = c.get("/api/v1/ready").json()
        return data.get("ready") is True

    def _check_root(self, c: TestClient) -> bool:
        data = c.get("/").json()
        return (data.get("service") == "NCERT Educational Tutor API"
                and "version" in data and data.get("docs") == "/docs")

    def _check_echo_round_trip(self, c: TestClient) -> bool:
        resp = c.post("/api/v1/tutor/ask", json={"query": "What is alpha?"})
        if resp.status_code != 200:
            return False
        data = resp.json()
        return (data["query"] == "What is alpha?"
                and bool(data["answer"])
                and data["execution"]["provider"] == "echo")

    def _check_session_round_trip(self, c: TestClient) -> bool:
        resp = c.post("/api/v1/session/process", json={
            "session": {
                "session_id": "eval-session",
                "events": [
                    {"type": "exercise_correct", "concept_id": "c1"},
                ],
            },
        })
        if resp.status_code != 200:
            return False
        data = resp.json()
        return "delta" in data and "after" in data and "summary" in data

    def _check_error_mapping(self) -> bool:
        # Strict verification + fail verifier → 422.
        c = _client(strict=True, verifier=_FailVerifier())
        resp = c.post("/api/v1/tutor/ask", json={"query": "What is alpha?"})
        if resp.status_code != 422:
            return False
        # Validation error (empty query) → 422.
        c2 = _client()
        resp2 = c2.post("/api/v1/tutor/ask", json={"query": ""})
        return resp2.status_code == 422

    def _check_determinism(self, c: TestClient) -> bool:
        a = c.post("/api/v1/tutor/ask", json={"query": "What is alpha?"}).json()
        b = c.post("/api/v1/tutor/ask", json={"query": "What is alpha?"}).json()
        return a["deterministic_fingerprint"] == b["deterministic_fingerprint"]

    def _check_chat_compat(self, c: TestClient) -> bool:
        resp = c.post("/chat", json={
            "messages": [{"role": "user", "content": "What is alpha?"}],
        })
        if resp.status_code != 200:
            return False
        data = resp.json()
        return bool(data.get("answer")) and "model" in data

    def _check_offline_default(self) -> bool:
        config = ServiceConfig()
        return config.provider == "echo" and config.model_id == "echo-v1"


def _print_summary(report: ApiEvalReport) -> None:
    print("\n=== API Service Layer eval (Phase 8.0) ===")
    for field in (
        "health_endpoint", "version_endpoint", "ready_endpoint", "root_endpoint",
        "echo_round_trip", "session_round_trip", "error_mapping", "determinism",
        "chat_compatibility", "offline_default",
    ):
        print(f"  {field:<22} {getattr(report, field)}")
    print(f"  {'ALL PASSED':<22} {report.all_passed}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the Phase 8.0 API Service Layer")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    report = ApiEvaluationEngine().evaluate()
    _print_summary(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report.model_dump_json(indent=2) + "\n")
        print(f"\nWrote {args.out}")
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
