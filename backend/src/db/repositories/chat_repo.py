from typing import Sequence

from sqlalchemy import update, select
from sqlalchemy.orm import selectinload

from db.models import Chat, Prompt, User, Message
from db.repositories.base_repo import BaseRepository


class ChatRepository(BaseRepository[Chat]):
    __model__ = Chat

    async def set_active(self, user: User, chat_id: int) -> None:
        await self._db.execute(
            update(Chat).where(Chat.user == user).values(is_active=False)
        )
        await self._db.execute(
            update(Chat).where(Chat.chat_id == chat_id).values(is_active=True)
        )

    async def create_new_chat(self, prompt: Prompt, user: User) -> Chat:
        chat = Chat(prompt_id=prompt.prompt_id, user=user)
        await self.set_active(chat_id=chat.id, user=user)
        await self.create(chat)

        stmt = (
            select(Chat)
            .options(
                selectinload(Chat.messages).selectinload(Message.attached_documents)
            )
            .options(selectinload(Chat.prompt))
            .where(Chat.id == chat.id)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one()

    async def get_all_for_user(self, user: User) -> Sequence[Chat]:
        stmt = select(Chat).where(
            Chat.user == user,
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def get_one_by_id(self, pk: int) -> Chat | None:
        from sqlalchemy.orm import selectinload

        stmt = (
            select(Chat)
            .where(Chat.id == pk)
            .options(
                selectinload(Chat.messages).selectinload(Message.attached_documents),
                selectinload(Chat.prompt),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()
