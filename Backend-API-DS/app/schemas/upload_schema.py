from __future__ import annotations

import enum

from typing import Optional

from pydantic import BaseModel, Field


class DocTypeEnum(str, enum.Enum):
    LAB_REPORTS = "lab_reports"
    RADIOLOGY_REPORTS = "radiology_reports"
    PROGRESS_NOTES = "progress_notes"
    CONSULTATION_NOTES = "consultation_notes"


class UploadMetadata(BaseModel):
    patient_id: Optional[str] = Field(None, min_length=1)
    hospital_id: Optional[str] = Field(None, min_length=1)
    doc_type: Optional[DocTypeEnum] = Field(None)


class PageExtraction(BaseModel):
    image_path: str
    extracted_text: str


class UploadResponse(BaseModel):
    job_id: str

