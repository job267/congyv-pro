from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Skill:
    skill_id: str
    name: str
    description: str
    system_prompt: str
    style_rules: list[str] = field(default_factory=list)
    thinking_rules: list[str] = field(default_factory=list)
    boundary_rules: list[str] = field(default_factory=list)
    version: str = "1.0.0"
    status: str = "enabled"
    welcome_message: str = ""
    avatar: str = ""

    @property
    def enabled(self) -> bool:
        return self.status.lower() == "enabled"


@dataclass
class Conversation:
    conversation_id: str
    user_id: str
    skill_id: str
    title: str
    channel: str
    created_at: datetime
    updated_at: datetime


@dataclass
class Message:
    message_id: str
    conversation_id: str
    role: str
    content: str
    token_count: int
    created_at: datetime

