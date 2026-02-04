from __future__ import annotations

from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field, AliasChoices


class EntityInfo(BaseModel):
    type: str = Field(validation_alias=AliasChoices('type', 'entity_type'))
    start: int
    end: int
    score: float
    text: str


class ExtractionEntry(BaseModel):
    page_id: str
    page_number: int
    image_path: str
    extracted_text: str
    spellchecked_text: str
    deid_text: str
    corrected_deid: Optional[str] = None
    is_validated: bool = False
    ocr_metadata: Optional[Dict[str, Any]] = None
    spellcheck_metadata: Optional[Dict[str, Any]] = None
    deid_metadata: Optional[Dict[str, Any]] = None
    entities_found: Optional[List[EntityInfo]] = None
    entities_count: Optional[Dict[str, int]] = None


class DocumentResult(BaseModel):
    doc_id: str
    original_file_path: str | None = None
    patient_id: str
    hospital_id: str
    doc_type: str
    total_pages: int
    extraction: List[ExtractionEntry]


class ResultResponse(BaseModel):
    job_id: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    document: List[DocumentResult]
    

class PageValidationRequest(BaseModel):
    corrected_text: str

