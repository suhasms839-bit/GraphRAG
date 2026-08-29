import logging
import os
from hashlib import sha1
from typing import List, Dict, Optional
from langchain_chroma import Chroma
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.models import Document as DBDocument, DocumentChunk as DBDocumentChunk

logger = logging.getLogger(__name__)

class VectorStoreManager:
    def __init__(self, user_id: Optional[int] = None):
        # FastEmbed uses BAAI/bge-small-en-v1.5 via ONNX Runtime (<20MB RAM, zero PyTorch footprint)
        self.embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
        base_dir = settings.CHROMA_PERSIST_DIR
        self.user_id = user_id
        if user_id:
            self.persist_directory = os.path.join(base_dir, f"user_{user_id}")
        else:
            self.persist_directory = base_dir
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=True,
        )

    def get_vectorstore(self) -> Chroma:
        try:
            abs_persist_directory = os.path.abspath(self.persist_directory)
            return Chroma(
                persist_directory=abs_persist_directory,
                embedding_function=self.embeddings,
                collection_name="langchain"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Chroma vectorstore at {self.persist_directory}: {e}")
            return None

    def similarity_search(self, query: str, k: int = 5, metadata_filter: Optional[Dict] = None) -> List[Document]:
        store = self.get_vectorstore()
        if store:
            try:
                results = store.similarity_search(query, k=k, filter=metadata_filter)
                if results:
                    return results
            except Exception as e:
                logger.error(f"Error during similarity_search on vectorstore: {e}")
        return []