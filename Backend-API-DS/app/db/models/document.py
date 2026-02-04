from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentStatusEnum(str, enum.Enum):
    UPLOADED = "uploaded"
    COMMITTED = "committed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


if TYPE_CHECKING:
    from app.db.models.job import Job
    from app.db.models.upload_session import UploadSession
    from app.db.models.document_page import DocumentPage


class Document(Base):
    """Document table - stores uploaded document metadata."""
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    # Job ID is now nullable - set when upload session is committed
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="CASCADE"),
        nullable=True,
    )
    # Link to upload session (nullable for legacy flow)
    upload_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("upload_sessions.upload_session_id", ondelete="CASCADE"),
        nullable=True,
    )
    # Keep patient_id and hospital_id for quick queries (denormalized)
    patient_id: Mapped[str] = mapped_column(String(64), nullable=False)
    hospital_id: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default=DocumentStatusEnum.UPLOADED.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="documents")
    upload_session: Mapped["UploadSession"] = relationship(
        "UploadSession", back_populates="documents"
    )
    pages: Mapped[List["DocumentPage"]] = relationship(
        "DocumentPage", back_populates="document", cascade="all, delete-orphan"
    )
