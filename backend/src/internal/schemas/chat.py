from datetime import datetime

from pydantic import BaseModel

from db.models import MessageType


class PromptID(BaseModel):
    prompt_id: int


class BaseMessage(BaseModel):
    content: str
    documents_ids: list[int] = []

    class Config:
        from_attributes = True


class MessageResponse(BaseMessage):
    message_id: int
    message_type: MessageType
    content: str
    created_at: datetime
    hidden_comments: str | None
    documents_ids: list[int]


class ChatResponse(BaseModel):
    chat_id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ExpandedChatResponse(ChatResponse):
    prompt: str
    messages: list[MessageResponse] = []

    @classmethod
    def from_chat(cls, chat) -> "ExpandedChatResponse":
        prompt_text = (
            chat.prompt.text if hasattr(chat.prompt, "text") else chat.prompt.title
        )

        messages = []
        if hasattr(chat, "messages") and chat.messages:
            for msg in chat.messages:
                messages.append(MessageResponse.model_validate(msg))

        return cls(
            chat_id=chat.id,
            is_active=chat.is_active,
            created_at=chat.created_at,
            prompt=prompt_text,
            messages=messages,
        )
