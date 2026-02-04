from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UploadSessionStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.patient import Patient
    from app.db.models.document import Document
    from app.db.models.job import Job


class UploadSession(Base):
    """Upload session table - staging area for document uploads before commit."""
    __tablename__ = "upload_sessions"

    upload_session_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.patient_id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=UploadSessionStatusEnum.ACTIVE.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="upload_sessions")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="upload_sessions")
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="upload_session", cascade="all, delete-orphan"
    )
    job: Mapped["Job"] = relationship("Job", back_populates="upload_session", uselist=False)
