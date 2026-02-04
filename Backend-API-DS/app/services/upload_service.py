from __future__ import annotations

import uuid
from pathlib import Path
from typing import List

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document, DocumentStatusEnum
from app.db.models.job import Job, JobStatusEnum
from app.schemas.upload_schema import UploadMetadata
from app.services.storage_service import get_storage_service
from app.utils.image_utils import detect_file_kind
from app.utils.logger import get_logger

logger = get_logger(__name__)


class UploadService:
    def __init__(self) -> None:
        self.storage = get_storage_service()

    async def create_job_with_documents(
        self,
        session: AsyncSession,
        files: List[UploadFile],
        metadata: UploadMetadata,
    ) -> str:
        """Persist uploaded files and return the job identifier."""
        job = Job(status=JobStatusEnum.PENDING.value)
        session.add(job)
        await session.flush()

        for file in files:
            content = await file.read()
            document_id = str(uuid.uuid4())

            file_kind = detect_file_kind(file.filename or "", file.content_type or "")
            original_name = Path(file.filename or "").name
            if not original_name:
                default_ext = ".pdf" if file_kind == "pdf" else ".bin"
                original_name = f"original{default_ext}"
            
            # Extract doc_type value, defaulting to 'unknown' if not provided
            if metadata.doc_type:
                doc_type_value = metadata.doc_type.value if hasattr(metadata.doc_type, "value") else str(metadata.doc_type)
            else:
                doc_type_value = "unknown"
            
            # Patient-centric storage path: {hospital_id}/{patient_id}/documents/legacy/{doc_type}
            base_storage_path = f"{metadata.hospital_id}/{metadata.patient_id}/documents/legacy/{doc_type_value}"
            
            original_content_type = file.content_type or (
                "application/pdf" if file_kind == "pdf" else "application/octet-stream"
            )

            original_path = f"{base_storage_path}/{original_name}"
            await self.storage.store_file(original_path, content, original_content_type)

            document = Document(
                document_id=document_id,
                job_id=job.job_id,
                patient_id=metadata.patient_id,
                hospital_id=metadata.hospital_id,
                doc_type=doc_type_value,
                file_path=base_storage_path,
                original_file_path=original_path,
                original_filename=original_name,
                file_size=len(content),
                mime_type=original_content_type,
                status=DocumentStatusEnum.UPLOADED.value,
            )
            session.add(document)

        await session.commit()

        logger.info("upload.ingested", job_id=job.job_id, documents=len(files))
        return job.job_id


def get_upload_service() -> UploadService:
    return UploadService()

