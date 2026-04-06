from typing import List, Dict, Any, Optional, Tuple
from itertools import combinations
import time
import os
from app.core.config import settings
from app.core.logging import logger
from .strategies.query_builder import Text2Cypher
from .strategies.schema import map_terminology

# Cached driver to avoid repeated connect attempts
_NEO4J_DRIVER = None
_NEO4J_DRIVER_ATTEMPTED = False


def get_neo4j_driver() -> Optional[Any]:
    """Return a cached Neo4j driver, waiting once before the first attempt.

    This waits for `settings.AURA_WAIT_SECONDS` before the first connection attempt
    (to allow managed Aura instances to become available), then tries to verify
    connectivity. If verification succeeds, the driver is cached and returned.
    If neo4j is not installed or connection fails, returns None.
    """
    global _NEO4J_DRIVER, _NEO4J_DRIVER_ATTEMPTED

    if _NEO4J_DRIVER:
        return _NEO4J_DRIVER

    if _NEO4J_DRIVER_ATTEMPTED:
        return None

    _NEO4J_DRIVER_ATTEMPTED = True

    try:
        from neo4j import GraphDatabase
    except Exception:
        logger.warning("neo4j package not available; skipping graph queries.")
        return None

    wait_seconds = getattr(settings, "AURA_WAIT_SECONDS", 60)
    try:
        wait_seconds = int(os.getenv("AURA_WAIT_SECONDS", str(wait_seconds)))
    except Exception:
        wait_seconds = 60

    logger.info(f"Waiting {wait_seconds}s before attempting Neo4j connection (AURA wait)")
    time.sleep(wait_seconds)

    try:
        driver = GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))
        # Verify connectivity (will raise if cannot connect)
        try:
            driver.verify_connectivity()
            _NEO4J_DRIVER = driver
            logger.info("Neo4j connectivity verified and driver cached.")
            return _NEO4J_DRIVER
        except Exception as e:
            logger.error(f"Failed to verify Neo4j connectivity: {e}")
            try:
                driver.close()
            except Exception:
                pass
            return None
    except Exception as e:
        logger.error(f"Failed to create Neo4j driver: {e}")
        return None

def query_graph_smart(question: str, limit: int = 5, anchor_hits: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Elite GraphRAG: Uses Text2Cypher + Steiner-Approx Pathfinding for high-precision multi-hop reasoning.
    """
    results = []
    driver = get_neo4j_driver()
    if not driver:
        # Neo4j not available or connection failed; return empty graph result
        return []
    
    # 1. Parallel Seed Discovery (Text2Cypher)
    cypher = Text2Cypher.generate(question)
    
    # 2. Steiner-Approx Pathfinding (if anchors provided)
    # This finds the most efficient 'knowledge bridges' between retrieved vector chunks
    path_results = []
    if anchor_hits and len(anchor_hits) >= 2:
        anchor_ids = [h["metadata"].get("chunk_id") for h in anchor_hits[:3] if h["metadata"].get("chunk_id")]
        if len(anchor_ids) >= 2:
            path_cypher = """
            UNWIND $pairs AS pair
            MATCH (start:Chunk {chunk_id: pair[0]}), (end:Chunk {chunk_id: pair[1]})
            MATCH path = shortestPath((start)-[:RELATES_TO*1..3]-(end))
            RETURN [n IN nodes(path) | n.text] AS texts
            LIMIT 1
            """
            pairs = list(combinations(anchor_ids, 2))
            try:
                with driver.session() as session:
                    for pair in pairs[:3]:
                        res = session.run(path_cypher, pairs=[pair])
                        for record in res:
                            path_results.extend([{"content": t, "metadata": {"source": "GraphPath"}} for t in record["texts"]])
            except Exception as e:
                logger.error(f"Steiner-Approx pathfinding failed: {e}")

    # 3. Fallback/Standard Query
    if not cypher:
        terms = map_terminology(question)
        cypher = "UNWIND $terms AS term MATCH (c:Chunk) WHERE toLower(c.text) CONTAINS term RETURN c.text AS content LIMIT $limit"
        params = {"terms": terms if terms else [question.lower()], "limit": limit}
    else:
        params = {"limit": limit}

    try:
        with driver.session() as session:
            res = session.run(cypher, **params)
            for record in res:
                content = record.get("content") or record.get("c.text")
                if content:
                    results.append({"content": content, "metadata": {"source": "Graph"}})
    except Exception as e:
        logger.error(f"Neo4j query failed: {e}")

    return (path_results + results)[:limit]
