"""Comprehensive evaluation for EduTutor v2."""

import sys
sys.path.insert(0, "/teamspace/studios/this_studio/sujho-assignment")

import os
from backend.v2.rag.engine import RAGEngine


def main():
    print("=== Comprehensive Evaluation for EduTutor v2 ===\n")

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

    # Test cases covering different query types
    test_cases = [
        # Definition queries
        {"question": "What is a matrix?", "type": "definition"},
        {"question": "What is a symmetric matrix?", "type": "definition"},
        {"question": "What is a row matrix?", "type": "definition"},
        
        # Comparison queries
        {"question": "Difference between row matrix and column matrix", "type": "comparison"},
        {"question": "Compare symmetric and skew symmetric matrices", "type": "comparison"},
        
        # Procedure queries
        {"question": "How do I multiply two matrices?", "type": "procedure"},
        
        # Follow-up queries
        {"question": "Give me an example", "type": "follow-up"},
        
        # Broad queries
        {"question": "Tell me about matrix manipulation", "type": "broad"},
    ]

    # Run evaluation
    print("\n3. Running queries...")
    results = {"definition": [], "comparison": [], "procedure": [], "follow-up": [], "broad": []}

    for tc in test_cases:
        print(f"\n   [{tc['type'].upper()}] {tc['question']}")
        response = engine.query(tc["question"])
        
        # Check quality
        answer = response["answer"]
        word_count = len(answer.split())
        has_content = word_count > 20
        has_sources = len(response["sources"]) > 0
        
        quality = "GOOD" if has_content and has_sources else "NEEDS_WORK"
        results[tc["type"]].append({
            "question": tc["question"],
            "answer_length": word_count,
            "sources_count": len(response["sources"]),
            "quality": quality,
        })
        
        print(f"   Answer: {answer[:100]}...")
        print(f"   Quality: {quality} ({word_count} words, {len(response['sources'])} sources)")

    # Summary
    print("\n=== Summary ===")
    for qtype, items in results.items():
        good = sum(1 for i in items if i["quality"] == "GOOD")
        total = len(items)
        if total > 0:
            print(f"{qtype}: {good}/{total} ({good/total:.0%})")

    # Overall
    all_items = [i for items in results.values() for i in items]
    good_total = sum(1 for i in all_items if i["quality"] == "GOOD")
    print(f"\nOverall: {good_total}/{len(all_items)} ({good_total/len(all_items):.0%})")


if __name__ == "__main__":
    main()
