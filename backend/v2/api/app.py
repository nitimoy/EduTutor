"""FastAPI wrapper for EduTutor v2."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.v2.rag.engine import RAGEngine


# Request/Response models
class QueryRequest(BaseModel):
    query: str
    subject: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]
    citations: list[dict]
    query: str
    grounded: bool
    verification: dict


class HealthResponse(BaseModel):
    status: str
    version: str
    documents_indexed: int


# Global v2 instance
_v2_instance: Optional[RAGEngine] = None

app = FastAPI(
    title="EduTutor v2 API",
    description="RAG-based educational tutor using LlamaIndex + Qdrant",
    version="2.0.0",
)


def get_engine() -> RAGEngine:
    """Get or create the v2 engine."""
    global _v2_instance
    if _v2_instance is None:
        _v2_instance = RAGEngine(
            compiled_dir="data/compiled",
            qdrant_path="data/v2/qdrant_full",
            llm_model="openai/gpt-4o-mini",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    return _v2_instance


@app.on_event("startup")
async def startup():
    """Build index on startup."""
    engine = get_engine()
    engine.build_index()


@app.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="2.0.0",
        documents_indexed=713,
    )


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """Process a query through the v2 RAG engine."""
    try:
        engine = get_engine()
        response = engine.query(
            question=request.query,
            subject_filter=request.subject,
        )
        return QueryResponse(
            answer=response["answer"],
            sources=response["sources"],
            citations=response["citations"],
            query=response["query"],
            grounded=response["grounded"],
            verification=response["verification"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
