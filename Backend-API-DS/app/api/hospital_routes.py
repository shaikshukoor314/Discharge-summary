from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.db.session import get_db_session
from app.db.models.hospital import Hospital
from app.db.models.user import User
from app.middleware.auth_middleware import get_current_user, require_role
from app.utils.logger import get_logger

router = APIRouter(prefix="/hospitals", tags=["hospitals"])
logger = get_logger(__name__)


class HospitalCreate(BaseModel):
    """Schema for creating a hospital."""
    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=2, max_length=50)
    address: Optional[str] = None


class HospitalResponse(BaseModel):
    """Schema for hospital response."""
    hospital_id: str
    name: str
    code: str
    address: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class HospitalsListResponse(BaseModel):
    """Schema for list of hospitals response."""
    hospitals: List[HospitalResponse]
    total: int


@router.post("", response_model=HospitalResponse, status_code=status.HTTP_201_CREATED)
async def create_hospital(
    data: HospitalCreate,
    session: AsyncSession = Depends(get_db_session),
) -> HospitalResponse:
    """
    Create a new hospital.
    Note: This endpoint should be admin-only in production.
    """
    # Check if code already exists
    existing = await session.scalar(
        select(Hospital).where(Hospital.code == data.code)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hospital with this code already exists",
        )

    hospital = Hospital(
        name=data.name,
        code=data.code,
        address=data.address,
    )
    session.add(hospital)
    await session.commit()

    logger.info("hospital.created", hospital_id=hospital.hospital_id, code=data.code)

    return HospitalResponse(
        hospital_id=hospital.hospital_id,
        name=hospital.name,
        code=hospital.code,
        address=hospital.address,
        is_active=hospital.is_active,
        created_at=hospital.created_at,
        updated_at=hospital.updated_at,
    )


@router.get("", response_model=HospitalsListResponse)
async def list_hospitals(
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> HospitalsListResponse:
    """List all hospitals."""
    query = select(Hospital)
    
    if is_active is not None:
        query = query.where(Hospital.is_active == is_active)

    # Get total count
    all_hospitals = (await session.scalars(query)).all()
    total = len(all_hospitals)

    # Get paginated results
    query = query.order_by(Hospital.name).limit(limit).offset(offset)
    hospitals = (await session.scalars(query)).all()

    return HospitalsListResponse(
        hospitals=[
            HospitalResponse(
                hospital_id=h.hospital_id,
                name=h.name,
                code=h.code,
                address=h.address,
                is_active=h.is_active,
                created_at=h.created_at,
                updated_at=h.updated_at,
            )
            for h in hospitals
        ],
        total=total,
    )


@router.get("/{hospital_id}", response_model=HospitalResponse)
async def get_hospital(
    hospital_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> HospitalResponse:
    """Get hospital by ID."""
    hospital = await session.get(Hospital, hospital_id)
    
    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found",
        )

    return HospitalResponse(
        hospital_id=hospital.hospital_id,
        name=hospital.name,
        code=hospital.code,
        address=hospital.address,
        is_active=hospital.is_active,
        created_at=hospital.created_at,
        updated_at=hospital.updated_at,
    )
