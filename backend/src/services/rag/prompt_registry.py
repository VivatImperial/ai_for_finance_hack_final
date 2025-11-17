from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Prompt
from db.repositories.prompt_repo import PromptRepository


PROMPT_DEFINITIONS: tuple[dict[str, object], ...] = (
    {
        "title": "system-ru",
        "filename": "system_ru.txt",
        "params": {"kind": "system", "language": "ru"},
    },
    {
        "title": "orchestrator-ru",
        "filename": "orchestrator_ru.txt",
        "params": {"kind": "scenario-orchestrator", "language": "ru"},
    },
    {
        "title": "fusion-ru",
        "filename": "fusion_ru.txt",
        "params": {"kind": "query-fusion", "language": "ru"},
    },
)


def _prompts_dir() -> Path:
    return Path(__file__).with_suffix("").parent / "prompt_storage"


def _load_prompt_text(filename: str) -> str:
    path = _prompts_dir() / filename
    return path.read_text(encoding="utf-8")


async def seed_prompts(session: AsyncSession) -> list[Prompt]:
    repo = PromptRepository(session)
    seeded: list[Prompt] = []
    for definition in PROMPT_DEFINITIONS:
        title = str(definition["title"])
        filename = str(definition["filename"])
        params = definition.get("params") or {}
        content = _load_prompt_text(filename)
        prompt = await repo.upsert_prompt(title=title, text=content, params=params)
        seeded.append(prompt)
    return seeded
