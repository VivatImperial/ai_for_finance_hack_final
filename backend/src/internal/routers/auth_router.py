from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from config import settings
from db.models import User
from db.repositories.user_repo import UserRepository
from internal.dependencies import CtxUser, Db
from internal.schemas.auth import Token, UserCreate, UserLogin, UserResponse
from internal.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db: Db) -> UserResponse:
    user_repo = UserRepository(db)
    hashed_password = User.get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role,
    )

    try:
        user = await user_repo.create(new_user)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        )

    return UserResponse.model_validate(user)


@router.post("/login", response_model=Token)
async def login_user(user_data: UserLogin, db: Db) -> Token:
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(user_data.email)

    if not user or not user.verify_password(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: CtxUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
