from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DischargeSummaryStatusEnum(str, enum.Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    SIGNED = "signed"


if TYPE_CHECKING:
    from app.db.models.job import Job
    from app.db.models.patient import Patient
    from app.db.models.user import User


class DischargeSummary(Base):
    """Discharge summary table - final output of the pipeline."""
    __tablename__ = "discharge_summaries"

    summary_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="CASCADE"),
        nullable=False,
    )
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.patient_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default=DischargeSummaryStatusEnum.DRAFT.value,
        nullable=False,
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="discharge_summary")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="discharge_summaries")
    user: Mapped["User"] = relationship("User", back_populates="discharge_summaries")
