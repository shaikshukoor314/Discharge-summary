from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import StreamingResponse, Response
import io
from PIL import Image

from app.services.storage_service import get_storage_service
from app.utils.logger import get_logger

router = APIRouter(prefix="/files", tags=["files"])
logger = get_logger(__name__)
storage_service = get_storage_service()

# In-memory thumbnail cache (simple LRU-like behavior)
_thumbnail_cache: dict[str, bytes] = {}
_CACHE_MAX_SIZE = 100


@router.get("/thumbnail")
async def get_thumbnail(
    path: str = Query(..., description="MinIO path to the image file"),
    width: int = Query(200, ge=50, le=400, description="Thumbnail width"),
    quality: int = Query(70, ge=30, le=95, description="JPEG quality"),
):
    """
    Get a thumbnail version of an image (much smaller file size).
    
    Query Parameters:
    - path: The full MinIO path to the image file
    - width: Target width (height auto-calculated to maintain aspect ratio)
    - quality: JPEG quality (lower = smaller file)
    
    Returns a compressed JPEG thumbnail.
    """
    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path parameter is required"
        )
    
    # Check cache first
    cache_key = f"{path}:{width}:{quality}"
    if cache_key in _thumbnail_cache:
        return Response(
            content=_thumbnail_cache[cache_key],
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
                "X-Cache": "HIT",
            }
        )
    
    try:
        # Retrieve original file from MinIO
        file_content = await storage_service.retrieve_file(path)
        
        # Open image and create thumbnail
        img = Image.open(io.BytesIO(file_content))
        
        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Calculate new height maintaining aspect ratio
        aspect_ratio = img.height / img.width
        new_height = int(width * aspect_ratio)
        
        # Resize using high-quality downsampling
        img = img.resize((width, new_height), Image.Resampling.LANCZOS)
        
        # Save as JPEG to buffer
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        thumbnail_bytes = buffer.getvalue()
        
        # Cache the result
        if len(_thumbnail_cache) >= _CACHE_MAX_SIZE:
            # Remove oldest entry (simple approach)
            _thumbnail_cache.pop(next(iter(_thumbnail_cache)))
        _thumbnail_cache[cache_key] = thumbnail_bytes
        
        logger.info("file.thumbnail_generated", path=path, width=width, size=len(thumbnail_bytes))
        
        return Response(
            content=thumbnail_bytes,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Cache": "MISS",
            }
        )
    
    except Exception as e:
        logger.error("file.thumbnail_error", path=path, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found or cannot generate thumbnail: {path}"
        )


@router.get("/image")
async def get_image(
    path: str = Query(..., description="MinIO path to the image file"),
):
    """
    Retrieve an image file from MinIO storage.
    
    Query Parameters:
    - path: The full MinIO path to the image file
    
    Returns the image with appropriate content type.
    
    Examples:
    - GET /files/image?path=hospital_id/patient_id/documents/session_id/doc_type/filename/pages/page_1.png
    """
    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path parameter is required"
        )
    
    try:
        logger.info("file.get_image", path=path)
        
        # Retrieve file from MinIO
        file_content = await storage_service.retrieve_file(path)
        
        # Determine content type based on file extension
        content_type = "image/png"
        if path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
            content_type = "image/jpeg"
        elif path.lower().endswith(".gif"):
            content_type = "image/gif"
        elif path.lower().endswith(".webp"):
            content_type = "image/webp"
        elif path.lower().endswith(".pdf"):
            content_type = "application/pdf"
        
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "Content-Disposition": f"inline; filename={path.split('/')[-1]}",
            }
        )
    
    except Exception as e:
        logger.error("file.get_image_error", path=path, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {path}"
        )


@router.get("/download")
async def download_file(
    path: str = Query(..., description="MinIO path to the file"),
):
    """
    Download a file from MinIO storage.
    
    Query Parameters:
    - path: The full MinIO path to the file
    
    Returns the file as an attachment download.
    """
    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path parameter is required"
        )
    
    try:
        logger.info("file.download", path=path)
        
        # Retrieve file from MinIO
        file_content = await storage_service.retrieve_file(path)
        
        filename = path.split('/')[-1]
        
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
            }
        )
    
    except Exception as e:
        logger.error("file.download_error", path=path, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {path}"
        )
