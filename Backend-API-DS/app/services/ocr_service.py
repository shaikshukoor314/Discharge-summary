from __future__ import annotations

import asyncio
import base64
import json
from typing import Dict, Any
from pathlib import Path
import tempfile

from app.config.settings import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OcrService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.chandra_ocr_url = getattr(self.settings, 'chandra_ocr_url', "http://101.53.140.236:8080")
        self.max_output_tokens = getattr(self.settings, 'ocr_max_tokens', 7000)
        self.fallback_enabled = getattr(self.settings, 'ocr_fallback_enabled', True)
        self.fallback_dir = Path(getattr(self.settings, 'ocr_fallback_dir', "./pipeline_outputs/OCR_output_pages"))
        # Ensure fallback directory exists
        self.fallback_dir.mkdir(parents=True, exist_ok=True)

    async def run_ocr(self, file_bytes: bytes, page_number: int = 1, file_extension: str = ".png") -> Dict[str, Any]:
        """
        Run OCR on file bytes (image or PDF) using Chandra OCR API.
        
        Args:
            file_bytes: Raw file data (PDF or image)
            page_number: Page number (1-indexed)
            file_extension: Extension of the original file
            
        Returns:
            Dictionary containing OCR results
        """
        # Try API first
        api_result = await self._try_api_ocr(file_bytes, page_number, file_extension)
        
        # If API succeeded, return the result
        if api_result.get('success', False):
            api_result['source'] = 'api'
            return api_result
        
        # API failed - try fallback if enabled
        if self.fallback_enabled:
            fallback_result = await self._try_fallback_ocr(page_number)
            if fallback_result.get('success', False):
                logger.warning(
                    "ocr.fallback_used",
                    page_number=page_number,
                    api_error=api_result.get('error', 'Unknown error')
                )
                fallback_result['source'] = 'fallback'
                return fallback_result
        
        # Both API and fallback failed
        logger.error(
            "ocr.all_methods_failed",
            page_number=page_number,
            api_error=api_result.get('error', 'Unknown error')
        )
        return {
            'success': False,
            'markdown': '',
            'html': '',
            'error': f"OCR API failed: {api_result.get('error', 'Unknown error')}. Fallback also unavailable.",
            'page_number': page_number,
            'token_count': 0,
            'source': 'none'
        }
    
    async def _try_api_ocr(self, file_bytes: bytes, page_number: int, file_extension: str) -> Dict[str, Any]:
        """Try to get OCR result from API using httpx."""
        import httpx
        
        try:
            # Prepare request to Chandra OCR API
            url = f"{self.chandra_ocr_url}/ocr"
            
            # Map extension to content type
            ext = file_extension.lower()
            if ext == ".pdf":
                content_type = "application/pdf"
                filename = f"document_{page_number}.pdf"
            else:
                content_type = "image/png"
                filename = f"image_{page_number}.png"

            data = {
                'max_output_tokens': self.max_output_tokens,
                'include_images': True,  # Set to True as per individual script
                'include_headers_footers': False,
                'method': 'vllm',
                'page_number': page_number - 1  # OCR server expects 0-indexed page for PDF extraction
            }
            
            # Using httpx for async non-blocking request
            logger.info("ocr.api_request", url=url, filename=filename, content_type=content_type)
            async with httpx.AsyncClient(timeout=300.0) as client:
                files = {'file': (filename, file_bytes, content_type)}
                response = await client.post(url, files=files, data=data)
            
            logger.info("ocr.api_response", status_code=response.status_code)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'markdown': '',
                    'html': '',
                    'error': f"API returned status {response.status_code}",
                    'page_number': page_number,
                    'token_count': 0
                }
            
            result = response.json()
            result['page_number'] = page_number
            return result
                
        except Exception as e:
            logger.error("ocr.api_error", error=str(e), page_number=page_number)
            return {
                'success': False,
                'markdown': '',
                'html': '',
                'error': str(e),
                'page_number': page_number,
                'token_count': 0
            }
    
    async def _try_fallback_ocr(self, page_number: int) -> Dict[str, Any]:
        """Try to get OCR result from fallback .txt or .md file."""
        try:
            # Try multiple possible file names with both .txt and .md extensions
            possible_files = [
                # .txt files (plain text)
                self.fallback_dir / f"page{page_number}.txt",
                self.fallback_dir / f"page_{page_number}.txt",
                self.fallback_dir / f"page-{page_number}.txt",
                self.fallback_dir / f"{page_number}.txt",
                # .md files (markdown)
                self.fallback_dir / f"page{page_number}.md",
                self.fallback_dir / f"page_{page_number}.md",
                self.fallback_dir / f"page-{page_number}.md",
                self.fallback_dir / f"{page_number}.md",
            ]
            
            for fallback_file in possible_files:
                if fallback_file.exists() and fallback_file.is_file():
                    try:
                        # Read the file content
                        file_content = fallback_file.read_text(encoding='utf-8').strip()
                        
                        # Skip files that look like error messages (not actual OCR output)
                        if not file_content or file_content.startswith('[OCR Failed:') or file_content.startswith('Error:'):
                            logger.warning(
                                "ocr.fallback_skipped_error_content",
                                page_number=page_number,
                                file_path=str(fallback_file),
                                reason="File contains error message, not OCR output"
                            )
                            continue
                        
                        # Determine if it's markdown or plain text based on extension
                        is_markdown = fallback_file.suffix.lower() == '.md'
                        
                        logger.info(
                            "ocr.fallback_success",
                            page_number=page_number,
                            file_path=str(fallback_file),
                            is_markdown=is_markdown,
                            content_length=len(file_content)
                        )
                        
                        # Return content as markdown (will be converted to text later in ocr_task)
                        # If it's a .txt file, treat it as plain text (no markdown conversion needed)
                        # If it's a .md file, treat it as markdown (will be converted)
                        return {
                            'success': True,
                            'markdown': file_content,  # Will be converted to text in ocr_task
                            'html': f"<p>{file_content}</p>",
                            'page_number': page_number,
                            'token_count': len(file_content.split()),
                            'fallback_file': str(fallback_file),
                            'is_markdown': is_markdown
                        }
                    except Exception as e:
                        logger.warning(
                            "ocr.fallback_read_error",
                            page_number=page_number,
                            file_path=str(fallback_file),
                            error=str(e)
                        )
                        continue  # Try next file
            
            # No fallback file found
            return {
                'success': False,
                'markdown': '',
                'html': '',
                'error': f"No fallback file found for page {page_number} in {self.fallback_dir}. Tried: .txt and .md files",
                'page_number': page_number,
                'token_count': 0
            }
            
        except Exception as e:
            return {
                'success': False,
                'markdown': '',
                'html': '',
                'error': f"Error reading fallback file: {str(e)}",
                'page_number': page_number,
                'token_count': 0
            }

    async def check_api_health(self) -> bool:
        """Check if Chandra OCR API is healthy."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.chandra_ocr_url}/health")
                return response.status_code == 200
        except Exception:
            return False


def get_ocr_service() -> OcrService:
    return OcrService()

