import enum
from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy import (
    String,
    TypeDecorator,
    Integer,
    ForeignKey,
    TEXT,
    Index,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, synonym, relationship
from sqlalchemy import func

from db.base import Base, int_pk


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class IntEnum(TypeDecorator):
    impl = Integer

    def __init__(self, enumtype, *args, **kwargs):
        super(IntEnum, self).__init__(*args, **kwargs)
        self._enumtype = enumtype

    def process_bind_param(self, value, dialect):
        if isinstance(value, int):
            return value

        return value.value

    def process_result_value(self, value, dialect):
        return self._enumtype(value)


class Role(enum.IntEnum):
    ADMIN = 1
    USER = 0


class MessageType(enum.IntEnum):
    MODEL = 1
    USER = 0


class User(Base):
    __tablename__ = "user"

    user_id: Mapped[int_pk] = mapped_column()
    username: Mapped[str] = mapped_column(String(100), unique=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(IntEnum(Role), default=Role.USER)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    id: Mapped[int] = synonym("user_id")

    chats: Mapped[list["Chat"]] = relationship(
        "Chat",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    documents: Mapped[list["ParsedDocument"]] = relationship(
        "ParsedDocument", back_populates="user"
    )

    def verify_password(self, plain_password: str) -> bool:
        return pwd_context.verify(plain_password, self.hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)


class Prompt(Base):
    __tablename__ = "prompt"

    prompt_id: Mapped[int_pk] = mapped_column()
    text: Mapped[str] = mapped_column(TEXT)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    title: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    id: Mapped[int] = synonym("prompt_id")
    chats: Mapped[list["Chat"]] = relationship("Chat", back_populates="prompt")


class Chat(Base):
    __tablename__ = "chat"

    chat_id: Mapped[int_pk] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.user_id", ondelete="CASCADE"))
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompt.prompt_id"))

    id: Mapped[int] = synonym("chat_id")
    user: Mapped["User"] = relationship("User", back_populates="chats")
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="chats")
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index(
            "uq_one_active_chat_per_user",
            "user_id",
            "is_active",
            unique=True,
            postgresql_where=(is_active.is_(True)),
        ),
    )


class Message(Base):
    __tablename__ = "message"

    message_id: Mapped[int_pk] = mapped_column()
    message_type: Mapped[MessageType] = mapped_column(IntEnum(MessageType))
    content: Mapped[str] = mapped_column(TEXT)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    hidden_comments: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    documents_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), default=list, nullable=True
    )

    chat_id: Mapped[int] = mapped_column(ForeignKey("chat.chat_id", ondelete="CASCADE"))

    id: Mapped[int] = synonym("message_id")
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")
    attached_documents: Mapped[list["ParsedDocument"]] = relationship(
        "ParsedDocument",
        primaryjoin="foreign(ParsedDocument.document_id) == any_(Message.documents_ids)",
        viewonly=True,
        uselist=True,
    )


class ParsedDocument(Base):
    __tablename__ = "parsed_document"

    document_id: Mapped[int_pk] = mapped_column()
    content: Mapped[str] = mapped_column(TEXT, nullable=False)
    minio_url: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(200))
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    id: Mapped[int] = synonym("document_id")
    user: Mapped["User"] = relationship("User", back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @hybrid_property
    def is_general(self) -> bool:
        return self.user_id is None

    @is_general.inplace.expression
    @classmethod
    def _is_general(cls):
        return cls.user_id.is_(None)

    @hybrid_property
    def document_length(self) -> int:
        return len(self.content) if self.content else 0

    @document_length.inplace.expression
    @classmethod
    def _length(cls):
        return func.length(cls.content)


class DocumentChunk(Base):
    __tablename__ = "document_chunk"

    chunk_id: Mapped[int_pk] = mapped_column()
    chunk_content: Mapped[str] = mapped_column(TEXT)
    chunk_serial: Mapped[int] = mapped_column()
    document_id: Mapped[int] = mapped_column(
        ForeignKey("parsed_document.document_id", ondelete="CASCADE")
    )

    id: Mapped[int] = synonym("chunk_id")
    document: Mapped["ParsedDocument"] = relationship(
        "ParsedDocument", back_populates="chunks"
    )

    @hybrid_property
    def chunk_length(self) -> int:
        return len(self.chunk_content) if self.chunk_content else 0

    @chunk_length.inplace.expression
    @classmethod
    def chunk_length(cls):
        return func.length(cls.chunk_content)
