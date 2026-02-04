from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.models.document import Document
from app.db.models.job import Job
from app.db.session import get_db_session
from app.utils.logger import get_logger
from pydantic import BaseModel

logger = get_logger(__name__)

router = APIRouter(prefix="/commit", tags=["commit"])


class DocumentInfo(BaseModel):
    document_id: str
    patient_id: str
    hospital_id: str
    doc_type: str
    file_path: str
    original_file_path: Optional[str] = None
    status: str
    created_at: str
    updated_at: str


class CommitResponse(BaseModel):
    job_id: str
    job_status: str
    total_documents: int
    documents: List[DocumentInfo]


@router.get("/{job_id}", response_model=CommitResponse, status_code=status.HTTP_200_OK)
async def commit_documents(
    job_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> CommitResponse:
    """
    Retrieve all documents saved in MinIO for a specific job.
    
    Takes a job_id and returns all documents associated with that job,
    including their paths in MinIO storage.
    """
    try:
        # Get the job
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found"
            )
        
        # Get all documents for this job
        documents = (
            await session.scalars(
                select(Document).where(Document.job_id == job_id)
            )
        ).all()
        
        if not documents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No documents found for job ID {job_id}"
            )
        
        # Convert documents to response format
        document_list = [
            DocumentInfo(
                document_id=doc.document_id,
                patient_id=doc.patient_id,
                hospital_id=doc.hospital_id,
                doc_type=doc.doc_type,
                file_path=doc.file_path,
                original_file_path=doc.original_file_path,
                status=doc.status,
                created_at=str(doc.created_at),
                updated_at=str(doc.updated_at),
            )
            for doc in documents
        ]
        
        logger.info(
            "commit.documents_retrieved",
            job_id=job_id,
            document_count=len(document_list),
        )
        
        return CommitResponse(
            job_id=job_id,
            job_status=job.status,
            total_documents=len(document_list),
            documents=document_list,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "commit.retrieval_failed",
            job_id=job_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving documents: {str(e)}",
        ) from e
