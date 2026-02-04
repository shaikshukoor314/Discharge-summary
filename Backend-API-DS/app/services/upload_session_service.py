from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.document import Document, DocumentStatusEnum
from app.db.models.job import Job, JobStatusEnum
from app.db.models.patient import Patient
from app.db.models.upload_session import UploadSession, UploadSessionStatusEnum
from app.db.models.user import User
from app.services.storage_service import get_storage_service
from app.utils.image_utils import detect_file_kind
from app.utils.logger import get_logger

logger = get_logger(__name__)


class UploadSessionService:
    """Service for managing upload sessions."""

    def __init__(self) -> None:
        self.storage = get_storage_service()

    async def create_session(
        self,
        session: AsyncSession,
        user: User,
        patient_id: str,
    ) -> Optional[UploadSession]:
        """Create a new upload session."""
        # Verify patient exists and belongs to user's hospital
        patient = await session.scalar(
            select(Patient).where(
                Patient.patient_id == patient_id,
                Patient.hospital_id == user.hospital_id,
            )
        )
        if not patient:
            logger.warning(
                "upload_session.create_failed",
                reason="patient_not_found",
                patient_id=patient_id,
            )
            return None

        upload_session = UploadSession(
            user_id=user.user_id,
            patient_id=patient_id,
            status=UploadSessionStatusEnum.ACTIVE.value,
        )
        session.add(upload_session)
        await session.commit()

        logger.info(
            "upload_session.created",
            upload_session_id=upload_session.upload_session_id,
            patient_id=patient_id,
        )
        return upload_session

    async def get_session(
        self,
        session: AsyncSession,
        upload_session_id: str,
        user: User,
    ) -> Optional[UploadSession]:
        """Get upload session by ID."""
        return await session.scalar(
            select(UploadSession)
            .options(selectinload(UploadSession.documents))
            .options(selectinload(UploadSession.patient))
            .where(
                UploadSession.upload_session_id == upload_session_id,
                UploadSession.user_id == user.user_id,
            )
        )

    async def get_active_sessions(
        self,
        session: AsyncSession,
        user: User,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[UploadSession], int]:
        """Get active upload sessions for a user."""
        query = (
            select(UploadSession)
            .options(selectinload(UploadSession.documents))
            .options(selectinload(UploadSession.patient))
            .where(
                UploadSession.user_id == user.user_id,
                UploadSession.status == UploadSessionStatusEnum.ACTIVE.value,
            )
            .order_by(UploadSession.created_at.desc())
        )

        # Get total count
        all_sessions = (await session.scalars(query)).all()
        total = len(all_sessions)

        # Get paginated results
        query = query.limit(limit).offset(offset)
        sessions_list = (await session.scalars(query)).all()

        return list(sessions_list), total

    async def upload_file(
        self,
        session: AsyncSession,
        upload_session: UploadSession,
        user: User,
        file: UploadFile,
        doc_type: str,
    ) -> Optional[Document]:
        """Upload a file to an upload session."""
        if upload_session.status != UploadSessionStatusEnum.ACTIVE.value:
            logger.warning(
                "upload_session.upload_failed",
                reason="session_not_active",
                upload_session_id=upload_session.upload_session_id,
            )
            return None

        # Get patient for storage path
        patient = await session.get(Patient, upload_session.patient_id)
        if not patient:
            return None

        content = await file.read()
        document_id = str(uuid.uuid4())

        file_kind = detect_file_kind(file.filename or "", file.content_type or "")
        original_name = Path(file.filename or "").name
        if not original_name:
            default_ext = ".pdf" if file_kind == "pdf" else ".bin"
            original_name = f"original{default_ext}"

        # Patient-centric storage path structure:
        # {hospital_id}/{patient_id}/documents/{upload_session_id}/{doc_type}/{filename}
        base_storage_path = (
            f"{user.hospital_id}/{patient.patient_id}/documents/"
            f"{upload_session.upload_session_id}/{doc_type}"
        )

        original_content_type = file.content_type or (
            "application/pdf" if file_kind == "pdf" else "application/octet-stream"
        )

        original_path = f"{base_storage_path}/{original_name}"
        await self.storage.store_file(original_path, content, original_content_type)

        document = Document(
            document_id=document_id,
            upload_session_id=upload_session.upload_session_id,
            job_id=None,  # Will be set when committed
            patient_id=patient.patient_id,
            hospital_id=user.hospital_id,
            doc_type=doc_type,
            file_path=base_storage_path,
            original_file_path=original_path,
            original_filename=original_name,
            file_size=len(content),
            mime_type=original_content_type,
            status=DocumentStatusEnum.UPLOADED.value,
        )
        session.add(document)
        await session.commit()

        logger.info(
            "upload_session.file_uploaded",
            upload_session_id=upload_session.upload_session_id,
            document_id=document_id,
            filename=original_name,
        )
        return document

    async def delete_file(
        self,
        session: AsyncSession,
        upload_session: UploadSession,
        document_id: str,
    ) -> bool:
        """Delete a file from an upload session."""
        if upload_session.status != UploadSessionStatusEnum.ACTIVE.value:
            return False

        document = await session.scalar(
            select(Document).where(
                Document.document_id == document_id,
                Document.upload_session_id == upload_session.upload_session_id,
            )
        )
        if not document:
            return False

        # Delete from storage
        try:
            if document.original_file_path:
                await self.storage.delete_file(document.original_file_path)
            if document.file_path:
                await self.storage.delete_directory(document.file_path)
        except Exception as e:
            logger.warning("upload_session.file_delete_storage_error", error=str(e))

        # Delete from database
        await session.delete(document)
        await session.commit()

        logger.info(
            "upload_session.file_deleted",
            upload_session_id=upload_session.upload_session_id,
            document_id=document_id,
        )
        return True

    async def commit_session(
        self,
        session: AsyncSession,
        upload_session: UploadSession,
        user: User,
    ) -> Optional[Job]:
        """Commit an upload session - creates a job and links documents."""
        if upload_session.status != UploadSessionStatusEnum.ACTIVE.value:
            logger.warning(
                "upload_session.commit_failed",
                reason="session_not_active",
                upload_session_id=upload_session.upload_session_id,
            )
            return None

        # Get documents in session
        documents = (
            await session.scalars(
                select(Document).where(
                    Document.upload_session_id == upload_session.upload_session_id
                )
            )
        ).all()

        if not documents:
            logger.warning(
                "upload_session.commit_failed",
                reason="no_documents",
                upload_session_id=upload_session.upload_session_id,
            )
            return None

        # Create job
        job = Job(
            user_id=user.user_id,
            upload_session_id=upload_session.upload_session_id,
            status=JobStatusEnum.PENDING.value,
        )
        session.add(job)
        await session.flush()

        # Link documents to job and update status
        for doc in documents:
            doc.job_id = job.job_id
            doc.status = DocumentStatusEnum.COMMITTED.value

        # Update session status
        upload_session.status = UploadSessionStatusEnum.COMMITTED.value

        await session.commit()

        logger.info(
            "upload_session.committed",
            upload_session_id=upload_session.upload_session_id,
            job_id=job.job_id,
            documents_count=len(documents),
        )
        return job

    async def cancel_session(
        self,
        session: AsyncSession,
        upload_session: UploadSession,
    ) -> bool:
        """Cancel an upload session - deletes all files."""
        if upload_session.status != UploadSessionStatusEnum.ACTIVE.value:
            return False

        # Get documents
        documents = (
            await session.scalars(
                select(Document).where(
                    Document.upload_session_id == upload_session.upload_session_id
                )
            )
        ).all()

        # Delete files from storage
        for doc in documents:
            try:
                if doc.original_file_path:
                    await self.storage.delete_file(doc.original_file_path)
                if doc.file_path:
                    await self.storage.delete_directory(doc.file_path)
            except Exception as e:
                logger.warning("upload_session.cancel_storage_error", error=str(e))

        # Update session status (cascade will delete documents)
        upload_session.status = UploadSessionStatusEnum.CANCELLED.value

        # Delete session (and documents via cascade)
        await session.delete(upload_session)
        await session.commit()

        logger.info(
            "upload_session.cancelled",
            upload_session_id=upload_session.upload_session_id,
            documents_deleted=len(documents),
        )
        return True


_upload_session_service: Optional[UploadSessionService] = None


def get_upload_session_service() -> UploadSessionService:
    global _upload_session_service
    if _upload_session_service is None:
        _upload_session_service = UploadSessionService()
    return _upload_session_service
