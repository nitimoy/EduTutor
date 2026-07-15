"""Legacy ``/chat`` compatibility endpoint.

Wraps the ``EducationalTutorEngine`` behind the original ``POST /chat`` interface
(``ChatRequest`` → ``ChatResponse``). The last user message becomes the query; the
engine runs the full pipeline; the rendered text becomes the answer.

This endpoint exists solely for backward compatibility with evaluation scripts and
older clients. New integrations should use ``POST /api/v1/tutor/ask``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_tutor_engine
from backend.api.schemas import ChatMessage, ChatRequest, ChatResponse
from backend.orchestrator.engine import EducationalTutorEngine
from backend.student.models import StudentProfile

router = APIRouter(tags=["legacy"])


@router.post("/chat")
def chat(
    request: ChatRequest,
    engine: EducationalTutorEngine = Depends(get_tutor_engine),
) -> ChatResponse:
    """Legacy chat endpoint — backward-compatible with the starter agent API.

    Extracts the last user message as the query, runs the educational pipeline,
    and returns the rendered answer in the original ``ChatResponse`` shape.
    """
    # Find the last user message (the question).
    query = _extract_query(request.messages)

    response = engine.answer(query, StudentProfile())
    return ChatResponse(
        answer=response.rendered_response.text,
        model=f"{response.execution_metadata.provider}/{response.execution_metadata.model_id}",
    )


def _extract_query(messages: list[ChatMessage]) -> str:
    """Return the content of the last user message, or the last message if none are 'user'."""
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    # Fallback: use the last message regardless of role.
    return messages[-1].content
