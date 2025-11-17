from pydantic import BaseModel

from db.models import Role


class UserBase(BaseModel):
    username: str
    email: str
    role: Role = Role.ADMIN


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

    class Config:
        from_attributes = True


class TokenData(BaseModel):
    username: str | None = None
