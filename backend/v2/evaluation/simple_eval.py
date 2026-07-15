"""Simple evaluation for EduTutor v2 without ragas dependency."""

import sys
sys.path.insert(0, "/teamspace/studios/this_studio/sujho-assignment")

import os
from backend.v2.rag.engine import RAGEngine


def evaluate_retrieval(engine: RAGEngine, test_cases: list[dict]) -> dict:
    """Evaluate retrieval quality."""
    results = {"correct": 0, "total": len(test_cases)}

    for tc in test_cases:
        response = engine.query(tc["question"])
        sources = [s.get("concept_name", "").lower() for s in response["sources"]]

        # Check if expected concept is in sources
        expected = tc.get("expected_concept", "").lower()
        if expected and any(expected in s for s in sources):
            results["correct"] += 1

    results["accuracy"] = results["correct"] / results["total"]
    return results


def evaluate_answer_quality(engine: RAGEngine, test_cases: list[dict]) -> dict:
    """Evaluate answer quality based on length and keywords."""
    results = {"good_answers": 0, "total": len(test_cases)}

    for tc in test_cases:
        response = engine.query(tc["question"])
        answer = response["answer"]

        # Check if answer is substantive (>50 words)
        word_count = len(answer.split())
        has_keywords = any(kw.lower() in answer.lower() for kw in tc.get("keywords", []))

        if word_count > 50 and has_keywords:
            results["good_answers"] += 1

    results["quality_score"] = results["good_answers"] / results["total"]
    return results


def main():
    print("=== Simple Evaluation for EduTutor v2 ===\n")

    # Initialize engine
    print("1. Initializing RAGEngine...")
    engine = RAGEngine(
        compiled_dir="data/compiled",
        qdrant_path="data/v2/qdrant_full",
        llm_model="openai/gpt-4o-mini",
    )

    # Build index
    print("2. Building index...")
    engine.build_index()

    # Test cases
    test_cases = [
        {
            "question": "What is a matrix?",
            "expected_concept": "matrix",
            "keywords": ["rectangular", "array", "rows", "columns"],
        },
        {
            "question": "What is a symmetric matrix?",
            "expected_concept": "symmetric",
            "keywords": ["transpose", "equal", "a_ij", "a_ji"],
        },
        {
            "question": "What is a row matrix?",
            "expected_concept": "row",
            "keywords": ["single", "row"],
        },
    ]

    # Evaluate
    print("\n3. Evaluating retrieval...")
    retrieval_results = evaluate_retrieval(engine, test_cases)
    print(f"   Retrieval Accuracy: {retrieval_results['accuracy']:.2%}")

    print("\n4. Evaluating answer quality...")
    quality_results = evaluate_answer_quality(engine, test_cases)
    print(f"   Answer Quality: {quality_results['quality_score']:.2%}")

    # Summary
    print("\n=== Summary ===")
    print(f"Retrieval Accuracy: {retrieval_results['accuracy']:.2%}")
    print(f"Answer Quality:     {quality_results['quality_score']:.2%}")
    print(f"Overall:            {(retrieval_results['accuracy'] + quality_results['quality_score']) / 2:.2%}")


if __name__ == "__main__":
    main()
