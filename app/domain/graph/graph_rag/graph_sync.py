from typing import List, Dict, Any
import re
from app.domain.graph.graph_querying import get_neo4j_driver
from app.core.logging import logger
from app.core.config import settings
from app.domain.graph.graph_rag.community import GraphRAGCommunityManager
from app.infrastructure.vectorstore.manager import VectorStoreManager
import asyncio
from langchain_core.documents import Document as LangchainDocument

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
        all_entities = []
        all_relationships = []

        with driver.session() as session:
            # track names to avoid duplicates
            entity_names_set = set()
            for doc in docs:
                # support both LangChain Document objects and simple dict shapes
                if isinstance(doc, dict):
                    meta = doc.get("metadata", {}) or {}
                    chunk_id = meta.get("chunk_id")
                    text = doc.get("content") or doc.get("page_content") or ""
                    source = meta.get("source")
                    document_id = meta.get("document_id")
                else:
                    meta = getattr(doc, "metadata", {}) or {}
                    chunk_id = meta.get("chunk_id")
                    text = getattr(doc, "page_content", None) or meta.get("content", "")
                    source = meta.get("source")
                    document_id = meta.get("document_id")

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
                # record entities and co-occurrence relationships for community detection
                for cand in candidates:
                    canon = alias_map.get(cand.lower(), None)
                    if not canon:
                        canon = normalize_entity(cand)
                    alias = normalize_entity(cand)
                    if canon and canon not in entity_names_set:
                        entity_names_set.add(canon)
                        all_entities.append({"name": canon})

                # co-occurrence edges
                for i in range(len(candidates)):
                    for j in range(i+1, len(candidates)):
                        s = normalize_entity(candidates[i])
                        t = normalize_entity(candidates[j])
                        all_relationships.append({"source": s, "target": t})

                for cand in candidates:
                    canon = alias_map.get(cand.lower(), None)
                    if not canon:
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

        # After upserting chunks & entities, generate community summaries and persist
        try:
            community_manager = GraphRAGCommunityManager()
            # process_communities is async; run it synchronously here
            summaries = asyncio.run(community_manager.process_communities(all_entities, all_relationships))

            # Persist community summaries into Neo4j and into global Chroma
            try:
                # Persist to Neo4j (Community nodes)
                with driver.session() as session:
                    for comm in summaries:
                        cid = comm.get("community_id")
                        summ = comm.get("summary") or ""
                        ents = comm.get("entities") or []
                        session.run(
                            "MERGE (cs:Community {user_id:$user_id, community_id:$cid}) SET cs.summary = $summary, cs.entities = $ents",
                            user_id=user_id, cid=cid, summary=summ[:4000], ents=ents
                        )
            except Exception as e:
                logger.warning(f"Failed to persist community summaries to Neo4j: {e}")

            # Persist summaries to global Chroma as fallback for global_search
            try:
                docs_for_global = []
                for comm in summaries:
                    docs_for_global.append(LangchainDocument(page_content=(comm.get("summary") or ""), metadata={"source": "community_summary", "community_id": comm.get("community_id"), "user_id": user_id}))

                if docs_for_global and getattr(settings, "CHROMA_PERSIST_COMMUNITY_SUMMARIES", True):
                    gsm = VectorStoreManager(user_id=None)
                    gsm.create_vector_store(docs_for_global)
            except Exception as e:
                logger.warning(f"Failed to persist community summaries to global Chroma: {e}")

        except Exception as e:
            logger.warning(f"Community processing failed: {e}")

        return True
    except Exception as e:
        logger.error(f"Graph sync failed: {e}")
        return False
