from __future__ import annotations

import enum
import uuid
from datetime import datetime

from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


if TYPE_CHECKING:
    from app.db.models.document import Document
    from app.db.models.user import User
    from app.db.models.upload_session import UploadSession
    from app.db.models.discharge_summary import DischargeSummary


class Job(Base):
    """Job table - created when user commits upload session."""
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    # New: Link to user who created the job
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    # New: Link to upload session
    upload_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("upload_sessions.upload_session_id", ondelete="SET NULL"),
        nullable=True,
        unique=True,  # One job per upload session
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=JobStatusEnum.PENDING.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    checkpoints: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=lambda: {
            "ocrCheckpoint": "pending",
            "dischargeMedicationsCheckpoint": "pending",
            "dischargeSummaryCheckpoint": "pending"
        }
    )

    # Relationships
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="job", cascade="all, delete-orphan"
    )
    user: Mapped["User"] = relationship("User", back_populates="jobs")
    upload_session: Mapped["UploadSession"] = relationship(
        "UploadSession", back_populates="job"
    )
    discharge_summary: Mapped["DischargeSummary"] = relationship(
        "DischargeSummary", back_populates="job", uselist=False
    )
