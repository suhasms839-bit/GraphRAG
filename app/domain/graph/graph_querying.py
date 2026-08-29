from typing import List, Dict, Any, Optional, Tuple
from itertools import combinations
import os
from app.core.config import settings
from app.core.logging import logger
from .strategies.query_builder import Text2Cypher
from .strategies.schema import map_terminology

_NEO4J_DRIVER = None

def get_neo4j_driver() -> Optional[Any]:
    global _NEO4J_DRIVER

    if _NEO4J_DRIVER:
        return _NEO4J_DRIVER

    try:
        from neo4j import GraphDatabase
    except Exception:
        logger.warning("neo4j package not available; skipping graph queries.")
        return None

    neo_uri = getattr(settings, "NEO4J_URI", None) or os.getenv("NEO4J_URI")
    neo_user = getattr(settings, "NEO4J_USER", None) or getattr(settings, "NEO4J_USERNAME", None) or os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or "ae363b93"
    neo_pass = getattr(settings, "NEO4J_PASSWORD", None) or os.getenv("NEO4J_PASSWORD")

    if not neo_uri or not neo_pass:
        return None

    try:
        driver = GraphDatabase.driver(
            neo_uri, 
            auth=(neo_user, neo_pass),
            max_connection_lifetime=200
        )
        driver.verify_connectivity()
        _NEO4J_DRIVER = driver
        logger.info(f"Neo4j driver successfully connected to {neo_uri} as {neo_user}")
        return _NEO4J_DRIVER
    except Exception as e:
        logger.warning(f"Neo4j connectivity error: {e}")
        return None


def query_graph_smart(question: str, limit: int = 5, anchor_hits: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """GraphRAG: Queries Entity knowledge graph and finds multi-hop Steiner bridges."""
    driver = get_neo4j_driver()
    if not driver:
        return []

    results = []
    path_results = []
    
    # 1. Text2Cypher Discovery
    cypher = None
    try:
        cypher = Text2Cypher.generate(question)
    except Exception:
        cypher = None

    # 2. Multi-hop Knowledge Bridges (Between Vector Chunks)
    if anchor_hits and len(anchor_hits) >= 2:
        anchor_ids = [h["metadata"].get("chunk_id") for h in anchor_hits[:3] if h.get("metadata", {}).get("chunk_id")]
        if len(anchor_ids) >= 2:
            max_depth = int(getattr(settings, "MAX_GRAPH_PATH_DEPTH", 2))
            path_cypher = f"""
            UNWIND $pairs AS pair
            MATCH (start:Chunk {{chunk_id: pair[0]}}), (end:Chunk {{chunk_id: pair[1]}})
            MATCH path = shortestPath((start)-[:MENTIONS|RELATES_TO*1..{max_depth}]-(end))
            RETURN [n IN nodes(path) | coalesce(n.text, n.name)] AS texts, length(path) AS path_length
            LIMIT 2
            """
            pairs = list(combinations(anchor_ids, 2))
            try:
                with driver.session() as session:
                    res = session.run(path_cypher, pairs=pairs[:3])
                    for record in res:
                        texts = record.get("texts") or []
                        pl = record.get("path_length") or 1
                        for t in texts:
                            if t and len(t) > 20:
                                path_results.append({"content": t, "metadata": {"source": "GraphKnowledgeBridge", "path_length": pl}})
            except Exception as e:
                logger.warning(f"Knowledge bridge traversal notice: {e}")

    # 3. Direct Entity and Chunk Lookup
    if not cypher:
        terms = map_terminology(question)
        if not terms:
            terms = [w.lower() for w in question.split() if len(w) > 3]
        cypher = """
        UNWIND $terms AS term
        MATCH (c:Chunk)
        WHERE toLower(c.text) CONTAINS term
        RETURN c.text AS content
        LIMIT $limit
        """
        params = {"terms": terms, "limit": limit}
    else:
        params = {"limit": limit}

    try:
        with driver.session() as session:
            res = session.run(cypher, **params)
            for record in res:
                content = record.get("content") or record.get("c.text")
                if content:
                    results.append({"content": content, "metadata": {"source": "GraphNode", "path_length": 0}})
    except Exception as e:
        logger.warning(f"Neo4j direct query notice: {e}")

    combined = path_results + results
    for item in combined:
        item["seed_score"] = 0.85

    return combined[:limit]