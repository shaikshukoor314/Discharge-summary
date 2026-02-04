from __future__ import annotations

from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime


class GenerateSummaryRequest(BaseModel):
    job_id: str
    template_id: str
    custom_instructions: Optional[str] = None


class SummaryContent(BaseModel):
    """Structured summary content."""
    sections: Dict[str, Any]  # Flexible structure based on template


class SummaryResponse(BaseModel):
    summary_id: str
    job_id: str
    patient_id: str
    template_id: str
    content: Dict[str, Any]
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class UpdateSummaryRequest(BaseModel):
    content: Optional[Dict[str, Any]] = None
    status: Optional[str] = None  # draft, finalized, signed
