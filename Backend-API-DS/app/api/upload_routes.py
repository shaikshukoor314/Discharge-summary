from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.upload_schema import DocTypeEnum, UploadMetadata, UploadResponse
from app.services.upload_service import get_upload_service
from app.utils.pdf_to_image import PopplerNotInstalledError

router = APIRouter(prefix="/upload", tags=["upload"])
upload_service = get_upload_service()


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_documents(
    files: List[UploadFile] = File(...),
    patient_id: Optional[str] = Form(None),
    hospital_id: Optional[str] = Form(None),
    doc_type: Optional[DocTypeEnum] = Form(None),
    session: AsyncSession = Depends(get_db_session),
) -> UploadResponse:
    metadata = UploadMetadata(patient_id=patient_id, hospital_id=hospital_id, doc_type=doc_type)
    try:
        job_id = await upload_service.create_job_with_documents(session, files, metadata)
        return UploadResponse(job_id=job_id)
    except PopplerNotInstalledError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) from e
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Storage service unavailable: {str(e)}. Please start MinIO server."
        ) from e
    except Exception as e:
        # Check if it's a database connection error
        error_str = str(e).lower()
        if "password" in error_str or "connection" in error_str or "asyncpg" in error_str or "postgres" in error_str:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database connection failed: {str(e)}. Please ensure PostgreSQL is running on localhost:5432 and credentials in .env are correct."
            ) from e
        # Re-raise other exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during upload: {str(e)}"
        ) from e

