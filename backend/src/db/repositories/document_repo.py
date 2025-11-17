from typing import Sequence

from sqlalchemy import select, or_, exists
from sqlalchemy.orm import selectinload

from db.models import ParsedDocument, User
from db.repositories.base_repo import BaseRepository


class ParsedDocumentRepository(BaseRepository[ParsedDocument]):
    __model__ = ParsedDocument

    async def get_all_for_user(self, user: User) -> Sequence[ParsedDocument]:
        stmt = select(ParsedDocument).where(
            or_(ParsedDocument.user_id == user.id, ParsedDocument.is_general)
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def get_one_with_chunks_by_id(self, document_id: int) -> ParsedDocument:
        stmt = (
            select(ParsedDocument)
            .where(ParsedDocument.document_id == document_id)
            .options(selectinload(ParsedDocument.chunks))
        )
        result = await self._db.execute(stmt)
        return result.scalars().one_or_none()

    async def get_many_by_ids(
        self, document_ids: Sequence[int]
    ) -> Sequence[ParsedDocument]:
        if not document_ids:
            return []
        stmt = select(ParsedDocument).where(
            ParsedDocument.document_id.in_(document_ids)
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def check_document_exists(self, document_name: str, user: User) -> bool:
        stmt = select(
            exists().where(
                ParsedDocument.filename == document_name,
                or_(ParsedDocument.user_id == user.user_id, ParsedDocument.is_general),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar()
