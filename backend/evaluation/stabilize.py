"""Stabilization runner that gates compiler changes on evaluation metrics."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from backend.evaluation.engine import EvaluationEngine, EvaluationMetrics
from backend.evaluation.models import GoldStandard
from backend.evaluation.validator import validate_gold_standard


ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
COMPILED_DIR = ROOT_DIR / "data" / "compiled"
GOLD_DIR = ROOT_DIR / "data" / "evaluation" / "gold_standards"
DEFAULT_BASELINE_PATH = ROOT_DIR / "data" / "evaluation" / "baselines" / "compiler_stability.json"

SUBJECT_ORDER = ["chemistry", "physics", "mathematics"]
CORE_METRICS = [
    "concept_precision",
    "concept_recall",
    "concept_f1",
    "edge_precision",
    "edge_recall",
    "edge_f1",
    "hierarchy_accuracy",
    "formula_linking_accuracy",
    "figure_linking_accuracy",
    "proof_linking_accuracy",
    "learning_path_accuracy",
]

SUBJECT_SPECS = {
    "chemistry": {
        "pdf": RAW_DIR / "chemistry_part_1.pdf",
        "compiled": COMPILED_DIR / "chemistry" / "chemistry_part_1",
        "gold": GOLD_DIR / "chem_ch1.yaml",
    },
    "physics": {
        "pdf": RAW_DIR / "physics_part_1.pdf",
        "compiled": COMPILED_DIR / "physics" / "physics_part_1",
        "gold": GOLD_DIR / "phys_ch1.yaml",
    },
    "mathematics": {
        "pdf": RAW_DIR / "mathematics_part_1.pdf",
        "compiled": COMPILED_DIR / "mathematics" / "mathematics_part_1",
        "gold": GOLD_DIR / "math_ch1.yaml",
    },
}


@dataclass
class SubjectResult:
    """Stabilization outcome for a single subject."""

    subject: str
    status: str
    message: str
    metrics: dict[str, float] | None = None
    gold_path: str | None = None
    compiled_dir: str | None = None


def _load_gold_standard(path: Path) -> GoldStandard:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return GoldStandard.model_validate(data)


def _metrics_snapshot(metrics: EvaluationMetrics) -> dict[str, Any]:
    snapshot = {name: getattr(metrics, name) for name in CORE_METRICS}
    snapshot["gold_concepts_count"] = metrics.gold_concepts_count
    snapshot["discovered_concepts_count"] = metrics.discovered_concepts_count
    snapshot["gold_edges_count"] = metrics.gold_edges_count
    snapshot["inferred_edges_count"] = metrics.inferred_edges_count
    snapshot["learning_path_coverage"] = metrics.learning_path_coverage
    return snapshot


def _compile_subject(pdf_path: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "backend.compiler.pipeline",
        str(pdf_path),
        "--stage",
        "export",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Compile failed for "
            f"{pdf_path.name}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )


def _evaluate_subject(subject: str, skip_compile: bool) -> SubjectResult:
    spec = SUBJECT_SPECS[subject]
    pdf_path = spec["pdf"]
    compiled_dir = spec["compiled"]
    gold_path = spec["gold"]

    if not gold_path.exists():
        return SubjectResult(
            subject=subject,
            status="missing_gold",
            message=f"Gold standard not found: {gold_path}",
            gold_path=str(gold_path),
            compiled_dir=str(compiled_dir),
        )

    # Validate gold standard before using it
    validation = validate_gold_standard(gold_path)
    if not validation.valid:
        error_msgs = [i.message for i in validation.issues if i.severity == "error"]
        return SubjectResult(
            subject=subject,
            status="invalid_gold",
            message=f"Gold standard validation failed: {'; '.join(error_msgs)}",
            gold_path=str(gold_path),
            compiled_dir=str(compiled_dir),
        )

    if not pdf_path.exists():
        return SubjectResult(
            subject=subject,
            status="missing_pdf",
            message=f"Raw PDF not found: {pdf_path}",
            gold_path=str(gold_path),
            compiled_dir=str(compiled_dir),
        )

    if not skip_compile:
        _compile_subject(pdf_path)

    if not compiled_dir.exists():
        return SubjectResult(
            subject=subject,
            status="missing_compiled",
            message=f"Compiled directory not found: {compiled_dir}",
            gold_path=str(gold_path),
            compiled_dir=str(compiled_dir),
        )

    engine = EvaluationEngine()
    gold_standard = _load_gold_standard(gold_path)
    metrics = engine.evaluate(compiled_dir, gold_standard)
    snapshot = _metrics_snapshot(metrics)
    return SubjectResult(
        subject=subject,
        status="ok",
        message="Evaluation completed",
        metrics=snapshot,
        gold_path=str(gold_path),
        compiled_dir=str(compiled_dir),
    )


def _ordered_subjects(requested: list[str] | None) -> list[str]:
    if not requested:
        return SUBJECT_ORDER[:]
    selected = {subject.strip().lower() for subject in requested}
    return [subject for subject in SUBJECT_ORDER if subject in selected]


def _load_baseline(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_baseline(path: Path, results: list[SubjectResult]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "core_metrics": CORE_METRICS,
        "subjects": {
            result.subject: {
                "status": result.status,
                "message": result.message,
                "gold_path": result.gold_path,
                "compiled_dir": result.compiled_dir,
                "metrics": result.metrics,
            }
            for result in results
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _compare_against_baseline(results: list[SubjectResult], baseline: dict[str, Any]) -> tuple[bool, list[str]]:
    success = True
    messages: list[str] = []
    baseline_subjects = baseline.get("subjects", {})

    for result in results:
        if result.status != "ok":
            success = False
            messages.append(f"{result.subject}: {result.status} - {result.message}")
            continue

        baseline_entry = baseline_subjects.get(result.subject)
        if not baseline_entry or baseline_entry.get("status") != "ok":
            success = False
            messages.append(f"{result.subject}: no usable baseline entry")
            continue

        baseline_metrics = baseline_entry.get("metrics") or {}
        current_metrics = result.metrics or {}
        regressions: list[str] = []
        for name in CORE_METRICS:
            current_value = float(current_metrics.get(name, 0.0))
            baseline_value = float(baseline_metrics.get(name, 0.0))
            if current_value + 1e-12 < baseline_value:
                regressions.append(f"{name} {current_value:.4f} < {baseline_value:.4f}")

        if regressions:
            success = False
            messages.append(f"{result.subject}: regression detected: {'; '.join(regressions)}")
        else:
            messages.append(f"{result.subject}: metrics maintained or improved")

    return success, messages


def _print_results(results: list[SubjectResult], comparison_messages: list[str] | None = None) -> None:
    for result in results:
        print(f"[{result.subject}] {result.status}: {result.message}")
        if result.metrics:
            for name in CORE_METRICS:
                print(f"  - {name}: {result.metrics[name]:.4f}")
            if "learning_path_coverage" in result.metrics:
                print(f"  - learning_path_coverage: {result.metrics['learning_path_coverage']:.4f}")
    if comparison_messages:
        print("")
        print("Comparison")
        for message in comparison_messages:
            print(f"- {message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate compiler changes on evaluation metrics.")
    parser.add_argument(
        "--subjects",
        nargs="+",
        choices=SUBJECT_ORDER,
        help="Subjects to evaluate. Defaults to chemistry, physics, mathematics in that order.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help="Path to the baseline JSON snapshot.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write the current results as the baseline instead of comparing against it.",
    )
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="Evaluate existing compiled outputs instead of recompiling raw PDFs first.",
    )
    args = parser.parse_args(argv)

    subjects = _ordered_subjects(args.subjects)
    results = [_evaluate_subject(subject, skip_compile=args.skip_compile) for subject in subjects]

    if args.write_baseline:
        _write_baseline(args.baseline, results)
        _print_results(results)
        print("")
        print(f"Baseline written to {args.baseline}")
        return 0

    if not args.baseline.exists():
        _print_results(results)
        print("")
        print(f"Baseline file not found: {args.baseline}")
        print("Run again with --write-baseline to capture the current state.")
        return 1

    baseline = _load_baseline(args.baseline)
    success, comparison_messages = _compare_against_baseline(results, baseline)
    _print_results(results, comparison_messages)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())