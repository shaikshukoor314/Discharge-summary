from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.db.models.user import User
from app.middleware.auth_middleware import get_current_user
from app.schemas.upload_schema import DocTypeEnum
from app.schemas.upload_session_schema import (
    UploadSessionCreate,
    UploadSessionResponse,
    UploadSessionDetailResponse,
    DocumentInSession,
    FileUploadResponse,
    FilesUploadResponse,
    CommitResponse,
    UploadSessionsListResponse,
)
from app.services.upload_session_service import get_upload_session_service
from app.utils.logger import get_logger

router = APIRouter(prefix="/upload-sessions", tags=["upload-sessions"])
logger = get_logger(__name__)


@router.post("", response_model=UploadSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_upload_session(
    data: UploadSessionCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> UploadSessionResponse:
    """
    Create a new upload session for a patient.
    This is the first step before uploading files.
    """
    service = get_upload_session_service()
    
    upload_session = await service.create_session(
        session=session,
        user=current_user,
        patient_id=data.patient_id,
    )

    if not upload_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create upload session. Patient may not exist.",
        )

    return UploadSessionResponse(
        upload_session_id=upload_session.upload_session_id,
        user_id=upload_session.user_id,
        patient_id=upload_session.patient_id,
        status=upload_session.status,
        document_count=0,
        created_at=upload_session.created_at,
        updated_at=upload_session.updated_at,
    )


@router.get("", response_model=UploadSessionsListResponse)
async def list_upload_sessions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> UploadSessionsListResponse:
    """List active upload sessions for the current user."""
    service = get_upload_session_service()
    
    sessions_list, total = await service.get_active_sessions(
        session=session,
        user=current_user,
        limit=limit,
        offset=offset,
    )

    return UploadSessionsListResponse(
        sessions=[
            UploadSessionResponse(
                upload_session_id=s.upload_session_id,
                user_id=s.user_id,
                patient_id=s.patient_id,
                patient_name=s.patient.full_name if s.patient else None,
                patient_mrn=s.patient.medical_record_number if s.patient else None,
                status=s.status,
                document_count=len(s.documents) if s.documents else 0,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in sessions_list
        ],
        total=total,
    )


@router.get("/{upload_session_id}", response_model=UploadSessionDetailResponse)
async def get_upload_session(
    upload_session_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> UploadSessionDetailResponse:
    """Get upload session details with documents."""
    service = get_upload_session_service()
    
    upload_session = await service.get_session(
        session=session,
        upload_session_id=upload_session_id,
        user=current_user,
    )

    if not upload_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload session not found",
        )

    return UploadSessionDetailResponse(
        upload_session_id=upload_session.upload_session_id,
        user_id=upload_session.user_id,
        patient_id=upload_session.patient_id,
        patient_name=upload_session.patient.full_name if upload_session.patient else None,
        patient_mrn=upload_session.patient.medical_record_number if upload_session.patient else None,
        status=upload_session.status,
        documents=[
            DocumentInSession(
                document_id=doc.document_id,
                doc_type=doc.doc_type,
                original_filename=doc.original_filename,
                file_size=doc.file_size,
                mime_type=doc.mime_type,
                status=doc.status,
                created_at=doc.created_at,
            )
            for doc in (upload_session.documents or [])
        ],
        created_at=upload_session.created_at,
        updated_at=upload_session.updated_at,
    )


@router.post("/{upload_session_id}/files", response_model=FilesUploadResponse)
async def upload_files(
    upload_session_id: str,
    files: List[UploadFile] = File(...),
    doc_type: Optional[DocTypeEnum] = Form(None),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FilesUploadResponse:
    """
    Upload files to an upload session.
    Files are staged here and not processed until commit.
    """
    service = get_upload_session_service()
    
    upload_session = await service.get_session(
        session=session,
        upload_session_id=upload_session_id,
        user=current_user,
    )

    if not upload_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload session not found",
        )

    if upload_session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload session is not active. Cannot upload files.",
        )

    doc_type_value = doc_type.value if doc_type else "unknown"
    uploaded_files = []

    for file in files:
        document = await service.upload_file(
            session=session,
            upload_session=upload_session,
            user=current_user,
            file=file,
            doc_type=doc_type_value,
        )

        if document:
            uploaded_files.append(
                FileUploadResponse(
                    document_id=document.document_id,
                    original_filename=document.original_filename or "",
                    doc_type=document.doc_type,
                    file_size=document.file_size or 0,
                    status=document.status,
                )
            )

    return FilesUploadResponse(
        upload_session_id=upload_session_id,
        uploaded_files=uploaded_files,
        total_uploaded=len(uploaded_files),
    )


@router.delete("/{upload_session_id}/files/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    upload_session_id: str,
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a file from an upload session."""
    service = get_upload_session_service()
    
    upload_session = await service.get_session(
        session=session,
        upload_session_id=upload_session_id,
        user=current_user,
    )

    if not upload_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload session not found",
        )

    success = await service.delete_file(
        session=session,
        upload_session=upload_session,
        document_id=document_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete file. Session may not be active or file not found.",
        )


@router.post("/{upload_session_id}/commit", response_model=CommitResponse)
async def commit_upload_session(
    upload_session_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CommitResponse:
    """
    Commit an upload session.
    This creates a job and prepares documents for processing.
    """
    service = get_upload_session_service()
    
    upload_session = await service.get_session(
        session=session,
        upload_session_id=upload_session_id,
        user=current_user,
    )

    if not upload_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload session not found",
        )

    job = await service.commit_session(
        session=session,
        upload_session=upload_session,
        user=current_user,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to commit session. Session may be empty or already committed.",
        )

    # Count documents
    documents_count = len(upload_session.documents) if upload_session.documents else 0

    return CommitResponse(
        job_id=job.job_id,
        upload_session_id=upload_session_id,
        status="committed",
        message=f"Upload session committed successfully. Job created with {documents_count} documents.",
        documents_committed=documents_count,
    )


@router.delete("/{upload_session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_upload_session(
    upload_session_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel and delete an upload session.
    This removes all uploaded files.
    """
    service = get_upload_session_service()
    
    upload_session = await service.get_session(
        session=session,
        upload_session_id=upload_session_id,
        user=current_user,
    )

    if not upload_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload session not found",
        )

    success = await service.cancel_session(
        session=session,
        upload_session=upload_session,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to cancel session. Session may already be committed.",
        )
