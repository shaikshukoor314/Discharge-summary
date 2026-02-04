from __future__ import annotations

import asyncio
import base64
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any

from sqlalchemy import select

from app.db.models.document import Document, DocumentStatusEnum
from app.db.models.document_page import DocumentPage
from app.db.models.job import Job, JobStatusEnum
from app.db.models.ocr_deidentified_text import OcrDeidentifiedText
from app.db.models.ocr_raw_text import OcrRawText
from app.db.models.ocr_spellchecked_text import OcrSpellcheckedText
from app.db.session import AsyncSessionLocal
from app.services.pdf_service import get_pdf_service
from app.services.storage_service import get_storage_service
from app.services.ocr_service import get_ocr_service
from app.services.spellcheck_service import get_spellcheck_service
from app.services.deid_service import get_deid_service
from app.utils.logger import get_logger
from app.utils.markdown_to_text import markdown_to_text

logger = get_logger(__name__)

# Local output directories for pipeline stages
LOCAL_OUTPUT_BASE = Path("./pipeline_outputs")
OCR_OUTPUT_DIR = LOCAL_OUTPUT_BASE / "OCR_output_pages"
SPELLCHECK_OUTPUT_DIR = LOCAL_OUTPUT_BASE / "Spell_check_Output_pages"
DEID_OUTPUT_DIR = LOCAL_OUTPUT_BASE / "De-identification_Output_pages"


class PipelineService:
    """Runs OCR -> spellcheck -> de-identification in the background."""

    def __init__(self) -> None:
        self.storage = get_storage_service()
        self.pdf_service = get_pdf_service()
        self.ocr_service = get_ocr_service()
        self.spellcheck_service = get_spellcheck_service()
        self.deid_service = get_deid_service()
        self._lock = asyncio.Lock()
        self._active_jobs: Dict[str, asyncio.Task] = {}
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary output directories."""
        OCR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        SPELLCHECK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        DEID_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("pipeline.directories_created")

    def _cleanup_local_outputs(self) -> None:
        """Clean up local output directories for fresh pipeline run."""
        try:
            if OCR_OUTPUT_DIR.exists():
                shutil.rmtree(OCR_OUTPUT_DIR)
            if SPELLCHECK_OUTPUT_DIR.exists():
                shutil.rmtree(SPELLCHECK_OUTPUT_DIR)
            if DEID_OUTPUT_DIR.exists():
                shutil.rmtree(DEID_OUTPUT_DIR)
            self._ensure_directories()
            logger.info("pipeline.local_outputs_cleaned")
        except Exception as e:
            logger.error("pipeline.cleanup_error", error=str(e))

    def _build_patient_result_path(
        self,
        hospital_id: str,
        patient_id: str,
        job_id: str,
        document_id: str,
        result_type: str,
        filename: str,
    ) -> str:
        """
        Build patient-centric path for processing results.
        
        Structure: {hospital_id}/{patient_id}/results/{job_id}/{document_id}/{result_type}/{filename}
        
        Args:
            hospital_id: Hospital UUID
            patient_id: Patient UUID
            job_id: Job UUID
            document_id: Document UUID
            result_type: One of 'ocr', 'spellcheck', 'deid'
            filename: The result filename (e.g., 'page1.json')
            
        Returns:
            Full MinIO path for the result file
        """
        return f"{hospital_id}/{patient_id}/results/{job_id}/{document_id}/{result_type}/{filename}"

    def _build_patient_page_path(
        self,
        base_path: str,
        original_stem: str,
        page_num: int,
        extension: str = ".jpg"
    ) -> str:
        """
        Build path for page images under the document's base path.
        
        Structure: {base_path}/{original_stem}/pages/page_{n}.{extension}
        
        Args:
            base_path: Document's base storage path
            original_stem: Original filename without extension
            page_num: Page number
            extension: File extension (e.g., '.jpg' or '.png')
            
        Returns:
            Full MinIO path for the page image
        """
        return f"{base_path}/{original_stem}/pages/page_{page_num}{extension}"

    async def ensure_started(self, job_id: str) -> None:
        """Start processing for the job if it's not already running."""
        async with self._lock:
            task = self._active_jobs.get(job_id)
            if task and not task.done():
                return
            # Clean up previous outputs before starting new pipeline
            self._cleanup_local_outputs()
            task = asyncio.create_task(self._run_job(job_id))
            self._active_jobs[job_id] = task
            task.add_done_callback(lambda _: self._active_jobs.pop(job_id, None))

    async def _run_job(self, job_id: str) -> None:
        logger.info("pipeline.start", job_id=job_id)
        try:
            async with AsyncSessionLocal() as session:
                job = await session.get(Job, job_id)
                if not job:
                    return
                job.status = JobStatusEnum.PROCESSING.value
                await session.commit()

            await self._process_documents(job_id)

            async with AsyncSessionLocal() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.status = JobStatusEnum.COMPLETED.value
                    await session.commit()
            logger.info("pipeline.completed", job_id=job_id)
        except Exception:
            logger.exception("pipeline.failed", job_id=job_id)
            async with AsyncSessionLocal() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.status = JobStatusEnum.FAILED.value
                    await session.commit()

    async def update_validated_text(self, page_id: str, corrected_text: str) -> bool:
        """Update corrected de-identified text in both database and MinIO."""
        async with AsyncSessionLocal() as session:
            # 1. Update Database
            deid_entry = await session.scalar(
                select(OcrDeidentifiedText).where(OcrDeidentifiedText.page_id == page_id)
            )
            if not deid_entry:
                logger.error("pipeline.update_validated_text.not_found", page_id=page_id)
                return False

            deid_entry.corrected_deid = corrected_text
            deid_entry.is_validated = True
            
            # Get context for MinIO path
            page = await session.get(DocumentPage, page_id)
            if not page:
                return False
            
            doc = await session.get(Document, page.document_id)
            if not doc:
                return False

            # 2. Update MinIO
            try:
                minio_path = self._build_patient_result_path(
                    doc.hospital_id,
                    doc.patient_id,
                    doc.job_id,
                    doc.document_id,
                    "deid",
                    f"page{page.page_number}.json"
                )
                
                # Retrieve existing JSON
                existing_bytes = await self.storage.retrieve_file(minio_path)
                result_data = json.loads(existing_bytes.decode('utf-8'))
                
                # Update with corrected text
                result_data['corrected_deid'] = corrected_text
                result_data['is_validated'] = True
                
                # Store back to MinIO
                await self.storage.store_file(
                    minio_path,
                    json.dumps(result_data).encode('utf-8'),
                    "application/json"
                )
                
                await session.commit()
                logger.info("pipeline.update_validated_text.success", page_id=page_id)
                return True
            except Exception as e:
                logger.exception("pipeline.update_validated_text.error", page_id=page_id, error=str(e))
                return False

    async def _process_documents(self, job_id: str) -> None:
        async with AsyncSessionLocal() as session:
            documents = (
                await session.scalars(select(Document).where(Document.job_id == job_id))
            ).all()

        for document in documents:
            await self._process_document(document.document_id)

    async def _process_document(self, document_id: str) -> None:
        """Process a single document through OCR -> Spellcheck -> DEID pipeline."""
        async with AsyncSessionLocal() as session:
            document = await session.get(Document, document_id)
            if not document:
                return
            if document.status == DocumentStatusEnum.COMPLETED.value:
                return
            document.status = DocumentStatusEnum.PROCESSING.value
            await session.commit()

        try:
            async with AsyncSessionLocal() as session:
                document = await session.get(Document, document_id)
                if not document:
                    return

                # Get patient context for storage paths
                hospital_id = document.hospital_id
                patient_id = document.patient_id
                job_id = document.job_id

                logger.info(
                    "pipeline.document_context",
                    document_id=document_id,
                    hospital_id=hospital_id,
                    patient_id=patient_id,
                    job_id=job_id,
                )

                # Retrieve original file from MinIO
                original_bytes = await self.storage.retrieve_file(document.original_file_path)
                is_pdf = Path(document.original_file_path).suffix.lower() == ".pdf"
                if is_pdf:
                    page_images = await self.pdf_service.convert_pdf_to_images(original_bytes)
                else:
                    page_images = [original_bytes]

                original_stem = Path(document.original_file_path).stem
                
                # Process each page through the pipeline
                for page_num, image_bytes in enumerate(page_images, start=1):
                    logger.info(
                        "pipeline.processing_page",
                        document_id=document_id,
                        page_num=page_num,
                        total_pages=len(page_images)
                    )
                    
                    # Store page image under document's path
                    # Structure: {base_path}/{original_stem}/pages/page_{n}.jpg
                    image_path = self._build_patient_page_path(
                        document.file_path,
                        original_stem,
                        page_num,
                        extension=".jpg"
                    )
                    await self.storage.store_file(image_path, image_bytes, "image/jpeg")
                    
                    page = DocumentPage(
                        document_id=document.document_id,
                        page_number=page_num,
                        image_minio_path=image_path,
                    )
                    session.add(page)
                    await session.flush()

                    ocr_result = await self.ocr_service.run_ocr(
                        image_bytes, 
                        page_num, 
                        file_extension=".jpg"
                    )
                    
                    if ocr_result.get('success', False):
                        # Get original markdown content
                        markdown_content = ocr_result.get('markdown', '')
                        
                        # Save original Markdown locally
                        ocr_md_file = OCR_OUTPUT_DIR / f"page{page_num}.md"
                        ocr_md_file.write_text(markdown_content, encoding="utf-8")
                        
                        # Convert markdown to plain text for pipeline processing
                        ocr_text = markdown_to_text(markdown_content)
                    else:
                        ocr_text = f"[OCR Failed: {ocr_result.get('error', 'Unknown error')}]"
                        logger.warning(
                            "pipeline.ocr_failed",
                            document_id=document_id,
                            page_num=page_num,
                            error=ocr_result.get('error')
                        )

                    # Save validated plain text output locally
                    ocr_output_file = OCR_OUTPUT_DIR / f"page{page_num}.txt"
                    ocr_output_file.write_text(ocr_text, encoding="utf-8")
                    
                    # Store OCR result in MinIO (patient-centric path)
                    ocr_minio_path = self._build_patient_result_path(
                        hospital_id, patient_id, job_id, document_id,
                        "ocr", f"page{page_num}.json"
                    )
                    await self.storage.store_file(
                        ocr_minio_path,
                        json.dumps({
                            'page_number': page_num,
                            'text': ocr_text,
                            'metadata': ocr_result.get('metadata', {}),
                            'success': ocr_result.get('success', False)
                        }).encode('utf-8'),
                        "application/json"
                    )

                    # Step 2: Spell Check
                    spellcheck_result = await self.spellcheck_service.correct_text(ocr_text)
                    spellchecked_text = spellcheck_result.get('corrected_text', ocr_text)

                    # Save Spell Check output locally and to MinIO
                    spellcheck_output_file = SPELLCHECK_OUTPUT_DIR / f"page{page_num}.txt"
                    spellcheck_output_file.write_text(spellchecked_text, encoding="utf-8")
                    
                    spellcheck_minio_path = self._build_patient_result_path(
                        hospital_id, patient_id, job_id, document_id,
                        "spellcheck", f"page{page_num}.json"
                    )
                    await self.storage.store_file(
                        spellcheck_minio_path,
                        json.dumps({
                            'page_number': page_num,
                            'text': spellchecked_text,
                            'corrections_made': spellcheck_result.get('corrections_made', 0),
                            'metadata': spellcheck_result.get('metadata', {}),
                            'success': spellcheck_result.get('success', False)
                        }).encode('utf-8'),
                        "application/json"
                    )

                    # Step 3: De-identification
                    deid_result = await self.deid_service.redact_phi(spellchecked_text)
                    deidentified_text = deid_result.get('deidentified_text', spellchecked_text)

                    # Save De-identification output locally and to MinIO
                    deid_output_file = DEID_OUTPUT_DIR / f"page{page_num}.txt"
                    deid_output_file.write_text(deidentified_text, encoding="utf-8")
                    
                    deid_minio_path = self._build_patient_result_path(
                        hospital_id, patient_id, job_id, document_id,
                        "deid", f"page{page_num}.json"
                    )
                    await self.storage.store_file(
                        deid_minio_path,
                        json.dumps({
                            'page_number': page_num,
                            'text': deidentified_text,
                            'entities_found': deid_result.get('entities_found', []),
                            'entities_count': deid_result.get('entities_count', {}),
                            'metadata': deid_result.get('metadata', {}),
                            'success': deid_result.get('success', False)
                        }).encode('utf-8'),
                        "application/json"
                    )

                    # Save to database
                    session.add(OcrRawText(
                        page_id=page.page_id, 
                        raw_text=ocr_text,
                        result_metadata=ocr_result.get('metadata', {})
                    ))
                    session.add(OcrSpellcheckedText(
                        page_id=page.page_id, 
                        spellchecked_text=spellchecked_text,
                        result_metadata=spellcheck_result.get('metadata', {})
                    ))
                    session.add(OcrDeidentifiedText(
                        page_id=page.page_id, 
                        deid_text=deidentified_text,
                        result_metadata=deid_result.get('metadata', {}),
                        entities_found=deid_result.get('entities_found', []),
                        entities_count=deid_result.get('entities_count', {})
                    ))
                    
                    await session.flush()

                    logger.info(
                        "pipeline.page_completed",
                        document_id=document_id,
                        page_num=page_num,
                        ocr_path=ocr_minio_path,
                        deid_path=deid_minio_path,
                        entities_found=len(deid_result.get('entities_found', []))
                    )

                document.status = DocumentStatusEnum.COMPLETED.value
                await session.commit()
                logger.info("pipeline.document_completed", document_id=document_id)
                
        except Exception as e:
            logger.exception("pipeline.document_processing_error", document_id=document_id, error=str(e))
            async with AsyncSessionLocal() as session:
                document = await session.get(Document, document_id)
                if document:
                    document.status = DocumentStatusEnum.FAILED.value
                    await session.commit()


def get_result_path_for_document(
    hospital_id: str,
    patient_id: str,
    job_id: str,
    document_id: str,
    result_type: str,
) -> str:
    """
    Get the base path for a document's results in MinIO.
    
    Useful for listing or retrieving results.
    
    Args:
        hospital_id: Hospital UUID
        patient_id: Patient UUID
        job_id: Job UUID
        document_id: Document UUID
        result_type: One of 'ocr', 'spellcheck', 'deid'
        
    Returns:
        Base MinIO path for the result type
    """
    return f"{hospital_id}/{patient_id}/results/{job_id}/{document_id}/{result_type}"


_pipeline_service = PipelineService()


def get_pipeline_service() -> PipelineService:
    return _pipeline_service
