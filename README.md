# Medical Document Processing Pipeline

An integrated pipeline for processing clinical documents using OCR, AI-powered spell-checking, and PHI (Protected Health Information) de-identification.

## 🚀 Overview

This application provides a robust API to:
1.  **OCR:** Extract high-quality Markdown and text from medical PDFs and images.
2.  **Spell Check:** Clean clinical terminology using LLMs (Groq API).
3.  **De-identify:** Redact sensitive information (PII/PHI) using an ensemble of the Stanford De-identifier and Microsoft Presidio.

---

## 🛠️ Prerequisites

Before running the application, ensure you have the following installed:

### **1. System Dependencies**
- **Python 3.10+**
- **Poppler:** Required for PDF processing.
    - [Download for Windows](https://github.com/oschwartz10612/poppler-windows/releases/) and add the `bin` folder to your System `PATH`.
- **PostgreSQL:** Primary database.
- **MinIO:** Object storage for files and results.

### **2. AI Models & NLP**
Run these commands after setting up your virtual environment:
```powershell
python -m spacy download en_core_web_sm
```
*Note: The Stanford DEID transformer (~500MB) will automatically download on the first run.*

---

## ⚙️ Setup & Installation

### **1. Clone and Prepare Environment**
```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### **2. Configure Environment Variables**
Create or edit the `.env` file in the root directory:
```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:189014800%40Postgres@localhost:5432/Hospital_records

# Storage (MinIO)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=medical-docs

# API Keys
GROQ_API_KEY=your_key_here

# OCR
CHANDRA_OCR_URL=http://101.53.140.236:8080
```

---

## 🏃 Running the Application

### **1. Start Core Services**
Ensure PostgreSQL and MinIO are running. If you use Docker:
```powershell
docker start postgres_med minio_med
```

### **2. Start the FastAPI Server**
```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
- **API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 📂 Project Structure

- **`main.py`**: Application entry point and router configuration.
- **`Backend-API-DS/`**: Core API logic, database models, and processing services.
- **`Ensemble_DEID/`**: NLP logic for spell checking and de-identification.
- **`pipeline_outputs/`**: Local storage for intermediate files (OCR .md, .txt output).

---

## 🧪 API Usage Flow

1.  **Upload:** `POST /upload`
    - Send your PDF/Image with `patient_id`, `hospital_id`, and `doc_type`.
    - Returns a `job_id`.
2.  **Process:** `POST /process/{job_id}`
    - Starts the OCR -> Spellcheck -> De-ID pipeline asynchronously.
3.  **Status:** `GET /status/{job_id}`
    - Check the real-time progress of each file stage.
4.  **Results:** `GET /result/{job_id}`
    - Retrieve the final de-identified text and associated metadata.

---

## 📝 Important Notes
- **OCR Quality:** The pipeline sends raw PDF bytes directly to the Chandra API for maximum accuracy.
- **Async Processing:** Background tasks run directly in the app (no Redis/Celery required).
- **Logging:** Logs are pretty-printed to the console in development mode for easy debugging.
