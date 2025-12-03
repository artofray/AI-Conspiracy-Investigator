# SHADOW Investigation Platform
# Multi-stage build for optimized image

FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Production image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY *.py ./
COPY frontend/ ./frontend/

# Create directories
RUN mkdir -p /app/data /app/foia_downloads /app/chroma_db

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/app/data/shadow.db

# Expose ports
EXPOSE 5000 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Default command
CMD ["python", "shadow_backend.py", "server", "--host", "0.0.0.0", "--port", "5000"]
