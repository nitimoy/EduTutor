import logging
from backend.compiler.models import EducationalIR
from backend.semantic.concepts.concept_models import ConceptIndex
from backend.semantic.relationships.relationship_models import RelationshipIndex
from backend.semantic.reasoning.reasoning_models import ConceptReasoning, ReasoningIndex

from .prerequisite_engine import PrerequisiteEngine
from .learning_path_builder import LearningPathBuilder
from .skill_extractor import SkillExtractor
from .difficulty_estimator import DifficultyEstimator
from .dependency_validator import DependencyValidator


logger = logging.getLogger(__name__)


class ReasoningEngine:
    """Orchestrates the Educational Reasoning Layer."""

    def __init__(self) -> None:
        self.prereq_engine = PrerequisiteEngine()
        self.path_builder = LearningPathBuilder()
        self.skill_extractor = SkillExtractor()
        self.difficulty_estimator = DifficultyEstimator()
        self.validator = DependencyValidator()

    def build(self, ir: EducationalIR, concept_index: ConceptIndex, rel_index: RelationshipIndex) -> ReasoningIndex:
        """Run all reasoning modules and return the aggregated ReasoningIndex."""
        logger.info("Running Dependency Validation...")
        report = self.validator.validate(concept_index, rel_index)
        if report.cycles_detected:
            logger.warning("Detected %d dependency cycles!", len(report.cycles_detected))
        if report.broken_chains:
            logger.warning("Detected %d broken prerequisite chains!", len(report.broken_chains))

        logger.info("Computing Prerequisites...")
        concept_ids = [c.id for c in concept_index.concepts]
        transitive_prereqs = self.prereq_engine.compute(concept_ids, rel_index)

        concept_reasoning: dict[str, ConceptReasoning] = {}
        for concept in concept_index.concepts:
            # 1. Coverage
            coverage = self.skill_extractor.compute_coverage(concept)
            
            # 2. Prerequisites
            prereqs = transitive_prereqs.get(concept.id, [])
            
            # 3. Learning Path
            sequence = self.path_builder.build(concept.id, ir.book.objects, concept_index)
            
            # 4. Skills & Outcomes
            skills = self.skill_extractor.extract_skills(concept, coverage)
            outcomes = self.skill_extractor.extract_outcomes(concept, coverage)
            
            # 5. Difficulty
            difficulty = self.difficulty_estimator.estimate(concept, len(prereqs))
            
            concept_reasoning[concept.id] = ConceptReasoning(
                concept_id=concept.id,
                required_prerequisites=prereqs,
                teaching_sequence=sequence,
                skills_developed=skills,
                learning_outcomes=outcomes,
                difficulty=difficulty,
                coverage=coverage
            )

        return ReasoningIndex(
            book_id=ir.book.id,
            concept_reasoning=concept_reasoning,
            validation_report=report
        )
