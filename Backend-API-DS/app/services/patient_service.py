from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.patient import Patient
from app.schemas.patient_schema import PatientCreate, PatientUpdate, PatientResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PatientService:
    """Service for patient management."""

    async def create_patient(
        self,
        session: AsyncSession,
        hospital_id: str,
        data: PatientCreate,
    ) -> Optional[Patient]:
        """Create a new patient."""
        # Check if MRN already exists for this hospital
        existing = await session.scalar(
            select(Patient).where(
                Patient.hospital_id == hospital_id,
                Patient.medical_record_number == data.medical_record_number,
            )
        )
        if existing:
            logger.warning(
                "patient.create_failed",
                reason="mrn_exists",
                mrn=data.medical_record_number,
                hospital_id=hospital_id,
            )
            return None

        patient = Patient(
            hospital_id=hospital_id,
            medical_record_number=data.medical_record_number,
            full_name=data.full_name,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            contact_number=data.contact_number,
            email=data.email,
            address=data.address,
        )
        session.add(patient)
        await session.commit()

        logger.info("patient.created", patient_id=patient.patient_id, mrn=data.medical_record_number)
        return patient

    async def get_patient(
        self,
        session: AsyncSession,
        patient_id: str,
        hospital_id: str,
    ) -> Optional[Patient]:
        """Get patient by ID."""
        return await session.scalar(
            select(Patient).where(
                Patient.patient_id == patient_id,
                Patient.hospital_id == hospital_id,
            )
        )

    async def get_patient_by_mrn(
        self,
        session: AsyncSession,
        hospital_id: str,
        medical_record_number: str,
    ) -> Optional[Patient]:
        """Get patient by medical record number."""
        return await session.scalar(
            select(Patient).where(
                Patient.hospital_id == hospital_id,
                Patient.medical_record_number == medical_record_number,
            )
        )

    async def search_patients(
        self,
        session: AsyncSession,
        hospital_id: str,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Patient], int]:
        """Search patients by name or MRN."""
        query = select(Patient).where(Patient.hospital_id == hospital_id)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Patient.full_name.ilike(search_pattern),
                    Patient.medical_record_number.ilike(search_pattern),
                )
            )

        # Get total count
        count_query = select(Patient).where(Patient.hospital_id == hospital_id)
        if search:
            count_query = count_query.where(
                or_(
                    Patient.full_name.ilike(search_pattern),
                    Patient.medical_record_number.ilike(search_pattern),
                )
            )
        all_patients = (await session.scalars(count_query)).all()
        total = len(all_patients)

        # Get paginated results
        query = query.order_by(Patient.full_name).limit(limit).offset(offset)
        patients = (await session.scalars(query)).all()

        return list(patients), total

    async def update_patient(
        self,
        session: AsyncSession,
        patient_id: str,
        hospital_id: str,
        data: PatientUpdate,
    ) -> Optional[Patient]:
        """Update patient information."""
        patient = await self.get_patient(session, patient_id, hospital_id)
        if not patient:
            return None

        # Update fields if provided
        if data.full_name is not None:
            patient.full_name = data.full_name
        if data.date_of_birth is not None:
            patient.date_of_birth = data.date_of_birth
        if data.gender is not None:
            patient.gender = data.gender
        if data.contact_number is not None:
            patient.contact_number = data.contact_number
        if data.email is not None:
            patient.email = data.email
        if data.address is not None:
            patient.address = data.address

        await session.commit()
        logger.info("patient.updated", patient_id=patient_id)
        return patient

    async def delete_patient(
        self,
        session: AsyncSession,
        patient_id: str,
        hospital_id: str,
    ) -> bool:
        """Delete a patient."""
        patient = await self.get_patient(session, patient_id, hospital_id)
        if not patient:
            return False

        await session.delete(patient)
        await session.commit()
        logger.info("patient.deleted", patient_id=patient_id)
        return True


_patient_service: Optional[PatientService] = None


def get_patient_service() -> PatientService:
    global _patient_service
    if _patient_service is None:
        _patient_service = PatientService()
    return _patient_service
