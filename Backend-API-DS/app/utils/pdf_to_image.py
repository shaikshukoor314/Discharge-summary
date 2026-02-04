from __future__ import annotations

import asyncio
import base64
from io import BytesIO
from tempfile import TemporaryDirectory
from typing import List

from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError


class PopplerNotInstalledError(Exception):
    """Raised when Poppler is not installed."""
    pass


async def pdf_bytes_to_images(pdf_bytes: bytes) -> List[bytes]:
    """Convert PDF bytes into a list of PNG image bytes."""
    try:
        with TemporaryDirectory() as temp_dir:
            images = await asyncio.to_thread(
                convert_from_bytes,
                pdf_bytes,
                dpi=200,
                fmt="jpg",
                output_folder=temp_dir,
            )
            byte_images: list[bytes] = []
            for image in images:
                buffer = BytesIO()
                await asyncio.to_thread(image.save, buffer, format="JPEG", quality=85)
                byte_images.append(buffer.getvalue())
            return byte_images
    except PDFInfoNotInstalledError:
        raise PopplerNotInstalledError(
            "Poppler is required for PDF conversion. "
            "Install it using:\n"
            "- Ubuntu/Debian: sudo apt-get install poppler-utils\n"
            "- macOS: brew install poppler\n"
            "- Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases/ "
            "or install via conda: conda install -c conda-forge poppler"
        )


def image_bytes_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")

