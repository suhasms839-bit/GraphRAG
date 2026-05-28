import asyncio
from app.core.config import settings

# Semaphore to limit concurrent ingestion operations per process.
ingest_semaphore = asyncio.Semaphore(settings.INGESTION_CONCURRENCY)
