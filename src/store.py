import hashlib
import threading
import uuid
from collections import defaultdict

from src.models import Conversation, Message, Skill
from src.utils import utc_now


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.skills: dict[str, Skill] = {}
        self.conversations: dict[str, Conversation] = {}
        self.messages: dict[str, list[Message]] = defaultdict(list)
        self.user_map: dict[tuple[str, str], str] = {}

    def health(self) -> bool:
        return True

    def upsert_skill(self, skill: Skill) -> None:
        with self._lock:
            self.skills[skill.skill_id] = skill

    def list_skills(self) -> list[Skill]:
        with self._lock:
            return list(self.skills.values())

    def get_skill(self, skill_id: str) -> Skill | None:
        with self._lock:
            return self.skills.get(skill_id)

    def create_conversation(self, user_id: str, skill_id: str, channel: str) -> Conversation:
        with self._lock:
            conversation_id = f"c_{uuid.uuid4().hex[:12]}"
            now = utc_now()
            conversation = Conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                skill_id=skill_id,
                title="New conversation",
                channel=channel,
                created_at=now,
                updated_at=now,
            )
            self.conversations[conversation_id] = conversation
            return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            return self.conversations.get(conversation_id)

    def touch_conversation(self, conversation_id: str) -> None:
        with self._lock:
            conversation = self.conversations.get(conversation_id)
            if conversation:
                conversation.updated_at = utc_now()

    def list_conversations_by_user(self, user_id: str) -> list[Conversation]:
        with self._lock:
            items = [c for c in self.conversations.values() if c.user_id == user_id]
            return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def append_message(self, conversation_id: str, role: str, content: str, token_count: int) -> Message:
        with self._lock:
            message = Message(
                message_id=f"m_{uuid.uuid4().hex[:12]}",
                conversation_id=conversation_id,
                role=role,
                content=content,
                token_count=token_count,
                created_at=utc_now(),
            )
            self.messages[conversation_id].append(message)
            self.touch_conversation(conversation_id)
            return message

    def get_messages(self, conversation_id: str) -> list[Message]:
        with self._lock:
            return list(self.messages.get(conversation_id, []))

    def resolve_user_id(self, channel: str, external_id: str) -> str:
        key = (channel, external_id)
        with self._lock:
            if key in self.user_map:
                return self.user_map[key]

            digest = hashlib.sha1(f"{channel}:{external_id}".encode("utf-8")).hexdigest()
            user_id = f"u_{digest[:12]}"
            self.user_map[key] = user_id
            return user_id

