from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Sequence


ToolHandler = Callable[["ToolInvocation", "ToolContext"], Awaitable["ToolResult"]]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(slots=True)
class ToolInvocation:
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ToolResult:
    content: dict[str, Any]
    used_chunks: list[Any] = field(default_factory=list)


@dataclass(slots=True)
class ToolContext:
    db: Any
    user: Any
    chat_id: int | None
    history: list[dict[str, str]]
    selected_document_ids: Sequence[int] | None
    scenario: int
    instructions: str
    intent: str | None
    current_datetime: str | None = None
    use_query_expansion: bool | None = None


class ToolRegistry:
    def __init__(self, definitions: Sequence[ToolDefinition]) -> None:
        self._definitions = {definition.name: definition for definition in definitions}

    def describe(self, allowed: Sequence[str] | None = None) -> list[dict[str, Any]]:
        if allowed is None:
            defs = self._definitions.values()
        else:
            defs = (
                self._definitions[name] for name in allowed if name in self._definitions
            )
        return [definition.to_openai() for definition in defs]

    async def execute(
        self,
        *,
        name: str,
        arguments_json: str | None,
        context: ToolContext,
    ) -> ToolResult:
        if name not in self._definitions:
            raise ValueError(f"Unknown tool: {name}")
        arguments = self._parse_arguments(arguments_json)
        invocation = ToolInvocation(name=name, arguments=arguments)
        handler = self._definitions[name].handler
        return await handler(invocation, context)

    @staticmethod
    def _parse_arguments(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid tool arguments: {raw}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Tool arguments must be an object")
        return parsed


__all__ = [
    "ToolContext",
    "ToolDefinition",
    "ToolInvocation",
    "ToolRegistry",
    "ToolResult",
]
