from typing import List, Dict, Any
import re
from app.domain.graph.graph_querying import get_neo4j_driver
from app.core.logging import logger

# Simple alias map; in production this should be extensible/configurable
DEFAULT_ALIAS_MAP = {
    "tcp": "transmission control protocol",
    "ai": "artificial intelligence",
}


def normalize_entity(entity: str) -> str:
    if not entity:
        return ""
    # Basic normalization: lowercase, strip punctuation and whitespace
    e = entity.lower().strip()
    e = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", e)
    return e


def extract_candidate_entities(text: str) -> List[str]:
    """Heuristic extraction: pick parenthetical acronyms and title-cased phrases."""
    if not text:
        return []

    candidates = set()
    # Parenthetical acronyms: e.g., Transmission Control Protocol (TCP)
    for m in re.findall(r"\(([A-Z]{2,})\)", text):
        candidates.add(m)

    # Title-cased phrases (2+ words)
    for m in re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", text):
        candidates.add(m)

    # Also capture uppercase tokens like HTTP, DNS
    for m in re.findall(r"\b([A-Z]{2,6})\b", text):
        candidates.add(m)

    return list(candidates)


def upsert_entities_and_links(user_id: int, docs: List[Dict[str, Any]], alias_map: Dict[str, str] = None):
    """
    Upsert canonical Entity nodes and alias lists, and create Chunk nodes and relationships.
    docs: list of LangChain-like documents with metadata containing 'chunk_id', 'source', 'document_id'
    """
    if alias_map is None:
        alias_map = DEFAULT_ALIAS_MAP

    driver = get_neo4j_driver()
    if not driver:
        logger.debug("Neo4j driver unavailable; skipping graph sync.")
        return False

    try:
        with driver.session() as session:
            for doc in docs:
                chunk_id = doc.metadata.get("chunk_id")
                text = doc.page_content if hasattr(doc, "page_content") else doc.get("content", "")
                source = doc.metadata.get("source")
                document_id = doc.metadata.get("document_id")

                # Create/merge Chunk node
                try:
                    session.run(
                        "MERGE (c:Chunk {chunk_id: $chunk_id}) SET c.text = $text, c.source = $source, c.user_id = $user_id, c.document_id = $document_id",
                        chunk_id=chunk_id, text=text[:2000], source=source, user_id=user_id, document_id=document_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to upsert Chunk node {chunk_id}: {e}")

                # Extract candidate entities and normalize
                candidates = extract_candidate_entities(text)
                for cand in candidates:
                    canon = alias_map.get(cand.lower(), None)
                    if not canon:
                        # if no mapping, try normalize title-like or acronym expansion
                        canon = normalize_entity(cand)
                    alias = normalize_entity(cand)

                    # Upsert Entity node with aliases list (append if exists)
                    try:
                        session.run(
                            "MERGE (e:Entity {name: $canon}) ON CREATE SET e.aliases = [$alias] ON MATCH SET e.aliases = apoc.coll.toSet(coalesce(e.aliases, []) + [$alias])",
                            canon=canon, alias=alias
                        )
                        # Create relationship (Chunk)-[:MENTIONS {alias:$alias}]->(Entity)
                        session.run(
                            "MATCH (c:Chunk {chunk_id: $chunk_id}), (e:Entity {name: $canon}) MERGE (c)-[r:MENTIONS {alias:$alias}]->(e) SET r.count = coalesce(r.count,0)+1",
                            chunk_id=chunk_id, canon=canon, alias=alias
                        )
                    except Exception as e:
                        logger.warning(f"Failed to link entity {canon} for chunk {chunk_id}: {e}")

        return True
    except Exception as e:
        logger.error(f"Graph sync failed: {e}")
        return False
