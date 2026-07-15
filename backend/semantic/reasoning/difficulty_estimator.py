from backend.semantic.concepts.concept_models import Concept


class DifficultyEstimator:
    """Estimates the learning difficulty of a concept."""

    def estimate(self, concept: Concept, num_prereqs: int) -> str:
        score = 1.0
        
        # +0.5 per transitive prerequisite
        score += num_prereqs * 0.5
        
        # +0.2 per formula/theorem/property
        num_formulas = len(concept.formula_ids) + len(concept.theorem_ids) + len(concept.property_ids)
        score += num_formulas * 0.2
        
        # +0.3 per proof
        score += len(concept.proof_ids) * 0.3
        
        # +0.1 per exercise beyond 5
        num_exercises = len(concept.exercise_ids)
        if num_exercises > 5:
            score += (num_exercises - 5) * 0.1
            
        if score < 3.0:
            return "Easy"
        elif score <= 6.0:
            return "Medium"
        else:
            return "Hard"
