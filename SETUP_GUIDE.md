# Backend Setup Guide - AI Discharge Summary API

## Overview

This document covers the complete backend setup for the AI Discharge Summary application, including database schemas, MinIO storage structure, and API endpoints.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Schema](#database-schema)
4. [MinIO Storage Structure](#minio-storage-structure)
5. [API Endpoints](#api-endpoints)
6. [Creating Demo Data](#creating-demo-data)
7. [Running the Application](#running-the-application)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Python 3.10+
- PostgreSQL 14+
- MinIO (or S3-compatible storage)
- Docker (optional, for MinIO)

---

## Environment Setup

### 1. Create Virtual Environment

```bash
cd /home/azureuser/ds_app/ds_backend
python3 -m venv venv
# OR using uv (faster)
uv venv venv
```

### 2. Activate Virtual Environment

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
# OR using uv
uv pip install -r requirements.txt
```

### 4. Install spaCy Model (for de-identification)

```bash
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
```

### 5. Configure Environment Variables

Create or update `.env` file:

```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/hospital_files_db

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=cortex-documents
MINIO_SECURE=false

# JWT Configuration
JWT_SECRET_KEY=cortex-discharge-summary-secret-key-change-in-production-2024
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

# OCR Service (external)
OCR_SERVICE_URL=http://216.48.189.216:8080
OCR_SERVICE_TIMEOUT=120

# Application Settings
DEBUG=true
LOG_LEVEL=INFO
```

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  hospitals  │────<│    users    │────<│  auth_sessions  │
└─────────────┘     └─────────────┘     └─────────────────┘
       │                   │
       │                   │
       ▼                   ▼
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│  patients   │────<│ upload_sessions │────<│    jobs     │
└─────────────┘     └─────────────────┘     └─────────────┘
                           │                       │
                           │                       │
                           ▼                       ▼
                    ┌─────────────┐         ┌───────────────┐
                    │  documents  │────────>│ document_pages│
                    └─────────────┘         └───────────────┘
                                                   │
                    ┌──────────────────────────────┼──────────────────────────────┐
                    │                              │                              │
                    ▼                              ▼                              ▼
            ┌───────────────┐            ┌─────────────────────┐        ┌─────────────────────┐
            │ ocr_raw_text  │            │ocr_spellchecked_text│        │ocr_deidentified_text│
            └───────────────┘            └─────────────────────┘        └─────────────────────┘
```

### Table Definitions

#### 1. hospitals
```sql
CREATE TABLE hospitals (
    hospital_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    address TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 2. users
```sql
CREATE TABLE users (
    user_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id VARCHAR(36) REFERENCES hospitals(hospital_id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'admin', 'doctor', 'nurse', 'staff'
    department VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 3. auth_sessions
```sql
CREATE TABLE auth_sessions (
    session_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(36) REFERENCES users(user_id) ON DELETE CASCADE,
    token VARCHAR(500) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 4. patients
```sql
CREATE TABLE patients (
    patient_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id VARCHAR(36) REFERENCES hospitals(hospital_id) ON DELETE CASCADE,
    medical_record_number VARCHAR(50) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(10),
    contact_number VARCHAR(20),
    email VARCHAR(255),
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(hospital_id, medical_record_number)
);
```

#### 5. upload_sessions
```sql
CREATE TABLE upload_sessions (
    upload_session_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(36) REFERENCES users(user_id) ON DELETE CASCADE,
    patient_id VARCHAR(36) REFERENCES patients(patient_id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'committed', 'cancelled'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 6. jobs
```sql
CREATE TABLE jobs (
    job_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(36) REFERENCES users(user_id),
    upload_session_id VARCHAR(36) UNIQUE REFERENCES upload_sessions(upload_session_id),
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 7. documents
```sql
CREATE TABLE documents (
    document_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(36) REFERENCES jobs(job_id) ON DELETE CASCADE,
    upload_session_id VARCHAR(36) REFERENCES upload_sessions(upload_session_id) ON DELETE CASCADE,
    patient_id VARCHAR(64) NOT NULL,
    hospital_id VARCHAR(64) NOT NULL,
    doc_type VARCHAR(64) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    original_file_path VARCHAR(500),
    original_filename VARCHAR(255),
    file_size INTEGER,
    mime_type VARCHAR(100),
    status VARCHAR(20) DEFAULT 'uploaded',  -- 'uploaded', 'committed', 'processing', 'completed', 'failed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 8. document_pages
```sql
CREATE TABLE document_pages (
    page_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(36) REFERENCES documents(document_id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    image_minio_path VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 9. ocr_raw_text
```sql
CREATE TABLE ocr_raw_text (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    page_id VARCHAR(36) REFERENCES document_pages(page_id) ON DELETE CASCADE,
    raw_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 10. ocr_spellchecked_text
```sql
CREATE TABLE ocr_spellchecked_text (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    page_id VARCHAR(36) REFERENCES document_pages(page_id) ON DELETE CASCADE,
    spellchecked_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 11. ocr_deidentified_text
```sql
CREATE TABLE ocr_deidentified_text (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    page_id VARCHAR(36) REFERENCES document_pages(page_id) ON DELETE CASCADE,
    deid_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 12. discharge_summaries
```sql
CREATE TABLE discharge_summaries (
    summary_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(36) REFERENCES jobs(job_id) ON DELETE CASCADE,
    patient_id VARCHAR(36) REFERENCES patients(patient_id),
    user_id VARCHAR(36) REFERENCES users(user_id),
    template_id VARCHAR(100),
    content JSONB,
    status VARCHAR(20) DEFAULT 'draft',  -- 'draft', 'finalized', 'signed'
    finalized_at TIMESTAMP WITH TIME ZONE,
    signed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## MinIO Storage Structure

### Patient-Centric Storage (Recommended)

```
{bucket}/
├── {hospital_id}/
│   └── {patient_id}/
│       ├── documents/
│       │   └── {upload_session_id}/
│       │       └── {doc_type}/
│       │           ├── original.pdf
│       │           └── {filename}/
│       │               └── pages/
│       │                   ├── page_1.png
│       │                   ├── page_2.png
│       │                   └── ...
│       │
│       └── results/
│           └── {job_id}/
│               └── {document_id}/
│                   ├── ocr/
│                   │   ├── page1.json
│                   │   └── page2.json
│                   ├── spellcheck/
│                   │   ├── page1.json
│                   │   └── page2.json
│                   └── deid/
│                       ├── page1.json
│                       └── page2.json
```

### Example Paths

```
# Original document
cortex-documents/451a284f-d975-4621-8005-3a920b333661/89bf7b35-e994-468c-9252-1c243e31a005/documents/3d490010-77ff-4151-8e2d-76e54298be67/lab_reports/cortex-sample-1.pdf

# Page image
cortex-documents/451a284f-d975-4621-8005-3a920b333661/89bf7b35-e994-468c-9252-1c243e31a005/documents/3d490010-77ff-4151-8e2d-76e54298be67/lab_reports/cortex-sample-1/pages/page_1.png

# OCR result
cortex-documents/451a284f-d975-4621-8005-3a920b333661/89bf7b35-e994-468c-9252-1c243e31a005/results/0f478397-b184-477f-8d30-651976dc8957/0db122d4-5160-42b1-ac77-7ec812f9832c/ocr/page1.json
```

### Benefits of Patient-Centric Storage

1. **HIPAA/GDPR Compliance**: Easy to delete all patient data with single path
2. **Data Export**: Single location for complete patient record
3. **Access Control**: Grant/revoke access at patient level
4. **Audit Trail**: Clear organization by patient

---

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login and get JWT token |
| POST | `/auth/logout` | Invalidate current token |
| POST | `/auth/logout-all` | Logout from all devices |
| GET | `/auth/me` | Get current user info |
| POST | `/auth/register` | Register new user |
| POST | `/auth/change-password` | Change password |

### Hospitals

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/hospitals` | Create hospital (admin) |
| GET | `/hospitals` | List hospitals |
| GET | `/hospitals/{id}` | Get hospital details |

### Patients

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/patients` | Create patient |
| GET | `/patients` | Search patients |
| GET | `/patients/by-mrn/{mrn}` | Get by medical record number |
| GET | `/patients/{id}` | Get patient details |
| PATCH | `/patients/{id}` | Update patient |
| DELETE | `/patients/{id}` | Delete patient |

### Upload Sessions (New Flow)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload-sessions` | Create upload session |
| GET | `/upload-sessions` | List active sessions |
| GET | `/upload-sessions/{id}` | Get session details |
| POST | `/upload-sessions/{id}/files` | Upload files to session |
| DELETE | `/upload-sessions/{id}/files/{doc_id}` | Delete file from session |
| POST | `/upload-sessions/{id}/commit` | Commit session (creates job) |
| DELETE | `/upload-sessions/{id}` | Cancel session |

### Processing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/process/{job_id}` | Start OCR pipeline |
| GET | `/status/{job_id}` | Check processing status |
| GET | `/result/{job_id}` | Get processing results |

### Files

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/files/image?path=...` | Get full image from MinIO |
| GET | `/files/thumbnail?path=...&width=150` | Get thumbnail (optimized) |
| GET | `/files/download?path=...` | Download file |

### Download

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/download/original` | Download original files |
| GET | `/download/processed` | Download processed files |
| GET | `/download/all` | Download all files as ZIP |

---

## Creating Demo Data

### Using Python Script

```python
import asyncio
import hashlib
import secrets
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/hospital_files_db"

async def create_demo_data():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Create Hospital
        hospital_id = "451a284f-d975-4621-8005-3a920b333661"
        await session.execute("""
            INSERT INTO hospitals (hospital_id, name, code, address, is_active)
            VALUES (:id, 'Demo Hospital', 'DEMO001', '123 Medical Center Drive', true)
            ON CONFLICT (hospital_id) DO NOTHING
        """, {"id": hospital_id})
        
        # Create User (password: demo1234)
        password = "demo1234"
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256(f"{password}{salt}".encode()).hexdigest() + ":" + salt
        
        await session.execute("""
            INSERT INTO users (user_id, hospital_id, email, password_hash, full_name, role, department, is_active)
            VALUES (:user_id, :hospital_id, 'demo@hospital.com', :password_hash, 'Dr. Demo User', 'doctor', 'General Medicine', true)
            ON CONFLICT (email) DO NOTHING
        """, {
            "user_id": "bc32dd87-4b6e-4955-948c-39f99cdec386",
            "hospital_id": hospital_id,
            "password_hash": password_hash
        })
        
        await session.commit()
        print("Demo data created successfully!")
        print("Login credentials:")
        print("  Email: demo@hospital.com")
        print("  Password: demo1234")

asyncio.run(create_demo_data())
```

### Using SQL

```sql
-- Create Hospital
INSERT INTO hospitals (hospital_id, name, code, address, is_active)
VALUES (
    '451a284f-d975-4621-8005-3a920b333661',
    'Demo Hospital',
    'DEMO001',
    '123 Medical Center Drive',
    true
) ON CONFLICT DO NOTHING;

-- Create User (password hash for 'demo1234')
-- Note: Generate proper hash in production
INSERT INTO users (user_id, hospital_id, email, password_hash, full_name, role, department, is_active)
VALUES (
    'bc32dd87-4b6e-4955-948c-39f99cdec386',
    '451a284f-d975-4621-8005-3a920b333661',
    'demo@hospital.com',
    '<generated_hash>',
    'Dr. Demo User',
    'doctor',
    'General Medicine',
    true
) ON CONFLICT DO NOTHING;
```

---

## Running the Application

### 1. Start PostgreSQL

```bash
# Using Docker
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=hospital_files_db \
  -p 5432:5432 \
  postgres:14

# Or ensure local PostgreSQL is running
sudo systemctl start postgresql
```

### 2. Start MinIO

```bash
# Using Docker
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# Create bucket
mc alias set local http://localhost:9000 minioadmin minioadmin
mc mb local/cortex-documents
```

### 3. Start Backend

```bash
cd /home/azureuser/ds_app/ds_backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 4. Verify Health

```bash
curl http://localhost:8001/health
# Expected: {"status":"healthy","service":"Medical Document Pipeline","version":"2.0.0"}
```

### 5. Test Login

```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@hospital.com", "password": "demo1234"}'
```

---

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U postgres -h localhost -d hospital_files_db -c "SELECT 1"

# Reset database (WARNING: deletes all data)
psql -U postgres -h localhost -c "DROP DATABASE hospital_files_db; CREATE DATABASE hospital_files_db;"
```

### MinIO Connection Issues

```bash
# Check MinIO is running
curl http://localhost:9000/minio/health/live

# Check bucket exists
mc ls local/cortex-documents
```

### Virtual Environment Issues

```bash
# Remove and recreate venv
rm -rf venv
uv venv venv
source venv/bin/activate
uv pip install -r requirements.txt
```

### Port Already in Use

```bash
# Find process using port 8001
lsof -i :8001

# Kill process
pkill -f "uvicorn main:app.*8001"
```

---

## API Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           COMPLETE API WORKFLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

1. LOGIN
   POST /auth/login
   ├── Request: { "email": "...", "password": "..." }
   └── Response: { "access_token": "...", "user_id": "...", "hospital_id": "..." }

2. CREATE PATIENT (if new)
   POST /patients
   ├── Headers: Authorization: Bearer <token>
   ├── Request: { "medical_record_number": "P001", "full_name": "John Doe" }
   └── Response: { "patient_id": "..." }

3. CREATE UPLOAD SESSION
   POST /upload-sessions
   ├── Headers: Authorization: Bearer <token>
   ├── Request: { "patient_id": "..." }
   └── Response: { "upload_session_id": "..." }

4. UPLOAD FILES
   POST /upload-sessions/{id}/files
   ├── Headers: Authorization: Bearer <token>
   ├── Form Data: files=@document.pdf, doc_type=lab_reports
   └── Response: { "uploaded_files": [...] }

5. COMMIT SESSION (creates job)
   POST /upload-sessions/{id}/commit
   ├── Headers: Authorization: Bearer <token>
   └── Response: { "job_id": "...", "documents_committed": 1 }

6. START PROCESSING
   POST /process/{job_id}
   ├── Headers: Authorization: Bearer <token>
   └── Response: { "job_id": "...", "status": "processing" }

7. CHECK STATUS (poll until complete)
   GET /status/{job_id}
   ├── Headers: Authorization: Bearer <token>
   └── Response: { "status": "Completed", "overall_progress": "100%" }

8. GET RESULTS
   GET /result/{job_id}
   ├── Headers: Authorization: Bearer <token>
   └── Response: { "document": [...], "extraction": [...] }
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2026-01-28 | Added user management, upload sessions, patient-centric storage |
| 1.0.0 | 2026-01-26 | Initial release with basic OCR pipeline |
