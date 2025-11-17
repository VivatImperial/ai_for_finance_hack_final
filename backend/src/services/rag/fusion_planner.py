from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from services.rag.configuration import PromptParams
from services.rag.openrouter_chat import OpenRouterChatClient


@dataclass(frozen=True)
class FusionPlan:
    base_query: str
    refinements: list[str]
    subqueries: list[str]
    priority_notes: str
    rerank: bool
    direct_answer_hint: str | None = None

    @property
    def expansions(self) -> list[str]:
        uniq: list[str] = []
        for item in [self.base_query, *self.refinements, *self.subqueries]:
            if item and item.strip() and item not in uniq:
                uniq.append(item.strip())
        return uniq


class FusionPlanner:
    def __init__(
        self,
        *,
        chat_client: OpenRouterChatClient,
        prompt_params: PromptParams,
        history_tail: int = 5,
    ) -> None:
        self._chat_client = chat_client
        self._prompt_params = prompt_params
        self._history_tail = max(0, history_tail)
        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        self._system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")
        self._fusion_prompt = (base / "fusion_ru.txt").read_text(encoding="utf-8")

    async def plan(
        self,
        *,
        query: str,
        history: Sequence[dict[str, str]] | None = None,
        selected_ids: Sequence[int] | None = None,
    ) -> FusionPlan:
        history_tail = (history or [])[-self._history_tail :]
        payload = {
            "query": query,
            "history_messages": len(history_tail),
            "history_preview": history_tail,
            "selected_document_ids": list(selected_ids or []),
        }
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "system", "content": self._fusion_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        response = await self._chat_client.chat(
            messages=messages,
            response_format={"type": "json_object"},
            **self._prompt_kwargs(),
        )
        content = response["choices"][0]["message"]["content"]
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {}
        refinements = _ensure_list(data.get("refinements"))
        subqueries = _ensure_list(data.get("subqueries"))
        notes = str(data.get("notes") or data.get("strategy") or "").strip()
        rerank = bool(data.get("rerank", True))
        direct_hint = str(data.get("direct_answer_hint", "")).strip() or None
        return FusionPlan(
            base_query=query,
            refinements=refinements,
            subqueries=subqueries,
            priority_notes=notes,
            rerank=rerank,
            direct_answer_hint=direct_hint,
        )

    def _prompt_kwargs(self) -> dict[str, Any]:
        return {
            "temperature": self._prompt_params.temperature,
            "top_p": self._prompt_params.top_p,
            "max_tokens": self._prompt_params.max_tokens,
        }


def _ensure_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


__all__ = ["FusionPlanner", "FusionPlan"]
