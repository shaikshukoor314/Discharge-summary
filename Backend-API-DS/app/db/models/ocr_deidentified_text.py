from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OcrDeidentifiedText(Base):
    __tablename__ = "ocr_deidentified_texts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id: Mapped[str] = mapped_column(
        ForeignKey("document_pages.page_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    deid_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_deid: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    result_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    entities_found: Mapped[list | None] = mapped_column(JSON, nullable=True)
    entities_count: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    page: Mapped["DocumentPage"] = relationship("DocumentPage", back_populates="deidentified_text")

