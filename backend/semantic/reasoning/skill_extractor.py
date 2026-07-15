from backend.semantic.concepts.concept_models import Concept
from backend.semantic.reasoning.reasoning_models import ConceptCoverage, LearningOutcome, Skill


class SkillExtractor:
    """Generates skills and learning outcomes based on concept properties and coverage."""

    def compute_coverage(self, concept: Concept) -> ConceptCoverage:
        has_def = len(concept.definition_ids) > 0
        has_form = len(concept.formula_ids) > 0 or len(concept.property_ids) > 0 or len(concept.theorem_ids) > 0
        has_ex = len(concept.example_ids) > 0
        has_assess = len(concept.exercise_ids) > 0
        
        is_complete = has_def and has_ex and has_assess

        return ConceptCoverage(
            has_definition=has_def,
            has_formula=has_form,
            has_examples=has_ex,
            has_exercises=has_assess,
            has_assessment=has_assess,
            is_complete=is_complete
        )

    def extract_skills(self, concept: Concept, coverage: ConceptCoverage) -> list[Skill]:
        skills = []
        name = concept.name
        
        if coverage.has_formula:
            skills.append(
                Skill(
                    name=f"Calculation and Application: {name}",
                    description=f"Ability to use formulas, properties, or theorems related to {name} in calculations."
                )
            )
            
        if len(concept.proof_ids) > 0:
            skills.append(
                Skill(
                    name=f"Mathematical Reasoning: {name}",
                    description=f"Understanding and deriving proofs related to {name}."
                )
            )
            
        if coverage.has_assessment:
            skills.append(
                Skill(
                    name=f"Problem Solving: {name}",
                    description=f"Applying the concept of {name} to solve complex exercises."
                )
            )
            
        # Fallback skill if no specific types are found
        if not skills:
            skills.append(
                Skill(
                    name=f"Conceptual Understanding: {name}",
                    description=f"Basic theoretical understanding of {name}."
                )
            )
            
        return skills

    def extract_outcomes(self, concept: Concept, coverage: ConceptCoverage) -> LearningOutcome:
        return LearningOutcome(
            objective=f"The student will be able to understand and apply the concept of {concept.name}.",
            assessment_targets=concept.exercise_ids
        )
