import asyncio
import logging
from app.domain.generation.answer_engine import answer_with_rag
from app.infrastructure.vectorstore.manager import VectorStoreManager

logging.basicConfig(level=logging.INFO)

async def test_generation_logic():
    print("\n[TEST START] Verifying Generation/Confidence Logic (OFFLINE)")
    
    question = "Explain common bus topology limitations."
    # 48 has the network topology data
    user_id = 48
    topic_title = "Computer Networks"
    from app.infrastructure.vectorstore.manager import VectorStoreManager
    from app.domain.learning.course_builder import CourseBuilder
    
    manager = VectorStoreManager(user_id=user_id)
    builder = CourseBuilder(manager)
    
    # This will trigger the real retrieval, including our new Confidence/Reranker logic
    print(f"Executing RAG (Confidence: Step 2.5, Fallback: Step 4)")
    answer, citations, meta = await answer_with_rag(builder, topic_title, question)
    
    print("\n--- FINAL GENERATED ANSWER ---")
    print(answer)
    print(f"\n[METADATA]: Confidence={meta.get('confidence_label')} ({meta.get('confidence')})")
    print(f"[SOURCE TYPE]: {meta.get('source_type')}")
    print("\n--- CITATIONS ---")
    for cit in citations:
        print(f"File: {cit['file']}, Page: {cit.get('page')}")

if __name__ == "__main__":
    asyncio.run(test_generation_logic())
