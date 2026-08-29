import logging
import os
from typing import List, Dict, Optional
import chromadb
from langchain_chroma import Chroma
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings

logger = logging.getLogger(__name__)

class VectorStoreManager:
    def __init__(self, user_id: Optional[int] = None):
        self.embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
        base_dir = settings.CHROMA_PERSIST_DIR
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
            client = chromadb.PersistentClient(path=self.persist_directory)
            return Chroma(
                client=client,
                collection_name="langchain",
                embedding_function=self.embeddings,
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
                    logger.info(f"Vector search returned {len(results)} matches for query '{query[:30]}...'")
                    return results
                else:
                    logger.warning(f"Vector search returned 0 matches for query '{query[:30]}...'")
            except Exception as e:
                logger.error(f"Error during similarity_search on vectorstore: {e}")
        return []