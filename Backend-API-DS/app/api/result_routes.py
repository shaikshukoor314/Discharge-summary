from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.db.models.document import Document
from app.db.models.document_page import DocumentPage
from app.db.models.job import Job
from app.db.models.ocr_raw_text import OcrRawText
from app.db.models.ocr_spellchecked_text import OcrSpellcheckedText
from app.db.models.ocr_deidentified_text import OcrDeidentifiedText
from app.db.session import get_db_session
from app.schemas.result_schema import ResultResponse, ExtractionEntry, DocumentResult, EntityInfo, PageValidationRequest
from app.services.pipeline_service import get_pipeline_service
from app.utils.logger import get_logger

router = APIRouter(prefix="/result", tags=["result"])
logger = get_logger(__name__)


@router.get("/{job_id}", response_model=ResultResponse)
async def job_result(job_id: str, session: AsyncSession = Depends(get_db_session)) -> ResultResponse:
    """
    Retrieve comprehensive pipeline results for a job.
    
    Returns JSON format with:
    - job_id, status, timestamps
    - documents with all pages
    - each page with OCR, spell check, and de-identification results
    - entity information for de-identified content
    """
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    documents = (await session.scalars(select(Document).where(Document.job_id == job_id))).all()
    document_payload: list[DocumentResult] = []
    
    for doc in documents:
        pages = (
            await session.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == doc.document_id)
                .order_by(DocumentPage.page_number)
            )
        ).all()
        
        extraction_entries = []
        for page in pages:
            raw = await session.scalar(select(OcrRawText).where(OcrRawText.page_id == page.page_id))
            spellchecked = await session.scalar(
                select(OcrSpellcheckedText).where(OcrSpellcheckedText.page_id == page.page_id)
            )
            deid = await session.scalar(
                select(OcrDeidentifiedText).where(OcrDeidentifiedText.page_id == page.page_id)
            )
            
            # Use actual image path from database (set during pipeline processing)
            image_path = page.image_minio_path or f"{doc.file_path}/page_{page.page_number}.png"
            
            # Default values
            ocr_metadata = None
            spellcheck_metadata = None
            deid_metadata = None
            entities_found = None
            entities_count = None
            
            # Parse metadata if available (stored as JSON in the result)
            # Note: In production, store metadata as separate JSON fields or in MinIO
            
            # Get metadata from database
            ocr_metadata = raw.result_metadata if raw else None
            spellcheck_metadata = spellchecked.result_metadata if spellchecked else None
            deid_metadata = deid.result_metadata if deid else None
            entities_found = deid.entities_found if deid else None
            entities_count = deid.entities_count if deid else None
            
            extraction_entry = ExtractionEntry(
                page_id=page.page_id,
                page_number=page.page_number,
                image_path=image_path,
                extracted_text=raw.raw_text if raw else "",
                spellchecked_text=spellchecked.spellchecked_text if spellchecked else "",
                deid_text=deid.deid_text if deid else "",
                corrected_deid=deid.corrected_deid if deid else None,
                is_validated=deid.is_validated if deid else False,
                ocr_metadata=ocr_metadata,
                spellcheck_metadata=spellcheck_metadata,
                deid_metadata=deid_metadata,
                entities_found=entities_found,
                entities_count=entities_count,
            )
            extraction_entries.append(extraction_entry)
        
        document_result = DocumentResult(
            doc_id=doc.document_id,
            original_file_path=doc.original_file_path,
            patient_id=doc.patient_id,
            hospital_id=doc.hospital_id,
            doc_type=doc.doc_type,
            total_pages=len(extraction_entries),
            extraction=extraction_entries,
        )
        document_payload.append(document_result)

    return ResultResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at.isoformat() if job.created_at else None,
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
        document=document_payload
    )


@router.post("/page/{page_id}/validate")
async def validate_page(
    page_id: str,
    request: PageValidationRequest,
    pipeline_service=Depends(get_pipeline_service)
) -> dict:
    """
    Update the corrected de-identified text for a specific page.
    This updates both the database and the JSON result stored in MinIO.
    """
    success = await pipeline_service.update_validated_text(page_id, request.corrected_text)
    if not success:
        raise HTTPException(
            status_code=500, 
            detail="Failed to update validated text in database and MinIO"
        )
    return {"status": "success", "message": "Page validation updated successfully"}


@router.get("/{job_id}/json")
async def job_result_json(job_id: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    """
    Retrieve pipeline results as raw JSON format.
    Useful for direct API consumption without Pydantic validation.
    """
    result = await job_result(job_id, session)
    return result.model_dump()

