import asyncio
import json
from app.domain.graph.graph_rag.indexer import GraphRAGIndexer
from app.domain.graph.graph_rag.community import GraphRAGCommunityManager

async def test_graph_rag_pipeline():
    print("--- Testing MS GraphRAG Pipeline ---")
    
    # Sample unstructured text
    text = """
    Preface: This document covers network topologies.
    The Star Topology is a common network configuration. In a Star Topology, all devices are connected to a central hub.
    The Hub acts as a central controller. If the hub fails, the entire network goes down, which is a Single Point of Failure.
    JSS STU uses Star Topology in its computer labs for easy management.
    Footnote: [1] Cisco Networking Guide.
    """
    
    indexer = GraphRAGIndexer()
    
    # 1. Preprocessing
    clean_text = indexer.preprocess(text)
    print(f"Clean Text: {clean_text[:100]}...")
    
    # 2. Extraction & Summarization (Simulated for speed in test)
    # In a real run, this would call Gemini
    print("Extracting entities and relationships...")
    entities = [
        {"name": "STAR TOPOLOGY", "type": "CONCEPT", "description": "A network configuration where all nodes connect to a central hub."},
        {"name": "HUB", "type": "COMPONENT", "description": "A central controller in a star network."},
        {"name": "SINGLE POINT OF FAILURE", "type": "CONCEPT", "description": "A part of a system that, if it fails, will stop the entire system from working."},
        {"name": "JSS STU", "type": "ORGANIZATION", "description": "A university in Mysuru."}
    ]
    relationships = [
        {"source": "STAR TOPOLOGY", "target": "HUB", "type": "USES", "description": "Star topology requires a central hub."},
        {"source": "HUB", "target": "SINGLE POINT OF FAILURE", "type": "IS", "description": "The hub is a single point of failure in star networks."}
    ]
    
    # 3. Community Detection
    print("Detecting communities...")
    manager = GraphRAGCommunityManager()
    communities = manager.detect_communities_local(entities, relationships)
    print(f"Detected Communities: {communities}")
    
    # 4. Community Summarization (Simulated)
    print("Summarizing communities...")
    # This would call Gemini in production
    
    print("--- MS GraphRAG Pipeline Test Complete ---")

if __name__ == "__main__":
    asyncio.run(test_graph_rag_pipeline())
