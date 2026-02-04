from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.document_page import DocumentPage
from app.db.models.job import Job, JobStatusEnum
from app.db.models.ocr_deidentified_text import OcrDeidentifiedText
from app.db.models.ocr_raw_text import OcrRawText
from app.db.models.ocr_spellchecked_text import OcrSpellcheckedText
from app.db.session import get_db_session
from app.schemas.process_schema import FileStageStatus, StatusResponse
from app.services.pipeline_service import get_pipeline_service

router = APIRouter(prefix="/status", tags=["status"])
pipeline_service = get_pipeline_service()


@router.get("/{job_id}", response_model=StatusResponse)
async def job_status(job_id: str, session: AsyncSession = Depends(get_db_session)) -> StatusResponse:
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatusEnum.PENDING.value:
        await pipeline_service.ensure_started(job.job_id)
        return StatusResponse(
            job_id=job.job_id,
            status="Starting",
            message="Initializing processing...",
        )

    if job.status == JobStatusEnum.PROCESSING.value:
        await pipeline_service.ensure_started(job.job_id)

    files, progress = await _gather_progress(session, job.job_id)

    status_label = _format_status(job.status)
    if job.status == JobStatusEnum.PROCESSING.value:
        return StatusResponse(
            job_id=job.job_id,
            status=status_label,
            overall_progress=f"{progress:.0f}%",
            files=files,
        )

    if job.status == JobStatusEnum.COMPLETED.value:
        return StatusResponse(
            job_id=job.job_id,
            status=status_label,
            overall_progress="100%",
            files=files,
            message="Process Completed",
        )

    return StatusResponse(
        job_id=job.job_id,
        status=status_label if job.status != JobStatusEnum.FAILED.value else "Failed",
        message="Processing failed. Please retry the job.",
        files=files,
    )


async def _gather_progress(session: AsyncSession, job_id: str) -> tuple[List[FileStageStatus], float]:
    documents = (await session.scalars(select(Document).where(Document.job_id == job_id))).all()
    total_stage_slots = max(len(documents) * 3, 1)
    completed_slots = 0
    files: List[FileStageStatus] = []

    for doc in documents:
        total_pages = await session.scalar(
            select(func.count()).select_from(DocumentPage).where(DocumentPage.document_id == doc.document_id)
        ) or 0

        ocr_pages = await session.scalar(
            select(func.count())
            .select_from(OcrRawText)
            .join(DocumentPage, OcrRawText.page_id == DocumentPage.page_id)
            .where(DocumentPage.document_id == doc.document_id)
        ) or 0
        spell_pages = await session.scalar(
            select(func.count())
            .select_from(OcrSpellcheckedText)
            .join(DocumentPage, OcrSpellcheckedText.page_id == DocumentPage.page_id)
            .where(DocumentPage.document_id == doc.document_id)
        ) or 0
        deid_pages = await session.scalar(
            select(func.count())
            .select_from(OcrDeidentifiedText)
            .join(DocumentPage, OcrDeidentifiedText.page_id == DocumentPage.page_id)
            .where(DocumentPage.document_id == doc.document_id)
        ) or 0

        ocr_status = _stage_status(total_pages, ocr_pages)
        spell_status = _stage_status(total_pages, spell_pages)
        deid_status = _stage_status(total_pages, deid_pages)

        completed_slots += sum(status == "completed" for status in (ocr_status, spell_status, deid_status))

        files.append(
            FileStageStatus(
                file=Path(doc.original_file_path).name if doc.original_file_path else doc.document_id,
                ocr=ocr_status,
                spellcheck=spell_status,
                deid=deid_status,
            )
        )

    overall_progress = min((completed_slots / total_stage_slots) * 100, 100.0)
    return files, overall_progress


def _stage_status(total_pages: int, processed_pages: int) -> str:
    if total_pages == 0:
        return "pending"
    if processed_pages == 0:
        return "pending"
    if processed_pages >= total_pages:
        return "completed"
    return "in-progress"


def _format_status(status: str) -> str:
    if status == JobStatusEnum.PROCESSING.value:
        return "In-Progress"
    if status == JobStatusEnum.COMPLETED.value:
        return "Completed"
    if status == JobStatusEnum.FAILED.value:
        return "Failed"
    return status.capitalize()

