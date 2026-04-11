import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    skills_dir: str = os.getenv("SKILLS_DIR", "data/skills")
    context_limit: int = int(os.getenv("CONTEXT_LIMIT", "12"))
    rate_limit_max_requests: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "30"))
    rate_limit_window_seconds: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    model_provider: str = os.getenv("MODEL_PROVIDER", "deepseek").lower()
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    deepseek_temperature: float = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.7"))
    deepseek_timeout_seconds: float = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "30"))
    deepseek_max_tokens: int = int(os.getenv("DEEPSEEK_MAX_TOKENS", "0"))
    wechat_token: str = os.getenv("WECHAT_TOKEN", "")
    wechat_default_skill_id: str = os.getenv("WECHAT_DEFAULT_SKILL_ID", "default_skill")
    wechat_allowed_openid: str = os.getenv("WECHAT_ALLOWED_OPENID", "").strip()


settings = Settings()
