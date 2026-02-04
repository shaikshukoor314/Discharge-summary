from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.job import Job
from app.db.session import get_db_session
from app.schemas.document_schema import DocumentOut, DocumentsResponse
from app.services.storage_service import get_storage_service
from app.utils.logger import get_logger

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)
storage_service = get_storage_service()


@router.get("", response_model=DocumentsResponse)
async def list_documents(
    patient_id: str = Query(...),
    hospital_id: str = Query(...),
    doc_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentsResponse:
    stmt = select(Document).where(Document.patient_id == patient_id, Document.hospital_id == hospital_id)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    if status_filter:
        stmt = stmt.where(Document.status == status_filter)

    documents = (await session.scalars(stmt)).all()
    return DocumentsResponse(documents=[DocumentOut.model_validate(doc, from_attributes=True) for doc in documents])


@router.delete("")
async def delete_records(
    patient_id: Optional[str] = Query(None),
    hospital_id: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    doc_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Delete records from database AND MinIO storage based on patient_id, hospital_id, job_id, and/or doc_id.
    
    At least one of the four parameters must be provided.
    
    Examples:
    - DELETE /documents?patient_id=p1 - Delete all documents for patient p1
    - DELETE /documents?hospital_id=h100 - Delete all documents for hospital h100
    - DELETE /documents?job_id=123 - Delete all documents for job 123
    - DELETE /documents?doc_id=doc123 - Delete specific document by ID
    - DELETE /documents?patient_id=p1&hospital_id=h100 - Delete documents for patient p1 in hospital h100
    - DELETE /documents?patient_id=p1&hospital_id=h100&job_id=123 - Delete specific job
    """
    # Validate at least one parameter is provided
    if not patient_id and not hospital_id and not job_id and not doc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of patient_id, hospital_id, job_id, or doc_id must be provided"
        )
    
    try:
        # First, retrieve all documents that match the criteria (before deleting)
        select_stmt = select(Document)
        filters = []
        
        if patient_id:
            filters.append(Document.patient_id == patient_id)
        if hospital_id:
            filters.append(Document.hospital_id == hospital_id)
        if job_id:
            filters.append(Document.job_id == job_id)
        if doc_id:
            filters.append(Document.document_id == doc_id)
        
        # Combine filters with AND logic
        if filters:
            for filter_condition in filters:
                select_stmt = select_stmt.where(filter_condition)
        
        # Get all documents that will be deleted
        documents_to_delete = (await session.scalars(select_stmt)).all()
        
        logger.info(
            "documents.delete_started",
            patient_id=patient_id,
            hospital_id=hospital_id,
            job_id=job_id,
            doc_id=doc_id,
            document_count=len(documents_to_delete)
        )
        
        # Delete from MinIO storage
        minio_deleted_count = 0
        minio_errors = []
        
        for doc in documents_to_delete:
            try:
                # Delete original file
                if doc.original_file_path:
                    await storage_service.delete_file(doc.original_file_path)
                    logger.info("documents.minio_file_deleted", file_path=doc.original_file_path)
                    minio_deleted_count += 1
                
                # Delete directory with all converted images and results
                if doc.file_path:
                    # Try to delete all files in the document's directory
                    try:
                        await storage_service.delete_directory(doc.file_path)
                        logger.info("documents.minio_directory_deleted", directory_path=doc.file_path)
                    except Exception as e:
                        # Directory deletion might fail if directory doesn't exist, log but continue
                        logger.warning(
                            "documents.minio_directory_delete_failed",
                            directory_path=doc.file_path,
                            error=str(e)
                        )
            
            except Exception as e:
                error_msg = f"Failed to delete MinIO file for document {doc.document_id}: {str(e)}"
                minio_errors.append(error_msg)
                logger.error("documents.minio_delete_error", document_id=doc.document_id, error=str(e))
        
        # Delete from database
        # Use the same select statement to identify documents, then delete them
        delete_stmt = delete(Document).where(select_stmt.whereclause is not None)
        
        # Build delete statement with the same filters
        if doc_id:
            delete_stmt = delete(Document).where(Document.document_id == doc_id)
        elif patient_id or hospital_id or job_id:
            delete_stmt = delete(Document)
            if patient_id:
                delete_stmt = delete_stmt.where(Document.patient_id == patient_id)
            if hospital_id:
                delete_stmt = delete_stmt.where(Document.hospital_id == hospital_id)
            if job_id:
                delete_stmt = delete_stmt.where(Document.job_id == job_id)
        
        # Execute delete
        result = await session.execute(delete_stmt)
        db_deleted_count = result.rowcount
        
        await session.commit()
        
        logger.info(
            "documents.deleted_successfully",
            patient_id=patient_id,
            hospital_id=hospital_id,
            job_id=job_id,
            doc_id=doc_id,
            db_deleted_count=db_deleted_count,
            minio_deleted_count=minio_deleted_count,
            minio_errors=len(minio_errors)
        )
        
        return {
            "message": f"Successfully deleted {db_deleted_count} record(s) from database and {minio_deleted_count} file(s) from MinIO storage",
            "database": {
                "deleted_count": db_deleted_count
            },
            "minio_storage": {
                "deleted_count": minio_deleted_count,
                "errors": minio_errors if minio_errors else []
            },
            "filters": {
                "patient_id": patient_id,
                "hospital_id": hospital_id,
                "job_id": job_id,
                "doc_id": doc_id
            }
        }
    
    except Exception as e:
        await session.rollback()
        logger.error(
            "documents.delete_error",
            error=str(e),
            patient_id=patient_id,
            hospital_id=hospital_id,
            job_id=job_id,
            doc_id=doc_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting records: {str(e)}"
        )

