import re
from dataclasses import dataclass

import httpx

from src.core.errors import AppError
from src.models import Message, Skill


@dataclass
class ModelResult:
    reply: str
    prompt_tokens: int
    completion_tokens: int


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return len(re.findall(r"\w+|[^\w\s]", text))


def build_skill_system_prompt(skill: Skill) -> str:
    style = "\n".join(f"- {rule}" for rule in skill.style_rules) or "- Keep responses clear."
    thinking = "\n".join(f"- {rule}" for rule in skill.thinking_rules) or "- Think step by step."
    boundary = "\n".join(f"- {rule}" for rule in skill.boundary_rules) or "- Follow safety boundaries."
    return (
        f"{skill.system_prompt}\n\n"
        "Style rules:\n"
        f"{style}\n\n"
        "Thinking rules:\n"
        f"{thinking}\n\n"
        "Boundary rules:\n"
        f"{boundary}"
    )


class DeepSeekModelClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30,
        temperature: float = 0.7,
        max_tokens: int = 0,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens

    def healthcheck(self) -> bool:
        return bool(self.api_key)

    def _build_messages(self, skill: Skill, history: list[Message], user_message: str) -> list[dict]:
        messages: list[dict] = [
            {
                "role": "system",
                "content": build_skill_system_prompt(skill),
            }
        ]

        for item in history:
            if item.role not in {"user", "assistant"}:
                continue
            messages.append({"role": item.role, "content": item.content})

        if not history or history[-1].role != "user" or history[-1].content != user_message:
            messages.append({"role": "user", "content": user_message})

        return messages

    def generate(self, skill: Skill, history: list[Message], user_message: str) -> ModelResult:
        if not self.api_key:
            raise AppError(
                "MODEL_CONFIG_ERROR",
                "DEEPSEEK_API_KEY is not configured.",
                status_code=500,
            )

        messages = self._build_messages(skill=skill, history=history, user_message=user_message)
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": False,
        }
        if self.max_tokens > 0:
            payload["max_tokens"] = self.max_tokens

        try:
            response = httpx.post(
                url=f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("error", {}).get("message", "")
            except ValueError:
                detail = exc.response.text[:200]
            raise AppError(
                "MODEL_CALL_FAILED",
                f"DeepSeek request failed ({exc.response.status_code}). {detail}".strip(),
                status_code=502,
            ) from exc
        except httpx.RequestError as exc:
            raise AppError(
                "MODEL_CALL_FAILED",
                f"DeepSeek request error: {exc}",
                status_code=502,
            ) from exc

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise AppError(
                "MODEL_CALL_FAILED",
                "DeepSeek returned empty choices.",
                status_code=502,
            )

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise AppError(
                "MODEL_CALL_FAILED",
                "DeepSeek returned empty content.",
                status_code=502,
            )

        usage = data.get("usage", {})
        prompt_tokens = int(usage.get("prompt_tokens", estimate_tokens(" ".join(m["content"] for m in messages))))
        completion_tokens = int(usage.get("completion_tokens", estimate_tokens(content)))
        return ModelResult(
            reply=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


class MockModelClient:
    def healthcheck(self) -> bool:
        return True

    def generate(self, skill: Skill, history: list[Message], user_message: str) -> ModelResult:
        style_hint = skill.style_rules[0] if skill.style_rules else "clear and practical"
        boundary_hint = skill.boundary_rules[0] if skill.boundary_rules else "stay safe and factual"
        reply = (
            f"[{skill.name}] I understand your message: {user_message}. "
            f"I will respond in a {style_hint} style and {boundary_hint}. "
            f"If you share your goal, constraints, and deadline, I can provide a concrete plan."
        )

        prompt_snapshot = " ".join(
            [skill.system_prompt, " ".join(skill.style_rules), " ".join(m.content for m in history)]
        )
        return ModelResult(
            reply=reply,
            prompt_tokens=estimate_tokens(prompt_snapshot),
            completion_tokens=estimate_tokens(reply),
        )
