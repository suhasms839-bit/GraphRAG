import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.core.database import engine, Base
from app.api.routes import auth, documents, chat
from app.core.logging import logger

# Create database tables
Base.metadata.create_all(bind=engine)


def _ensure_legacy_users_schema() -> None:
    """Patch older `users` table schemas with columns required by the current auth model."""
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return

    existing = {col["name"] for col in inspector.get_columns("users")}
    alter_statements = []

    if "username" not in existing:
        alter_statements.append("ALTER TABLE users ADD COLUMN username VARCHAR(255)")
    if "hashed_password" not in existing:
        alter_statements.append("ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255)")
    if "full_name" not in existing:
        alter_statements.append("ALTER TABLE users ADD COLUMN full_name VARCHAR(255)")
    if "role" not in existing:
        alter_statements.append("ALTER TABLE users ADD COLUMN role VARCHAR(100)")
    if "department" not in existing:
        alter_statements.append("ALTER TABLE users ADD COLUMN department VARCHAR(255)")
    if "organization" not in existing:
        alter_statements.append("ALTER TABLE users ADD COLUMN organization VARCHAR(255)")
    if "is_active" not in existing:
        alter_statements.append("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
    if "created_at" not in existing:
        alter_statements.append("ALTER TABLE users ADD COLUMN created_at TIMESTAMP")
    if "updated_at" not in existing:
        alter_statements.append("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP")

    if not alter_statements:
        return

    with engine.begin() as conn:
        for stmt in alter_statements:
            conn.execute(text(stmt))


def _ensure_legacy_documents_schema() -> None:
    """Patch older `documents` table schemas with columns required by current upload/list APIs."""
    inspector = inspect(engine)
    if not inspector.has_table("documents"):
        return

    existing = {col["name"] for col in inspector.get_columns("documents")}
    alter_statements = []

    if "user_id" not in existing:
        alter_statements.append("ALTER TABLE documents ADD COLUMN user_id INTEGER")
    if "file_path" not in existing:
        alter_statements.append("ALTER TABLE documents ADD COLUMN file_path VARCHAR(512)")
    if "file_size" not in existing:
        alter_statements.append("ALTER TABLE documents ADD COLUMN file_size INTEGER")
    if "mime_type" not in existing:
        alter_statements.append("ALTER TABLE documents ADD COLUMN mime_type VARCHAR(100)")
    if "uploaded_at" not in existing:
        alter_statements.append("ALTER TABLE documents ADD COLUMN uploaded_at TIMESTAMP")

    if not alter_statements:
        return

    with engine.begin() as conn:
        for stmt in alter_statements:
            conn.execute(text(stmt))


_ensure_legacy_users_schema()
_ensure_legacy_documents_schema()

app = FastAPI(title="Agentic RAG API")

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
