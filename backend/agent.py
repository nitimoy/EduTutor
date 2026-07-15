import os

from openai import OpenAI

from backend.constants import DEFAULT_OPENAI_MODEL, SYSTEM_PROMPT
from backend.inputs import message_items
from backend.types import ChatRequest, ChatResponse


class StarterAgent:
    """Starter agent that candidates will extend or replace."""

    def __init__(self) -> None:
        self.model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def answer(self, request: ChatRequest) -> ChatResponse:
        response = self.client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=message_items(request.messages),
        )
        return ChatResponse(answer=response.output_text.strip(), model=self.model)
