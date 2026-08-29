import asyncio
import re
import math
import statistics
import time
from typing import List, Dict, Any, Optional

from .bm25 import BM25Ranker
from .reranker import rerank_with_rrf
from .strategies.query_rewriting import QueryRewriter
from .strategies.hypothetical_queries import HypotheticalQueryGenerator
from .strategies.reranker import PrecisionReranker
from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.core.logging import logger
from app.core.config import settings
from app.core.telemetry import record_event

class HybridRetriever:
    def __init__(self, manager: VectorStoreManager):
        self.manager = manager
        self.bm25 = BM25Ranker()
        self.rewriter = QueryRewriter()
        self.hyde_gen = HypotheticalQueryGenerator()
        self.precision_reranker = PrecisionReranker()

    def _extract_clean_query(self, raw_query: str) -> str:
        """Extract the exact user question if wrapped in a template prompt."""
        if "Current Question:" in raw_query:
            return raw_query.split("Current Question:")[-1].strip()
        return raw_query.strip()

    async def _search_single_query(self, query: str, k: int) -> List[Dict[str, Any]]:
        """Executes vector similarity search safely in an async thread pool."""
        try:
            loop = asyncio.get_running_loop()
            docs = await loop.run_in_executor(None, self.manager.similarity_search, query, k)
            return [{"content": d.page_content, "metadata": d.metadata} for d in docs]
        except Exception as e:
            logger.error(f"Vector search failed for '{query[:30]}': {e}")
            return []

    async def retrieve(
        self, 
        query: str, 
        topic_title: Optional[str] = None, 
        k: int = 5, 
        include_parent: bool = True
    ) -> Dict[str, Any]:
        start_time = time.monotonic()
        clean_query = self._extract_clean_query(query)
        logger.info(f"Executing Hybrid Retrieval for: '{clean_query}'")

        # ---------------------------------------------------------
        # 1. Advanced Query Expansion (Rewriting + HyDE in Parallel)
        # ---------------------------------------------------------
        rewriting_task = asyncio.to_thread(self.rewriter.rewrite, clean_query)
        hyde_task = asyncio.to_thread(self.hyde_gen.generate, clean_query, topic_title)

        try:
            query_variants, hyde_variants = await asyncio.wait_for(
                asyncio.gather(rewriting_task, hyde_task, return_exceptions=True),
                timeout=3.0
            )
            if isinstance(query_variants, Exception) or not query_variants:
                query_variants = [clean_query]
            if isinstance(hyde_variants, Exception) or not hyde_variants:
                hyde_variants = []
        except Exception as e:
            logger.warning(f"Query expansion timed out/failed: {e}. Using raw query.")
            query_variants = [clean_query]
            hyde_variants = []

        # Ensure original clean query is always present and prioritized first
        all_search_queries = [clean_query]
        for q in (query_variants + hyde_variants):
            if q and q not in all_search_queries:
                all_search_queries.append(q)

        # ---------------------------------------------------------
        # 2. Parallel Multi-Vector Search & Graph Seed Discovery
        # ---------------------------------------------------------
        from app.domain.graph.graph_querying import query_graph_smart

        vector_tasks = [self._search_single_query(q, k) for q in all_search_queries[:4]]
        graph_seed_task = asyncio.to_thread(query_graph_smart, clean_query, limit=3)

        vector_results = await asyncio.gather(*vector_tasks, return_exceptions=True)
        try:
            graph_seeds = await asyncio.wait_for(graph_seed_task, timeout=2.0)
        except Exception:
            graph_seeds = []

        # Deduplicate retrieved chunks across all queries
        all_hits = []
        seen_content = set()
        primary_vector_order = []

        for idx, sublist in enumerate(vector_results):
            if isinstance(sublist, list):
                if idx == 0:
                    primary_vector_order = sublist
                for hit in sublist:
                    content_str = hit.get("content", "")
                    if content_str and content_str not in seen_content:
                        all_hits.append(hit)
                        seen_content.add(content_str)

        # If zero vector hits found across all queries, return immediately
        if not all_hits:
            logger.warning(f"No vector hits found for '{clean_query}'.")
            return {
                "hits": [],
                "confidence": 0.0,
                "confidence_label": "fallback",
                "confidence_reason": "no_hits",
                "detailed_hits": [],
                "scores": [],
                "mode": "fallback",
                "top_score": 0.0,
                "graph_used": False,
                "reranker_skipped": False
            }

        # ---------------------------------------------------------
        # 3. Sparse Keyword Ranking (BM25)
        # ---------------------------------------------------------
        bm25_order = self.bm25.rank_hits(clean_query, all_hits)

        # ---------------------------------------------------------
        # 4. Hybrid Fusion via Reciprocal Rank Fusion (RRF)
        # ---------------------------------------------------------
        if not primary_vector_order:
            primary_vector_order = all_hits
        fused_hits = rerank_with_rrf(all_hits, primary_vector_order, bm25_order)

        # ---------------------------------------------------------
        # 5. Precision Cross-Encoder / LLM Reranking
        # ---------------------------------------------------------
        reranker_skipped = False
        reranker_attempted = False
        final_hits = []
        reranker_timeout = float(getattr(settings, "RE_RANKER_TIMEOUT", 3.5))

        if bool(getattr(settings, "RERANKER_ENABLED", True)):
            reranker_attempted = True
            try:
                # LLM Precision reranker with a realistic 3.5s timeout
                final_hits = await asyncio.wait_for(
                    self.precision_reranker.rerank(clean_query, fused_hits, top_n=k), 
                    timeout=reranker_timeout
                )
                logger.info(f"Precision Reranker successfully reranked {len(final_hits)} documents.")
            except Exception as re_err:
                logger.warning(f"Precision Reranker bypassed ({re_err}). Falling back to RRF fused order.")
                final_hits = fused_hits[:k]
                reranker_skipped = True
        else:
            final_hits = fused_hits[:k]

        # ---------------------------------------------------------
        # 6. Graph Signal Integration & Confidence Scoring
        # ---------------------------------------------------------
        detailed_hits = []
        scores = []
        any_graph_used = False

        for idx, hit in enumerate(final_hits[:k]):
            content = hit.get("content", "")
            
            # Vector position score
            try:
                vec_pos = next((i for i, h in enumerate(primary_vector_order) if h.get("content") == content), None)
                vec_score = (1.0 - (vec_pos / max(1, len(primary_vector_order)))) if vec_pos is not None else 0.5
            except Exception:
                vec_score = 0.5

            # Graph relevance score
            graph_score = 0.0
            for seed in graph_seeds:
                seed_content = seed.get("content", "")
                if any(term in content.lower() for term in seed_content.lower().split() if len(term) > 3):
                    graph_score = 0.8
                    any_graph_used = True
                    break

            combined_score = round(0.6 * vec_score + 0.4 * (graph_score or vec_score), 2)
            scores.append(combined_score)

            detailed_hits.append({
                "index": idx,
                "content": content[:1000],
                "metadata": hit.get("metadata", {}),
                "score": combined_score,
                "graph_score": graph_score
            })

        top_score = max(scores) if scores else 0.85
        mode = "strong" if top_score >= 0.7 else ("hybrid" if top_score >= 0.4 else "fallback")
        confidence_val = top_score

        elapsed = time.monotonic() - start_time
        logger.info(f"Retrieval complete in {elapsed:.2f}s | Hits: {len(final_hits)} | Mode: {mode} | Confidence: {confidence_val}")

        return {
            "hits": final_hits[:k],
            "confidence": confidence_val,
            "confidence_label": mode,
            "confidence_reason": f"Hybrid (RRF + BM25 + CrossRanker, latency {elapsed:.2f}s)",
            "detailed_hits": detailed_hits,
            "scores": scores,
            "mode": mode,
            "top_score": top_score,
            "graph_used": any_graph_used,
            "reranker_skipped": reranker_skipped
        }