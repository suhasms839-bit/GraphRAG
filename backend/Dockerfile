FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system build dependencies for C-extensions (PyMuPDF, psycopg2, cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy repository
COPY . /app

# Default environment values; overridden by Render/Cloud environment variables
ENV DATABASE_URL="sqlite:///./graphrag.db"
ENV VECTORSTORE_PERSIST_DIRECTORY="/data/chroma_db"
ENV UPLOADS_DIR="/data/uploads"

# Render dynamically assigns PORT at runtime (defaults to 8001 locally)
ENV PORT=8001

EXPOSE 8001

CMD ["sh", "-c", "python scripts/migrations/upgrade_schema.py && uvicorn app.api.server:app --host 0.0.0.0 --port ${PORT:-8001}"]