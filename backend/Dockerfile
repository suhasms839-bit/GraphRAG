FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies for native wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source code
COPY . /app

# Ensure directories exist
RUN mkdir -p /data/chroma_db /data/uploads

# Default environment values
ENV DATABASE_URL="sqlite:///./graphrag.db"
ENV VECTORSTORE_PERSIST_DIRECTORY="/data/chroma_db"
ENV UPLOADS_DIR="/data/uploads"
ENV PORT=10000

EXPOSE 10000

# Use shell form or explicit entrypoint script so $PORT expands properly at runtime
ENTRYPOINT ["sh", "-c", "python scripts/migrations/upgrade_schema.py && exec uvicorn app.api.server:app --host 0.0.0.0 --port ${PORT:-10000}"]