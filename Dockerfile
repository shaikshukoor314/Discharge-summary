# Stage 1: Base image with Python
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for PDF processing and spacy
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libpoppler-cpp-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy entire application
COPY . .

# Create necessary directories for pipeline outputs
RUN mkdir -p pipeline_outputs/De-identification_Output_pages \
    && mkdir -p pipeline_outputs/OCR_output_pages \
    && mkdir -p pipeline_outputs/Spell_check_Output_pages \
    && mkdir -p output

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/docs', timeout=5)" || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
