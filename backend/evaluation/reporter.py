"""Reporter for formatting evaluation metrics into human-readable output."""

from __future__ import annotations

from backend.evaluation.engine import EvaluationMetrics

class EvaluationReporter:
    """Formats metrics into a markdown report."""

    def generate_markdown(self, metrics: EvaluationMetrics) -> str:
        """Generate a markdown report from the metrics."""
        
        lines = [
            f"# Evaluation Report: {metrics.book_id} / {metrics.chapter}",
            "",
            "## Summary",
            "",
            f"- **Gold Concepts**: {metrics.gold_concepts_count}",
            f"- **Discovered Concepts**: {metrics.discovered_concepts_count}",
            f"- **Gold Relationships**: {metrics.gold_edges_count}",
            f"- **Inferred Relationships**: {metrics.inferred_edges_count}",
            "",
            "### Core Metrics",
            "| Metric | Precision | Recall | F1 Score |",
            "|--------|-----------|--------|----------|",
            f"| Concepts | {metrics.concept_precision:.2f} | {metrics.concept_recall:.2f} | {metrics.concept_f1:.2f} |",
            f"| Relationships | {metrics.edge_precision:.2f} | {metrics.edge_recall:.2f} | {metrics.edge_f1:.2f} |",
            "",
            f"**Hierarchy Accuracy**: {metrics.hierarchy_accuracy:.2%}",
            "",
            "### Linking Metrics",
            "| Metric | Accuracy |",
            "|--------|----------|",
            f"| Formula Linking | {metrics.formula_linking_accuracy:.2%} |",
            f"| Figure Linking | {metrics.figure_linking_accuracy:.2%} |",
            f"| Proof Linking | {metrics.proof_linking_accuracy:.2%} |",
            f"| Learning Path | {metrics.learning_path_accuracy:.2%} (coverage: {metrics.learning_path_coverage:.2%}) |",
            "",
            "## Concepts Analysis",
            "",
            "### ❌ False Negatives (Missed Concepts)",
            "Concepts in the Gold Standard that the compiler failed to extract:"
        ]
        
        if metrics.concept_false_negatives:
            for c in metrics.concept_false_negatives:
                lines.append(f"- {c}")
        else:
            lines.append("- *None! Perfect recall.*")
            
        lines.append("")
        lines.append("### ⚠️ False Positives (Noise)")
        lines.append("Extracted concepts that are not in the Gold Standard:")
        
        if metrics.concept_false_positives:
            for c in metrics.concept_false_positives:
                lines.append(f"- {c}")
        else:
            lines.append("- *None! Perfect precision.*")
            
        lines.append("")
        lines.append("## Hierarchy Analysis")
        
        if metrics.hierarchy_mismatches:
            lines.append("The following concepts were assigned to the wrong parent:")
            for m in metrics.hierarchy_mismatches:
                lines.append(f"- **{m['concept']}**: expected `{m['expected_parent']}`, got `{m['actual_parent']}`")
        else:
            lines.append("All discovered concepts were placed in the correct hierarchy.")
            
        lines.append("")
        lines.append("## Relationships Analysis")
        
        lines.append("### ❌ False Negatives (Missed Edges)")
        if metrics.edge_false_negatives:
            for s, t, rtype in metrics.edge_false_negatives:
                lines.append(f"- `{s}` -> `{rtype}` -> `{t}`")
        else:
            lines.append("- *None! Perfect recall.*")
            
        lines.append("")
        lines.append("### ⚠️ False Positives (Incorrect Edges)")
        if metrics.edge_false_positives:
            # Show up to 20 to avoid spamming the report
            for s, t, rtype in metrics.edge_false_positives[:20]:
                lines.append(f"- `{s}` -> `{rtype}` -> `{t}`")
            if len(metrics.edge_false_positives) > 20:
                lines.append(f"- *(...and {len(metrics.edge_false_positives) - 20} more)*")
        else:
            lines.append("- *None! Perfect precision.*")

        # Formula Linking Analysis
        lines.append("")
        lines.append("## Formula Linking Analysis")
        if metrics.formula_linking_details:
            lines.append("The following expected formulas were not found linked to their concepts:")
            lines.append("")
            lines.append("| Concept | Expected Keyword | Linked Formulas |")
            lines.append("|---------|-----------------|-----------------|")
            for detail in metrics.formula_linking_details:
                lines.append(f"| {detail['concept']} | `{detail['expected_keyword']}` | {detail['linked_formula_count']} |")
        elif metrics.formula_linking_accuracy > 0:
            lines.append("All expected formulas were correctly linked to their concepts.")
        else:
            lines.append("No formula linking annotations in gold standard.")

        # Figure Linking Analysis
        lines.append("")
        lines.append("## Figure Linking Analysis")
        if metrics.figure_linking_details:
            lines.append("The following expected figures were not found linked to their concepts:")
            lines.append("")
            lines.append("| Concept | Expected Keyword | Linked Figures |")
            lines.append("|---------|-----------------|----------------|")
            for detail in metrics.figure_linking_details:
                lines.append(f"| {detail['concept']} | `{detail['expected_keyword']}` | {detail['linked_figure_count']} |")
        elif metrics.figure_linking_accuracy > 0:
            lines.append("All expected figures were correctly linked to their concepts.")
        else:
            lines.append("No figure linking annotations in gold standard.")

        # Proof Linking Analysis
        lines.append("")
        lines.append("## Proof Linking Analysis")
        if metrics.proof_linking_details:
            lines.append("The following expected proofs were not found linked to their concepts:")
            lines.append("")
            lines.append("| Concept | Expected Keyword | Linked Proofs |")
            lines.append("|---------|-----------------|---------------|")
            for detail in metrics.proof_linking_details:
                lines.append(f"| {detail['concept']} | `{detail['expected_keyword']}` | {detail['linked_proof_count']} |")
        elif metrics.proof_linking_accuracy > 0:
            lines.append("All expected proofs were correctly linked to their concepts.")
        else:
            lines.append("No proof linking annotations in gold standard.")

        # Learning Path Analysis
        lines.append("")
        lines.append("## Learning Path Analysis")
        if metrics.learning_path_details:
            lines.append(f"**Order Accuracy**: {metrics.learning_path_accuracy:.2%} | **Coverage**: {metrics.learning_path_coverage:.2%}")
            lines.append("")
            lines.append("Issues detected:")
            lines.append("")
            lines.append("| Concept | Expected Pos | Actual Pos | Status |")
            lines.append("|---------|-------------|------------|--------|")
            for detail in metrics.learning_path_details:
                actual = detail['actual_position'] if detail['actual_position'] is not None else "—"
                lines.append(f"| {detail['concept']} | {detail['expected_position']} | {actual} | {detail['status']} |")
        elif metrics.learning_path_accuracy > 0:
            lines.append("Learning path matches expected ordering.")
        else:
            lines.append("No learning path annotations in gold standard.")
            
        return "\n".join(lines)
