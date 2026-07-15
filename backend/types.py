from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)


class ChatResponse(BaseModel):
    answer: str
    model: str
