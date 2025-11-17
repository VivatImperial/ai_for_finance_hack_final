from __future__ import annotations

from typing import Iterable

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .models import DocumentChunkPayload, MarkdownDocument


class ChunkSplitter:
    def __init__(
        self,
        *,
        chunk_size: int = 1200,
        chunk_overlap: int = 200,
        separators: Iterable[str] | None = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be in range [0, chunk_size)")

        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._separators = tuple(
            separators
            or (
                "\n## ",
                "\n### ",
                "\n#### ",
                "\n##### ",
                "\n",
                " ",
                "",
            )
        )

        self._char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            separators=self._separators,
        )

    def split(self, document: MarkdownDocument) -> list[DocumentChunkPayload]:
        base_document = Document(
            page_content=document.content,
            metadata=document.metadata or {},
        )
        chunk_documents = self._char_splitter.split_documents([base_document])
        payloads: list[DocumentChunkPayload] = []
        for index, doc in enumerate(chunk_documents):
            text = doc.page_content.strip()
            if not text:
                continue

            payloads.append(
                DocumentChunkPayload(
                    content=text,
                    serial=index,
                    metadata=doc.metadata,
                )
            )

        if not payloads and document.content.strip():
            payloads.append(
                DocumentChunkPayload(
                    content=document.content.strip(),
                    serial=0,
                    metadata=document.metadata,
                )
            )

        return payloads
