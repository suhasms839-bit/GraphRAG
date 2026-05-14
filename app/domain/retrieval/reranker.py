from typing import Any, Dict, List, Optional
from .bm25 import BM25Ranker

def rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)

def rerank_with_rrf(
    hits: List[Dict[str, Any]],
    vector_order: List[Dict[str, Any]],
    bm25_order: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not hits: return []
    
    vector_ranks = {id(h): i + 1 for i, h in enumerate(vector_order)}
    bm25_ranks = {id(h): i + 1 for i, h in enumerate(bm25_order)}
    
    fused = []
    for h in hits:
        v_rank = vector_ranks.get(id(h), len(hits) + 1)
        b_rank = bm25_ranks.get(id(h), len(hits) + 1)
        score = rrf_score(v_rank) + rrf_score(b_rank)
        fused.append((score, h))
        
    fused.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in fused]
