import os
import sys
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.generation.answer_engine import answer_with_rag
from app.domain.learning.course_builder import CourseBuilder
from app.core.logging import logger

def test_quality():
    logger.info("Starting RAG quality test...")
    
    manager = VectorStoreManager()
    
    # 1. Indexing
    data_dir = "./data"
    logger.info(f"Loading documents from {data_dir}")
    documents = manager.load_documents(data_dir)
    if not documents:
        logger.error("No documents found in data directory.")
        return

    logger.info(f"Indexing {len(documents)} documents...")
    manager.create_vector_store(documents)
    
    # 2. Vectorstore verification
    logger.info("Testing vectorstore retrieval...")
    results = manager.similarity_search("bus topology", k=3)
    logger.info(f"Vectorstore test results: {len(results)} hits")
    if results:
        for i, result in enumerate(results):
            logger.info(f"Result {i+1}: {result.page_content[:100]}...")
    else:
        logger.warning("Vectorstore test returned no results - ingestion may be broken!")
    
    # 3. Querying
    builder = CourseBuilder(manager)
    
    questions = [
        "What are the advantages of mesh topology?",
        "Compare star and bus topology in terms of reliability.",
        "What happens if the central hub fails in a star topology?",
        "Explain the unidirectional traffic issue in ring topology."
    ]
    
    for q in questions:
        print(f"\n--- Question: {q} ---")
        import asyncio
        result = asyncio.run(answer_with_rag(
            builder=builder,
            topic_title="Computer Networks",
            question=q
        ))
        # Support both dict and tuple return shapes
        if isinstance(result, dict):
            answer = result.get("answer", "")
            citations = result.get("citations", [])
        elif isinstance(result, tuple) and len(result) >= 2:
            answer, citations = result[0], result[1]
        else:
            raise AssertionError(f"Unexpected answer_with_rag return shape: {type(result)}")

        print(f"Answer: {answer}")
        print(f"Citations: {citations}")

if __name__ == "__main__":
    test_quality()
