import re
from typing import List, Optional
from app.domain.generation.llm_gateway import call_gemini_text
from app.core.logging import logger

class QueryRewriter:
    @staticmethod
    def generate_keyword_variants(question: str) -> List[str]:
        """Deterministic keyword extraction for fast fallback."""
        tokens = re.findall(r"[a-z0-9]{3,}", question.lower())
        stop_words = {"what", "how", "why", "explain", "compare", "the", "and", "with"}
        keywords = [t for t in tokens if t not in stop_words]
        return [" ".join(keywords)] if keywords else []

    @staticmethod
    def rewrite(question: str, use_llm: bool = True) -> List[str]:
        """
        Generates 2-3 search variants. 
        Combines deterministic keywords with LLM-based expansion.
        """
        variants = [question]
        
        # Add deterministic variant immediately
        keywords = QueryRewriter.generate_keyword_variants(question)
        if keywords:
            variants.extend(keywords)

        if not use_llm:
            return list(set(variants))

        # Fast LLM expansion
        prompt = f"""Rewrite the following technical question into 2 distinct search queries for a vector database.
Focus on core technical concepts. Return ONLY the queries, one per line.

Question: {question}"""
        
        try:
            llm_output = call_gemini_text(prompt, max_tokens=100, temperature=0.1)
            if llm_output and "LLM Error" not in llm_output:
                llm_variants = [line.strip("- ") for line in llm_output.split("\n") if line.strip()]
                variants.extend(llm_variants)
        except Exception as e:
            logger.error(f"Query rewriting LLM call failed: {e}")

        # Return unique variants, capped for performance
        return list(dict.fromkeys(variants))[:3]
