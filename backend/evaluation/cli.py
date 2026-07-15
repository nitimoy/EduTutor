"""CLI runner for the evaluation framework."""

import argparse
import sys
import json
from pathlib import Path

import yaml

from backend.evaluation.models import GoldStandard
from backend.evaluation.engine import EvaluationEngine
from backend.evaluation.reporter import EvaluationReporter
from backend.evaluation.validator import validate_gold_standard

from backend.evaluation.retrieval_models import RetrievalQueryDataset
from backend.evaluation.retrieval_engine import RetrievalEvaluationEngine
from backend.retrieval.api.search import RetrievalAPI


def run_compiler_evaluation(args):
    """Run the compiler evaluation."""
    if not args.gold.exists():
        print(f"Error: Gold standard file not found: {args.gold}")
        sys.exit(1)

    # Always validate the gold standard first
    validation = validate_gold_standard(args.gold)
    if validation.issues:
        for issue in validation.issues:
            prefix = "ERROR" if issue.severity == "error" else "WARNING"
            print(f"[{prefix}] {issue.message}")

    if args.validate_only:
        if validation.valid:
            print(f"\nGold standard is valid: {args.gold}")
            sys.exit(0)
        else:
            print(f"\nGold standard has errors: {args.gold}")
            sys.exit(1)

    if not validation.valid:
        print(f"\nGold standard validation failed. Fix errors before running evaluation.")
        sys.exit(1)

    if not args.compiled:
        print("Error: --compiled is required when not using --validate-only")
        sys.exit(1)

    if not args.compiled.exists():
        print(f"Error: Compiled directory not found: {args.compiled}")
        sys.exit(1)
        
    # Load gold standard
    with open(args.gold) as f:
        data = yaml.safe_load(f)
        gold_standard = GoldStandard.model_validate(data)
            
    # Run evaluation
    engine = EvaluationEngine()
    metrics = engine.evaluate(args.compiled, gold_standard)
        
    # Generate report
    reporter = EvaluationReporter()
    report = reporter.generate_markdown(metrics)
    
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Report saved to {args.output}")
    else:
        print(report)


def run_retrieval_evaluation(args):
    """Run the retrieval evaluation."""
    if not args.dataset.exists():
        print(f"Error: Dataset file not found: {args.dataset}")
        sys.exit(1)

    if not args.compiled.exists():
        print(f"Error: Compiled directory not found: {args.compiled}")
        sys.exit(1)

    index_path = args.compiled / "knowledge_index.json"
    if not index_path.exists():
        print(f"Error: Knowledge index not found: {index_path}. Build it first.")
        sys.exit(1)

    with open(args.dataset) as f:
        data = yaml.safe_load(f)
        dataset = RetrievalQueryDataset.model_validate(data)

    api = RetrievalAPI(index_path)
    engine = RetrievalEvaluationEngine(api)
    
    report = engine.evaluate(dataset)

    output = json.dumps(report.model_dump(), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)


def main():
    parser = argparse.ArgumentParser(description="Evaluation Framework CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # evaluate-compiler command
    compiler_parser = subparsers.add_parser("evaluate-compiler", help="Evaluate compiler against gold standard")
    compiler_parser.add_argument("--gold", type=Path, required=True, help="Path to the YAML gold standard file.")
    compiler_parser.add_argument("--compiled", type=Path, help="Path to compiled output directory.")
    compiler_parser.add_argument("--output", type=Path, help="Path to save the markdown report.")
    compiler_parser.add_argument("--validate-only", action="store_true", help="Validate gold YAML only.")

    # evaluate-retrieval command
    retrieval_parser = subparsers.add_parser("evaluate-retrieval", help="Evaluate retrieval API against query dataset")
    retrieval_parser.add_argument("--dataset", type=Path, required=True, help="Path to the YAML query dataset.")
    retrieval_parser.add_argument("--compiled", type=Path, required=True, help="Path to compiled output directory.")
    retrieval_parser.add_argument("--output", type=Path, help="Path to save the JSON report.")

    args = parser.parse_args()

    if args.command == "evaluate-compiler":
        run_compiler_evaluation(args)
    elif args.command == "evaluate-retrieval":
        run_retrieval_evaluation(args)

if __name__ == "__main__":
    main()
