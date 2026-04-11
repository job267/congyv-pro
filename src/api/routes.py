from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse, Response

from src.config import settings
from src.core.errors import AppError
from src.core.wechat import build_wechat_text_reply, parse_wechat_xml, verify_wechat_signature
from src.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationSummaryResponse,
    HealthResponse,
    MessageResponse,
    SkillDetailResponse,
    SkillSummaryResponse,
)


def create_router(
    skill_service,
    conversation_service,
    chat_service,
    model_client,
    store,
    rate_limiter,
) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/skills", response_model=list[SkillSummaryResponse])
    def list_skills() -> list[SkillSummaryResponse]:
        return skill_service.list_skills()

    @router.get("/skills/{skill_id}", response_model=SkillDetailResponse)
    def get_skill(skill_id: str) -> SkillDetailResponse:
        return skill_service.get_skill_detail(skill_id)

    @router.post("/conversations", response_model=ConversationCreateResponse)
    def create_conversation(payload: ConversationCreateRequest) -> ConversationCreateResponse:
        skill_service.require_enabled_skill(payload.skill_id)
        return conversation_service.create_conversation(
            user_id=payload.user_id,
            skill_id=payload.skill_id,
            channel=payload.channel,
        )

    @router.get("/conversations", response_model=list[ConversationSummaryResponse])
    def get_conversations(user_id: str = Query(min_length=1)) -> list[ConversationSummaryResponse]:
        return conversation_service.list_conversations(user_id=user_id)

    @router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
    def get_messages(conversation_id: str) -> list[MessageResponse]:
        return conversation_service.list_messages(conversation_id)

    @router.post("/chat", response_model=ChatResponse)
    def chat(payload: ChatRequest) -> ChatResponse:
        key = f"{payload.channel}:{payload.user_id}"
        if not rate_limiter.allow(key):
            raise AppError(
                "RATE_LIMITED",
                "Too many requests. Please retry later.",
                status_code=429,
            )
        return chat_service.chat(payload)

    @router.get("/wechat/callback", response_class=PlainTextResponse)
    def wechat_verify(
        signature: str = Query(default=""),
        timestamp: str = Query(default=""),
        nonce: str = Query(default=""),
        echostr: str = Query(default=""),
    ) -> PlainTextResponse:
        if not verify_wechat_signature(
            token=settings.wechat_token,
            signature=signature,
            timestamp=timestamp,
            nonce=nonce,
        ):
            return PlainTextResponse("invalid signature", status_code=403)
        return PlainTextResponse(echostr)

    @router.post("/wechat/callback")
    async def wechat_callback(
        request: Request,
        signature: str = Query(default=""),
        timestamp: str = Query(default=""),
        nonce: str = Query(default=""),
    ) -> Response:
        if not verify_wechat_signature(
            token=settings.wechat_token,
            signature=signature,
            timestamp=timestamp,
            nonce=nonce,
        ):
            return PlainTextResponse("invalid signature", status_code=403)

        raw = await request.body()
        if not raw:
            return PlainTextResponse("success")

        try:
            payload = parse_wechat_xml(raw)
        except Exception:
            return PlainTextResponse("success")

        from_user = payload.get("FromUserName", "")
        to_user = payload.get("ToUserName", "")
        msg_type = payload.get("MsgType", "")

        # Keep a single-account bot behavior by allowing only one OpenID when configured.
        if settings.wechat_allowed_openid and from_user != settings.wechat_allowed_openid:
            return PlainTextResponse("success")

        if msg_type == "event":
            return PlainTextResponse("success")

        if msg_type != "text":
            reply_xml = build_wechat_text_reply(
                to_user=from_user,
                from_user=to_user,
                content="当前仅支持文本消息。",
            )
            return Response(content=reply_xml, media_type="application/xml")

        text = payload.get("Content", "").strip()
        if not text:
            return PlainTextResponse("success")

        user_id = store.resolve_user_id(channel="wechat", external_id=from_user)
        latest = conversation_service.find_latest_conversation(
            user_id=user_id,
            skill_id=settings.wechat_default_skill_id,
            channel="wechat",
        )
        chat_response = chat_service.chat(
            ChatRequest(
                conversation_id=latest.conversation_id if latest else None,
                user_id=user_id,
                skill_id=settings.wechat_default_skill_id,
                channel="wechat",
                message=text,
            )
        )

        reply_xml = build_wechat_text_reply(
            to_user=from_user,
            from_user=to_user,
            content=chat_response.reply,
        )
        return Response(content=reply_xml, media_type="application/xml")

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            service_status="ok",
            model_status="ok" if model_client.healthcheck() else "degraded",
            db_status="ok" if store.health() else "degraded",
        )

    return router
