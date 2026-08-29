from typing import List, Dict, Any
import re
import asyncio
from app.domain.graph.graph_querying import get_neo4j_driver
from app.core.logging import logger
from app.core.config import settings
from app.domain.graph.graph_rag.community import GraphRAGCommunityManager
from app.infrastructure.vectorstore.manager import VectorStoreManager
from langchain_core.documents import Document as LangchainDocument

DEFAULT_ALIAS_MAP = {
    "tcp": "transmission control protocol",
    "ai": "artificial intelligence",
    "gwf": "green water footprint",
}

def normalize_entity(entity: str) -> str:
    if not entity:
        return ""
    e = entity.lower().strip()
    return re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", e)

def extract_candidate_entities(text: str) -> List[str]:
    if not text:
        return []
    candidates = set()
    for m in re.findall(r"\(([A-Z]{2,})\)", text):
        candidates.add(m)
    for m in re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", text):
        candidates.add(m)
    for m in re.findall(r"\b([A-Z]{2,6})\b", text):
        candidates.add(m)
    return list(candidates)

def ensure_graph_indexes(driver):
    """Ensure unique constraints/indexes exist on Entity and Chunk for high-speed lookups."""
    try:
        with driver.session() as session:
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE")
    except Exception as e:
        logger.debug(f"Index creation notice: {e}")

def upsert_entities_and_links(user_id: int, docs: List[Dict[str, Any]], alias_map: Dict[str, str] = None):
    """Sync extracted entities, chunks, and relationships into Neo4j AuraDB without cartesian products."""
    if alias_map is None:
        alias_map = DEFAULT_ALIAS_MAP

    driver = get_neo4j_driver()
    if not driver:
        logger.info("Neo4j driver unavailable; skipping graph sync.")
        return False

    ensure_graph_indexes(driver)

    try:
        with driver.session() as session:
            for doc in docs:
                if isinstance(doc, dict):
                    meta = doc.get("metadata", {}) or {}
                    chunk_id = meta.get("chunk_id", "")
                    text = doc.get("content") or doc.get("page_content") or ""
                    source = meta.get("source", "Document")
                    document_id = meta.get("document_id", 0)
                else:
                    meta = getattr(doc, "metadata", {}) or {}
                    chunk_id = meta.get("chunk_id", "")
                    text = getattr(doc, "page_content", "") or ""
                    source = meta.get("source", "Document")
                    document_id = meta.get("document_id", 0)

                # 1. Upsert Chunk Node
                try:
                    session.run(
                        """
                        MERGE (c:Chunk {chunk_id: $chunk_id})
                        SET c.text = $text, c.source = $source, c.user_id = $user_id, c.document_id = $document_id
                        """,
                        chunk_id=chunk_id, text=text[:3000], source=source, user_id=user_id, document_id=document_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to upsert Chunk node: {e}")

                # 2. Extract Entities & Link sequentially (No Cartesian Product)
                candidates = extract_candidate_entities(text)
                for cand in candidates:
                    canon = alias_map.get(cand.lower(), normalize_entity(cand))
                    alias = normalize_entity(cand)
                    if not canon:
                        continue

                    try:
                        session.run(
                            """
                            MERGE (e:Entity {name: $canon})
                            WITH e
                            MATCH (c:Chunk {chunk_id: $chunk_id})
                            MERGE (c)-[r:MENTIONS]->(e)
                            SET r.alias = $alias, r.count = coalesce(r.count, 0) + 1
                            """,
                            canon=canon, chunk_id=chunk_id, alias=alias
                        )
                    except Exception as e:
                        logger.warning(f"Entity link failed for {canon}: {e}")

                # 3. Create Co-occurrence relationships between entities in same chunk without cartesian product
                for i in range(len(candidates)):
                    for j in range(i + 1, len(candidates)):
                        s = normalize_entity(candidates[i])
                        t = normalize_entity(candidates[j])
                        if s and t and s != t:
                            try:
                                session.run(
                                    """
                                    MATCH (e1:Entity {name: $s})
                                    MATCH (e2:Entity {name: $t})
                                    MERGE (e1)-[r:RELATES_TO]-(e2)
                                    SET r.weight = coalesce(r.weight, 0) + 1
                                    """,
                                    s=s, t=t
                                )
                            except Exception:
                                pass

        logger.info(f"Graph sync completed successfully for {len(docs)} chunks.")
        return True
    except Exception as e:
        logger.error(f"Graph sync failed: {e}")
        return False