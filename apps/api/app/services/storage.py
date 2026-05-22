from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote
from uuid import UUID

from minio import Minio

from app.core.config import get_settings


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    object_name: str
    url: str


class ObjectStorageService:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket_name = settings.minio_bucket_videos
        self.secure = settings.minio_secure
        self.endpoint = settings.minio_endpoint
        self.client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def ensure_bucket_exists(self) -> None:
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    def upload_stream(
        self,
        *,
        video_id: UUID,
        filename: str,
        data: BinaryIO,
        length: int,
        content_type: str | None = None,
        object_name: str | None = None,
    ) -> StoredObject:
        safe_filename = make_safe_filename(filename)
        resolved_object_name = object_name or f"videos/{video_id}/original/{safe_filename}"

        self.ensure_bucket_exists()
        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=resolved_object_name,
                data=data,
                length=length,
                content_type=content_type or "application/octet-stream",
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to upload object {self.bucket_name}/{resolved_object_name}: {exc}"
            ) from exc
        return StoredObject(
            bucket=self.bucket_name,
            object_name=resolved_object_name,
            url=self.build_object_url(resolved_object_name),
        )

    def download_object(
        self,
        bucket: str,
        object_name: str,
        destination_path: str,
    ) -> None:
        try:
            self.client.fget_object(
                bucket_name=bucket,
                object_name=object_name,
                file_path=destination_path,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to download object {bucket}/{object_name}: {exc}"
            ) from exc

    def delete_object(self, bucket: str, object_name: str) -> None:
        self.client.remove_object(bucket, object_name)

    def build_object_url(self, object_name: str) -> str:
        scheme = "https" if self.secure else "http"
        encoded_object_name = quote(object_name, safe="/")
        return f"{scheme}://{self.endpoint}/{self.bucket_name}/{encoded_object_name}"


@lru_cache
def get_storage_service() -> ObjectStorageService:
    return ObjectStorageService()


def make_safe_filename(filename: str) -> str:
    base_name = Path(filename).name.strip()
    if not base_name:
        return "upload.bin"

    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)
    return safe_name or "upload.bin"
