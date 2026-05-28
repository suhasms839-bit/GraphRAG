import os
import socket
from typing import Dict, List
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, documents, chat, system
from app.api.routes import mcp as mcp_route
from app.core.logging import logger

from app.core.config import settings
from app.core.database import engine
try:
    from neo4j import GraphDatabase
except Exception:
    GraphDatabase = None
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from uuid import uuid4
import time


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(settings.REQUEST_ID_HEADER) or str(uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[settings.REQUEST_ID_HEADER] = rid
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check Content-Length header when present
        cl = request.headers.get("content-length")
        if cl:
            try:
                if int(cl) > settings.MAX_UPLOAD_SIZE_BYTES:
                    return JSONResponse({"detail": "Request body too large"}, status_code=413)
            except Exception:
                pass
        return await call_next(request)


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.storage = {}  # ip -> (count, window_start)

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        now = int(time.time())
        window = settings.RATE_LIMIT_WINDOW_SECONDS
        limit = settings.RATE_LIMIT_REQUESTS

        rec = self.storage.get(client)
        if not rec or now - rec[1] >= window:
            self.storage[client] = [1, now]
        else:
            rec[0] += 1
            self.storage[client] = rec

        if self.storage[client][0] > limit:
            return JSONResponse({"detail": "Too many requests"}, status_code=429)

        return await call_next(request)


def _parse_cors_origins(raw_value: str | None) -> List[str]:
    if not raw_value:
        return [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:5180",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5180",
        ]

    origins = [origin.strip() for origin in raw_value.split(",") if origin.strip()]
    return origins or ["http://localhost:3000"]

app = FastAPI(title="Agentic RAG API")

# Operational middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(SimpleRateLimitMiddleware)

allowed_origins = _parse_cors_origins(os.getenv("CORS_ORIGINS"))

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("CORS origins configured: %s", allowed_origins)

# Include routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(system.router)
app.include_router(mcp_route.router)

@app.get("/health")
async def health_check():
    """Basic liveness health check."""
    return {"status": "ok", "message": "API is running"}


@app.get("/health/liveness")
async def liveness():
    return {"status": "alive"}


def _check_db() -> Dict[str, str]:
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return {"db": "ok"}
    except Exception as e:
        return {"db": f"error: {e}"}


def _check_chroma() -> Dict[str, str]:
    path = settings.CHROMA_PERSIST_DIR
    try:
        if not os.path.exists(path):
            return {"chroma": f"missing: {path}"}
        if not os.access(path, os.W_OK | os.R_OK):
            return {"chroma": f"permission error: {path}"}
        return {"chroma": "ok"}
    except Exception as e:
        return {"chroma": f"error: {e}"}


def _check_neo4j() -> Dict[str, str]:
    if not settings.NEO4J_URI or not GraphDatabase:
        return {"neo4j": "skipped"}
    try:
        parsed = urlparse(settings.NEO4J_URI)
        host = parsed.hostname or "localhost"
        port = parsed.port or 7687
        with socket.create_connection((host, port), timeout=2):
            return {"neo4j": "ok"}
    except Exception as e:
        return {"neo4j": f"error: {e}"}


def _check_llm() -> Dict[str, str]:
    # Check that at least one LLM path is configured
    if settings.USE_OLLAMA:
        try:
            parsed = urlparse(settings.OLLAMA_BASE_URL)
            host = parsed.hostname or "localhost"
            port = parsed.port or 11434
            with socket.create_connection((host, port), timeout=2):
                return {"llm": "ollama:ok"}
        except Exception as e:
            return {"llm": f"ollama:error: {e}"}
    if settings.GEMINI_API_KEY:
        return {"llm": "gemini:configured"}
    return {"llm": "none-configured"}


@app.get("/health/readiness")
async def readiness():
    """Readiness endpoint — checks dependent services and returns 200/503."""
    results: Dict[str, str] = {}
    results.update(_check_db())
    results.update(_check_chroma())
    results.update(_check_neo4j())
    results.update(_check_llm())

    unhealthy = [k for k, v in results.items() if isinstance(v, str) and (v.startswith("error") or v.startswith("missing") or v.startswith("permission"))]
    http_status = 200 if not unhealthy else 503
    return JSONResponse(content=results, status_code=http_status)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
