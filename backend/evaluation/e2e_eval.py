"""Offline architectural evaluation of the E2E OpenRouter integration.

Verifies that configuring PROVIDER=openrouter correctly constructs the engine,
routes requests to the OpenRouterLanguageModel, and propagates metadata, all without
making real network requests (HTTP mocked).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.api.app import app
from backend.api.config import ServiceConfig
from backend.api.deps import get_factory
from backend.api.factory import EngineFactory
from backend.evaluation.orchestrator_eval import FakeStrategy
from backend.integrations.openrouter import OpenRouterLanguageModel
from backend.orchestrator.engine import EducationalTutorEngine


class E2EEvalReport(BaseModel):
    """Evaluation results for the E2E integration infrastructure."""

    provider_selectable: bool = False
    api_key_configured: bool = False
    base_url_configured: bool = False
    mocked_round_trip: bool = False
    metadata_propagated: bool = False
    all_passed: bool = False


# A mock client to inject into the OpenRouterLanguageModel
class _MockOpenAIClient:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.chat = self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        class _MockResponse:
            def model_dump(self):
                return {
                    "choices": [
                        {
                            "message": {"content": "Eval mock response"},
                            "finish_reason": "stop"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30
                    }
                }
        return _MockResponse()


class _E2EEvalFactory(EngineFactory):
    """Factory that forces OpenRouter config and injects a mock client."""

    def __init__(self) -> None:
        import os
        os.environ["PROVIDER"] = "openrouter"
        os.environ["MODEL_ID"] = "eval-model"
        os.environ["OPENROUTER_API_KEY"] = "sk-eval-test"
        os.environ["OPENROUTER_BASE_URL"] = "https://eval.local"
        
        config = ServiceConfig()
        super().__init__(config)

    @property
    def tutor_engine(self) -> EducationalTutorEngine:
        if self._tutor_engine is None:
            oc = self._config.to_orchestrator_config()
            oc.use_repository = False
            # Construct the OpenRouter model but patch its client
            lm = OpenRouterLanguageModel(
                model_id=oc.generation.model_id,
                api_key=self._config.api_key,
                base_url=self._config.base_url,
            )
            lm._client = _MockOpenAIClient(api_key=self._config.api_key, base_url=self._config.base_url)
            
            self._tutor_engine = EducationalTutorEngine(
                oc, strategy=FakeStrategy(), language_model=lm
            )
        return self._tutor_engine


def _client() -> TestClient:
    factory = _E2EEvalFactory()
    app.dependency_overrides[get_factory] = lambda: factory
    return TestClient(app)


class E2EEvaluationEngine:
    """Evaluate E2E OpenRouter infrastructure (offline)."""

    def evaluate(self) -> E2EEvalReport:
        c = _client()
        report = E2EEvalReport()
        
        # Test selection and configuration
        factory = _E2EEvalFactory()
        engine = factory.tutor_engine
        lm = engine._language_model
        
        if isinstance(lm, OpenRouterLanguageModel):
            report.provider_selectable = True
            if lm._api_key == "sk-eval-test":
                report.api_key_configured = True
            if lm._base_url == "https://eval.local":
                report.base_url_configured = True
                
        # Test round trip
        resp = c.post("/api/v1/tutor/ask", json={"query": "Evaluate me"})
        data = resp.json()
        
        # The mock response will fail verification (grounding), so expect 422
        if resp.status_code in (200, 422):
            if "Eval mock response" in str(data):
                report.mocked_round_trip = True
            
            # Check metadata propagation
            exec_meta = data.get("execution", {})
            if not exec_meta and resp.status_code == 422:
                # Execution trace might be inside the 422 detail if it's our VerificationFailed mapping
                exec_meta = data.get("detail", {}).get("trace", {})
                
            if exec_meta.get("provider") == "openrouter" and exec_meta.get("model_id") == "eval-model":
                report.metadata_propagated = True

        report.all_passed = all([
            report.provider_selectable,
            report.api_key_configured,
            report.base_url_configured,
            report.mocked_round_trip,
            report.metadata_propagated,
        ])
        return report


def _print_summary(report: E2EEvalReport) -> None:
    print("\n=== E2E Architecture Eval (Phase 8.5) ===")
    for field in (
        "provider_selectable", "api_key_configured", "base_url_configured",
        "mocked_round_trip", "metadata_propagated",
    ):
        print(f"  {field:<22} {getattr(report, field)}")
    print(f"  {'ALL PASSED':<22} {report.all_passed}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate E2E Infrastructure")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    report = E2EEvaluationEngine().evaluate()
    _print_summary(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report.model_dump_json(indent=2) + "\n")
        print(f"\nWrote {args.out}")
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
