from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.db.models.user import User
from app.middleware.auth_middleware import get_current_user
from app.schemas.patient_schema import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientsListResponse,
)
from app.services.patient_service import get_patient_service
from app.utils.logger import get_logger

router = APIRouter(prefix="/patients", tags=["patients"])
logger = get_logger(__name__)


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    data: PatientCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PatientResponse:
    """Create a new patient."""
    patient_service = get_patient_service()
    # Check if patient with this MRN already exists
    existing = await patient_service.get_patient_by_mrn(
        session=session,
        hospital_id=current_user.hospital_id,
        medical_record_number=data.medical_record_number,
    )
    
    if existing:
        patient = existing
    else:
        patient = await patient_service.create_patient(
            session=session,
            hospital_id=current_user.hospital_id,
            data=data,
        )

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create patient",
        )

    return PatientResponse(
        patient_id=patient.patient_id,
        hospital_id=patient.hospital_id,
        medical_record_number=patient.medical_record_number,
        full_name=patient.full_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        contact_number=patient.contact_number,
        email=patient.email,
        address=patient.address,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


@router.get("", response_model=PatientsListResponse)
async def list_patients(
    search: Optional[str] = Query(None, description="Search by name or MRN"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PatientsListResponse:
    """List patients with optional search."""
    patient_service = get_patient_service()
    
    patients, total = await patient_service.search_patients(
        session=session,
        hospital_id=current_user.hospital_id,
        search=search,
        limit=limit,
        offset=offset,
    )

    return PatientsListResponse(
        patients=[
            PatientResponse(
                patient_id=p.patient_id,
                hospital_id=p.hospital_id,
                medical_record_number=p.medical_record_number,
                full_name=p.full_name,
                date_of_birth=p.date_of_birth,
                gender=p.gender,
                contact_number=p.contact_number,
                email=p.email,
                address=p.address,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in patients
        ],
        total=total,
    )


@router.get("/by-mrn/{medical_record_number}", response_model=PatientResponse)
async def get_patient_by_mrn(
    medical_record_number: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PatientResponse:
    """Get patient by medical record number."""
    patient_service = get_patient_service()
    
    patient = await patient_service.get_patient_by_mrn(
        session=session,
        hospital_id=current_user.hospital_id,
        medical_record_number=medical_record_number,
    )

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    return PatientResponse(
        patient_id=patient.patient_id,
        hospital_id=patient.hospital_id,
        medical_record_number=patient.medical_record_number,
        full_name=patient.full_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        contact_number=patient.contact_number,
        email=patient.email,
        address=patient.address,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PatientResponse:
    """Get patient by ID."""
    patient_service = get_patient_service()
    
    patient = await patient_service.get_patient(
        session=session,
        patient_id=patient_id,
        hospital_id=current_user.hospital_id,
    )

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    return PatientResponse(
        patient_id=patient.patient_id,
        hospital_id=patient.hospital_id,
        medical_record_number=patient.medical_record_number,
        full_name=patient.full_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        contact_number=patient.contact_number,
        email=patient.email,
        address=patient.address,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: str,
    data: PatientUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PatientResponse:
    """Update patient information."""
    patient_service = get_patient_service()
    
    patient = await patient_service.update_patient(
        session=session,
        patient_id=patient_id,
        hospital_id=current_user.hospital_id,
        data=data,
    )

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    return PatientResponse(
        patient_id=patient.patient_id,
        hospital_id=patient.hospital_id,
        medical_record_number=patient.medical_record_number,
        full_name=patient.full_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        contact_number=patient.contact_number,
        email=patient.email,
        address=patient.address,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a patient."""
    patient_service = get_patient_service()
    
    success = await patient_service.delete_patient(
        session=session,
        patient_id=patient_id,
        hospital_id=current_user.hospital_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
