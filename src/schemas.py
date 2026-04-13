from pydantic import BaseModel, Field


class SkillSummaryResponse(BaseModel):
    skill_id: str
    name: str
    description: str
    avatar: str = ""
    enabled: bool


class SkillDetailResponse(BaseModel):
    skill_id: str
    name: str
    description: str
    welcome_message: str = ""
    enabled: bool


class ConversationCreateRequest(BaseModel):
    skill_id: str = Field(min_length=1)
    channel: str = Field(default="web", min_length=1)


class ConversationCreateResponse(BaseModel):
    conversation_id: str
    created_at: str


class ConversationSummaryResponse(BaseModel):
    conversation_id: str
    title: str
    skill_id: str
    last_message: str = ""
    updated_at: str


class MessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: str


class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    skill_id: str = Field(min_length=1)
    channel: str = Field(default="web", min_length=1)
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    message_id: str
    conversation_id: str
    reply: str
    usage_info: UsageInfo
    created_at: str


class WechatCallbackRequest(BaseModel):
    external_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    skill_id: str = Field(default="default_skill", min_length=1)


class WechatCallbackResponse(BaseModel):
    external_id: str
    conversation_id: str
    message_id: str
    reply: str
    created_at: str


class HealthResponse(BaseModel):
    service_status: str
    model_status: str
    db_status: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class UserProfile(BaseModel):
    user_id: str
    username: str


class AuthResponse(BaseModel):
    token: str
    user: UserProfile


class TtsSynthesizeRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str | None = None
    speed: float = 1.0


class TtsSynthesizeResponse(BaseModel):
    provider: str
    audio_url: str | None = None
    audio_base64: str | None = None
    mime_type: str | None = None
    message: str = ""
