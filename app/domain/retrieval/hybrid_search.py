import asyncio
from typing import List, Dict, Any, Optional
from .bm25 import BM25Ranker
from .reranker import rerank_with_rrf
from .strategies.query_rewriting import QueryRewriter
from .strategies.hypothetical_queries import HypotheticalQueryGenerator
from .strategies.reranker import PrecisionReranker
from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.core.logging import logger
from app.core.config import settings
import re
import math
import statistics
import time

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

        # Deterministic reranking fallback used when LLM reranking is skipped.
        # Goal: avoid a quality cliff under concurrency/timeouts.
        def _heuristic_rerank_on_skip(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            if not hits:
                return []

            # Precompute positions from upstream rankers (lower pos == better)
            vector_pos_map = {h.get("content"): i for i, h in enumerate(primary_vector_order or [])}
            bm25_pos_map = {h.get("content"): i for i, h in enumerate(bm25_order or [])}

            def _term_overlap(q: str, text: str) -> float:
                try:
                    q_terms = set(re.findall(r"\w+", (q or "").lower()))
                    t_terms = set(re.findall(r"\w+", (text or "").lower()))
                    if not q_terms:
                        return 0.0
                    return len(q_terms.intersection(t_terms)) / max(1, len(q_terms))
                except Exception:
                    return 0.0

            def _score(hit: Dict[str, Any]) -> float:
                content = hit.get("content") or ""
                overlap = _term_overlap(query, content)

                # Rank-based priors (favor BM25 for short/keyword-y queries)
                vp = vector_pos_map.get(content)
                bp = bm25_pos_map.get(content)
                vec_prior = (1.0 - (vp / max(1, len(hits)))) if vp is not None else 0.0
                bm25_prior = (1.0 - (bp / max(1, len(hits)))) if bp is not None else 0.0

                q_len = len((query or "").split())
                if q_len <= 3:
                    w_overlap, w_bm25, w_vec = 0.45, 0.40, 0.15
                else:
                    w_overlap, w_bm25, w_vec = 0.50, 0.25, 0.25

                return w_overlap * overlap + w_bm25 * bm25_prior + w_vec * vec_prior

            return sorted(hits, key=_score, reverse=True)
        
        # 5. Precision Reranking (LLM-based) with timeout-based skip
        reranker_skipped = False
        reranker_attempted = False
        reranker_timeout = float(getattr(settings, "RE_RANKER_TIMEOUT", 0.5))

        start_t = time.monotonic()
        final_hits = []
        if bool(getattr(settings, "RERANKER_ENABLED", True)):
            reranker_attempted = True
            reranker = PrecisionReranker()
            try:
                # try to run reranker within timeout
                final_hits = await asyncio.wait_for(reranker.rerank(query, fused_hits, top_n=k), timeout=reranker_timeout)
            except Exception:
                # on timeout or error, fall back to deterministic rerank for stability
                final_hits = _heuristic_rerank_on_skip(fused_hits)[:k]
                reranker_skipped = True
        else:
            # Explicitly disabled: no skip semantics; just use deterministic ordering.
            final_hits = _heuristic_rerank_on_skip(fused_hits)[:k]

        elapsed = time.monotonic() - start_t
        # If reranker took too long, skip graph-based scoring to keep latency bounded.
        # Only apply this when we actually attempted the LLM reranker.
        skip_graph_due_to_time = bool(reranker_attempted and elapsed > reranker_timeout)

        # 6. Parent Context Enrichment
        if include_parent:
            for hit in final_hits[:3]:
                parent_id = hit["metadata"].get("parent_id")
                if parent_id:
                    parent_text = self.manager.get_parent_context(parent_id)
                    if parent_text:
                        hit["parent_context"] = parent_text

        # 7. Relevance scoring per hit (heuristic)
        def term_overlap_score(query: str, text: str) -> float:
            try:
                q_terms = set(re.findall(r"\w+", query.lower()))
                t_terms = set(re.findall(r"\w+", text.lower()))
                if not q_terms:
                    return 0.0
                overlap = q_terms.intersection(t_terms)
                return min(1.0, len(overlap) / max(1, len(q_terms)))
            except Exception:
                return 0.0

        detailed_hits = []
        scores = []
        combined_raw_scores = []
        primary_order = primary_vector_order if primary_vector_order else []
        any_graph_used = False

        # helper: overlap between two texts
        def overlap_between(a: str, b: str) -> float:
            try:
                at = set(re.findall(r"\w+", a.lower()))
                bt = set(re.findall(r"\w+", b.lower()))
                if not at:
                    return 0.0
                return len(at.intersection(bt)) / max(1, len(at))
            except Exception:
                return 0.0

        # adaptive weight chooser based on query and graph seed confidence
        def choose_weights(q: str, graph_conf: float):
            q_len = len(q.split()) if q else 0
            try:
                if graph_conf > 0.7:
                    return 0.4, 0.2, 0.4
                if q_len <= 3:
                    return 0.3, 0.5, 0.2
            except Exception:
                pass
            return 0.5, 0.3, 0.2

        # robust normalizer: z-score followed by sigmoid; fallback to rank-norm if sigma tiny
        def normalize_scores(scores: List[float]) -> List[float]:
            if not scores:
                return []
            if len(scores) == 1:
                return [1.0]
            mu = statistics.mean(scores)
            sigma = statistics.pstdev(scores)  # population stddev
            eps = 1e-6
            if sigma < 1e-4:
                # rank-based normalization
                ranked = sorted(((s, i) for i, s in enumerate(scores)), key=lambda x: x[0])
                ranks = {idx: r for r, (_, idx) in enumerate(ranked)}
                n = len(scores)
                if n <= 1:
                    return [1.0 for _ in scores]
                return [ranks[i] / (n - 1) for i in range(n)]
            # z-score -> sigmoid
            z = [(s - mu) / (sigma + eps) for s in scores]
            return [1.0 / (1.0 + math.exp(-v)) for v in z]

        for idx, hit in enumerate(final_hits[:k]):
            content = hit.get("content", "")
            # vector rank (position in primary vector order)
            try:
                vector_pos = next((i for i, h in enumerate(primary_order) if h.get("content") == hit.get("content")), None)
            except Exception:
                vector_pos = None

            try:
                bm25_pos = next((i for i, h in enumerate(bm25_order) if h.get("content") == hit.get("content")), None)
            except Exception:
                bm25_pos = None

            overlap = term_overlap_score(query, content)
            length_score = min(1.0, len(content) / 500.0)

            vec_score = (1.0 - (vector_pos / k)) if (vector_pos is not None and k > 0) else 0.0
            bm25_score = (1.0 - (bm25_pos / k)) if (bm25_pos is not None and k > 0) else 0.0

            # Graph score: compare hit content to graph seed contents (if any)
            graph_score = 0.0
            try:
                # Check if graph signals should be used: ensure graph is ready for documents
                from app.core.database import SessionLocal
                from app.core.models import Document as DBDocument
                graph_enabled = True
                try:
                    doc_ids = set()
                    for h in final_hits[:k]:
                        did = h.get("metadata", {}).get("document_id")
                        if did:
                            doc_ids.add(did)
                    if doc_ids:
                        db = SessionLocal()
                        rows = db.query(DBDocument.id, DBDocument.graph_ready).filter(DBDocument.id.in_(list(doc_ids))).all()
                        db.close()
                        # if any doc is not graph_ready, disable graph scoring for this request
                        for _id, ready in rows:
                            if not ready:
                                graph_enabled = False
                                break
                except Exception:
                    graph_enabled = False

                # Also respect time-based skip
                if graph_enabled and not skip_graph_due_to_time:
                    for seed in graph_seeds:
                        seed_content = seed.get("content", "")
                        seed_rel = seed.get("seed_score", 0) or 0
                        path_len = int(seed.get("metadata", {}).get("path_length", seed.get("path_length", 0) or 0))
                        max_depth = int(getattr(settings, "MAX_GRAPH_PATH_DEPTH", 2))
                        if path_len and path_len > max_depth:
                            continue
                        # overlap between hit and seed, weighted by seed's internal score and penalized by path length
                        g_ov = overlap_between(content, seed_content)
                        decay = 0.85 ** path_len if path_len and path_len > 0 else 1.0
                        graph_score = max(graph_score, g_ov * float(seed_rel) * decay)
            except Exception:
                graph_score = 0.0

            # Gate graph contribution by minimum trust
            try:
                min_trust = float(getattr(settings, "GRAPH_MIN_TRUST", 0.3))
                if graph_score < min_trust:
                    graph_score = 0.0
            except Exception:
                pass

            # track whether graph contributed
            graph_used_flag = graph_score > 0.0
            if graph_used_flag:
                any_graph_used = True

            # choose adaptive weights per query and graph seed confidence
            try:
                graph_seed_conf = max((s.get("seed_score", 0) or 0) for s in graph_seeds) if graph_seeds else 0.0
            except Exception:
                graph_seed_conf = 0.0

            w_vec, w_bm25, w_graph = choose_weights(query, graph_seed_conf)
            combined_raw = w_vec * vec_score + w_bm25 * bm25_score + w_graph * graph_score
            combined_raw = max(0.0, min(1.0, combined_raw))

            detailed = {
                "index": idx,
                "content": content[:1000],
                "metadata": hit.get("metadata", {}),
                "vector_pos": vector_pos,
                "bm25_pos": bm25_pos,
                "overlap": overlap,
                "length_score": length_score,
                "graph_score": graph_score,
                "raw": combined_raw,
                # 'score' will be normalized later
            }
            detailed_hits.append(detailed)
            combined_raw_scores.append(combined_raw)

        # Determine top score and mode
        # robust normalization across combined raw scores
        norm_scores = normalize_scores(combined_raw_scores)

        # attach normalized scores back to detailed_hits and prepare scores list
        for i, s in enumerate(norm_scores):
            detailed_hits[i]["score"] = s
        scores = norm_scores

        top_score = max(scores) if scores else 0.0
        # Warn on poor retrieval quality
        try:
            if top_score < 0.2:
                logger.warning("Poor retrieval quality: top_score < 0.2")
        except Exception:
            pass

        # blended confidence: 0.6 * top + 0.4 * avg(top3)
        avg_top3 = 0.0
        if scores:
            n = min(3, len(scores))
            top_n = sorted(scores, reverse=True)[:n]
            avg_top3 = sum(top_n) / max(1, n)
        confidence_val = 0.6 * top_score + 0.4 * avg_top3
        confidence_reason = f"blended:0.6*top({top_score:.3f})+0.4*avgTop3({avg_top3:.3f})"

        mode = "fallback"
        if top_score >= getattr(settings, "STRONG_CONTEXT_THRESHOLD", 0.75):
            mode = "strong"
        elif top_score >= getattr(settings, "WEAK_CONTEXT_THRESHOLD", 0.4) or confidence_val >= 0.5:
            mode = "hybrid"

        # Provide a stable label for upstream callers.
        # Keep this intentionally coarse-grained to avoid breaking UIs/tests.
        confidence_label = mode

        logger.info(f"Retrieved {len(final_hits)} docs. Confidence: {confidence_val:.3f} Mode: {mode} TopScore: {top_score}")
        logger.debug(f"Top scores: {scores}")
        logger.debug(f"Selected chunks: {[h.get('metadata',{}).get('source') for h in final_hits[:k]]}")

        # Telemetry: record retrieval metrics for ops visibility
        try:
            user_id = getattr(self.manager, 'user_id', None)
            query_variants_count = len(all_search_queries) if 'all_search_queries' in locals() else 0
            vector_results_count = sum(len(v) for v in vector_results) if isinstance(vector_results, list) else 0
            fused_count = len(fused_hits) if fused_hits is not None else 0
            final_count = len(final_hits[:k]) if final_hits is not None else 0
            telemetry_payload = {
                "query_variants_count": query_variants_count,
                "vector_results_count": vector_results_count,
                "fused_count": fused_count,
                "final_count": final_count,
                "reranker_skipped": bool(reranker_skipped),
                "reranker_attempted": bool(reranker_attempted),
                "reranker_latency_ms": int(elapsed * 1000),
                "graph_used": bool(any_graph_used),
                "mode": mode,
                "top_score": float(top_score)
            }
            try:
                record_event("retrieval", telemetry_payload, user_id=user_id)
            except Exception:
                logger.debug("Failed to record retrieval telemetry")
        except Exception:
            pass

        return {
            "hits": final_hits[:k],
            "confidence": confidence_val,
            "confidence_label": confidence_label,
            "confidence_reason": confidence_reason,
            "detailed_hits": detailed_hits,
            "scores": scores,
            "mode": mode,
            "top_score": top_score,
            "graph_used": any_graph_used,
            "reranker_skipped": reranker_skipped
        }
