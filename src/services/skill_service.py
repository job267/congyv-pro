import json
from pathlib import Path

from src.core.errors import AppError
from src.models import Skill
from src.schemas import SkillDetailResponse, SkillSummaryResponse
from src.store import InMemoryStore


class SkillService:
    def __init__(self, store: InMemoryStore, skills_dir: Path) -> None:
        self.store = store
        self.skills_dir = skills_dir

    def load_skills(self) -> None:
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)

        loaded = 0
        for path in sorted(self.skills_dir.glob("*.json")):
            skill = self._load_json_skill(path)
            self.store.upsert_skill(skill)
            loaded += 1

        for path in sorted(self.skills_dir.glob("*.md")):
            skill = self._load_markdown_skill(path)
            self.store.upsert_skill(skill)
            loaded += 1

        if loaded == 0:
            self.store.upsert_skill(
                Skill(
                    skill_id="default_skill",
                    name="Default Skill",
                    description="Fallback style for assistant responses.",
                    system_prompt="You are a practical assistant.",
                    style_rules=["concise"],
                    thinking_rules=["step-by-step"],
                    boundary_rules=["avoid unsafe or misleading output"],
                    version="1.0.0",
                    status="enabled",
                    welcome_message="Hello, how can I help you today?",
                )
            )

    def _read_text(self, path: Path) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Cannot decode skill file: {path}")

    def _load_json_skill(self, path: Path) -> Skill:
        payload = json.loads(self._read_text(path))
        return Skill(
            skill_id=payload["skill_id"],
            name=payload["name"],
            description=payload.get("description", ""),
            system_prompt=payload.get("system_prompt", ""),
            style_rules=self._normalize_rules(payload.get("style_rules", [])),
            thinking_rules=self._normalize_rules(payload.get("thinking_rules", [])),
            boundary_rules=self._normalize_rules(payload.get("boundary_rules", [])),
            version=payload.get("version", "1.0.0"),
            status=payload.get("status", "enabled"),
            welcome_message=payload.get("welcome_message", ""),
            avatar=payload.get("avatar", ""),
        )

    def _load_markdown_skill(self, path: Path) -> Skill:
        content = self._read_text(path)
        meta, body = self._split_frontmatter(content)

        skill_id = str(meta.get("skill_id") or path.stem).strip()
        name = str(meta.get("name") or skill_id).strip()
        description = str(meta.get("description") or f"Loaded from {path.name}").strip()
        system_prompt = body.strip() or str(meta.get("system_prompt") or "").strip()
        if not system_prompt:
            raise ValueError(f"Markdown skill is empty: {path}")

        return Skill(
            skill_id=skill_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            style_rules=self._normalize_rules(meta.get("style_rules", [])),
            thinking_rules=self._normalize_rules(meta.get("thinking_rules", [])),
            boundary_rules=self._normalize_rules(meta.get("boundary_rules", [])),
            version=str(meta.get("version", "1.0.0")).strip() or "1.0.0",
            status=str(meta.get("status", "enabled")).strip() or "enabled",
            welcome_message=str(meta.get("welcome_message", "")).strip(),
            avatar=str(meta.get("avatar", "")).strip(),
        )

    def _split_frontmatter(self, content: str) -> tuple[dict, str]:
        lines = content.splitlines()
        if not lines or lines[0].strip() != "---":
            return {}, content

        end_index = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_index = i
                break

        if end_index is None:
            return {}, content

        frontmatter = self._parse_frontmatter(lines[1:end_index])
        body = "\n".join(lines[end_index + 1 :]).strip()
        return frontmatter, body

    def _parse_frontmatter(self, lines: list[str]) -> dict:
        data: dict = {}
        active_list_key: str | None = None

        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("- ") and active_list_key:
                data.setdefault(active_list_key, []).append(self._parse_scalar(line[2:].strip()))
                continue

            if ":" not in line:
                active_list_key = None
                continue

            key, raw_value = line.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if not key:
                active_list_key = None
                continue

            if raw_value == "":
                data[key] = []
                active_list_key = key
                continue

            data[key] = self._parse_scalar(raw_value)
            active_list_key = None

        return data

    def _parse_scalar(self, value: str):
        text = value.strip()
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
            return text[1:-1]

        if text.startswith("[") and text.endswith("]"):
            try:
                arr = json.loads(text)
                if isinstance(arr, list):
                    return [str(item).strip() for item in arr if str(item).strip()]
            except json.JSONDecodeError:
                pass

        return text

    def _normalize_rules(self, value) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            separators = [",", "，", ";", "；", "|"]
            chunks = [text]
            for sep in separators:
                if sep in text:
                    chunks = [part.strip() for part in text.split(sep)]
                    break
            return [item for item in chunks if item]
        return []

    def list_skills(self) -> list[SkillSummaryResponse]:
        return [
            SkillSummaryResponse(
                skill_id=skill.skill_id,
                name=skill.name,
                description=skill.description,
                avatar=skill.avatar,
                enabled=skill.enabled,
            )
            for skill in self.store.list_skills()
        ]

    def get_skill_detail(self, skill_id: str) -> SkillDetailResponse:
        skill = self.store.get_skill(skill_id)
        if not skill:
            raise AppError("SKILL_NOT_FOUND", "Skill does not exist.", status_code=404)
        return SkillDetailResponse(
            skill_id=skill.skill_id,
            name=skill.name,
            description=skill.description,
            welcome_message=skill.welcome_message,
            enabled=skill.enabled,
        )

    def require_enabled_skill(self, skill_id: str) -> Skill:
        skill = self.store.get_skill(skill_id)
        if not skill:
            raise AppError("SKILL_NOT_FOUND", "Skill does not exist.", status_code=404)
        if not skill.enabled:
            raise AppError("SKILL_DISABLED", "Skill is disabled.", status_code=400)
        return skill
