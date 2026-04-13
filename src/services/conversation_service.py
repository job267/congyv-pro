from src.core.errors import AppError
from src.models import Conversation, Message
from src.schemas import (
    ConversationCreateResponse,
    ConversationSummaryResponse,
    MessageResponse,
)
from src.store import InMemoryStore
from src.utils import isoformat


class ConversationService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_conversation(self, user_id: str, skill_id: str, channel: str) -> ConversationCreateResponse:
        conversation = self.store.create_conversation(user_id=user_id, skill_id=skill_id, channel=channel)
        return ConversationCreateResponse(
            conversation_id=conversation.conversation_id,
            created_at=isoformat(conversation.created_at),
        )

    def get_or_create_conversation(
        self,
        conversation_id: str | None,
        user_id: str,
        skill_id: str,
        channel: str,
    ) -> Conversation:
        if not conversation_id:
            return self.store.create_conversation(user_id=user_id, skill_id=skill_id, channel=channel)

        conversation = self.store.get_conversation(conversation_id)
        if not conversation:
            raise AppError("CONVERSATION_NOT_FOUND", "Conversation does not exist.", status_code=404)
        if conversation.user_id != user_id:
            raise AppError("CONVERSATION_FORBIDDEN", "Conversation does not belong to current user.", status_code=403)
        if conversation.skill_id != skill_id:
            raise AppError(
                "SKILL_MISMATCH",
                "Provided skill_id does not match this conversation.",
                status_code=400,
            )
        return conversation

    def list_conversations(self, user_id: str) -> list[ConversationSummaryResponse]:
        items = []
        for conversation in self.store.list_conversations_by_user(user_id):
            messages = self.store.get_messages(conversation.conversation_id)
            last_message = messages[-1].content if messages else ""
            items.append(
                ConversationSummaryResponse(
                    conversation_id=conversation.conversation_id,
                    title=conversation.title,
                    skill_id=conversation.skill_id,
                    last_message=last_message[:200],
                    updated_at=isoformat(conversation.updated_at),
                )
            )
        return items

    def find_latest_conversation(self, user_id: str, skill_id: str, channel: str) -> Conversation | None:
        for conversation in self.store.list_conversations_by_user(user_id):
            if conversation.skill_id == skill_id and conversation.channel == channel:
                return conversation
        return None

    def list_messages(self, conversation_id: str, user_id: str) -> list[MessageResponse]:
        conversation = self.store.get_conversation(conversation_id)
        if not conversation:
            raise AppError("CONVERSATION_NOT_FOUND", "Conversation does not exist.", status_code=404)
        if conversation.user_id != user_id:
            raise AppError("CONVERSATION_FORBIDDEN", "Conversation does not belong to current user.", status_code=403)
        return [
            MessageResponse(
                message_id=message.message_id,
                role=message.role,
                content=message.content,
                created_at=isoformat(message.created_at),
            )
            for message in self.store.get_messages(conversation_id)
        ]

    def append_message(self, conversation_id: str, role: str, content: str, token_count: int) -> Message:
        return self.store.append_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            token_count=token_count,
        )

    def recent_context(self, conversation_id: str, limit: int) -> list[Message]:
        messages = self.store.get_messages(conversation_id)
        if limit <= 0:
            return []
        return messages[-limit:]
