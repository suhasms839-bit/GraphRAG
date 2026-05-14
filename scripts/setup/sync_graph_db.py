import asyncio
import os
import uuid
import sys
from typing import List, Dict, Any

# Ensure we can import from the app
sys.path.append(os.getcwd())

from app.core.config import settings
from app.core.logging import logger
from app.domain.graph.graph_querying import get_neo4j_driver
from app.domain.graph.graph_rag.indexer import GraphRAGIndexer

async def populate_neo4j_from_chroma(user_id: int):
    """
    Reads chunks from ChromaDB for a specific user and populates Neo4j with Entities and Relationships.
    """
    print(f"--- Populating Neo4j for User {user_id} ---")
    
    driver = get_neo4j_driver()
    if not driver:
        print("Error: Could not connect to Neo4j. Check your .env settings.")
        return

    # 1. Fetch chunks from Chroma (simulate or read from persist)
    # Since we know user_48 has 'langchain' collection with 8 chunks
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    
    embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
    persist_dir = os.path.join(settings.CHROMA_PERSIST_DIR, f"user_{user_id}")
    
    vectorstore = Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings,
        collection_name="langchain"
    )
    
    all_docs = vectorstore.get()
    documents = all_docs.get("documents", [])
    metadatas = all_docs.get("metadatas", [])
    ids = all_docs.get("ids", [])
    
    if not documents:
        print(f"No documents found in Chroma for User {user_id} at {persist_dir}")
        return

    print(f"Found {len(documents)} chunks to process.")
    
    indexer = GraphRAGIndexer()
    
    # 2. Extract and Load
    for i, (doc_text, meta, chunk_id) in enumerate(zip(documents, metadatas, ids)):
        print(f"Processing chunk {i+1}/{len(documents)}: {chunk_id}")
        
        # Extract Entities & Relationships using LLM
        extraction = await indexer.extract_entities_and_relationships(doc_text)
        
        entities = extraction.get("entities", [])
        relationships = extraction.get("relationships", [])
        
        print(f"  Extracted {len(entities)} entities, {len(relationships)} relationships.")
        
        # 3. Write to Neo4j
        with driver.session() as session:
            # Create Chunk Node
            session.run("""
                MERGE (c:Chunk {chunk_id: $chunk_id})
                SET c.text = $text,
                    c.source = $source,
                    c.user_id = $user_id,
                    c.title = $title
            """, chunk_id=chunk_id, text=doc_text, source=meta.get("source", "unknown"), 
                 user_id=user_id, title=meta.get("title", "Unknown"))
            
            # Create Entities and link to Chunk
            for ent in entities:
                ent_name = ent["name"].strip().upper()
                session.run("""
                    MERGE (e:Entity {name: $name})
                    SET e.type = $type,
                        e.description = $description
                    WITH e
                    MATCH (c:Chunk {chunk_id: $chunk_id})
                    MERGE (c)-[:HAS_ENTITY]->(e)
                """, name=ent_name, type=ent["type"], description=ent["description"], chunk_id=chunk_id)
            
            # Create Relationships
            for rel in relationships:
                source = rel["source"].strip().upper()
                target = rel["target"].strip().upper()
                session.run("""
                    MERGE (s:Entity {name: $source})
                    MERGE (t:Entity {name: $target})
                    MERGE (s)-[r:RELATES_TO {type: $rel_type}]->(t)
                    SET r.description = $description
                """, source=source, target=target, rel_type=rel["type"], description=rel["description"])

    print(f"--- Neo4j Population Complete for User {user_id} ---")

if __name__ == "__main__":
    asyncio.run(populate_neo4j_from_chroma(48))
