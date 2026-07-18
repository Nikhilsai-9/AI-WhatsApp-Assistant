# Build stage: install dependencies
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies (setuptools for whisper's setup.py, build-essential for compiling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment first
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install build tools for Python packages
# setuptools<68 includes pkg_resources needed by legacy whisper package
RUN pip install --no-cache-dir --upgrade pip "setuptools<68" wheel

# Copy and install Python dependencies
# --no-build-isolation is needed for whisper which uses legacy setup.py with pkg_resources
COPY requirements.txt .
RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt

# Production stage: runtime dependencies only
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install runtime system dependencies:
# - libpq5: PostgreSQL client library for psycopg2
# - libgl1: OpenGL library (replaces deprecated libgl1-mesa-glx)
# - libglib2.0-0: GLib for GObject introspection
# - tesseract-ocr + lang packs: OCR engine
# - ffmpeg: Audio processing for whisper
# - libjpeg, libpng, zlib: Image format support for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-tel \
    tesseract-ocr-eng \
    ffmpeg \
    libjpeg62-turbo \
    libpng16-16 \
    zlib1g \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Run migrations and start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]