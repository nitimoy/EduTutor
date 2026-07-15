"""Evaluation engine for computing precision and recall metrics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.evaluation.models import GoldStandard
from backend.semantic.concepts.concept_resolver import normalize_concept_name


@dataclass
class EvaluationMetrics:
    """Metrics computed by the evaluation engine."""
    book_id: str
    chapter: str

    # Concepts
    gold_concepts_count: int = 0
    discovered_concepts_count: int = 0
    concept_true_positives: list[str] = field(default_factory=list)
    concept_false_positives: list[str] = field(default_factory=list)
    concept_false_negatives: list[str] = field(default_factory=list)
    concept_precision: float = 0.0
    concept_recall: float = 0.0
    concept_f1: float = 0.0

    # Relationships
    gold_edges_count: int = 0
    inferred_edges_count: int = 0
    edge_true_positives: list[tuple[str, str, str]] = field(default_factory=list)
    edge_false_positives: list[tuple[str, str, str]] = field(default_factory=list)
    edge_false_negatives: list[tuple[str, str, str]] = field(default_factory=list)
    edge_precision: float = 0.0
    edge_recall: float = 0.0
    edge_f1: float = 0.0
    
    # Hierarchy
    hierarchy_accuracy: float = 0.0
    hierarchy_mismatches: list[dict[str, str]] = field(default_factory=list)

    # Formula Linking
    formula_linking_accuracy: float = 0.0
    formula_linking_details: list[dict[str, Any]] = field(default_factory=list)

    # Figure Linking
    figure_linking_accuracy: float = 0.0
    figure_linking_details: list[dict[str, Any]] = field(default_factory=list)

    # Proof Linking
    proof_linking_accuracy: float = 0.0
    proof_linking_details: list[dict[str, Any]] = field(default_factory=list)

    # Learning Path
    learning_path_accuracy: float = 0.0
    learning_path_coverage: float = 0.0
    learning_path_details: list[dict[str, Any]] = field(default_factory=list)


def _kendall_tau(expected: list[str], actual: list[str]) -> float:
    """Compute Kendall's tau rank correlation between two orderings.

    Only considers items present in both lists.  Returns a value in
    [-1.0, 1.0] where 1.0 means perfect agreement, rescaled to [0.0, 1.0]
    for use as an accuracy score.
    """
    common = [item for item in expected if item in actual]
    if len(common) < 2:
        return 1.0 if common else 0.0

    actual_rank = {item: idx for idx, item in enumerate(actual)}
    ordered = [actual_rank[item] for item in common]

    concordant = 0
    discordant = 0
    n = len(ordered)
    for i in range(n):
        for j in range(i + 1, n):
            if ordered[i] < ordered[j]:
                concordant += 1
            else:
                discordant += 1

    pairs = n * (n - 1) / 2
    tau = (concordant - discordant) / pairs if pairs > 0 else 0.0
    # Rescale from [-1, 1] to [0, 1]
    return (tau + 1.0) / 2.0


class EvaluationEngine:
    """Computes deterministic metrics against a GoldStandard."""

    def evaluate(self, compiled_dir: Path, gold_standard: GoldStandard) -> EvaluationMetrics:
        """Run evaluation by comparing compiled data with the gold standard."""
        metrics = EvaluationMetrics(book_id=gold_standard.book_id, chapter=gold_standard.chapter)

        # 1. Load Compiled Data
        concepts_file = compiled_dir / "concepts.json"
        relationships_file = compiled_dir / "relationships.json"
        ir_file = compiled_dir / "educational_ir.json"
        
        if not concepts_file.exists() or not relationships_file.exists() or not ir_file.exists():
            raise FileNotFoundError(f"Missing compiled data in {compiled_dir}")

        with open(ir_file) as f:
            ir_data = json.load(f)

        # Resolve target chapter title
        target_chapter_title = gold_standard.chapter
        gold_num_match = re.search(r'\d+', gold_standard.chapter)
        if gold_num_match:
            gold_num = gold_num_match.group(0)
            for ch in ir_data.get("book", {}).get("chapters", []):
                if ch.get("number") == gold_num:
                    target_chapter_title = ch.get("title", gold_standard.chapter)
                    break

        with open(concepts_file) as f:
            all_concepts_data = json.load(f)
            # Filter concepts to only those in the target chapter
            chapter_concepts = [c for c in all_concepts_data if c["chapter"] == target_chapter_title]
            
        with open(relationships_file) as f:
            all_relationships_data = json.load(f)

        # Build lookup tables
        concept_map = {c["id"]: c for c in all_concepts_data}
        
        # We need a way to map normalized name -> concept ID for relationship checking
        norm_to_id: dict[str, str] = {}
        norm_to_concept: dict[str, dict[str, Any]] = {}
        for c in chapter_concepts:
            norm = normalize_concept_name(c["name"])
            norm_to_id[norm] = c["id"]
            norm_to_concept[norm] = c

        # 2. Evaluate Concepts
        gold_name_to_concept = {normalize_concept_name(c.name): c for c in gold_standard.concepts}
        discovered_norms = {normalize_concept_name(c["name"]) for c in chapter_concepts}
        
        metrics.gold_concepts_count = len(gold_standard.concepts)
        metrics.discovered_concepts_count = len(discovered_norms)
        
        # A discovered concept is a true positive if it matches a gold name OR any of its gold aliases.
        matched_gold_names: set[str] = set()
        # Also track which gold norm → compiled concept for linking evaluation
        gold_to_compiled: dict[str, dict[str, Any]] = {}
        for disc_norm in discovered_norms:
            matched = False
            for gold_norm, gold_c in gold_name_to_concept.items():
                valid_names = {gold_norm} | {normalize_concept_name(a) for a in gold_c.aliases}
                if disc_norm in valid_names:
                    matched_gold_names.add(gold_norm)
                    metrics.concept_true_positives.append(disc_norm)
                    gold_to_compiled[gold_norm] = norm_to_concept.get(disc_norm, {})
                    matched = True
                    break
            if not matched:
                metrics.concept_false_positives.append(disc_norm)
                
        metrics.concept_false_negatives = sorted(list(set(gold_name_to_concept.keys()) - matched_gold_names))
        
        metrics.concept_precision = self._safe_div(len(metrics.concept_true_positives), len(discovered_norms))
        metrics.concept_recall = self._safe_div(len(matched_gold_names), len(gold_standard.concepts))
        metrics.concept_f1 = self._f1(metrics.concept_precision, metrics.concept_recall)

        # 3. Evaluate Hierarchy
        correct_parents = 0
        total_parents_checked = 0
        for gold_c in gold_standard.concepts:
            if not gold_c.parent_name:
                continue
            
            total_parents_checked += 1
            child_norm = normalize_concept_name(gold_c.name)
            expected_parent_norm = normalize_concept_name(gold_c.parent_name)
            
            child_id = norm_to_id.get(child_norm)
            if not child_id:
                # Child not found, can't check hierarchy
                continue
                
            actual_parent_id = concept_map[child_id].get("parent_id")
            actual_parent_norm = normalize_concept_name(concept_map[actual_parent_id]["name"]) if actual_parent_id and actual_parent_id in concept_map else None
            
            if actual_parent_norm == expected_parent_norm:
                correct_parents += 1
            else:
                metrics.hierarchy_mismatches.append({
                    "concept": child_norm,
                    "expected_parent": expected_parent_norm,
                    "actual_parent": str(actual_parent_norm)
                })
                
        metrics.hierarchy_accuracy = self._safe_div(correct_parents, total_parents_checked)

        # 4. Evaluate Relationships
        # Only evaluate relationships where BOTH source and target are in the chapter concepts
        chapter_rels = []
        for r in all_relationships_data:
            if r["source_id"] in concept_map and r["target_id"] in concept_map:
                s_chap = concept_map[r["source_id"]]["chapter"]
                t_chap = concept_map[r["target_id"]]["chapter"]
                if s_chap == target_chapter_title and t_chap == target_chapter_title:
                    chapter_rels.append(r)
        
        # Build normalized edge tuples: (source_norm, target_norm, type)
        inferred_edges: set[tuple[str, str, str]] = set()
        for r in chapter_rels:
            s_norm = normalize_concept_name(concept_map[r["source_id"]]["name"])
            t_norm = normalize_concept_name(concept_map[r["target_id"]]["name"])
            inferred_edges.add((s_norm, t_norm, r["relationship_type"]))
            
        gold_edges: set[tuple[str, str, str]] = set()
        for r in gold_standard.relationships:
            s_gold_norm = normalize_concept_name(r.source)
            t_gold_norm = normalize_concept_name(r.target)
            
            s_compiled = gold_to_compiled.get(s_gold_norm)
            t_compiled = gold_to_compiled.get(t_gold_norm)
            
            s_norm = normalize_concept_name(s_compiled["name"]) if s_compiled else s_gold_norm
            t_norm = normalize_concept_name(t_compiled["name"]) if t_compiled else t_gold_norm
            
            gold_edges.add((s_norm, t_norm, r.relationship_type))
            
        metrics.gold_edges_count = len(gold_edges)
        metrics.inferred_edges_count = len(inferred_edges)
        
        metrics.edge_true_positives = sorted(list(gold_edges & inferred_edges))
        metrics.edge_false_positives = sorted(list(inferred_edges - gold_edges))
        metrics.edge_false_negatives = sorted(list(gold_edges - inferred_edges))
        
        metrics.edge_precision = self._safe_div(len(metrics.edge_true_positives), len(inferred_edges))
        metrics.edge_recall = self._safe_div(len(metrics.edge_true_positives), len(gold_edges))
        metrics.edge_f1 = self._f1(metrics.edge_precision, metrics.edge_recall)

        # 5. Evaluate Formula Linking
        self._evaluate_formula_linking(metrics, gold_standard, gold_to_compiled, compiled_dir)

        # 6. Evaluate Figure Linking
        self._evaluate_figure_linking(metrics, gold_standard, gold_to_compiled, compiled_dir)

        # 7. Evaluate Proof Linking
        self._evaluate_proof_linking(metrics, gold_standard, gold_to_compiled, compiled_dir)

        # 8. Evaluate Learning Path
        self._evaluate_learning_path(metrics, gold_standard, compiled_dir, gold_to_compiled)

        return metrics

    def _evaluate_formula_linking(
        self,
        metrics: EvaluationMetrics,
        gold: GoldStandard,
        gold_to_compiled: dict[str, dict[str, Any]],
        compiled_dir: Path,
    ) -> None:
        """Check that gold-annotated formulas are linked to the correct concepts."""
        formulas_file = compiled_dir / "formulas.json"
        if not formulas_file.exists():
            return

        with open(formulas_file) as f:
            all_formulas = json.load(f)
        formula_map = {fm["id"]: fm for fm in all_formulas}

        total_expected = 0
        total_matched = 0

        for gold_c in gold.concepts:
            if not gold_c.required_formulas:
                continue

            gold_norm = normalize_concept_name(gold_c.name)
            compiled = gold_to_compiled.get(gold_norm, {})
            formula_ids = compiled.get("formula_ids", [])

            # Collect all formula text from linked formulas
            linked_texts: list[str] = []
            for fid in formula_ids:
                fm = formula_map.get(fid, {})
                text = f"{fm.get('latex', '')} {fm.get('text', '')}".lower()
                linked_texts.append(text)

            for expected_keyword in gold_c.required_formulas:
                total_expected += 1
                keyword_lower = expected_keyword.lower()
                found = any(keyword_lower in text for text in linked_texts)
                if found:
                    total_matched += 1
                else:
                    metrics.formula_linking_details.append({
                        "concept": gold_c.name,
                        "expected_keyword": expected_keyword,
                        "status": "missing",
                        "linked_formula_count": len(formula_ids),
                    })

        metrics.formula_linking_accuracy = self._safe_div(total_matched, total_expected)

    def _evaluate_figure_linking(
        self,
        metrics: EvaluationMetrics,
        gold: GoldStandard,
        gold_to_compiled: dict[str, dict[str, Any]],
        compiled_dir: Path,
    ) -> None:
        """Check that gold-annotated figures are linked to the correct concepts."""
        # Figure IDs in concepts reference IR objects of type 'figure'/'diagram'.
        # Load the IR to get figure object text/title.
        ir_file = compiled_dir / "educational_ir.json"
        if not ir_file.exists():
            return

        with open(ir_file) as f:
            ir_data = json.load(f)
        obj_map = {o["id"]: o for o in ir_data.get("book", {}).get("objects", [])}

        total_expected = 0
        total_matched = 0

        for gold_c in gold.concepts:
            if not gold_c.required_figures:
                continue

            gold_norm = normalize_concept_name(gold_c.name)
            compiled = gold_to_compiled.get(gold_norm, {})
            figure_ids = compiled.get("figure_ids", [])

            # Collect figure descriptions from linked IR objects
            linked_texts: list[str] = []
            for fid in figure_ids:
                obj = obj_map.get(fid, {})
                text = f"{obj.get('title', '')} {obj.get('text', '')}".lower()
                linked_texts.append(text)

            for expected_keyword in gold_c.required_figures:
                total_expected += 1
                keyword_lower = expected_keyword.lower()
                found = any(keyword_lower in text for text in linked_texts)
                if found:
                    total_matched += 1
                else:
                    metrics.figure_linking_details.append({
                        "concept": gold_c.name,
                        "expected_keyword": expected_keyword,
                        "status": "missing",
                        "linked_figure_count": len(figure_ids),
                    })

        metrics.figure_linking_accuracy = self._safe_div(total_matched, total_expected)

    def _evaluate_proof_linking(
        self,
        metrics: EvaluationMetrics,
        gold: GoldStandard,
        gold_to_compiled: dict[str, dict[str, Any]],
        compiled_dir: Path,
    ) -> None:
        """Check that gold-annotated proofs are linked to the correct concepts."""
        ir_file = compiled_dir / "educational_ir.json"
        if not ir_file.exists():
            return

        with open(ir_file) as f:
            ir_data = json.load(f)
        obj_map = {o["id"]: o for o in ir_data.get("book", {}).get("objects", [])}

        total_expected = 0
        total_matched = 0

        for gold_c in gold.concepts:
            if not gold_c.required_proofs:
                continue

            gold_norm = normalize_concept_name(gold_c.name)
            compiled = gold_to_compiled.get(gold_norm, {})
            proof_ids = compiled.get("proof_ids", [])

            # Collect proof text from linked IR objects
            linked_texts: list[str] = []
            for pid in proof_ids:
                obj = obj_map.get(pid, {})
                text = f"{obj.get('title', '')} {obj.get('text', '')}".lower()
                linked_texts.append(text)

            for expected_keyword in gold_c.required_proofs:
                total_expected += 1
                keyword_lower = expected_keyword.lower()
                found = any(keyword_lower in text for text in linked_texts)
                if found:
                    total_matched += 1
                else:
                    metrics.proof_linking_details.append({
                        "concept": gold_c.name,
                        "expected_keyword": expected_keyword,
                        "status": "missing",
                        "linked_proof_count": len(proof_ids),
                    })

        metrics.proof_linking_accuracy = self._safe_div(total_matched, total_expected)

    def _evaluate_learning_path(
        self,
        metrics: EvaluationMetrics,
        gold: GoldStandard,
        compiled_dir: Path,
        gold_to_compiled: dict[str, dict[str, Any]],
    ) -> None:
        """Compare gold learning path against actual concept ordering."""
        if not gold.learning_path:
            return

        reasoning_file = compiled_dir / "reasoning.json"
        concepts_file = compiled_dir / "concepts.json"

        # Build actual concept order from compiled data.
        # Use concept metadata page_start + reading_order_start for ordering.
        with open(concepts_file) as f:
            all_concepts = json.load(f)
            
        target_chapter_title = gold.chapter
        gold_num_match = re.search(r'\d+', gold.chapter)
        if gold_num_match:
            gold_num = gold_num_match.group(0)
            ir_file = compiled_dir / "educational_ir.json"
            if ir_file.exists():
                with open(ir_file) as f:
                    ir_data = json.load(f)
                    for ch in ir_data.get("book", {}).get("chapters", []):
                        if ch.get("number") == gold_num:
                            target_chapter_title = ch.get("title", gold.chapter)
                            break
                            
        chapter_concepts = [c for c in all_concepts if c["chapter"] == target_chapter_title]
        # Sort by page_start then reading_order_start
        chapter_concepts.sort(
            key=lambda c: (
                c.get("metadata", {}).get("page_start", 0),
                c.get("metadata", {}).get("reading_order_start", 0),
            )
        )

        # Actual order
        actual_norms = [normalize_concept_name(c["name"]) for c in chapter_concepts]
        actual_rank = {name: idx for idx, name in enumerate(actual_norms)}

        # Resolve gold names to their matched actual norms (using gold_to_compiled)
        resolved_gold_norms = []
        for name in gold.learning_path:
            gold_norm = normalize_concept_name(name)
            compiled_c = gold_to_compiled.get(gold_norm)
            if compiled_c:
                resolved_gold_norms.append(normalize_concept_name(compiled_c["name"]))
            else:
                resolved_gold_norms.append(gold_norm)  # Keep the original if it didn't match anything

        # Coverage: what fraction of gold path concepts appear in actual
        gold_set = set(resolved_gold_norms)
        actual_set = set(actual_norms)
        covered = gold_set & actual_set
        metrics.learning_path_coverage = self._safe_div(len(covered), len(gold_set))

        # Ordering: Kendall's tau on common elements
        metrics.learning_path_accuracy = _kendall_tau(resolved_gold_norms, actual_norms)

        # Details: show expected vs actual ordering for common elements
        for idx, (original_name, resolved_norm) in enumerate(zip(gold.learning_path, resolved_gold_norms)):
            actual_idx = actual_rank.get(resolved_norm)
            if actual_idx is None:
                metrics.learning_path_details.append({
                    "concept": original_name,
                    "expected_position": idx,
                    "actual_position": None,
                    "status": "missing",
                })
            elif actual_idx != idx:
                metrics.learning_path_details.append({
                    "concept": original_name,
                    "expected_position": idx,
                    "actual_position": actual_idx,
                    "status": "misordered",
                })

    def _safe_div(self, num: int, den: int) -> float:
        return float(num) / den if den > 0 else 0.0
        
    def _f1(self, precision: float, recall: float) -> float:
        return 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
