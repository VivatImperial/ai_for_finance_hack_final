from __future__ import annotations

import asyncio
import io
import mimetypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote, urlparse
from uuid import uuid4

import structlog
from minio import Minio

from config import settings


logger = structlog.get_logger(__name__)


def _parse_endpoint(endpoint: str | None, use_ssl: bool) -> tuple[str, bool]:
    if not endpoint:
        return "", use_ssl

    parsed = urlparse(endpoint)
    if parsed.scheme and parsed.netloc:
        secure = parsed.scheme == "https"
        return parsed.netloc, secure

    return endpoint, use_ssl


@dataclass
class MinioConfig:
    endpoint: str
    secure: bool
    access_key: str
    secret_key: str
    bucket_name: str
    region: str | None
    public_endpoint: str


class MinioStorageClient:
    def __init__(self, config: MinioConfig) -> None:
        if not config.endpoint:
            raise RuntimeError("MINIO_ENDPOINT is not configured")
        if not config.access_key or not config.secret_key:
            raise RuntimeError("MINIO access credentials are not configured")

        self._config = config
        self._client = Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
            region=config.region,
        )
        self._bucket_checked = False
        self._bucket_lock = asyncio.Lock()

    @classmethod
    def from_settings(cls) -> "MinioStorageClient":
        endpoint, secure = _parse_endpoint(
            settings.MINIO_ENDPOINT, settings.MINIO_USE_SSL
        )
        public_endpoint = (
            settings.MINIO_PUBLIC_ENDPOINT
            or settings.MINIO_ENDPOINT
            or f"http{'s' if secure else ''}://{endpoint}"
        )

        config = MinioConfig(
            endpoint=endpoint,
            secure=secure,
            access_key=settings.MINIO_ACCESS_KEY or "",
            secret_key=settings.MINIO_SECRET_KEY or "",
            bucket_name=settings.MINIO_BUCKET_NAME,
            region=settings.MINIO_REGION,
            public_endpoint=public_endpoint,
        )
        return cls(config)

    async def upload_bytes(
        self,
        *,
        data: bytes,
        filename: str,
        user_id: int | None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        await self._ensure_bucket()

        object_name = self._build_object_name(filename=filename, user_id=user_id)
        mtype = (
            content_type
            or mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )
        meta = metadata or {}
        if user_id is not None:
            meta.setdefault("user-id", str(user_id))
        meta.setdefault("original-filename", filename)

        await asyncio.to_thread(
            self._client.put_object,
            self._config.bucket_name,
            object_name,
            io.BytesIO(data),
            len(data),
            content_type=mtype,
            metadata={k: str(v) for k, v in meta.items()},
        )

        url = self._build_browser_url(object_name)
        logger.info(
            "minio-upload-success",
            bucket=self._config.bucket_name,
            object_name=object_name,
            url=url,
        )
        return url

    async def _ensure_bucket(self) -> None:
        if self._bucket_checked:
            return

        async with self._bucket_lock:
            if self._bucket_checked:
                return

            exists = await asyncio.to_thread(
                self._client.bucket_exists, self._config.bucket_name
            )
            if not exists:
                make_bucket_kwargs: dict[str, Any] = {}
                if self._config.region:
                    make_bucket_kwargs["location"] = self._config.region
                await asyncio.to_thread(
                    self._client.make_bucket,
                    self._config.bucket_name,
                    **make_bucket_kwargs,
                )
                logger.info("minio-bucket-created", bucket=self._config.bucket_name)

            self._bucket_checked = True

    def _build_object_name(self, *, filename: str, user_id: int | None) -> str:
        timestamp = datetime.utcnow().strftime("%Y/%m/%d")
        unique_id = uuid4().hex
        extension = PurePosixPath(filename).suffix.lower()
        sanitized = extension if extension else ""
        user_segment = f"user-{user_id}" if user_id is not None else "common"
        object_path = (
            PurePosixPath(user_segment) / timestamp / f"{unique_id}{sanitized}"
        )
        return str(object_path)

    def _build_browser_url(self, object_name: str) -> str:
        base = self._config.public_endpoint.strip()
        if not base.startswith(("http://", "https://")):
            scheme = "https" if self._config.secure else "http"
            base = f"{scheme}://{base}"

        encoded_object = quote(object_name, safe="")  # safe="" forces encoding of /

        return f"{base.rstrip('/')}/browser/{self._config.bucket_name}/{encoded_object}"


class MinioNotConfiguredError(RuntimeError):
    pass
