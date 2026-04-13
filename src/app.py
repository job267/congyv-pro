import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request

from src.api.routes import create_router
from src.config import settings
from src.core.errors import register_exception_handlers
from src.core.rate_limiter import InMemoryRateLimiter
from src.llm.model_client import DeepSeekModelClient, MockModelClient
from src.services.auth_service import AuthService
from src.services.chat_service import ChatService
from src.services.conversation_service import ConversationService
from src.services.skill_service import SkillService
from src.store import InMemoryStore


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def create_model_client():
    if settings.model_provider == "deepseek":
        if settings.deepseek_api_key:
            logger.info(
                "Using DeepSeek model provider. model=%s base_url=%s",
                settings.deepseek_model,
                settings.deepseek_base_url,
            )
            return DeepSeekModelClient(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_model,
                timeout_seconds=settings.deepseek_timeout_seconds,
                temperature=settings.deepseek_temperature,
                max_tokens=settings.deepseek_max_tokens,
            )
        logger.warning("MODEL_PROVIDER=deepseek but DEEPSEEK_API_KEY is empty. Falling back to MockModelClient.")

    if settings.model_provider != "mock":
        logger.warning("Unsupported MODEL_PROVIDER=%s, fallback to MockModelClient.", settings.model_provider)
    return MockModelClient()


store = InMemoryStore(database_path=settings.database_path)
skill_service = SkillService(store=store, skills_dir=Path(settings.skills_dir))
skill_service.load_skills()
conversation_service = ConversationService(store=store)
auth_service = AuthService(
    store=store,
    secret_key=settings.auth_secret_key,
    token_ttl_seconds=settings.auth_token_ttl_seconds,
)
model_client = create_model_client()
rate_limiter = InMemoryRateLimiter(
    max_requests=settings.rate_limit_max_requests,
    window_seconds=settings.rate_limit_window_seconds,
)
chat_service = ChatService(
    skill_service=skill_service,
    conversation_service=conversation_service,
    model_client=model_client,
    context_limit=settings.context_limit,
)

app = FastAPI(title="Skill Chat System", version="0.1.0")
register_exception_handlers(app)
app.include_router(
    create_router(
        skill_service=skill_service,
        conversation_service=conversation_service,
        chat_service=chat_service,
        auth_service=auth_service,
        model_client=model_client,
        store=store,
        rate_limiter=rate_limiter,
    )
)


@app.middleware("http")
async def request_timing(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "%s %s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response
