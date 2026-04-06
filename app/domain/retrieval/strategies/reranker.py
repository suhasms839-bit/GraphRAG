import json
from typing import List, Dict, Any
from app.domain.generation.llm_gateway import call_gemini_text, extract_json_object_text
from app.core.logging import logger

class PrecisionReranker:
    @staticmethod
    async def rerank(query: str, hits: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Uses Gemini to rerank the top retrieved hits for maximum precision.
        """
        if not hits:
            return []

        # Only rerank the top 10 to maintain sub-5s performance
        candidates = hits[:10]
        
        context_block = ""
        for i, hit in enumerate(candidates):
            context_block += f"ID: {i}\nContent: {hit['content'][:500]}\n---\n"

        prompt = f"""You are an expert search evaluator. Rank the following document snippets based on their relevance to the user's query.
Query: {query}

Documents:
{context_block}

Return a JSON object with the IDs of the top {top_n} most relevant documents in order of relevance.
Format: {{"ranked_ids": [2, 0, 5]}}"""

        try:
            # High-speed reranking call
            raw_output = call_gemini_text(prompt, max_tokens=150, temperature=0.0, response_mime_type="application/json")
            parsed = extract_json_object_text(raw_output or "")
            
            if parsed and "ranked_ids" in parsed:
                ranked_ids = parsed["ranked_ids"]
                reranked_hits = []
                for idx in ranked_ids:
                    if isinstance(idx, int) and 0 <= idx < len(candidates):
                        reranked_hits.append(candidates[idx])
                
                # Add any candidates that weren't in the top ranked list to the end
                seen_indices = set(ranked_ids)
                for i, hit in enumerate(candidates):
                    if i not in seen_indices:
                        reranked_hits.append(hit)
                
                return reranked_hits
        except Exception as e:
            logger.error(f"Precision reranking failed: {e}")

        return hits
