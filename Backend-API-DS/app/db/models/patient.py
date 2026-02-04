from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import TYPE_CHECKING, List

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.db.models.hospital import Hospital
    from app.db.models.upload_session import UploadSession
    from app.db.models.discharge_summary import DischargeSummary


class Patient(Base):
    """Patient table for storing patient information."""
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    hospital_id: Mapped[str] = mapped_column(
        ForeignKey("hospitals.hospital_id", ondelete="CASCADE"),
        nullable=False,
    )
    medical_record_number: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Unique constraint: one MRN per hospital
    __table_args__ = (
        UniqueConstraint('hospital_id', 'medical_record_number', name='uq_hospital_mrn'),
    )

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="patients")
    upload_sessions: Mapped[List["UploadSession"]] = relationship(
        "UploadSession", back_populates="patient"
    )
    discharge_summaries: Mapped[List["DischargeSummary"]] = relationship(
        "DischargeSummary", back_populates="patient"
    )
