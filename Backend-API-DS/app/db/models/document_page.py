from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.db.models.document import Document
    from app.db.models.ocr_raw_text import OcrRawText
    from app.db.models.ocr_spellchecked_text import OcrSpellcheckedText
    from app.db.models.ocr_deidentified_text import OcrDeidentifiedText


class DocumentPage(Base):
    __tablename__ = "document_pages"

    page_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_minio_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    document: Mapped["Document"] = relationship("Document", back_populates="pages")
    raw_text: Mapped["OcrRawText"] = relationship("OcrRawText", back_populates="page", uselist=False)
    spellchecked_text: Mapped["OcrSpellcheckedText"] = relationship(
        "OcrSpellcheckedText", back_populates="page", uselist=False
    )
    deidentified_text: Mapped["OcrDeidentifiedText"] = relationship(
        "OcrDeidentifiedText", back_populates="page", uselist=False
    )

