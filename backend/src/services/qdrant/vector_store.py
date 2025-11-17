from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

import structlog

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from config import settings

if TYPE_CHECKING:
    from services.document_processing.vector_manager import ChunkRecord

logger = structlog.get_logger(__name__)


class QdrantVectorStore:
    DEFAULT_COLLECTION_NAME = "document_chunks"

    def __init__(
        self,
        *,
        url: str | None,
        collection_name: str | None = None,
        batch_size: int = 64,
    ) -> None:
        self._url = url
        self._collection_name = collection_name or self.DEFAULT_COLLECTION_NAME
        self._batch_size = batch_size
        self._client: AsyncQdrantClient | None = (
            AsyncQdrantClient(url=url, prefer_grpc=False) if url else None
        )

    @classmethod
    def from_settings(cls) -> "QdrantVectorStore":
        return cls(
            url=getattr(settings, "QDRANT_URL", None),
            collection_name=getattr(settings, "QDRANT_COLLECTION_NAME", None),
            batch_size=int(getattr(settings, "QDRANT_BATCH_SIZE", 64)),
        )

    @property
    def is_enabled(self) -> bool:
        return self._client is not None

    async def upsert_document_embeddings(
        self,
        *,
        document,
        chunk_records: Sequence["ChunkRecord"],
        embeddings: Sequence[Sequence[float]],
        document_metadata: dict | None,
    ) -> None:
        if not self.is_enabled or not self._client:
            return

        if not embeddings:
            logger.warning("qdrant-no-embeddings", document_id=document.document_id)
            return

        vector_size = len(embeddings[0])
        await self._ensure_collection(vector_size)

        points: list[PointStruct] = []
        for chunk_record, embedding in zip(chunk_records, embeddings):
            point_payload = {
                "document_id": document.document_id,
                "chunk_id": chunk_record.chunk.chunk_id,
                "chunk_serial": chunk_record.chunk.chunk_serial,
                "user_id": document.user_id,
                "filename": document.filename,
                "minio_url": document.minio_url,
                "document_created_at": getattr(document, "created_at", None).isoformat()
                if getattr(document, "created_at", None)
                else None,
                "document_metadata": document_metadata or {},
                "chunk_metadata": chunk_record.metadata or {},
                "chunk_content": getattr(
                    getattr(chunk_record, "chunk", None), "chunk_content", None
                ),
            }

            points.append(
                PointStruct(
                    id=chunk_record.chunk.chunk_id,
                    vector=list(embedding),
                    payload=point_payload,
                )
            )

        for start in range(0, len(points), self._batch_size):
            batch = points[start : start + self._batch_size]
            await self._client.upsert(
                collection_name=self._collection_name,
                points=batch,
                wait=True,
            )

        logger.info(
            "qdrant-upsert-success",
            document_id=document.document_id,
            collection=self._collection_name,
            points=len(points),
        )

    async def _ensure_collection(self, vector_size: int) -> None:
        if not self._client:
            return

        try:
            collection_info = await self._client.get_collection(self._collection_name)
        except UnexpectedResponse as exc:
            if (
                getattr(exc, "status_code", None) != 404
                and "not found" not in str(exc).lower()
            ):
                raise
            await self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info(
                "qdrant-collection-created",
                collection=self._collection_name,
                vector_size=vector_size,
            )
        except Exception as exc:
            if "not found" not in str(exc).lower():
                raise
            await self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info(
                "qdrant-collection-created",
                collection=self._collection_name,
                vector_size=vector_size,
            )
        else:
            params = getattr(collection_info.config.params, "vectors", None)
            current_size = getattr(params, "size", None) if params else None
            if current_size and current_size != vector_size:
                logger.warning(
                    "qdrant-vector-size-mismatch",
                    collection=self._collection_name,
                    stored_size=current_size,
                    required_size=vector_size,
                    action="recreate_collection",
                )
                await self._client.recreate_collection(
                    collection_name=self._collection_name,
                    vectors_config=VectorParams(
                        size=vector_size, distance=Distance.COSINE
                    ),
                )
                logger.info(
                    "qdrant-collection-recreated",
                    collection=self._collection_name,
                    vector_size=vector_size,
                )

    async def drop_collection(self) -> None:
        if not self._client:
            return

        try:
            await self._client.delete_collection(collection_name=self._collection_name)
            logger.info(
                "qdrant-collection-dropped",
                collection=self._collection_name,
            )
        except UnexpectedResponse as exc:
            status = getattr(exc, "status_code", None)
            if status == 404:
                logger.info(
                    "qdrant-collection-drop-missed",
                    collection=self._collection_name,
                    reason="collection not found",
                )
            else:
                raise
        except Exception as exc:
            if "not found" in str(exc).lower():
                logger.info(
                    "qdrant-collection-drop-missed",
                    collection=self._collection_name,
                    reason="collection not found",
                )
            else:
                raise

    async def search_document_embeddings(
        self,
        *,
        user_id: int,
        query_embedding: Sequence[float],
        limit: int,
        score_threshold: float | None = None,
        document_ids: Sequence[int] | None = None,
        extra_filter_conditions: Sequence[FieldCondition] | None = None,
    ):
        if not self.is_enabled or not self._client:
            return []

        filter_conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=user_id))
        ]

        if document_ids:
            filter_conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchAny(any=[int(doc_id) for doc_id in document_ids]),
                )
            )

        if extra_filter_conditions:
            filter_conditions.extend(extra_filter_conditions)

        qdrant_filter = Filter(must=filter_conditions)

        results = await self._client.search(
            collection_name=self._collection_name,
            query_vector=list(query_embedding),
            limit=limit,
            query_filter=qdrant_filter,
            with_payload=True,
            with_vectors=False,
        )

        if score_threshold is None:
            return results

        filtered_results = [
            point
            for point in results
            if getattr(point, "score", 0.0) >= score_threshold
        ]
        return filtered_results
