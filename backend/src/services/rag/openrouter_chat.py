from __future__ import annotations

from typing import Any, Literal

import httpx

from config import settings


Role = Literal["system", "user", "assistant", "tool"]


class OpenRouterChatClient:
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str | None = None,
        referer: str | None = None,
        title: str | None = None,
        timeout_seconds: float = 60.0,
        default_temperature: float | None = None,
        default_top_p: float | None = None,
        default_max_tokens: int | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._referer = referer
        self._title = title
        self._timeout_seconds = timeout_seconds
        self._default_temperature = default_temperature
        self._default_top_p = default_top_p
        self._default_max_tokens = default_max_tokens

    @classmethod
    def from_settings(cls) -> "OpenRouterChatClient":
        return cls(
            api_key=getattr(settings, "OPENROUTER_API_KEY", None),
            model=getattr(
                settings, "OPENROUTER_CHAT_MODEL", "qwen/qwen3-235b-a22b-2507"
            ),
            base_url=getattr(settings, "OPENROUTER_CHAT_URL", None),
            referer=getattr(settings, "OPENROUTER_HTTP_REFERER", None),
            title=getattr(settings, "OPENROUTER_APP_TITLE", None) or settings.APP_NAME,
            timeout_seconds=float(
                getattr(settings, "OPENROUTER_CHAT_TIMEOUT_SECONDS", 60.0)
            ),
            default_temperature=getattr(
                settings, "OPENROUTER_CHAT_DEFAULT_TEMPERATURE", None
            ),
            default_top_p=getattr(settings, "OPENROUTER_CHAT_DEFAULT_TOP_P", None),
            default_max_tokens=getattr(
                settings, "OPENROUTER_CHAT_DEFAULT_MAX_TOKENS", None
            ),
        )

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature
        elif self._default_temperature is not None:
            payload["temperature"] = self._default_temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        elif self._default_max_tokens is not None:
            payload["max_tokens"] = self._default_max_tokens
        if top_p is not None:
            payload["top_p"] = top_p
        elif self._default_top_p is not None:
            payload["top_p"] = self._default_top_p
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._referer:
            headers["HTTP-Referer"] = self._referer
        if self._title:
            headers["X-Title"] = self._title

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(self._base_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
