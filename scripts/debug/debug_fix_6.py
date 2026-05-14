import asyncio
import logging
from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.retrieval.hybrid_search import HybridRetriever

async def debug_retrieval():
    print("\n--- [FIX 6] RETRIEVAL DEBUG: 'ABCDE method' ---")
    query = "ABCDE method"
    user_id = 48
    
    manager = VectorStoreManager(user_id=user_id)
    retriever = HybridRetriever(manager)
    
    result = await retriever.retrieve(query, topic_title="General", k=5)
    
    print(f"Query: {query}")
    print(f"Confidence: {result['confidence']} ({result['confidence_label']})")
    print(f"\nRetrieved {len(result['hits'])} hits:")
    
    for i, h in enumerate(result['hits']):
        source = h['metadata'].get('source', 'Unknown')
        snippet = h['content'][:250].replace('\n', ' ')
        print(f"\n[HIT {i+1}] Source: {source}")
        print(f"Content: {snippet}...")

if __name__ == "__main__":
    asyncio.run(debug_retrieval())
