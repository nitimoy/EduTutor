from openai.types.responses import ResponseInputItemParam

from backend.types import Message


def message_items(messages: list[Message]) -> list[ResponseInputItemParam]:
    """Serialize chat messages into Responses API input items."""

    items: list[ResponseInputItemParam] = []
    for message in messages:
        content_type = "output_text" if message.role == "assistant" else "input_text"
        items.append(
            {
                "type": "message",
                "role": message.role,
                "content": [{"type": content_type, "text": message.content}],
            }
        )
    return items
