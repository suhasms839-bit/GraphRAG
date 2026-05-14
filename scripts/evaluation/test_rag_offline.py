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
    result = await answer_with_rag(builder, topic_title, question)
    # Support dict or tuple return shapes
    if isinstance(result, dict):
        answer = result.get("answer", "")
        citations = result.get("citations", [])
        meta = {"confidence": result.get("confidence"), "source_type": result.get("source"), "confidence_reason": result.get("confidence_reason", "")}
    elif isinstance(result, tuple):
        if len(result) == 2:
            answer, citations = result
            meta = {}
        elif len(result) >= 3:
            answer, citations, meta = result[0], result[1], result[2]
        else:
            answer, citations, meta = "", [], {}
    else:
        answer, citations, meta = "", [], {}

    print("\n--- FINAL GENERATED ANSWER ---")
    print(answer)
    print(f"\n[METADATA]: Confidence={meta.get('confidence_label') or meta.get('confidence')} ({meta.get('confidence')})")
    print(f"[SOURCE TYPE]: {meta.get('source_type') or meta.get('source')}")
    print("\n--- CITATIONS ---")
    for cit in citations:
        print(f"File: {cit.get('file')}, Page: {cit.get('page')}")

if __name__ == "__main__":
    asyncio.run(test_generation_logic())
