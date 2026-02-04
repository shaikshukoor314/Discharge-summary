from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.upload_schema import DocTypeEnum


class UploadSessionCreate(BaseModel):
    """Schema for creating an upload session."""
    patient_id: str = Field(..., min_length=1)


class UploadSessionResponse(BaseModel):
    """Schema for upload session response."""
    upload_session_id: str
    user_id: str
    patient_id: str
    patient_name: Optional[str] = None
    patient_mrn: Optional[str] = None
    status: str
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentInSession(BaseModel):
    """Schema for document within an upload session."""
    document_id: str
    doc_type: str
    original_filename: Optional[str]
    file_size: Optional[int]
    mime_type: Optional[str]
    status: str
    created_at: datetime


class UploadSessionDetailResponse(BaseModel):
    """Schema for detailed upload session response with documents."""
    upload_session_id: str
    user_id: str
    patient_id: str
    patient_name: Optional[str] = None
    patient_mrn: Optional[str] = None
    status: str
    documents: List[DocumentInSession]
    created_at: datetime
    updated_at: datetime


class FileUploadResponse(BaseModel):
    """Schema for file upload response."""
    document_id: str
    original_filename: str
    doc_type: str
    file_size: int
    status: str


class FilesUploadResponse(BaseModel):
    """Schema for multiple files upload response."""
    upload_session_id: str
    uploaded_files: List[FileUploadResponse]
    total_uploaded: int


class CommitResponse(BaseModel):
    """Schema for commit response."""
    job_id: str
    upload_session_id: str
    status: str
    message: str
    documents_committed: int


class UploadSessionsListResponse(BaseModel):
    """Schema for list of upload sessions."""
    sessions: List[UploadSessionResponse]
    total: int
