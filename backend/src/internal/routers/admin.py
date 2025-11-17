import structlog
from sqladmin import ModelView, Admin
from sqladmin.authentication import AuthenticationBackend
from sqladmin.fields import SelectField
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.requests import Request
from wtforms import TextAreaField
from wtforms.validators import DataRequired

from config import settings
from db.base import session_factory
from db.models import (
    User,
    Role,
    ParsedDocument,
    DocumentChunk,
    Chat,
    Message,
    MessageType,
    Prompt,
)
from db.repositories.user_repo import UserRepository

logger = structlog.get_logger(__name__)


class GayError(Exception):
    def __str__(self):
        return "🏳️‍🌈 GayError"


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        logger.info(f"{username=}, {password=}")

        if not username or not password:
            return False

        try:
            async with session_factory() as db:
                user_repo = UserRepository(db)
                user = await user_repo.get_by_username(username)

                if user and user.verify_password(password) and user.role == Role.ADMIN:
                    request.session.update(
                        {
                            "user_id": str(user.user_id),
                            "role": "ADMIN",
                        }
                    )
                    return True

                raise GayError

        except Exception as e:
            logger.error("Error while admin login", username=username, error=str(e))

        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        user_id = request.session.get("user_id")
        role = request.session.get("role")

        if user_id and role == "ADMIN":
            return True

        return False


class UserAdmin(ModelView, model=User):
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True

    form_include_pk = False
    form_excluded_columns = [User.user_id, User.created_at, User.hashed_password]

    column_list = [User.id, User.username, User.email, User.role, User.created_at]
    column_searchable_list = [User.username, User.email]
    column_sortable_list = [User.created_at]

    form_overrides = {"role": SelectField}

    form_args = {
        "role": {
            "choices": [
                (Role.ADMIN, "🏳️‍🌈 Администратор"),
                (Role.USER, "👤 Пользователь"),
            ],
            "validators": [DataRequired()],
            "coerce": int,
        }
    }


class PromptAdmin(ModelView, model=Prompt):
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True

    form_include_pk = False
    form_excluded_columns = [Prompt.created_at, Prompt.chats]

    column_list = [Prompt.prompt_id, Prompt.title, Prompt.created_at]
    column_details_list = [
        Prompt.prompt_id,
        Prompt.title,
        Prompt.text,
        Prompt.params,
        Prompt.created_at,
    ]
    column_searchable_list = [Prompt.title, Prompt.text]
    column_sortable_list = [Prompt.created_at]

    form_overrides = {"text": TextAreaField}


class DocumentAdmin(ModelView, model=ParsedDocument):
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True

    column_list = [
        ParsedDocument.id,
        ParsedDocument.user_id,
        ParsedDocument.is_general,
        ParsedDocument.created_at,
        ParsedDocument.filename,
    ]
    column_searchable_list = [ParsedDocument.minio_url, ParsedDocument.content]
    column_sortable_list = [ParsedDocument.created_at, ParsedDocument.user_id]

    @staticmethod
    def _is_general_formatter(model, attribute):
        return "Yes" if model.is_general else "No"

    column_formatters = {"is_general": _is_general_formatter}


class DocumentChunkAdmin(ModelView, model=DocumentChunk):
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True

    column_list = [
        DocumentChunk.id,
        DocumentChunk.document_id,
        DocumentChunk.chunk_length,
    ]
    column_searchable_list = [DocumentChunk.chunk_content, DocumentChunk.document_id]
    column_sortable_list = [DocumentChunk.chunk_length]


class ChatAdmin(ModelView, model=Chat):
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True

    column_list = [
        Chat.id,
        Chat.user_id,
        Chat.prompt_id,
        Chat.is_active,
        Chat.created_at,
    ]
    column_searchable_list = [Chat.user_id]
    column_sortable_list = [Chat.is_active, Chat.created_at]

    @staticmethod
    def _is_active_formatter(model, attribute):
        return "Active" if model.is_active else "Inactive"

    column_formatters = {"is_active": _is_active_formatter}


class MessageAdmin(ModelView, model=Message):
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True

    column_list = [
        Message.id,
        Message.message_type,
        Message.created_at,
        Message.chat_id,
    ]
    column_searchable_list = [Message.content, Message.chat_id]
    column_sortable_list = [Message.created_at, Message.chat_id]

    @staticmethod
    def _message_type_formatter(model, attribute):
        return "Model" if model.message_type == MessageType.MODEL else "User"

    column_formatters = {"message_type": _message_type_formatter}


def setup_admin(app, engine: AsyncEngine):
    authentication_backend = AdminAuth(secret_key=settings.ADMIN_SECRET_KEY)

    admin = Admin(
        app=app,
        engine=engine,
        authentication_backend=authentication_backend,
        title="Admin Panel",
    )

    admin.add_view(UserAdmin)
    admin.add_view(ChatAdmin)
    admin.add_view(MessageAdmin)
    admin.add_view(PromptAdmin)
    admin.add_view(DocumentChunkAdmin)
    admin.add_view(DocumentAdmin)
    logger.info("SQLAdmin configured successfully")
    return admin
