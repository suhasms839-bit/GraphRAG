import logging
import os
import re
from hashlib import sha1
from typing import List, Dict, Optional
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.models import Document as DBDocument, DocumentChunk as DBDocumentChunk

logger = logging.getLogger(__name__)

class VectorStoreManager:
    def __init__(self, user_id: Optional[int] = None):
        self.embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
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

    def load_documents(self, data_folder: str) -> List[Document]:
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)
            return []

        documents = []
        for filename in os.listdir(data_folder):
            file_path = os.path.join(data_folder, filename)
            try:
                if filename.endswith(".txt"):
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = f.read()
                    # Store the full document as a "parent"
                    documents.append(Document(
                        page_content=text,
                        metadata={
                            "source": filename,
                            "doc_type": "parent",
                            "title": filename.rsplit(".", 1)[0].replace("_", " ").title()
                        }
                    ))
            except Exception as e:
                logger.error(f"Error loading {filename}: {e}")
        return documents

    def create_vector_store(self, documents: List[Document]):
        if not documents:
            return None
        
        all_splits = []
        doc_ids = []
        
        for doc in documents:
            # Create a unique ID for the parent
            parent_id = sha1(doc.page_content.encode('utf-8')).hexdigest()[:20]
            
            # Split the document into child chunks
            splits = self.text_splitter.split_documents([doc])
            
            for i, split in enumerate(splits):
                # METADATA ENRICHMENT (The "Finetuning" equivalent)
                # Prepend title to content to improve embedding quality for technical terms
                title = split.metadata.get("title", "Unknown")
                split.page_content = f"Topic: {title}\nContent: {split.page_content}"
                
                split.metadata["doc_type"] = "chunk"
                split.metadata["parent_id"] = parent_id
                
                stable_key = f"{split.metadata['source']}|{i}|{split.page_content[:50]}"
                doc_id = f"chunk_{sha1(stable_key.encode('utf-8')).hexdigest()[:20]}"
                
                all_splits.append(split)
                doc_ids.append(doc_id)

        try:
            vectorstore = Chroma.from_documents(
                documents=all_splits,
                ids=doc_ids,
                embedding=self.embeddings,
                persist_directory=self.persist_directory
            )
            logger.info(f"Created vector store with {len(all_splits)} enriched chunks")
            return vectorstore
        except Exception as e:
            logger.error(f"Failed to create Chroma vector store at {self.persist_directory}: {e}")
            return None

    def get_parent_context(self, parent_id: str) -> Optional[str]:
        """Retrieves the full parent document text (or a large window)."""
        # In this implementation, we simulate parent retrieval by searching for 
        # other chunks with the same parent_id and joining them, 
        # or we could store parents in a separate collection.
        # For simplicity and performance, we'll fetch the top 3 chunks of the same parent.
        store = self.get_vectorstore()
        results = store.get(where={"parent_id": parent_id}, limit=5)
        if results and results["documents"]:
            return "\n...\n".join(results["documents"])
        return None

    def similarity_search(self, query: str, k: int = 5, metadata_filter: Optional[Dict] = None) -> List[Document]:
        store = self.get_vectorstore()
        # Try vectorstore first if available
        if store:
            try:
                results = store.similarity_search(query, k=k, filter=metadata_filter)
                if results:
                    return results
                else:
                    logger.warning("Vectorstore returned no hits; will attempt DB/file fallback")
            except Exception as e:
                logger.error(f"Error during similarity_search on vectorstore: {e}")

        # DB/file fallback: search stored document chunks for the user (simple ilike match)
        logger.warning("Vectorstore unavailable or empty; attempting DB/file fallback similarity search")
        try:
            if not self.user_id:
                return []
            db = SessionLocal()
            q = db.query(DBDocumentChunk, DBDocument).join(DBDocument, DBDocument.id == DBDocumentChunk.document_id).filter(DBDocument.user_id == self.user_id)
            q = q.filter(DBDocumentChunk.chunk_text.ilike(f"%{query}%"))
            q = q.limit(k)
            results = q.all()
            docs = []
            for chunk, doc in results:
                docs.append(Document(page_content=chunk.chunk_text, metadata={"source": doc.filename or "unknown", "page": chunk.chunk_index}))

            # If no chunk rows exist, fallback to searching raw uploaded files (full-document scan)
            if not docs:
                docs_rows = db.query(DBDocument).filter(DBDocument.user_id == self.user_id).all()
                for d in docs_rows:
                    try:
                        fp = d.file_path or d.filename
                        if not fp:
                            continue
                        # Normalize path
                        fp = os.path.abspath(fp)
                        if not os.path.exists(fp):
                            # Try relative to project root
                            alt = os.path.join(os.getcwd(), fp)
                            if os.path.exists(alt):
                                fp = alt
                            else:
                                continue
                        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                            text = f.read()
                        if query.lower() in text.lower():
                            snippet = text[:2000]
                            docs.append(Document(page_content=snippet, metadata={"source": d.filename or "unknown", "page": 1}))
                            if len(docs) >= k:
                                break
                    except Exception:
                        continue

            return docs
        except Exception as e:
            logger.error(f"DB/file fallback similarity_search failed: {e}")
            return []

        try:
            return store.similarity_search(query, k=k, filter=metadata_filter)
        except Exception as e:
            logger.error(f"Error during similarity_search: {e}")
            return []
