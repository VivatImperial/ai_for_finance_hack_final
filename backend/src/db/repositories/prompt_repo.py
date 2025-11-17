from sqlalchemy import select

from db.models import Prompt
from db.repositories.base_repo import BaseRepository


class PromptRepository(BaseRepository[Prompt]):
    __model__ = Prompt

    async def get_by_title(self, title: str) -> Prompt | None:
        stmt = select(Prompt).where(Prompt.title == title)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_prompt(
        self, *, title: str, text: str, params: dict | None = None
    ) -> Prompt:
        prompt = await self.get_by_title(title)
        payload = params or {}
        if prompt:
            prompt.text = text
            prompt.params = payload
            await self._db.flush()
            return prompt

        prompt = Prompt(title=title, text=text, params=payload)
        await self.create(prompt)
        return prompt
