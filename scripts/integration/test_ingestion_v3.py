import asyncio
import os
import sys

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.domain.graph.graph_rag.vector_ingest import VectorIngestionPipeline

async def test_ingestion():
    user_id = 49
    filename = "test_case.txt"
    doc_id = 999
    
    text = """# Introduction to Bus Topology
        
    Bus topology is a network topology in which all nodes are connected to a single common cable called the bus. 
    It is the simplest way to connect terminal units together. 
    
    ## Advantages
    - Simple and cost-effective.
    - Easy to install and extend.
    
    ## Disadvantages
    - If the main cable fails, the entire network goes down.
    - Performance decreases as more nodes are added.
    
    This is Page 1 of the notes.
    PAGE 1
    
    Duplicate line test.
    Duplicate line test.
    """
    
    pipeline = VectorIngestionPipeline(user_id=user_id)
    print("Starting ingestion test...")
    
    # 1. Test Cleaning
    cleaned = pipeline.clean_text(text)
    print("\n--- CLEANED TEXT ---\n")
    print(cleaned)
    
    # 2. Test Pipeline (Includes Chunking, Enrichment, Embeddings, Storage)
    print("\nProcessing through pipeline...")
    store = await pipeline.ingest(text, filename, doc_id)
    
    if store:
        print("\nSuccess! Ingested into Chroma.")
        # 3. Verify retrieval
        results = store.similarity_search("What are the advantages of bus topology?", k=1)
        if results:
            print("\n--- VERIFICATION RETRIEVAL ---\n")
            doc = results[0]
            print(f"Content: {doc.page_content[:200]}...")
            print(f"Metadata: {doc.metadata}")
        else:
            print("\nRetrieval failed after ingestion.")
    else:
        print("\nPipeline ingestion failed.")

if __name__ == "__main__":
    asyncio.run(test_ingestion())
