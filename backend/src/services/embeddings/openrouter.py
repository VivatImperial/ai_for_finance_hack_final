from __future__ import annotations

import logging
from typing import Sequence

import httpx

from config import settings


class OpenRouterEmbeddingClient:
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/embeddings"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str | None = None,
        referer: str | None = None,
        title: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._referer = referer
        self._title = title
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls) -> "OpenRouterEmbeddingClient":
        return cls(
            api_key=getattr(settings, "OPENROUTER_API_KEY", None),
            model=getattr(
                settings, "OPENROUTER_EMBED_MODEL", "openai/text-embedding-3-large"
            ),
            base_url=getattr(settings, "OPENROUTER_EMBED_URL", None),
            referer=getattr(settings, "OPENROUTER_HTTP_REFERER", None),
            title=getattr(settings, "OPENROUTER_APP_TITLE", None) or settings.APP_NAME,
            timeout_seconds=float(
                getattr(settings, "OPENROUTER_TIMEOUT_SECONDS", 30.0)
            ),
        )

    @property
    def is_enabled(self) -> bool:
        return bool(self._api_key)

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        if not self.is_enabled:
            raise RuntimeError("OpenRouter API key is not configured")

        payload = {
            "model": self._model,
            "input": list(texts),
        }

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

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logging.exception(
                "openrouter-embedding-request-failed",
                status_code=exc.response.status_code,
            )
            raise

        data = response.json()
        embeddings = [item["embedding"] for item in data.get("data", [])]

        if not embeddings:
            raise RuntimeError("OpenRouter returned no embeddings")

        return embeddings
