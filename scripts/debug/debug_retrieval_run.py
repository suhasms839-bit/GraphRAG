import asyncio
import json
import os

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
import sys
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.retrieval.hybrid_search import HybridRetriever

async def main():
    manager = VectorStoreManager(user_id=49)
    retriever = HybridRetriever(manager)
    hits = await retriever.retrieve("bus topology", topic_title="Debug", k=5)
    print(json.dumps(hits, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main())
