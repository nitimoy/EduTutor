"""Regression tests for realistic LLM generation Verification."""

from backend.generation.models import GenerationResult, LanguageGenerationPlan, RenderedResponse
from backend.tutor.models import Citation, PlanSection, SectionStatus, TutorPlan
from backend.verification.engine import ResponseVerificationEngine


def _setup():
    citations = [
        Citation(concept_id="concept1", concept_name="Alpha", source_field="content", locator="0", object_type="content")
    ]
    tutor_plan = TutorPlan(
        query="Test query",
        intent="explanation",
        strategy="concept_explanation",
        prerequisites=PlanSection(status=SectionStatus.PRESENT, kind="prerequisites", items=["Test line one."]),
        main_explanation=PlanSection(status=SectionStatus.EMPTY, kind="main_explanation"),
        formula=PlanSection(status=SectionStatus.EMPTY, kind="formula"),
        worked_example=PlanSection(status=SectionStatus.EMPTY, kind="worked_example"),
        proof=PlanSection(status=SectionStatus.EMPTY, kind="proof"),
        exercise=PlanSection(status=SectionStatus.EMPTY, kind="exercise"),
        comparison=PlanSection(status=SectionStatus.EMPTY, kind="comparison"),
        related_concepts=PlanSection(status=SectionStatus.EMPTY, kind="related_concepts"),
        suggested_next_topics=PlanSection(status=SectionStatus.EMPTY, kind="next_topics"),
        summary=PlanSection(status=SectionStatus.EMPTY, kind="summary"),
        references=citations
    )
    from backend.generation.models import PromptBlock, RenderUnit
    generation_plan = LanguageGenerationPlan(
        query="Test",
        intent="explanation",
        strategy="concept_explanation",
        units=[
            RenderUnit(
                unit_id="u1", kind="prerequisites", content_lines=("Test line one.",), citations=citations
            )
        ]
    )
    
    from backend.generation.models import PromptDocument, PromptBlock
    prompt_doc = PromptDocument(
        unit_id="u1", unit_kind="prerequisites", system="system",
        blocks=(
            PromptBlock(label="Content", lines=("Test line one.",)),
            PromptBlock(label="Citations", lines=("[Alpha] concept=concept1 field=content locator=0",))
        ),
        citations=citations
    )
    return tutor_plan, generation_plan, citations, prompt_doc


def test_realistic_rephrasing_passes():
    tutor_plan, generation_plan, citations, prompt_doc = _setup()
    
    rendered = RenderedResponse(
        sections=[
            GenerationResult(
                unit_id="u1", unit_kind="prerequisites", citations=citations,
                text="It is important to note that the test line one is here! [Alpha] concept=concept1 field=content locator=0",
                prompt=prompt_doc
            )
        ],
        query="Test query",
        references=citations
    )
    report = ResponseVerificationEngine().verify(tutor_plan, generation_plan, rendered)
    
    # Grounding should pass (citations stripped, "important to note" ignored)
    assert report.metrics.grounding_completeness == 1.0
    
    # Completeness should pass (intersection includes "test", "line", "one")
    assert report.metrics.coverage == 1.0
    assert report.passed


def test_genuinely_new_concepts_fail_grounding():
    tutor_plan, generation_plan, citations, prompt_doc = _setup()
    
    rendered = RenderedResponse(
        sections=[
            GenerationResult(
                unit_id="u1", unit_kind="prerequisites", citations=citations,
                text="Test line one. Also thermodynamics is cool.",
                prompt=prompt_doc
            )
        ],
        query="Test query",
        references=citations
    )
    report = ResponseVerificationEngine().verify(tutor_plan, generation_plan, rendered)
    
    # Grounding fails due to "thermodynamics", "cool"
    assert report.metrics.grounding_completeness == 0.0
    assert not report.passed


def test_omitted_educational_content_fails_completeness():
    tutor_plan, generation_plan, citations, prompt_doc = _setup()
    
    # Text completely omits "Test line one."
    rendered = RenderedResponse(
        sections=[
            GenerationResult(
                unit_id="u1", unit_kind="prerequisites", citations=citations,
                text="Important to note that this is different.",
                prompt=prompt_doc
            )
        ],
        query="Test query",
        references=citations
    )
    report = ResponseVerificationEngine().verify(tutor_plan, generation_plan, rendered)
    
    # Completeness fails because intersection is empty
    assert report.completeness.coverage_pct == 0.0
    assert not report.passed
