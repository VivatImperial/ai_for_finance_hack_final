from typing import Sequence

from sqlalchemy import select

from db.models import Message
from db.repositories.base_repo import BaseRepository


class MessageRepository(BaseRepository[Message]):
    __model__ = Message

    async def get_last_for_chat(
        self, *, chat_id: int, limit: int = 20
    ) -> Sequence[Message]:
        stmt = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        messages = result.scalars().all()
        return list(reversed(messages))
