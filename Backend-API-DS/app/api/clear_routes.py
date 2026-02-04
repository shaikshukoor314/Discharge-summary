"""
Clear API routes for removing uploaded files before processing.
This allows users to remove incorrectly uploaded files from the frontend.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db_session
from app.db.models.document import Document
from app.db.models.job import Job
from app.services.storage_service import StorageService
from app.utils.logger import get_logger

router = APIRouter(prefix="/clear", tags=["clear"])
storage_service = StorageService()
logger = get_logger(__name__)


@router.post("/files/{job_id}")
async def clear_job_files(
    job_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Clear all files for a specific job from MinIO storage and optionally from database.
    This is useful when user uploads wrong files and wants to clear them before processing.
    
    Args:
        job_id: The job ID to clear files for
        session: Database session
    
    Returns:
        Dictionary with cleared file count and status
    """
    try:
        # Fetch the job
        result = await session.execute(
            select(Job).where(Job.job_id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Fetch all documents for this job
        result = await session.execute(
            select(Document).where(Document.job_id == job_id)
        )
        documents = result.scalars().all()
        
        if not documents:
            logger.info("clear.no_documents", job_id=job_id)
            return {
                "job_id": job_id,
                "cleared_files": 0,
                "cleared_documents": 0,
                "message": "No files found for this job"
            }
        
        # Clear files from MinIO for each document
        cleared_count = 0
        for document in documents:
            try:
                # Delete original file
                if document.original_file_path:
                    await storage_service.delete_file(document.original_file_path)
                
                # Delete entire document directory (includes all OCR, spellcheck, deid outputs)
                if document.document_id:
                    await storage_service.delete_directory(f"documents/{job_id}/{document.document_id}")
                
                cleared_count += 1
                logger.info(
                    "clear.file_cleared",
                    job_id=job_id,
                    document_id=document.document_id
                )
            except Exception as e:
                logger.warning(
                    "clear.file_clear_failed",
                    job_id=job_id,
                    document_id=document.document_id,
                    error=str(e)
                )
        
        logger.info(
            "clear.completed",
            job_id=job_id,
            cleared_files=cleared_count
        )
        
        return {
            "job_id": job_id,
            "cleared_files": cleared_count,
            "cleared_documents": len(documents),
            "status": "success",
            "message": f"Cleared {cleared_count} files from MinIO storage"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("clear.error", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing files: {str(e)}"
        )


@router.post("/document/{document_id}")
async def clear_document_files(
    document_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Clear files for a specific document from MinIO storage.
    Useful for clearing a single uploaded file that was incorrect.
    
    Args:
        document_id: The document ID to clear files for
        session: Database session
    
    Returns:
        Dictionary with cleared file count and status
    """
    try:
        # Fetch the document
        result = await session.execute(
            select(Document).where(Document.document_id == document_id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
        # Delete original file
        if document.original_file_path:
            await storage_service.delete_file(document.original_file_path)
        
        # Delete entire document directory
        await storage_service.delete_directory(f"documents/{document.job_id}/{document.document_id}")
        
        logger.info(
            "clear.document_cleared",
            document_id=document_id,
            job_id=document.job_id
        )
        
        return {
            "document_id": document_id,
            "job_id": document.job_id,
            "status": "success",
            "message": "Document files cleared from MinIO storage"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("clear.document_error", document_id=document_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing document files: {str(e)}"
        )


@router.post("/all/{job_id}")
async def clear_all_job_data(
    job_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Clear all files AND database records for a job.
    This completely removes the job and all its data.
    Use this when user wants a complete reset before re-uploading.
    
    Args:
        job_id: The job ID to clear completely
        session: Database session
    
    Returns:
        Dictionary with cleared data count and status
    """
    try:
        # Fetch the job
        result = await session.execute(
            select(Job).where(Job.job_id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Fetch all documents for this job
        result = await session.execute(
            select(Document).where(Document.job_id == job_id)
        )
        documents = result.scalars().all()
        
        # Delete files from MinIO
        cleared_count = 0
        for document in documents:
            try:
                if document.original_file_path:
                    await storage_service.delete_file(document.original_file_path)
                await storage_service.delete_directory(f"documents/{job_id}/{document.document_id}")
                cleared_count += 1
            except Exception as e:
                logger.warning(
                    "clear_all.file_clear_failed",
                    job_id=job_id,
                    document_id=document.document_id,
                    error=str(e)
                )
        
        # Delete database records (cascading delete via SQLAlchemy relationships)
        await session.delete(job)
        await session.commit()
        
        logger.info(
            "clear_all.completed",
            job_id=job_id,
            cleared_files=cleared_count,
            cleared_documents=len(documents)
        )
        
        return {
            "job_id": job_id,
            "cleared_files": cleared_count,
            "cleared_documents": len(documents),
            "status": "success",
            "message": f"Completely cleared job: {cleared_count} files and {len(documents)} documents removed"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("clear_all.error", job_id=job_id, error=str(e))
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing job data: {str(e)}"
        )
