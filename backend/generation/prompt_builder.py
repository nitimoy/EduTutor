"""Build a provider-neutral PromptDocument from a RenderUnit.

The document is the deterministic, provider-agnostic request artifact. Its ``system``
text is a fixed teaching-style directive plus the hard **renderer contract** (rephrase
only, add nothing, preserve citations) — pure formatting/rules, no facts. Its ``blocks``
carry only the unit's own ``TutorPlan``-derived content.

Phase 8 additions
-----------------
* Section-specific LLM contract extensions per QuestionType:
  - COMPARISON  → "Present as a structured comparison table."
  - CONCEPTUAL_REASONING → "Do NOT use a worked example as a proxy for WHY."
  - GROUNDED_FACTS → "State the disclaimer verbatim, then list only grounded facts."
  - LEARNING_PATH / NEXT_TOPICS → "Present as ordered study sequence."
* The base contract is unchanged: rephrase only, add nothing, preserve citations.
"""

from __future__ import annotations

from backend.generation.models import (
    GenerationConfig,
    LanguageGenerationPlan,
    PromptBlock,
    PromptDocument,
    RenderUnit,
)
from backend.tutor.models import Citation, QuestionType, SectionKind

# ---------------------------------------------------------------------------
# Base contract — unchanged from previous version.
# ---------------------------------------------------------------------------
_BASE_CONTRACT = (
    "You are a teaching renderer. Rephrase ONLY the provided content into clear, "
    "natural prose for a student. Do NOT add facts, examples, numbers, formulas, "
    "or concepts that are not present in the content. Do NOT reorder or merge "
    "unrelated points. Preserve every citation marker exactly as given. "
    "Do NOT generate fake references, links, or citations like '[Resource Name]' or "
    "'[See Chapter X]'. Do NOT add sentences like 'refer to...', 'see...', or "
    "'for more information...'. The system handles citations separately. "
    "Output ONLY the rendered section text — nothing else."
)

# ---------------------------------------------------------------------------
# Section + QuestionType specific contract extensions.
# These are APPENDED to the base contract, never replace it.
# ---------------------------------------------------------------------------

_COMPARISON_CONTRACT = (
    "IMPORTANT: This is a COMPARISON section. "
    "If the Content block contains definitions for BOTH concepts, present them as a "
    "structured comparison table:\n"
    "| Aspect | [Concept A] | [Concept B] |\n"
    "|--------|-------------|-------------|\n"
    "| Definition | ... | ... |\n"
    "| Properties | ... | ... |\n"
    "| Key Difference | ... | ... |\n\n"
    "If only ONE concept is available in the Content, state clearly: "
    "'A full comparison requires both concepts to be present in the knowledge base. "
    "Only [concept name] is currently available. The other concept has not been compiled yet.' "
    "Then briefly explain the one available concept. "
    "Do NOT invent or assume information about the missing concept. "
    "Do NOT use outside knowledge."
)

_CONCEPTUAL_CONTRACT = (
    "IMPORTANT: The student is asking WHY or HOW something works. "
    "Explain the underlying principle or reason. "
    "Do NOT use a worked numerical example as a substitute for the explanation. "
    "If the provided content does not contain an explicit causal explanation, "
    "say so clearly before listing the grounded facts."
)

_GROUNDED_FACTS_CONTRACT = (
    "IMPORTANT: This section contains a disclaimer. "
    "Begin your response with the disclaimer note VERBATIM, word for word. "
    "Then list ONLY the grounded facts that appear in the Content block. "
    "Do NOT infer, deduce, or complete any missing explanation. "
    "Do NOT hallucinate mathematical claims. "
    "If you cannot explain WHY from the content, say so explicitly."
)

_LEARNING_PATH_CONTRACT = (
    "IMPORTANT: The student is asking what to study BEFORE a topic. "
    "The Content block contains PREREQUISITES and RELATED CONCEPTS from the knowledge graph. "
    "Present the study path as an ordered numbered list:\n"
    "1. Start with the prerequisites (concepts that MUST be learned first)\n"
    "2. Then related concepts (helpful but not strictly required)\n"
    "3. Finally, the topic they asked about\n\n"
    "Use the prerequisite relationships from the Content block — these come from "
    "the NCERT chapter structure. Do NOT invent prerequisites. "
    "Do NOT suggest concepts that are not in the Content block. "
    "If no prerequisites are listed, say 'This topic has no listed prerequisites "
    "in the current source material.' and suggest related concepts instead."
)

_NEXT_TOPICS_CONTRACT = (
    "Present these as an ordered study sequence (numbered list): what to learn next, "
    "in the order of the chapter hierarchy. "
    "Do NOT suggest unrelated concepts or guess at the next topic."
)

_REVISION_CONTRACT = (
    "This is a REVISION / EXAM PREPARATION section. "
    "The Content block contains key information from the chapter. "
    "Present a comprehensive revision covering:\n"
    "1. Key definitions (concise, one line each)\n"
    "2. Important formulae (with brief context)\n"
    "3. Common mistakes to avoid\n"
    "4. Tips for the exam\n\n"
    "Use bullet points. Be concise but thorough. "
    "Cover ALL concepts mentioned in the Content block, not just one."
)

_WORKED_EXAMPLE_CONTRACT = (
    "IMPORTANT: The Content block contains EXAMPLES from the NCERT textbook. "
    "Use ONLY the examples provided in the Content block. Do NOT invent new examples. "
    "Do NOT create your own numbers, symbols, or problems. "
    "Pick the SINGLE most relevant example and solve it step by step. "
    "Show your working clearly: state the given information, the formula used, "
    "the step-by-step calculation, and the final answer. "
    "If the Content block has no matching example, say 'No worked example is available "
    "for this problem in the current source material.' and stop."
)


def _contract_for(unit: RenderUnit, plan: LanguageGenerationPlan) -> str:
    """Return the full contract text for ``unit`` based on its kind and plan intent."""
    lines = [_BASE_CONTRACT]

    qt_str = plan.strategy.value if plan.strategy else ""
    section = unit.kind

    # GROUNDED_FACTS disclaimer — must come first, highest priority.
    if section == SectionKind.GROUNDED_FACTS:
        lines.append(_GROUNDED_FACTS_CONTRACT)
        return "\n\n".join(lines)

    # WORKED_EXAMPLE: solve ONE problem, don't dump all examples.
    if section == SectionKind.WORKED_EXAMPLE:
        lines.append(_WORKED_EXAMPLE_CONTRACT)

    # COMPARISON section: always use table format.
    elif section == SectionKind.COMPARISON:
        lines.append(_COMPARISON_CONTRACT)

    # NEXT_TOPICS: ordered study sequence.
    elif section == SectionKind.NEXT_TOPICS:
        lines.append(_NEXT_TOPICS_CONTRACT)

    # SUMMARY in REVISION context.
    elif section == SectionKind.SUMMARY and "revision" in qt_str:
        lines.append(_REVISION_CONTRACT)

    # MAIN_EXPLANATION — prevent textbook dumping and focus on teaching.
    elif section == SectionKind.MAIN_EXPLANATION:
        if plan.intent and plan.intent.value in ("explanation", "definition"):
            if unit.note and "conceptual" in unit.note.lower():
                lines.append(_CONCEPTUAL_CONTRACT)
        
        # Determine what to include based on the query intent.
        query_lower = plan.query.lower() if plan.query else ""
        
        # Definition-only queries: just the definition, nothing else.
        if any(w in query_lower for w in ["what is", "define", "definition of", "meaning of"]):
            lines.append(
                "DEFINITION-ONLY RESPONSE: The student asked for a definition. "
                "Provide ONLY a clear, concise definition of the concept. "
                "Do NOT include examples, notation, properties, or worked problems. "
                "Keep it to 2-3 sentences maximum. "
                "If the Content block has a definition, use it. If not, state that "
                "no definition is available in the current source material."
            )
        else:
            # Full explanation: definition first, then notation, then brief example.
            lines.append(
                "STRUCTURE YOUR RESPONSE IN THIS ORDER:\n"
                "1. DEFINITION: Start with a clear, concise definition of the concept.\n"
                "2. NOTATION & ORDER: Explain how it is written and its structure (rows, columns, etc.).\n"
                "3. KEY PROPERTIES: List 2-3 essential properties.\n"
                "4. ONE EXAMPLE: Use ONE brief example from the Content to illustrate.\n\n"
                "Do NOT start with examples. Do NOT read out raw textbook content. "
                "Do NOT invent new examples. Use ONLY the definition texts from the Content block."
            )

    # LEARNING_PATH: ordered sequence.
    if section in (SectionKind.PREREQUISITES, SectionKind.NEXT_TOPICS):
        if plan.strategy and plan.strategy.value == "prerequisite_pathway":
            lines.append(_LEARNING_PATH_CONTRACT)

    return "\n\n".join(lines)


class PromptBuilder:
    """Deterministically turn a render unit into a provider-neutral prompt document."""

    def build(
        self,
        unit: RenderUnit,
        plan: LanguageGenerationPlan,
        config: GenerationConfig,
    ) -> PromptDocument:
        system = self._system_text(unit, plan)
        content_block = PromptBlock(label="Content", lines=unit.content_lines)
        citation_block = PromptBlock(
            label="Citations", lines=tuple(_format_citation(c) for c in unit.citations))
        return PromptDocument(
            unit_id=unit.unit_id,
            unit_kind=unit.kind,
            system=system,
            blocks=(content_block, citation_block),
            citations=unit.citations,
            metadata={
                "section": unit.kind.value,
                "intent": plan.intent.value,
                "strategy": plan.strategy.value,
                "preset": plan.preset,
                "model_id": config.model_id,
            },
        )

    def _system_text(self, unit: RenderUnit, plan: LanguageGenerationPlan) -> str:
        contract = _contract_for(unit, plan)
        style = unit.style
        lines = [
            contract,
            f"Section: {unit.kind.value}.",
            f"Tone: {style.tone}.",
            f"Format: {style.format}.",
        ]
        if style.max_sentences is not None:
            lines.append(f"Use at most {style.max_sentences} sentences.")
        if plan.query:
            lines.append(f"The student asked: {plan.query}")
        return "\n".join(lines)


def _format_citation(citation: Citation) -> str:
    """Deterministic, stable one-line serialization of a citation."""
    ref = citation.concept_id if citation.concept_id else "unresolved"
    obj = f" object={citation.object_type}:{citation.locator}" if citation.object_type else ""
    return (
        f"[{citation.concept_name}] concept={ref} field={citation.source_field}"
        f" locator={citation.locator}{obj}"
    )
