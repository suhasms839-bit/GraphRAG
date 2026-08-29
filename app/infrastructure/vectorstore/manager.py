import logging
import os
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings

logger = logging.getLogger(__name__)

class VectorStoreManager:
    def __init__(self, user_id: Optional[int] = None):
        self.embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
        
        # Resolve to valid local directory on both Windows & Linux
        base_dir = getattr(settings, "VECTORSTORE_PERSIST_DIRECTORY", "./chroma_db")
        if base_dir.startswith("/data") and not os.path.exists("/data"):
            base_dir = "./chroma_db"
            
        self.user_id = user_id
        if user_id:
            self.persist_directory = os.path.abspath(os.path.join(base_dir, f"user_{user_id}"))
        else:
            self.persist_directory = os.path.abspath(base_dir)
            
        os.makedirs(self.persist_directory, exist_ok=True)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=True,
        )

    def get_vectorstore(self) -> Optional[Chroma]:
        try:
            client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False, is_persistent=True)
            )
            return Chroma(
                client=client,
                collection_name="langchain",
                embedding_function=self.embeddings,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Chroma vectorstore at {self.persist_directory}: {e}")
            return None

    def get_parent_context(self, parent_id: str) -> Optional[str]:
        return None

    def similarity_search(self, query: str, k: int = 5, metadata_filter: Optional[Dict] = None) -> List[Document]:
        store = self.get_vectorstore()
        if store:
            try:
                results = store.similarity_search(query, k=k, filter=metadata_filter)
                if results:
                    logger.info(f"Vector search returned {len(results)} matches for query '{query[:40]}'")
                    return results
            except Exception as e:
                logger.error(f"Error during similarity_search on vectorstore: {e}")

        # Fallback: scan user text files directly from disk if vectorstore is indexing or empty
        try:
            uploads_dir = getattr(settings, "UPLOADS_DIR", "./uploads")
            if uploads_dir.startswith("/data") and not os.path.exists("/data"):
                uploads_dir = "./uploads"
            
            user_upload_dir = os.path.abspath(os.path.join(uploads_dir, str(self.user_id))) if self.user_id else uploads_dir
            fallback_docs = []
            if os.path.exists(user_upload_dir):
                for fname in os.listdir(user_upload_dir):
                    if fname.endswith(".txt"):
                        fpath = os.path.join(user_upload_dir, fname)
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            text = f.read()
                        if any(term in text.lower() for term in query.lower().split() if len(term) > 3):
                            fallback_docs.append(Document(page_content=text[:1500], metadata={"source": fname, "page": 1}))
            if fallback_docs:
                logger.info(f"Disk sidecar fallback retrieved {len(fallback_docs)} documents.")
                return fallback_docs[:k]
        except Exception as fb_err:
            logger.error(f"Fallback scan failed: {fb_err}")

        return []