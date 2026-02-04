from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.db.models.job import Job
    from app.db.models.document import Document


class LogEntry(Base):
    __tablename__ = "logs"

    log_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    job: Mapped["Job"] = relationship("Job", backref="logs")
    document: Mapped["Document"] = relationship("Document", backref="logs")

