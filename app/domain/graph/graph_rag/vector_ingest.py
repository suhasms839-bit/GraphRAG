import os
import re
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document as LangchainDocument
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.models import Document
from app.domain.graph.graph_rag.graph_sync import upsert_entities_and_links

logger = logging.getLogger("app")

class IngestResult:
    def __init__(self, vs, count):
        self.vectorstore = vs
        self.chunks = count
        self.ok = True
    def __getattr__(self, name):
        return getattr(self.vectorstore, name)

class VectorIngestionPipeline:
    def __init__(self, user_id: int):
        self.user_id = user_id
        base_dir = settings.CHROMA_PERSIST_DIR
        self.persist_directory = os.path.join(base_dir, f"user_{user_id}")
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="text-embedding-004",  # <--- Change from "models/text-embedding-004" to "text-embedding-004"
            google_api_key=settings.GEMINI_API_KEY
        )
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200, add_start_index=True)

    def clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"(\n\s*){2,}", "\n\n", text)
        return text.strip()

    def enrich_metadata(self, chunk: str, filename: str, doc_id: int) -> Dict[str, Any]:
        import uuid
        lines = chunk.split("\n")
        topic = lines[0][:100] if lines else "General"
        subtopic = "Intro" if "intro" in chunk.lower() else "Content"
        return {"source": filename, "document_id": doc_id, "user_id": self.user_id, "chunk_id": str(uuid.uuid4()), "topic": topic, "subtopic": subtopic, "created_at": datetime.now(timezone.utc).isoformat()}

    async def ingest(self, text: str, filename: str, doc_id: int):
        cleaned_text = self.clean_text(text)
        output_chunks = self.text_splitter.split_text(cleaned_text)
        langchain_docs = []
        for chunk in output_chunks:
            metadata = self.enrich_metadata(chunk, filename, doc_id)
            langchain_docs.append(LangchainDocument(page_content=chunk, metadata=metadata))
        
        try:
            db = SessionLocal()
            user_docs = db.query(Document).filter(Document.user_id == self.user_id).all()
            existing_chunks = sum([d.chunk_count or 0 for d in user_docs])
            db.close()
        except:
            existing_chunks = 0

        max_per_user = int(getattr(settings, "CHROMA_MAX_CHUNKS_PER_USER", 20000))
        max_per_ingest = int(getattr(settings, "CHROMA_MAX_CHUNKS_PER_INGEST", 2000))
        planned = len(langchain_docs)
        if planned > max_per_ingest: 
            raise ValueError("Ingest limit exceeded")
        if existing_chunks + planned > max_per_user: 
            raise ValueError("User quota exceeded")
        if not langchain_docs: 
            return None

        try:
            vectorstore = Chroma.from_documents(documents=langchain_docs, embedding=self.embeddings, persist_directory=self.persist_directory)
            docs_for_graph = [{"content": d.page_content, "metadata": d.metadata} for d in langchain_docs]
            
            async def _bg_sync(docs, doc_id):
                try:
                    loop = asyncio.get_running_loop()
                    ok = await loop.run_in_executor(None, upsert_entities_and_links, self.user_id, docs)
                    from app.core.database import SessionLocal as BGSessionLocal
                    from app.core.models import Document as DBDocument
                    db = BGSessionLocal()
                    doc = db.query(DBDocument).filter(DBDocument.id == doc_id).first()
                    if doc and ok:
                        doc.graph_ready = True
                        db.commit()
                    db.close()
                except Exception as e: 
                    logger.exception(f"BG sync failed: {e}")
            
            asyncio.create_task(_bg_sync(docs_for_graph, doc_id))
            return IngestResult(vectorstore, len(langchain_docs))
        except Exception as e:
            logger.error(f"Chroma failure: {e}")
            raise