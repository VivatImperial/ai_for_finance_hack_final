from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

M = TypeVar("M")


def set_attrs(instance: Any, values: dict) -> None:
    for k, v in values.items():
        setattr(instance, k, v)


class BaseRepository(Generic[M]):
    __model__: Type

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_one_by_id(self, pk: int) -> M | None:
        result = await self._db.execute(
            select(self.__model__).filter(self.__model__.id == pk)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> Sequence[M]:
        result = await self._db.execute(select(self.__model__))
        return result.scalars().all()

    async def create(self, obj: M) -> M:
        self._db.add(obj)
        await self._db.flush()
        return obj

    async def delete(self, *args: Any, **kwargs: Any) -> None:
        stmt = delete(self.__model__).where(*args).filter_by(**kwargs)
        await self._db.execute(stmt)
        await self._db.flush()

    async def save(self, obj: M, **attrs: Any) -> None:
        self._db.add(obj)
        set_attrs(obj, attrs)
        try:
            await self._db.flush((obj,))
        except IntegrityError as exc:
            await self._db.rollback()
            raise exc
