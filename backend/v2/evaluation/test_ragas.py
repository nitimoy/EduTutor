"""Ragas evaluation for EduTutor v2."""

import sys
sys.path.insert(0, "/teamspace/studios/this_studio/sujho-assignment")

import os
from backend.v2.rag.engine import RAGEngine
from backend.v2.evaluation.ragas_eval import RAGASEvaluator


def main():
    print("=== Ragas Evaluation for EduTutor v2 ===\n")

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

    # Test questions with ground truths
    test_cases = [
        {
            "question": "What is a matrix?",
            "ground_truth": "A matrix is a rectangular array of numbers arranged in rows and columns.",
        },
        {
            "question": "What is the difference between row matrix and column matrix?",
            "ground_truth": "A row matrix has only one row, while a column matrix has only one column.",
        },
        {
            "question": "What is a symmetric matrix?",
            "ground_truth": "A symmetric matrix is equal to its transpose, meaning a_ij = a_ji.",
        },
    ]

    # Run queries
    print("\n3. Running queries...")
    questions = []
    answers = []
    contexts = []
    ground_truths = []

    for tc in test_cases:
        print(f"   Query: {tc['question']}")
        response = engine.query(tc["question"])

        questions.append(tc["question"])
        answers.append(response["answer"])
        contexts.append([s.get("text", "") for s in response["sources"]])
        ground_truths.append(tc["ground_truth"])

        print(f"   Answer: {response['answer'][:100]}...")
        print()

    # Evaluate with Ragas
    print("4. Evaluating with Ragas...")
    evaluator = RAGASEvaluator()
    result = evaluator.evaluate(questions, answers, contexts, ground_truths)

    print("\n=== Evaluation Results ===")
    print(f"Faithfulness:      {result.faithfulness:.3f}")
    print(f"Answer Relevancy:  {result.answer_relevancy:.3f}")
    print(f"Context Precision: {result.context_precision:.3f}")
    print(f"Context Recall:    {result.context_recall:.3f}")
    print(f"Overall Score:     {result.overall_score:.3f}")


if __name__ == "__main__":
    main()
