import os
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Header
from sqlalchemy.orm import Session
import fitz

from app.core.config import settings
from app.core.database import get_db
from app.core.models import User, Document
from app.core.schemas import DocumentResponse, DocumentListResponse
from app.core.security import verify_token
from app.core.logging import logger
from app.domain.graph.graph_rag.vector_ingest import VectorIngestionPipeline

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Document storage directory
UPLOAD_DIR = settings.UPLOADS_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _extract_text_for_indexing(file_path: str, extension: str) -> str:
    """Best-effort text extraction used to build retrieval context."""
    ext = extension.lower()

    if ext == "pdf":
        pages = []
        with fitz.open(file_path) as doc:
            for page in doc:
                pages.append(page.get_text("text"))
        return "\n".join(pages).strip()

    if ext in {"txt", "csv"}:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()

    return ""


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Extract and verify JWT token from Authorization header"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    
    token = parts[1]
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a document (PDF, TXT, etc.)"""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required"
        )
    
    allowed_types = {
        "application/pdf",
        "application/x-pdf",
        "text/plain",
        "text/csv",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    }
    allowed_extensions = {"pdf", "txt", "csv", "doc", "docx"}
    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if file.content_type not in allowed_types and extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type not allowed. Allowed: PDF, TXT, CSV, DOC, DOCX"
        )
    
    try:
        contents = await file.read()
        file_size = len(contents)

        if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds max size of {settings.MAX_UPLOAD_SIZE_BYTES} bytes"
            )
        
        # User-specific storage directory
        user_dir = os.path.join(UPLOAD_DIR, str(current_user.id))
        os.makedirs(user_dir, exist_ok=True)
        
        file_name = f"{current_user.id}_{file.filename}"
        file_path = os.path.join(user_dir, file_name)
        
        with open(file_path, "wb") as f:
            f.write(contents)

        # Extract text for sidecar and vector ingestion
        extracted_text = ""
        try:
            extracted_text = _extract_text_for_indexing(file_path, extension)
            if extracted_text:
                sidecar_name = f"{os.path.splitext(file_name)[0]}.txt"
                sidecar_path = os.path.join(user_dir, sidecar_name)
                with open(sidecar_path, "w", encoding="utf-8") as tf:
                    tf.write(extracted_text)
        except Exception as extraction_err:
            logger.warning(f"Text extraction failed for {file.filename}: {extraction_err}")
        
        # Save record in SQL DB
        mime = file.content_type or (f"application/{extension}" if extension else "application/octet-stream")
        document = Document(
            user_id=current_user.id,
            filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime,
            ingested=False,
            chunk_count=0,
            ingest_log=None
        )

        db.add(document)
        db.commit()
        db.refresh(document)
        logger.info(f"Document saved to database: {file.filename} (ID: {document.id}) by user {current_user.id}")

        # Ingestion pipeline execution
        if extracted_text:
            try:
                pipeline = VectorIngestionPipeline(user_id=current_user.id)
                result = await pipeline.ingest(text=extracted_text, filename=file.filename, doc_id=document.id)
                if result:
                    document.ingested = True
                    document.chunk_count = getattr(result, "chunks", 0)
                else:
                    document.ingested = False
            except Exception as ex:
                logger.error(f"Ingestion failed for document {document.id}: {ex}")
                document.ingest_log = str(ex)
            
            db.add(document)
            db.commit()
            db.refresh(document)

        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get("/list", response_model=DocumentListResponse)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all documents for current user"""
    documents = db.query(Document).filter(Document.user_id == current_user.id).all()
    return DocumentListResponse(
        documents=[DocumentResponse.from_orm(doc) for doc in documents],
        total_count=len(documents)
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a document"""
    document = db.query(Document).filter(
        (Document.id == document_id) & (Document.user_id == current_user.id)
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    try:
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
    
    db.delete(document)
    db.commit()
    logger.info(f"Document deleted: {document.id} by user {current_user.id}")
    
    return {"message": "Document deleted successfully"}