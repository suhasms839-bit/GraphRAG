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
            max_depth = int(getattr(settings, "MAX_GRAPH_PATH_DEPTH", 2))
            max_paths = int(getattr(settings, "MAX_GRAPH_PATHS_PER_SEED", 5))
            path_cypher = f"""
            UNWIND $pairs AS pair
            MATCH (start:Chunk {{chunk_id: pair[0]}}), (end:Chunk {{chunk_id: pair[1]}})
            MATCH path = shortestPath((start)-[:RELATES_TO*1..{max_depth}]-(end))
            RETURN [n IN nodes(path) | n.text] AS texts, length(path) AS path_length
            LIMIT 1
            """
            pairs = list(combinations(anchor_ids, 2))
            try:
                with driver.session() as session:
                    for pair in pairs[:max_paths]:
                        res = session.run(path_cypher, pairs=[pair])
                        for record in res:
                            texts = record.get("texts") or []
                            pl = record.get("path_length") or 0
                            for t in texts:
                                path_results.append({"content": t, "metadata": {"source": "GraphPath", "path_length": pl}})
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
                    results.append({"content": content, "metadata": {"source": "Graph", "path_length": 0}})
    except Exception as e:
        logger.error(f"Neo4j query failed: {e}")

    # Combine path results and direct results
    combined = path_results + results

    # Seed scoring: pragmatic heuristic combining content-length and anchor overlap
    scored = []
    try:
        seed_threshold = float(getattr(settings, "SEED_SCORE_THRESHOLD", 0.6))
    except Exception:
        seed_threshold = 0.6

    anchor_texts = []
    if anchor_hits:
        for h in anchor_hits:
            anchor_texts.append((h.get("metadata", {}).get("chunk_id"), h.get("content", "")))

    for item in combined:
        content = item.get("content", "")
        # length-based score (longer contextual excerpts score higher)
        length_score = min(1.0, len(content) / 1000.0)

        # anchor overlap: if the content mentions any anchor chunk_id or share tokens
        overlap_score = 0.0
        for aid, atext in anchor_texts:
            if not aid:
                continue
            if aid in content:
                overlap_score = 1.0
                break
            # fallback token overlap heuristic
            if atext and any(tok in content for tok in atext.split()[:5]):
                overlap_score = max(overlap_score, 0.5)

        seed_score = 0.6 * length_score + 0.4 * overlap_score
        item["seed_score"] = seed_score
        if seed_score >= seed_threshold:
            scored.append(item)

    logger.debug(f"Graph seed scores: {[s.get('seed_score') for s in combined]}")

    return scored[:limit]
