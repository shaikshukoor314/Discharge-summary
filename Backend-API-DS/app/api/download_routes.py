from __future__ import annotations

import io
import zipfile
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.document_page import DocumentPage
from app.db.models.ocr_raw_text import OcrRawText
from app.db.models.ocr_spellchecked_text import OcrSpellcheckedText
from app.db.models.ocr_deidentified_text import OcrDeidentifiedText
from app.db.session import get_db_session
from app.services.storage_service import get_storage_service
from app.utils.logger import get_logger
from app.utils.minio_client import get_minio_client

router = APIRouter(prefix="/download", tags=["download"])
logger = get_logger(__name__)
storage_service = get_storage_service()
minio_client = get_minio_client()


@router.get("/original")
async def download_original_file(
    patient_id: Optional[str] = Query(None),
    hospital_id: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Download original uploaded files.
    
    Query Parameters:
    - patient_id: Filter by patient
    - hospital_id: Filter by hospital
    - job_id: Filter by job
    - At least one parameter must be provided
    
    Returns a zip file if multiple documents, single file if one document.
    
    Examples:
    - GET /download/original?patient_id=p1
    - GET /download/original?hospital_id=h100
    - GET /download/original?job_id=123
    - GET /download/original?patient_id=p1&hospital_id=h100
    """
    if not patient_id and not hospital_id and not job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of patient_id, hospital_id, or job_id must be provided"
        )
    
    try:
        # Build query to find documents
        stmt = select(Document)
        if patient_id:
            stmt = stmt.where(Document.patient_id == patient_id)
        if hospital_id:
            stmt = stmt.where(Document.hospital_id == hospital_id)
        if job_id:
            stmt = stmt.where(Document.job_id == job_id)
        
        documents = (await session.scalars(stmt)).all()
        
        if not documents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No documents found matching the criteria"
            )
        
        logger.info(
            "download.original.start",
            patient_id=patient_id,
            hospital_id=hospital_id,
            job_id=job_id,
            documents_count=len(documents)
        )
        
        # If single document, return single file
        if len(documents) == 1:
            doc = documents[0]
            if not doc.original_file_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Original file path not found"
                )
            
            file_content = await storage_service.retrieve_file(doc.original_file_path)
            filename = Path(doc.original_file_path).name
            
            logger.info("download.original.single_file", filename=filename)
            
            return StreamingResponse(
                iter([file_content]),
                media_type="application/octet-stream",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
        # Multiple documents - return as zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for doc in documents:
                if doc.original_file_path:
                    file_content = await storage_service.retrieve_file(doc.original_file_path)
                    filename = Path(doc.original_file_path).name
                    zip_file.writestr(filename, file_content)
        
        zip_buffer.seek(0)
        
        logger.info("download.original.zip_file", documents_count=len(documents))
        
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=original_files.zip"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("download.original.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading files: {str(e)}"
        )


@router.get("/processed")
async def download_processed_files(
    patient_id: Optional[str] = Query(None),
    hospital_id: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    file_type: str = Query("all", pattern="^(ocr|spellcheck|deid|all)$"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Download processed (OCR, spell check, de-identification) files.
    
    Query Parameters:
    - patient_id: Filter by patient
    - hospital_id: Filter by hospital
    - job_id: Filter by job
    - file_type: Type of file to download (ocr|spellcheck|deid|all) - default: all
    - At least one of patient_id, hospital_id, job_id must be provided
    
    Returns a zip file with all matching processed files.
    
    Examples:
    - GET /download/processed?patient_id=p1&file_type=ocr
    - GET /download/processed?job_id=123&file_type=all
    - GET /download/processed?hospital_id=h100&file_type=deid
    """
    if not patient_id and not hospital_id and not job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of patient_id, hospital_id, or job_id must be provided"
        )
    
    try:
        # Build query to find documents
        stmt = select(Document)
        if patient_id:
            stmt = stmt.where(Document.patient_id == patient_id)
        if hospital_id:
            stmt = stmt.where(Document.hospital_id == hospital_id)
        if job_id:
            stmt = stmt.where(Document.job_id == job_id)
        
        documents = (await session.scalars(stmt)).all()
        
        if not documents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No documents found matching the criteria"
            )
        
        logger.info(
            "download.processed.start",
            patient_id=patient_id,
            hospital_id=hospital_id,
            job_id=job_id,
            file_type=file_type,
            documents_count=len(documents)
        )
        
        # Collect all files to download
        files_to_download = []
        
        for doc in documents:
            pages = (
                await session.scalars(
                    select(DocumentPage).where(DocumentPage.document_id == doc.document_id)
                )
            ).all()
            
            for page in pages:
                # Fetch OCR data
                if file_type in ["ocr", "all"]:
                    raw = await session.scalar(
                        select(OcrRawText).where(OcrRawText.page_id == page.page_id)
                    )
                    if raw:
                        files_to_download.append({
                            "type": "ocr",
                            "doc_id": doc.document_id[:8],
                            "page": page.page_number,
                            "text": raw.raw_text,
                            "filename": f"ocr_{doc.document_id[:8]}_page_{page.page_number}.txt"
                        })
                
                # Fetch Spell Check data
                if file_type in ["spellcheck", "all"]:
                    spellcheck = await session.scalar(
                        select(OcrSpellcheckedText).where(OcrSpellcheckedText.page_id == page.page_id)
                    )
                    if spellcheck:
                        files_to_download.append({
                            "type": "spellcheck",
                            "doc_id": doc.document_id[:8],
                            "page": page.page_number,
                            "text": spellcheck.spellchecked_text,
                            "filename": f"spellcheck_{doc.document_id[:8]}_page_{page.page_number}.txt"
                        })
                
                # Fetch De-identification data
                if file_type in ["deid", "all"]:
                    deid = await session.scalar(
                        select(OcrDeidentifiedText).where(OcrDeidentifiedText.page_id == page.page_id)
                    )
                    if deid:
                        files_to_download.append({
                            "type": "deid",
                            "doc_id": doc.document_id[:8],
                            "page": page.page_number,
                            "text": deid.deid_text,
                            "filename": f"deid_{doc.document_id[:8]}_page_{page.page_number}.txt"
                        })
        
        if not files_to_download:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {file_type} processed files found"
            )
        
        # Create zip file with processed data
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_info in files_to_download:
                zip_file.writestr(file_info["filename"], file_info["text"])
        
        zip_buffer.seek(0)
        
        logger.info(
            "download.processed.zip_created",
            files_count=len(files_to_download),
            file_type=file_type
        )
        
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=processed_{file_type}_files.zip"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("download.processed.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading files: {str(e)}"
        )


@router.get("/all")
async def download_all_files(
    patient_id: Optional[str] = Query(None),
    hospital_id: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Download all files from MinIO (original + processed) in organized folder structure.
    
    Query Parameters:
    - patient_id: Filter by patient
    - hospital_id: Filter by hospital
    - job_id: Filter by job
    - At least one parameter must be provided
    
    Returns a zip file containing:
    - Original uploaded files (from original storage)
    - All processed files (images, OCR results, spell check, de-identification)
    
    Examples:
    - GET /download/all?patient_id=p1
    - GET /download/all?job_id=123
    - GET /download/all?patient_id=p1&hospital_id=h100
    """
    if not patient_id and not hospital_id and not job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of patient_id, hospital_id, or job_id must be provided"
        )
    
    try:
        # Build query to find documents
        stmt = select(Document)
        if patient_id:
            stmt = stmt.where(Document.patient_id == patient_id)
        if hospital_id:
            stmt = stmt.where(Document.hospital_id == hospital_id)
        if job_id:
            stmt = stmt.where(Document.job_id == job_id)
        
        documents = (await session.scalars(stmt)).all()
        
        if not documents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No documents found matching the criteria"
            )
        
        logger.info(
            "download.all.start",
            patient_id=patient_id,
            hospital_id=hospital_id,
            job_id=job_id,
            documents_count=len(documents)
        )
        
        # Create zip file with all files from MinIO
        zip_buffer = io.BytesIO()
        total_files = 0
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            
            # Process each document
            for doc in documents:
                doc_id_short = doc.document_id[:8]
                
                # 1. Download original file
                if doc.original_file_path:
                    try:
                        file_content = await storage_service.retrieve_file(doc.original_file_path)
                        filename = f"original/{Path(doc.original_file_path).name}"
                        zip_file.writestr(filename, file_content)
                        total_files += 1
                        logger.info("download.all.original_added", filename=filename)
                    except Exception as e:
                        logger.warning("download.all.original_file_error", file_path=doc.original_file_path, error=str(e))
                
                # 2. Download all files from document's file_path directory in MinIO
                if doc.file_path:
                    try:
                        # List all objects in the document's directory
                        objects = await minio_client.list_objects_in_directory(doc.file_path)
                        
                        for obj in objects:
                            try:
                                # Download each file
                                file_content = await storage_service.retrieve_file(obj)
                                # Organize by folder in zip
                                relative_path = obj.replace(doc.file_path, "").lstrip("/")
                                zip_path = f"processed/{doc_id_short}/{relative_path}"
                                zip_file.writestr(zip_path, file_content)
                                total_files += 1
                                logger.info("download.all.file_added", zip_path=zip_path)
                            except Exception as e:
                                logger.warning("download.all.file_error", minio_path=obj, error=str(e))
                    
                    except Exception as e:
                        logger.warning("download.all.directory_list_error", directory=doc.file_path, error=str(e))
                
                # 3. Download OCR/spellcheck/deid result files from MinIO
                # New patient-centric structure: {hospital_id}/{patient_id}/results/{job_id}/{document_id}/{result_type}/
                result_types = ["ocr", "spellcheck", "deid"]
                
                for result_type in result_types:
                    # New patient-centric path
                    patient_centric_prefix = f"{doc.hospital_id}/{doc.patient_id}/results/{doc.job_id}/{doc.document_id}/{result_type}"
                    # Legacy job-centric path (fallback for old data)
                    legacy_prefix = f"{result_type}_results/{doc.job_id}/{doc.document_id}"
                    
                    for prefix in [patient_centric_prefix, legacy_prefix]:
                        try:
                            objects = await minio_client.list_objects_in_directory(prefix)
                            if not objects:
                                continue
                            
                            for obj in objects:
                                try:
                                    file_content = await storage_service.retrieve_file(obj)
                                    # Extract meaningful filename from path
                                    relative_path = obj.split("/")[-1]  # Just the filename
                                    zip_path = f"results/{result_type}/{doc_id_short}/{relative_path}"
                                    zip_file.writestr(zip_path, file_content)
                                    total_files += 1
                                    logger.info("download.all.result_file_added", zip_path=zip_path)
                                except Exception as e:
                                    logger.warning("download.all.result_file_error", minio_path=obj, error=str(e))
                            break  # Found files in this prefix, don't check fallback
                        except Exception as e:
                            logger.debug("download.all.result_prefix_not_found", prefix=prefix)
        
        zip_buffer.seek(0)
        
        if total_files == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No files found in MinIO for the selected documents"
            )
        
        logger.info(
            "download.all.zip_created",
            documents_count=len(documents),
            total_files=total_files
        )
        
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=all_files_{total_files}.zip"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("download.all.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading files: {str(e)}"
        )
