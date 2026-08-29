import os
import re
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document as LangchainDocument
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
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
        self.persist_directory = os.path.abspath(os.path.join(base_dir, f"user_{user_id}"))
        os.makedirs(self.persist_directory, exist_ok=True)
        self.embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
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
        return {
            "source": filename,
            "document_id": doc_id,
            "user_id": self.user_id,
            "chunk_id": str(uuid.uuid4()),
            "topic": topic,
            "subtopic": subtopic,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    async def ingest(self, text: str, filename: str, doc_id: int):
        cleaned_text = self.clean_text(text)
        output_chunks = self.text_splitter.split_text(cleaned_text)
        langchain_docs = []
        for chunk in output_chunks:
            metadata = self.enrich_metadata(chunk, filename, doc_id)
            langchain_docs.append(LangchainDocument(page_content=chunk, metadata=metadata))
        
        if not langchain_docs: 
            return None

        try:
            # Explicit PersistentClient prevents tenant/RustBindingsAPI mismatches
            client = chromadb.PersistentClient(path=self.persist_directory)
            vectorstore = Chroma(
                client=client,
                collection_name="langchain",
                embedding_function=self.embeddings,
            )
            
            # Add documents
            vectorstore.add_documents(documents=langchain_docs)
            logger.info(f"Successfully indexed {len(langchain_docs)} chunks into ChromaDB at {self.persist_directory}")

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
                    logger.warning(f"Background Graph sync deferred: {e}")
            
            asyncio.create_task(_bg_sync(docs_for_graph, doc_id))
            return IngestResult(vectorstore, len(langchain_docs))
        except Exception as e:
            logger.error(f"Chroma failure: {e}", exc_info=True)
            raise