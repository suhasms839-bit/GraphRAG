import pytest
import os
from app.domain.generation.answer_engine import answer_with_rag
from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.learning.course_builder import CourseBuilder

def test_multihop_generation():
    """
    Tests that the generation produces a coherent answer for a multi-hop query.
    """
    # Ensure we have a mock or real vector store for testing
    manager = VectorStoreManager()
    builder = CourseBuilder(manager)

    question = "What are the advantages and disadvantages of ring topology compared to star topology?"
    
    # Note: This requires the vector store to be populated with relevant data
    # In a real CI environment, we would seed the DB first.
    try:
        import asyncio
        answer, citations = asyncio.run(answer_with_rag(
            builder=builder,
            topic_title="Data Communication",
            question=question,
        ))

        assert answer != "No relevant content found.", "The generation should produce an answer."
        assert len(answer) > 50, "The answer should be more than 50 characters."
        print(f"Generated answer: {answer}")
    except Exception as e:
        pytest.fail(f"RAG pipeline failed: {e}")
