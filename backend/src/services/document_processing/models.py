from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MarkdownDocument:
    content: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class DocumentChunkPayload:
    content: str
    serial: int
    metadata: dict[str, Any] | None = None
