from __future__ import annotations

import asyncio
from typing import Tuple

from app.utils.minio_client import get_minio_client
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StorageService:
    def __init__(self) -> None:
        self.client = get_minio_client()

    async def store_file(self, path: str, data: bytes, content_type: str) -> str:
        logger.info("storage.upload.start", path=path)
        await self.client.upload(path, data, content_type)
        logger.info("storage.upload.completed", path=path)
        return path

    async def retrieve_file(self, path: str) -> bytes:
        logger.info("storage.download.start", path=path)
        content = await self.client.download(path)
        logger.info("storage.download.completed", path=path)
        return content

    async def delete_file(self, path: str) -> None:
        """Delete a single file from MinIO storage."""
        logger.info("storage.delete_file.start", path=path)
        await self.client.delete_file(path)
        logger.info("storage.delete_file.completed", path=path)

    async def delete_directory(self, directory_path: str) -> None:
        """Delete all files in a directory from MinIO storage."""
        logger.info("storage.delete_directory.start", directory_path=directory_path)
        await self.client.delete_directory(directory_path)
        logger.info("storage.delete_directory.completed", directory_path=directory_path)


def get_storage_service() -> StorageService:
    return StorageService()

