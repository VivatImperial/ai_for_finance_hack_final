from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import structlog

from db.models import DocumentChunk, ParsedDocument
from db.repositories.chunk_repo import DocumentChunkRepository
from services.embeddings.openrouter import OpenRouterEmbeddingClient
from services.qdrant.vector_store import QdrantVectorStore


logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ChunkRecord:
    chunk: DocumentChunk
    metadata: dict[str, Any] | None


@dataclass(frozen=True)
class VectorSearchResult:
    chunk: DocumentChunk
    score: float
    payload: dict[str, Any]


class DocumentVectorManager:
    def __init__(
        self,
        *,
        embedding_client: OpenRouterEmbeddingClient | None = None,
        vector_store: QdrantVectorStore | None = None,
    ) -> None:
        self._embedding_client = (
            embedding_client or OpenRouterEmbeddingClient.from_settings()
        )
        self._vector_store = vector_store or QdrantVectorStore.from_settings()

    async def index_document(
        self,
        *,
        document: ParsedDocument,
        chunk_records: Sequence[ChunkRecord],
        document_metadata: dict[str, Any] | None = None,
    ) -> None:
        if not chunk_records:
            return

        if not self._embedding_client.is_enabled:
            logger.info(
                "embedding-disabled", reason="OpenRouter API key not configured"
            )
            return

        if not self._vector_store.is_enabled:
            logger.info("qdrant-disabled", reason="Qdrant URL not configured")
            return

        texts = [record.chunk.chunk_content for record in chunk_records]
        embeddings = await self._embedding_client.embed_texts(texts)

        if len(embeddings) != len(chunk_records):
            raise RuntimeError(
                "The number of embeddings does not match the number of chunks"
            )

        await self._vector_store.upsert_document_embeddings(
            document=document,
            chunk_records=chunk_records,
            embeddings=embeddings,
            document_metadata=document_metadata,
        )

    async def search_chunks(
        self,
        *,
        chunk_repo: DocumentChunkRepository,
        user_id: int,
        query: str,
        limit: int = 5,
        score_threshold: float | None = None,
        document_ids: Sequence[int] | None = None,
    ) -> list[VectorSearchResult]:
        if not query.strip():
            return []

        if not self._embedding_client.is_enabled:
            logger.info(
                "embedding-disabled", reason="OpenRouter API key not configured"
            )
            return []

        if not self._vector_store.is_enabled:
            logger.info("qdrant-disabled", reason="Qdrant URL not configured")
            return []

        embeddings = await self._embedding_client.embed_texts([query])
        if not embeddings:
            return []

        search_results = await self._vector_store.search_document_embeddings(
            user_id=user_id,
            query_embedding=embeddings[0],
            limit=limit,
            score_threshold=score_threshold,
            document_ids=document_ids,
        )

        if not search_results:
            return []

        chunk_ids: list[int] = []
        for point in search_results:
            payload = getattr(point, "payload", {}) or {}
            chunk_id = payload.get("chunk_id") or getattr(point, "id", None)
            if isinstance(chunk_id, str) and chunk_id.isdigit():
                chunk_id = int(chunk_id)
            if isinstance(chunk_id, int):
                chunk_ids.append(chunk_id)

        if not chunk_ids:
            return []

        chunks = await chunk_repo.get_many_by_ids(chunk_ids)
        chunk_map = {chunk.chunk_id: chunk for chunk in chunks}

        results: list[VectorSearchResult] = []
        for point in search_results:
            payload = getattr(point, "payload", {}) or {}
            chunk_id = payload.get("chunk_id") or getattr(point, "id", None)
            if isinstance(chunk_id, str) and chunk_id.isdigit():
                chunk_id = int(chunk_id)
            chunk = chunk_map.get(chunk_id)
            if not chunk:
                continue

            results.append(
                VectorSearchResult(
                    chunk=chunk,
                    score=getattr(point, "score", 0.0),
                    payload=payload,
                )
            )

        return results
