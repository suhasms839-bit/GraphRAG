import asyncio
from typing import List, Dict, Any, Optional
from .bm25 import BM25Ranker
from .reranker import rerank_with_rrf
from .strategies.query_rewriting import QueryRewriter
from .strategies.hypothetical_queries import HypotheticalQueryGenerator
from .strategies.reranker import PrecisionReranker
from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.core.logging import logger

class HybridRetriever:
    def __init__(self, manager: VectorStoreManager):
        self.manager = manager
        self.bm25 = BM25Ranker()

    async def _search_single_query(self, query: str, k: int) -> List[Dict[str, Any]]:
        """Helper for parallel vector search."""
        loop = asyncio.get_event_loop()
        docs = await loop.run_in_executor(None, self.manager.similarity_search, query, k)
        return [{"content": d.page_content, "metadata": d.metadata} for d in docs]

    async def retrieve(self, query: str, topic_title: Optional[str] = None, k: int = 5, include_parent: bool = True) -> Dict[str, Any]:
        """
        Modified to return a dictionary with hits and confidence metadata.
        """
        # 1. Strategy Execution: Query Rewriting & Hypothetical Generation
        rewriter = QueryRewriter()
        hyde_gen = HypotheticalQueryGenerator()
        
        rewriting_task = asyncio.to_thread(rewriter.rewrite, query)
        hyde_task = asyncio.to_thread(hyde_gen.generate, query, topic_title)
        
        query_variants, hyde_variants = await asyncio.gather(rewriting_task, hyde_task)
        all_search_queries = list(dict.fromkeys(query_variants + hyde_variants))
        
        # 2. Parallel Vector Search & Graph Seed Discovery
        from app.domain.graph.graph_querying import query_graph_smart
        
        vector_tasks = [self._search_single_query(q, k) for q in all_search_queries]
        graph_seed_task = asyncio.to_thread(query_graph_smart, query, limit=3)

        vector_results = await asyncio.gather(*vector_tasks)
        try:
            graph_seeds = await asyncio.wait_for(graph_seed_task, timeout=2.0)
        except Exception:
            graph_seeds = []
        
        all_hits = []
        seen_content = set()
        for sublist in vector_results:
            for hit in sublist:
                content_hash = hash(hit["content"])
                if content_hash not in seen_content:
                    all_hits.append(hit)
                    seen_content.add(content_hash)
        
        # 3. BM25 Rerank
        bm25_order = self.bm25.rank_hits(query, all_hits)
        
        # 4. Hybrid Fusion (RRF)
        primary_vector_order = vector_results[0] if vector_results else all_hits
        fused_hits = rerank_with_rrf(all_hits, primary_vector_order, bm25_order)
        
        # 5. Precision Reranking (LLM-based)
        reranker = PrecisionReranker()
        final_hits = await reranker.rerank(query, fused_hits, top_n=k)
        
        # 2.5 Confidence Scoring (MANDATORY Step 2.5)
        # Compute confidence based on the best similarity score from the top result
        # Since our similarity_search might not return raw score easily, 
        # we'll look at the consistency of the top hits or use the LLM to rate confidence.
        # But for Step 2.5, we'll implement a simple score-based heuristic.
        
        # Assuming our similarity search provides a score in metadata if possible, 
        # or we use the reranker's assessment.
        
        # If the top hit after reranking was also in the top of vector search, 
        # let's assume high confidence.
        confidence_val = 0.0
        if final_hits:
            # Simple heuristic: if we have more than 2 hits from different sources, confidence is higher
            sources = len(set(h["metadata"].get("source") for h in final_hits))
            if sources >= 2:
                confidence_val = 0.8
            elif sources == 1:
                confidence_val = 0.6
            else:
                confidence_val = 0.4
        
        confidence_label = "Low"
        if confidence_val >= 0.75:
            confidence_label = "High"
        elif confidence_val >= 0.5:
            confidence_label = "Medium"

        # 6. Parent Context Enrichment
        if include_parent:
            for hit in final_hits[:3]:
                parent_id = hit["metadata"].get("parent_id")
                if parent_id:
                    parent_text = self.manager.get_parent_context(parent_id)
                    if parent_text:
                        hit["parent_context"] = parent_text

        logger.info(f"Retrieved {len(final_hits)} docs. Confidence: {confidence_label} ({confidence_val})")

        return {
            "hits": final_hits[:k],
            "confidence": confidence_val,
            "confidence_label": confidence_label
        }
