from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class PatientCreate(BaseModel):
    """Schema for creating a patient."""
    medical_record_number: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=255)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    contact_number: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=500)


class PatientUpdate(BaseModel):
    """Schema for updating a patient."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    contact_number: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=500)


class PatientResponse(BaseModel):
    """Schema for patient response."""
    patient_id: str
    hospital_id: str
    medical_record_number: str
    full_name: str
    date_of_birth: Optional[date]
    gender: Optional[str]
    contact_number: Optional[str]
    email: Optional[str]
    address: Optional[str]
    created_at: datetime
    updated_at: datetime


class PatientsListResponse(BaseModel):
    """Schema for list of patients response."""
    patients: List[PatientResponse]
    total: int
