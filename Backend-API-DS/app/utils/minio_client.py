from __future__ import annotations

import asyncio
from functools import lru_cache
from io import BytesIO
from typing import BinaryIO

from minio import Minio

from app.config.settings import get_settings


class AsyncMinioClient:
    """Thin async wrapper around the MinIO SDK using thread executors."""

    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.minio_bucket
        self.endpoint = settings.minio_endpoint
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    async def ensure_bucket(self) -> None:
        try:
            exists = await asyncio.to_thread(
                self._client.bucket_exists,
                bucket_name=self.bucket,
            )
            if not exists:
                await asyncio.to_thread(self._client.make_bucket, bucket_name=self.bucket)
        except Exception as e:
            raise ConnectionError(f"MinIO connection failed: {e}. Please ensure MinIO is running on {self.endpoint}") from e

    async def upload(self, object_name: str, data: bytes, content_type: str) -> None:
        try:
            await self.ensure_bucket()
            stream = BytesIO(data)
            await asyncio.to_thread(
                self._client.put_object,
                bucket_name=self.bucket,
                object_name=object_name,
                data=stream,
                length=len(data),
                content_type=content_type,
            )
        except Exception as e:
            raise ConnectionError(f"Failed to upload to MinIO: {e}. Please ensure MinIO is running.") from e

    async def download(self, object_name: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                bucket_name=self.bucket,
                object_name=object_name,
            )
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception as e:
            raise ConnectionError(f"Failed to download from MinIO: {e}. Please ensure MinIO is running.") from e

    async def upload_stream(self, object_name: str, stream: BinaryIO, content_type: str) -> None:
        data = stream.read()
        await self.upload(object_name, data, content_type)

    async def delete_file(self, object_name: str) -> None:
        """Delete a single file from MinIO."""
        try:
            await self.ensure_bucket()
            await asyncio.to_thread(
                self._client.remove_object,
                bucket_name=self.bucket,
                object_name=object_name,
            )
        except Exception as e:
            raise ConnectionError(f"Failed to delete file from MinIO: {e}. Please ensure MinIO is running.") from e

    async def delete_directory(self, directory_path: str) -> None:
        """Delete all objects in a directory from MinIO."""
        try:
            await self.ensure_bucket()
            # List all objects with the directory prefix
            objects = await asyncio.to_thread(
                self._client.list_objects,
                bucket_name=self.bucket,
                prefix=directory_path,
                recursive=True,
            )
            
            # Delete each object
            for obj in objects:
                await asyncio.to_thread(
                    self._client.remove_object,
                    bucket_name=self.bucket,
                    object_name=obj.object_name,
                )
        except Exception as e:
            raise ConnectionError(f"Failed to delete directory from MinIO: {e}. Please ensure MinIO is running.") from e

    async def list_objects_in_directory(self, directory_path: str) -> list[str]:
        """List all object names (paths) in a directory from MinIO."""
        try:
            await self.ensure_bucket()
            objects = await asyncio.to_thread(
                self._client.list_objects,
                bucket_name=self.bucket,
                prefix=directory_path,
                recursive=True,
            )
            
            # Return list of object names
            return [obj.object_name for obj in objects]
        except Exception as e:
            # Return empty list if directory doesn't exist
            return []


@lru_cache
def get_minio_client() -> AsyncMinioClient:
    return AsyncMinioClient()

