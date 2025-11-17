from __future__ import annotations

import mimetypes

import structlog

from db.models import User

from .client import MinioStorageClient


logger = structlog.get_logger(__name__)

storage_client = MinioStorageClient.from_settings()


async def upload_to_s3(file: bytes, filename: str, user: User) -> str:
    if not file:
        raise ValueError("File content is empty")

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    try:
        return await storage_client.upload_bytes(
            data=file,
            filename=filename,
            user_id=user.user_id,
            content_type=content_type,
            metadata={"username": user.username, "email": user.email},
        )
    except Exception as exc:
        logger.error(
            "minio-upload-failed",
            filename=filename,
            user_id=user.user_id,
            reason=str(exc),
        )
        raise
