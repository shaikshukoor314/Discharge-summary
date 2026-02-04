from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OcrSpellcheckedText(Base):
    __tablename__ = "ocr_spellchecked_texts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id: Mapped[str] = mapped_column(
        ForeignKey("document_pages.page_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    spellchecked_text: Mapped[str] = mapped_column(Text, nullable=False)
    result_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    page: Mapped["DocumentPage"] = relationship("DocumentPage", back_populates="spellchecked_text")

