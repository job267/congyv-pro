from src.llm.model_client import estimate_tokens
from src.schemas import ChatRequest, ChatResponse, UsageInfo
from src.services.conversation_service import ConversationService
from src.services.skill_service import SkillService
from src.utils import isoformat


class ChatService:
    def __init__(
        self,
        skill_service: SkillService,
        conversation_service: ConversationService,
        model_client,
        context_limit: int,
    ) -> None:
        self.skill_service = skill_service
        self.conversation_service = conversation_service
        self.model_client = model_client
        self.context_limit = context_limit

    def chat(self, payload: ChatRequest) -> ChatResponse:
        skill = self.skill_service.require_enabled_skill(payload.skill_id)

        conversation = self.conversation_service.get_or_create_conversation(
            conversation_id=payload.conversation_id,
            user_id=payload.user_id,
            skill_id=payload.skill_id,
            channel=payload.channel,
        )

        user_token_count = estimate_tokens(payload.message)
        self.conversation_service.append_message(
            conversation_id=conversation.conversation_id,
            role="user",
            content=payload.message,
            token_count=user_token_count,
        )

        history = self.conversation_service.recent_context(
            conversation_id=conversation.conversation_id,
            limit=self.context_limit,
        )
        model_result = self.model_client.generate(
            skill=skill,
            history=history,
            user_message=payload.message,
        )

        assistant_message = self.conversation_service.append_message(
            conversation_id=conversation.conversation_id,
            role="assistant",
            content=model_result.reply,
            token_count=model_result.completion_tokens,
        )

        return ChatResponse(
            message_id=assistant_message.message_id,
            conversation_id=conversation.conversation_id,
            reply=model_result.reply,
            usage_info=UsageInfo(
                prompt_tokens=model_result.prompt_tokens,
                completion_tokens=model_result.completion_tokens,
            ),
            created_at=isoformat(assistant_message.created_at),
        )

