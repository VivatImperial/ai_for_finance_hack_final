from typing import Annotated

import structlog
from sqlalchemy import Integer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, mapped_column

from config import settings


class Base(DeclarativeBase): ...


logger = structlog.get_logger()


int_pk = Annotated[int, mapped_column(Integer, primary_key=True)]


def create_db_engine(db_url, **kwargs):
    return create_async_engine(url=db_url, **kwargs)


engine = create_db_engine(settings.db_url)

session_factory = async_sessionmaker(bind=engine)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def init_db():
    # await drop_tables()
    await create_tables()
