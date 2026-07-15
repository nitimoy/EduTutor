"""Pydantic models for the Retrieval Evaluation Framework."""

from pydantic import BaseModel, Field

class RetrievalQuery(BaseModel):
    query: str
    expected_concept_names: list[str] = Field(default_factory=list)
    
class RetrievalQueryDataset(BaseModel):
    version: str
    subject: str
    book: str
    queries: list[RetrievalQuery] = Field(default_factory=list)

class QueryEvaluation(BaseModel):
    query: str
    mrr: float = 0.0
    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    precision_at_1: float = 0.0
    precision_at_3: float = 0.0
    precision_at_5: float = 0.0
    ndcg_at_5: float = 0.0
    
class RetrievalEvaluationReport(BaseModel):
    dataset_version: str
    search_strategy: str
    overall_mrr: float = 0.0
    overall_recall_at_1: float = 0.0
    overall_recall_at_3: float = 0.0
    overall_recall_at_5: float = 0.0
    overall_precision_at_1: float = 0.0
    overall_precision_at_3: float = 0.0
    overall_precision_at_5: float = 0.0
    overall_ndcg_at_5: float = 0.0
    query_evaluations: list[QueryEvaluation] = Field(default_factory=list)
