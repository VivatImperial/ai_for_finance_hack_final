from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from db.base import session_factory
from db.models import Role, User
from db.repositories.user_repo import UserRepository
from internal.security import verify_token


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    db = session_factory()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


Db = Annotated[AsyncSession, Depends(get_db)]


security = HTTPBearer()


async def get_current_user(
    db: Db,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    token = credentials.credentials
    email = verify_token(token)
    user_repo = UserRepository(db)

    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await user_repo.get_by_email(email)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


UserAuthChecker = Depends(get_current_user)
CtxUser = Annotated[User, Depends(get_current_user)]


async def check_admin_role(
    user: CtxUser,
) -> None:
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an admin",
        )


AdminRoleChecker = Depends(check_admin_role)


# async def get_current_session(
#     db: Db,
#     user: CtxUser,
#     session_id: int,
# ) -> Session:
#     stmt = (
#         select(Session)
#         .options(selectinload(Session.messages), selectinload(Session.scenario))
#         .filter(Session.session_id == session_id, Session.user_id == user.user_id)
#     )
#     result = await db.execute(stmt)
#     session = result.scalar_one_or_none()
#     if not session:
#         raise HTTPException(status_code=404)
#
#     if session.user != user:
#         raise HTTPException(status_code=403)
#
#     return session
#
#
# CurrentSession = Annotated[Session, Depends(get_current_session)]
