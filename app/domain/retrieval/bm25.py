import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2]

@dataclass
class BM25State:
    docs_tokens: List[List[str]]
    doc_freq: Dict[str, int]
    doc_len: List[int]
    avg_doc_len: float
    corpus_size: int

class BM25Ranker:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def rank_hits(self, query: str, hits: List[Dict[str, Any]], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not hits: return []
        
        docs_tokens = [_tokens(str(h.get("content") or "")) for h in hits]
        doc_len = [len(t) for t in docs_tokens]
        corpus_size = len(hits)
        avg_doc_len = sum(doc_len) / corpus_size if corpus_size else 0
        
        doc_freq = {}
        for tokens in docs_tokens:
            for tok in set(tokens):
                doc_freq[tok] = doc_freq.get(tok, 0) + 1
        
        q_tokens = _tokens(query)
        scored = []
        for i, h in enumerate(hits):
            tokens = docs_tokens[i]
            tf = {t: tokens.count(t) for t in set(tokens)}
            score = 0.0
            norm = self.k1 * (1 - self.b + self.b * (doc_len[i] / max(1e-9, avg_doc_len)))
            for q in q_tokens:
                freq = tf.get(q, 0)
                if freq == 0: continue
                n_q = doc_freq.get(q, 0)
                idf = math.log(1.0 + ((corpus_size - n_q + 0.5) / (n_q + 0.5)))
                score += idf * ((freq * (self.k1 + 1.0)) / (freq + norm))
            scored.append((score, h))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        return [h for _, h in scored][:limit] if limit else [h for _, h in scored]
