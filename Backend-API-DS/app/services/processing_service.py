from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document, DocumentStatusEnum
from app.db.models.job import Job, JobStatusEnum
from app.utils.logger import get_logger

# Import pipeline service for direct async processing (no Celery/Redis required)
from app.services.pipeline_service import get_pipeline_service

logger = get_logger(__name__)


class ProcessingService:
    def __init__(self) -> None:
        self._pipeline_service = None
    
    def _get_pipeline_service(self):
        """Lazy load pipeline service to avoid circular imports."""
        if self._pipeline_service is None:
            self._pipeline_service = get_pipeline_service()
        return self._pipeline_service

    async def start_job(self, session: AsyncSession, job_id: str) -> None:
        job = await session.scalar(select(Job).where(Job.job_id == job_id))
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatusEnum.PROCESSING.value

        documents = (await session.scalars(select(Document).where(Document.job_id == job_id))).all()
        for doc in documents:
            doc.status = DocumentStatusEnum.PROCESSING.value

        await session.commit()
        logger.info("processing.job.started", job_id=job_id)
        
        # Use direct async processing instead of Celery (no Redis required)
        # This runs the pipeline asynchronously in the background
        pipeline_service = self._get_pipeline_service()
        await pipeline_service.ensure_started(job_id)


def get_processing_service() -> ProcessingService:
    return ProcessingService()

