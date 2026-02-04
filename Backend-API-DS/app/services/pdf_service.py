from __future__ import annotations

from typing import List

from app.utils.pdf_to_image import pdf_bytes_to_images


class PdfService:
    async def convert_pdf_to_images(self, pdf_bytes: bytes) -> List[bytes]:
        return await pdf_bytes_to_images(pdf_bytes)


def get_pdf_service() -> PdfService:
    return PdfService()

