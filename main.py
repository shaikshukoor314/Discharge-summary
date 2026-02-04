from __future__ import annotations
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project subdirectories to sys.path
root_dir = Path(__file__).parent.absolute()
backend_dir = root_dir / "Backend-API-DS"
ensemble_dir = root_dir / "Ensemble_DEID"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(ensemble_dir) not in sys.path:
    sys.path.insert(0, str(ensemble_dir))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# New authentication and user management routers
from app.api.auth_routes import router as auth_router
from app.api.hospital_routes import router as hospital_router
from app.api.patient_routes import router as patient_router
from app.api.upload_session_routes import router as upload_session_router

# Existing routers (kept for backward compatibility)
from app.api.document_routes import router as document_router
from app.api.processing_routes import router as processing_router
from app.api.result_routes import router as result_router
from app.api.status_routes import router as status_router
from app.api.upload_routes import router as upload_router
from app.api.download_routes import router as download_router
from app.api.clear_routes import router as clear_router
from app.api.commit_routes import router as commit_router
from app.api.file_routes import router as file_router
from app.api.template_routes import router as template_router
from app.api.summary_routes import router as summary_router
from app.api.checkpoint_routes import router as checkpoint_router

from app.db.base import Base
from app.db.session import engine
from app.utils.logger import configure_logging

# Configure logging early
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="AI Discharge Summary",
    description="""
    Medical Document Processing Pipeline with User Management.
    
    ## Features
    - User authentication with JWT tokens
    - Hospital and patient management
    - Document upload sessions with staging
    - OCR, Spell Check, and De-identification pipeline
    
    ## API Flow
    1. **Login** - POST /auth/login
    2. **Create Patient** - POST /patients (if new patient)
    3. **Create Upload Session** - POST /upload-sessions
    4. **Upload Files** - POST /upload-sessions/{id}/files
    5. **Commit Session** - POST /upload-sessions/{id}/commit (creates job)
    6. **Process** - POST /process/{job_id}
    7. **Check Status** - GET /status/{job_id}
    8. **Get Results** - GET /result/{job_id}
    """,
    version="2.0.0",
    lifespan=lifespan
)

# CORS Configuration for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# NEW API Routers (v2 - with user management)
# ============================================
app.include_router(auth_router)          # /auth - Authentication
app.include_router(hospital_router)      # /hospitals - Hospital management
app.include_router(patient_router)       # /patients - Patient management
app.include_router(upload_session_router) # /upload-sessions - Upload workflow

# ============================================
# Legacy API Routers (v1 - backward compatibility)
# ============================================
app.include_router(upload_router)        # /upload - Direct upload (legacy)
app.include_router(processing_router)    # /process - Start processing
app.include_router(document_router)      # /documents - Document management
app.include_router(result_router)        # /result - Get results
app.include_router(download_router)      # /download - Download files
app.include_router(clear_router)         # /clear - Clear files
app.include_router(status_router)        # /status - Job status
app.include_router(commit_router)        # /commit - Commit documents (legacy)
app.include_router(file_router)          # /files - File serving from MinIO
app.include_router(template_router)      # /templates - Template management
app.include_router(summary_router)       # /summaries - Summary generation
app.include_router(checkpoint_router)    # /session-status-checkpoints - Verification checkpoints


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Medical Document Pipeline", "version": "2.0.0"}


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "service": "AI Discharge Summary API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "flow": [
            "1. POST /auth/login - Authenticate",
            "2. POST /patients - Create patient (if new)",
            "3. POST /upload-sessions - Create upload session",
            "4. POST /upload-sessions/{id}/files - Upload files",
            "5. POST /upload-sessions/{id}/commit - Commit & create job",
            "6. POST /process/{job_id} - Start processing",
            "7. GET /status/{job_id} - Check progress",
            "8. GET /result/{job_id} - Get results",
        ]
    }
