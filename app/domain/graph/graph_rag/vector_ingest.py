import os
import re
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from langchain_core.documents import Document as LangchainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from app.core.config import settings
from app.core.logging import logger

class VectorIngestionPipeline:
    """
    Implements Step 1: Ingestion Pipeline (v3.0) for Vector storage.
    Includes Data Cleaning, Semantic Chunking, and Metadata Enrichment.
    """
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        # v3.0 Requirement: Strong embeddings
        self.embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
        
        # FIX 4: Improve Chunking (200-300 tokens, paragraph awareness)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=300,      # ~300 tokens/characters
            chunk_overlap=50,    # ~50 tokens/characters
            separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
            keep_separator=True,
        )
        
        # User-specific storage
        base_dir = settings.CHROMA_PERSIST_DIR
        self.persist_directory = os.path.join(base_dir, f"user_{user_id}")

    def clean_text(self, text: str) -> str:
        """
        1.1 Data Cleaning (MANDATORY)
        - Remove headers, footers (pattern-based)
        - Remove duplicate text
        - Normalize whitespace
        - Convert to clean paragraphs
        """
        # Normalize whitespace and newlines
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Remove common PDF artifacts/headers/footers (regex example)
        # e.g., page numbers at the start or end of lines
        text = re.sub(r'^\s*PAGE\s*\d+\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)

        # Remove consecutive duplicate lines (simple deduplication)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                if cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")
                continue
            if not cleaned_lines or line != cleaned_lines[-1]:
                cleaned_lines.append(line)
        
        text = '\n'.join(cleaned_lines)
        
        # Normalize whitespace once more for paragraphs
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def enrich_metadata(self, chunk: str, filename: str, doc_id: int) -> Dict[str, Any]:
        """
        1.3 Metadata Enrichment (REQUIRED)
        """
        # Simple topic/subtopic detection (can be improved with LLM)
        topic = "General"
        subtopic = "Intro"
        
        # Try to find a header in the first part of the chunk
        lines = chunk.split('\n')
        for line in lines[:3]:
            if line.startswith('#'):
                topic = line.lstrip('#').strip()
                break
        
        return {
            "chunk_id": str(uuid.uuid4()),
            "source": filename,
            "document_id": doc_id,
            "user_id": self.user_id,
            "topic": topic,
            "subtopic": subtopic,
            "created_at": datetime.utcnow().isoformat()
        }

    async def ingest(self, text: str, filename: str, doc_id: int):
        """
        Executes the full ingestion pipeline.
        """
        # 1. Clean
        cleaned_text = self.clean_text(text)
        
        # 2. Chunk (Semantic-ish)
        output_chunks = self.text_splitter.split_text(cleaned_text)
        
        # 3. Enrich & Create Langchain Documents
        langchain_docs = []
        for chunk in output_chunks:
            metadata = self.enrich_metadata(chunk, filename, doc_id)
            langchain_docs.append(LangchainDocument(
                page_content=chunk,
                metadata=metadata
            ))
            
        # 4. Storage (Vector DB)
        status = {"ok": False, "chunks": 0, "errors": []}
        if langchain_docs:
            try:
                # Store in user-specific Chroma
                # Note: Embedding generation happens inside from_documents
                vectorstore = Chroma.from_documents(
                    documents=langchain_docs,
                    embedding=self.embeddings,
                    persist_directory=self.persist_directory
                )
                logger.info(f"Ingested {len(langchain_docs)} chunks for {filename} (User {self.user_id})")
                status["ok"] = True
                status["chunks"] = len(langchain_docs)
                return status
            except Exception as e:
                logger.error(f"Failed to store chunks in Chroma: {e}")
                status["errors"].append(str(e))
                return status
        return status
