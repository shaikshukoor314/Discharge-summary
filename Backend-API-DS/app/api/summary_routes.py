"""Summary generation and management API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.discharge_summary import DischargeSummary
from app.db.models.job import Job
from app.db.models.patient import Patient
from app.db.models.template import Template
from app.db.models.ocr_deidentified_text import OcrDeidentifiedText
from app.db.models.document_page import DocumentPage
from app.db.models.document import Document
from app.db.session import get_db_session
from app.schemas.summary_schema import (
    GenerateSummaryRequest,
    SummaryResponse,
    UpdateSummaryRequest
)
from app.services.summary_service import SummaryGenerationService
from app.utils.logger import get_logger

router = APIRouter(prefix="/summaries", tags=["summaries"])
logger = get_logger(__name__)


@router.post("/generate", response_model=SummaryResponse)
async def generate_summary(
    request: GenerateSummaryRequest,
    session: AsyncSession = Depends(get_db_session)
) -> SummaryResponse:
    """
    Generate a discharge summary using LLM.
    
    Process:
    1. Fetch validated OCR text from database
    2. Fetch template structure
    3. Fetch patient metadata
    4. Call LLM service to generate summary
    5. Save to discharge_summaries table
    6. Return summary response
    """
    # 1. Fetch job and validate
    job = await session.get(Job, request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before generating summary")
    
    # NEW: Check OCR checkpoint is completed
    checkpoints = job.checkpoints
    if isinstance(checkpoints, str):
        import json
        try:
            checkpoints = json.loads(checkpoints)
        except:
            checkpoints = {}
    elif checkpoints is None:
        checkpoints = {}
        
    if checkpoints.get("ocrCheckpoint") != "completed":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Cannot generate summary: OCR verification not completed",
                "checkpoints": checkpoints,
                "message": "Please complete OCR verification before generating summary"
            }
        )
    
    # 2. Fetch patient info through upload session
    from app.db.models.upload_session import UploadSession
    upload_session = await session.get(UploadSession, job.upload_session_id)
    if not upload_session:
        raise HTTPException(status_code=404, detail="Upload session not found for this job")
        
    patient = await session.get(Patient, upload_session.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # 3. Fetch template
    template = await session.get(Template, request.template_id)
    if not template or not template.is_active:
        raise HTTPException(status_code=404, detail="Template not found or inactive")
    
    # 4. Fetch all validated OCR text for this job
    documents = (await session.scalars(select(Document).where(Document.job_id == request.job_id))).all()
    
    all_text_parts = []
    for doc in documents:
        pages = (await session.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == doc.document_id)
            .order_by(DocumentPage.page_number)
        )).all()
        
        for page in pages:
            deid = await session.scalar(
                select(OcrDeidentifiedText).where(OcrDeidentifiedText.page_id == page.page_id)
            )
            if deid:
                # Use corrected text if validated, otherwise use original deid text
                text = deid.corrected_deid if deid.is_validated and deid.corrected_deid else deid.deid_text
                if text:
                    all_text_parts.append(f"--- Page {page.page_number} ---\n{text}")
    
    if not all_text_parts:
        raise HTTPException(status_code=400, detail="No validated text found for this job")
    
    validated_text = "\n\n".join(all_text_parts)
    
    # 5. Prepare template data
    template_data = {
        "id": template.template_id,
        "name": template.name,
        "description": template.description,
        "type": template.template_type,
        "category": template.category,
        "sections": template.sections
    }
    
    # 6. Prepare patient info
    patient_info = {
        "name": patient.full_name,
        "mrn": patient.medical_record_number,
        "dob": patient.date_of_birth.strftime("%Y-%m-%d") if patient.date_of_birth else "N/A",
        "gender": patient.gender or "N/A",
        "admission_date": job.created_at.strftime("%Y-%m-%d") if job.created_at else "N/A",
        "discharge_date": job.updated_at.strftime("%Y-%m-%d") if job.updated_at else "N/A"
    }
    
    # 7. Generate summary using LLM
    try:
        summary_service = SummaryGenerationService()
        summary_content = summary_service.generate_summary(
            validated_text=validated_text,
            template=template_data,
            patient_info=patient_info,
            custom_instructions=request.custom_instructions
        )
    except Exception as e:
        logger.error(f"Failed to generate summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")
    
    # 8. Save summary to database
    discharge_summary = DischargeSummary(
        job_id=request.job_id,
        patient_id=patient.patient_id,
        user_id=None,  # TODO: Get from auth context
        template_id=request.template_id,
        content=summary_content,
        status="draft"
    )
    
    session.add(discharge_summary)
    await session.commit()
    await session.refresh(discharge_summary)
    
    logger.info(f"Summary generated successfully: {discharge_summary.summary_id}")
    
    # 9. Return response
    return SummaryResponse(
        summary_id=discharge_summary.summary_id,
        job_id=discharge_summary.job_id,
        patient_id=discharge_summary.patient_id,
        template_id=discharge_summary.template_id,
        content=discharge_summary.content,
        status=discharge_summary.status,
        created_at=discharge_summary.created_at.isoformat(),
        updated_at=discharge_summary.updated_at.isoformat()
    )


@router.get("/{summary_id}", response_model=SummaryResponse)
async def get_summary(
    summary_id: str,
    session: AsyncSession = Depends(get_db_session)
) -> SummaryResponse:
    """Retrieve a discharge summary by ID."""
    summary = await session.get(DischargeSummary, summary_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    
    return SummaryResponse(
        summary_id=summary.summary_id,
        job_id=summary.job_id,
        patient_id=summary.patient_id,
        template_id=summary.template_id,
        content=summary.content,
        status=summary.status,
        created_at=summary.created_at.isoformat(),
        updated_at=summary.updated_at.isoformat()
    )


@router.patch("/{summary_id}", response_model=SummaryResponse)
async def update_summary(
    summary_id: str,
    request: UpdateSummaryRequest,
    session: AsyncSession = Depends(get_db_session)
) -> SummaryResponse:
    """Update a discharge summary (edit content, finalize, etc.)."""
    summary = await session.get(DischargeSummary, summary_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    
    # Update fields
    if request.content is not None:
        summary.content = request.content
    
    if request.status is not None:
        if request.status not in ["draft", "finalized", "signed"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        summary.status = request.status
        
        if request.status == "finalized":
            from datetime import datetime
            summary.finalized_at = datetime.utcnow()
    
    await session.commit()
    await session.refresh(summary)
    
    return SummaryResponse(
        summary_id=summary.summary_id,
        job_id=summary.job_id,
        patient_id=summary.patient_id,
        template_id=summary.template_id,
        content=summary.content,
        status=summary.status,
        created_at=summary.created_at.isoformat(),
        updated_at=summary.updated_at.isoformat()
    )


@router.get("/job/{job_id}", response_model=SummaryResponse | None)
async def get_summary_by_job(
    job_id: str,
    session: AsyncSession = Depends(get_db_session)
) -> SummaryResponse | None:
    """Get the discharge summary for a specific job."""
    summary = await session.scalar(
        select(DischargeSummary).where(DischargeSummary.job_id == job_id)
    )
    
    if not summary:
        return None
    
    return SummaryResponse(
        summary_id=summary.summary_id,
        job_id=summary.job_id,
        patient_id=summary.patient_id,
        template_id=summary.template_id,
        content=summary.content,
        status=summary.status,
        created_at=summary.created_at.isoformat(),
        updated_at=summary.updated_at.isoformat()
    )
