from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class DocumentFilter(BaseModel):
    patient_id: str
    hospital_id: str
    doc_type: Optional[str] = None
    status: Optional[str] = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    job_id: str
    patient_id: str
    hospital_id: str
    doc_type: str
    file_path: str
    original_file_path: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class DocumentsResponse(BaseModel):
    documents: List[DocumentOut]

