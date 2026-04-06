import asyncio
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.learning.course_builder import CourseBuilder
from app.domain.generation.answer_engine import answer_with_rag

async def main():
    manager = VectorStoreManager(user_id=49)
    builder = CourseBuilder(manager)
    answer, citations = await answer_with_rag(builder=builder, topic_title="Debug", question="bus topology", k=5)
    print("\n=== ANSWER ===\n")
    print(answer)
    print("\n=== CITATIONS ===\n")
    print(json.dumps(citations, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main())
