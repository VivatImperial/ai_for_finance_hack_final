import structlog
from sqlalchemy import select

from db.base import session_factory
from db.models import User, Role
from db.repositories.base_repo import BaseRepository


logger = structlog.get_logger()


BASE_ADMIN_USERNAME = "admin"
BASE_ADMIN_EMAIL = "test"
BASE_ADMIN_PASSWORD = "test"


class UserRepository(BaseRepository[User]):
    __model__ = User

    async def get_by_email(self, email: str) -> User | None:
        return await self._db.scalar(select(User).filter(User.email == email))

    async def get_by_username(self, username: str) -> User | None:
        return await self._db.scalar(select(User).filter(User.username == username))

    async def create_base_admin(
        self, username: str, email: str, password: str
    ) -> User | None:
        user = User(
            username=username,
            email=email,
            hashed_password=User.get_password_hash(password),
            role=Role.ADMIN,
        )
        return await self.create(user)


async def create_default_admin():
    db = session_factory()
    try:
        repo = UserRepository(db)
        if await repo.create_base_admin(
            BASE_ADMIN_USERNAME, BASE_ADMIN_EMAIL, BASE_ADMIN_PASSWORD
        ):
            logger.info(
                "Created base admin",
                username=BASE_ADMIN_USERNAME,
                email=BASE_ADMIN_EMAIL,
                password=BASE_ADMIN_PASSWORD,
            )
            await db.commit()
            return
    except Exception as exc:
        logger.info("Error creating base admin", exc=str(exc))
    finally:
        await db.close()
