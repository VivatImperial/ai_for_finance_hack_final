from __future__ import annotations

from typing import Any

import structlog
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_413_REQUEST_ENTITY_TOO_LARGE

from db.models import DocumentChunk, ParsedDocument, User
from db.repositories.chunk_repo import DocumentChunkRepository
from db.repositories.document_repo import ParsedDocumentRepository
from services.s3.s3_test import upload_to_s3

from .chunk_splitter import ChunkSplitter
from .models import DocumentChunkPayload, MarkdownDocument
from .parser import DocumentParser
from .vector_manager import ChunkRecord, DocumentVectorManager


logger = structlog.get_logger(__name__)


class DocumentExistsError(Exception): ...


class DocumentUploadPipeline:
    def __init__(
        self,
        *,
        max_file_size_bytes: int,
        parser: DocumentParser | None = None,
        chunk_splitter: ChunkSplitter | None = None,
        vector_manager: DocumentVectorManager | None = None,
    ) -> None:
        self._max_file_size_bytes = max_file_size_bytes
        self._parser_instance = parser  # Store parser instance, but don't create it yet
        self._chunk_splitter = chunk_splitter or ChunkSplitter()
        self._vector_manager = vector_manager or DocumentVectorManager()

    @property
    def _parser(self) -> DocumentParser:
        """Lazy initialization of parser to avoid import errors at module level"""
        if self._parser_instance is None:
            self._parser_instance = DocumentParser()
        return self._parser_instance

    async def handle(
        self, file: UploadFile, db: AsyncSession, user: User
    ) -> ParsedDocument:
        filename = file.filename or "uploaded_document"

        doc_repo = ParsedDocumentRepository(db)
        if await doc_repo.check_document_exists(filename, user):
            raise DocumentExistsError

        content_bytes = await file.read()
        self._ensure_file_size(content_bytes)
        minio_url = await upload_to_s3(content_bytes, filename, user)

        markdown_doc = await self._parse_document(
            content_bytes=content_bytes,
            filename=filename,
        )
        chunk_payloads = self._chunk_splitter.split(markdown_doc)

        chunk_repo = DocumentChunkRepository(db)

        document = ParsedDocument(
            content=markdown_doc.content,
            user=user,
            filename=filename,
            minio_url=minio_url,
        )

        try:
            await doc_repo.create(document)
            await db.flush()
            await db.refresh(document)

            stored_chunks = await self._store_chunks(
                chunk_repo=chunk_repo,
                document=document,
                chunk_payloads=chunk_payloads,
            )

            await self._index_chunks(
                document=document,
                chunk_records=stored_chunks,
                document_metadata=markdown_doc.metadata,
            )

        except Exception as exc:
            logger.error(
                "document-processing-failed",
                filename=filename,
                reason=str(exc),
            )
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Failed to process document",
            ) from exc

        return document

    def _ensure_file_size(self, content_bytes: bytes) -> None:
        if len(content_bytes) > self._max_file_size_bytes:
            raise HTTPException(
                status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File is too large",
            )

    async def _parse_document(
        self,
        *,
        content_bytes: bytes,
        filename: str | None,
    ) -> MarkdownDocument:
        try:
            markdown_doc = await self._parser.parse(
                content_bytes=content_bytes,
                filename=filename,
            )
        except Exception as exc:
            logger.error(
                "document-parse-failed",
                filename=filename,
                reason=str(exc),
            )
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Failed to parse document",
            ) from exc

        if not markdown_doc.content.strip():
            logger.error(
                "document-parse-empty-result",
                filename=filename,
            )
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Parsed document is empty",
            )

        return markdown_doc

    async def _store_chunks(
        self,
        *,
        chunk_repo: DocumentChunkRepository,
        document: ParsedDocument,
        chunk_payloads: list[DocumentChunkPayload],
    ) -> list[ChunkRecord]:
        stored_chunks: list[ChunkRecord] = []

        for payload in chunk_payloads:
            chunk_content = payload.content
            serial = payload.serial

            doc_chunk = DocumentChunk(
                chunk_content=chunk_content,
                chunk_serial=serial,
                document=document,
            )
            await chunk_repo.create(doc_chunk)
            stored_chunks.append(
                ChunkRecord(chunk=doc_chunk, metadata=payload.metadata)
            )

        return stored_chunks

    async def _index_chunks(
        self,
        *,
        document: ParsedDocument,
        chunk_records: list[ChunkRecord],
        document_metadata: dict[str, Any] | None,
    ) -> None:
        if not chunk_records:
            return

        try:
            await self._vector_manager.index_document(
                document=document,
                chunk_records=chunk_records,
                document_metadata=document_metadata,
            )
        except Exception as exc:
            logger.error(
                "document-vector-index-failed",
                document_id=document.document_id,
                reason=str(exc),
            )
