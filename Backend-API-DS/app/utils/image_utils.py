from __future__ import annotations

from typing import Literal

ImageType = Literal["pdf", "image"]


def detect_file_kind(filename: str, content_type: str) -> ImageType:
    if filename.lower().endswith(".pdf") or content_type == "application/pdf":
        return "pdf"
    return "image"

