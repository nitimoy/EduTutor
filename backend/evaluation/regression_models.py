"""Models for the Regression Evaluation Framework."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

class ExpectedOutput(BaseModel):
    concept: str
    intent: str
    strategy: str
    supported: bool
    sections: List[str]

class DatasetItem(BaseModel):
    query: str
    expected: ExpectedOutput

class RegressionResult(BaseModel):
    query: str
    
    # Retrieval
    expected_concept: str
    actual_concept: Optional[str]
    retrieval_correct: bool
    retrieval_rank: Optional[int]
    retrieval_score: Optional[float]
    
    # Intent
    expected_intent: str
    actual_intent: Optional[str]
    intent_correct: bool
    
    # Strategy
    expected_strategy: str
    actual_strategy: Optional[str]
    strategy_correct: bool
    
    # Sections
    expected_sections: List[str]
    actual_sections: List[str]
    sections_correct: bool
    
    # Verification
    verification_passed: bool
    
    # Overall 
    supported_expected: bool
    supported_actual: bool
    supported_correct: bool
    
    # Timings (ms)
    time_retrieval_ms: float
    time_planning_ms: float
    time_generation_ms: float
    time_verification_ms: float
    time_total_ms: float
    
    # Determinism
    deterministic: bool

class RegressionMetrics(BaseModel):
    total_queries: int
    
    overall_accuracy: float
    
    retrieval_recall_1: float
    retrieval_recall_5: float
    
    intent_accuracy: float
    strategy_accuracy: float
    verification_pass_rate: float
    unsupported_query_rate: float
    
    avg_latency_ms: float
    determinism_rate: float
