from typing import Sequence

from sqlalchemy import select

from db.models import DocumentChunk
from db.repositories.base_repo import BaseRepository


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    __model__ = DocumentChunk

    async def get_all_by_document_id(self, document_id: int) -> Sequence[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_serial)
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def get_many_by_ids(
        self, chunk_ids: Sequence[int]
    ) -> Sequence[DocumentChunk]:
        if not chunk_ids:
            return []

        stmt = select(DocumentChunk).where(DocumentChunk.chunk_id.in_(chunk_ids))
        result = await self._db.execute(stmt)
        return result.scalars().all()
