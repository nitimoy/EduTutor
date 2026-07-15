from pydantic import BaseModel, Field


class ConceptCoverage(BaseModel):
    has_definition: bool = False
    has_formula: bool = False
    has_examples: bool = False
    has_exercises: bool = False
    has_assessment: bool = False
    is_complete: bool = False


class Skill(BaseModel):
    name: str
    description: str


class LearningOutcome(BaseModel):
    objective: str
    assessment_targets: list[str] = Field(default_factory=list)


class ConceptReasoning(BaseModel):
    concept_id: str
    required_prerequisites: list[str] = Field(default_factory=list)
    teaching_sequence: list[str] = Field(default_factory=list)
    skills_developed: list[Skill] = Field(default_factory=list)
    learning_outcomes: LearningOutcome | None = None
    difficulty: str
    coverage: ConceptCoverage


class ReasoningValidationReport(BaseModel):
    cycles_detected: list[list[str]] = Field(default_factory=list)
    orphan_concepts: list[str] = Field(default_factory=list)
    broken_chains: list[str] = Field(default_factory=list)


class ReasoningIndex(BaseModel):
    book_id: str
    concept_reasoning: dict[str, ConceptReasoning] = Field(default_factory=dict)
    validation_report: ReasoningValidationReport
