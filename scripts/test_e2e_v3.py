import asyncio
import logging

from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.learning.course_builder import CourseBuilder
from app.domain.agents.orchestrator import AgenticOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_full_rag_pipeline():
    # Run the orchestrator directly in-process to avoid needing a running HTTP server
    payload_question = "What are the characteristics of a bus topology and when should it be avoided?"
    user_id = 48
    topic = "network_topologies"

    try:
        manager = VectorStoreManager(user_id=user_id)
        builder = CourseBuilder(manager)
        orchestrator = AgenticOrchestrator(manager)

        result = asyncio.run(orchestrator.run(question=payload_question, topic_title=topic))

        print("\n=== SYSTEM RESPONSE ===")
        print(f"Answer: {result.get('answer', '')[:500]}...")
        print(f"Confidence: {result.get('confidence', 0.0)}")
        print(f"Citations: {result.get('citations', [])}")
    except Exception as e:
        logger.error(f"E2E Test failed: {e}")
        raise


if __name__ == "__main__":
    test_full_rag_pipeline()
