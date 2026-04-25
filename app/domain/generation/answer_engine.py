from typing import List, Dict, Any, Tuple
import re
from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.retrieval.hybrid_search import HybridRetriever
from app.domain.graph.graph_querying import query_graph_smart
from app.domain.generation.llm_gateway import call_gemini_text, format_final_output
from app.core.logging import logger

async def answer_with_rag(
    builder: Any,
    topic_title: str,
    question: str,
    k: int = 5
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    logger.info(f"Answering question: {question}")
    
    # 1. Retrieval (Hybrid: Vector + BM25 with Query Rewriting & HyDE)
    retriever = HybridRetriever(builder.manager)
    retrieval_result = await retriever.retrieve(question, topic_title=topic_title, k=k)
    ranked_hits = retrieval_result["hits"]
    confidence_val = retrieval_result["confidence"]
    confidence_label = retrieval_result["confidence_label"]
    
    # 2. Graph Enrichment (Smart Cypher)
    graph_hits = query_graph_smart(question, limit=3)

    # 4.1 Multi-Level Fallback behavior (FIX 3: TRUE FALLBACK SWITCH)
    if not ranked_hits and not graph_hits:
        logger.info("No retrieval hits found. Switching to PURE LLM answer.")
        prompt = f"""### ROLE: Expert Learning Assistant
### CORE TOPIC: {topic_title}
### STUDENT QUESTION: "{question}"
### INSTRUCTION: Use your general technical knowledge to provide a comprehensive and accurate answer.
### Answer:"""
        answer = call_gemini_text(prompt, max_tokens=800) or "I'm sorry, I don't have enough information to answer that."
        return format_final_output(answer, [], 0.0, "General Knowledge")

    # 4.2 Prompt Strategy (FIX 2: NATURAL INTEGRATION)
    if confidence_val >= 0.75:
        # HIGH: Strong grounding
        fallback_instructions = "Answer using the provided context as the primary source. Be precise."
    else:
        # WEAK/MEDIUM: Combine context + LLM (FIX 1: REMOVED HARD DISCLAIMER)
        fallback_instructions = "Use the provided context where relevant. If the context is insufficient, use your general knowledge to provide a complete and natural answer without explicitly mentioning limitations."
    
    # 3. Generation (Prompt Template v3.0)
    def deduplicate_context(parts: List[str]) -> List[str]:
        unique_parts = []
        seen_sigs = set()
        for p in parts:
            # Simple token-based signature for near-duplicate detection
            sig = "".join(sorted(re.findall(r"[a-z0-9]{4,}", p.lower())))[:100]
            if sig not in seen_sigs:
                unique_parts.append(p)
                seen_sigs.add(sig)
        return unique_parts

    context_parts = []
    for i, h in enumerate(ranked_hits):
        source_info = f"[Source {i+1}]"
        if "parent_context" in h:
            context_parts.append(f"{source_info} (Broad Context): {h['parent_context'][:1000]}")
        context_parts.append(f"{source_info} (Specific Detail): {h['content']}")
        
    # Pre-generation filtering: remove weak chunks and limit number
    def filter_context(chunks: List[str]) -> List[str]:
        filtered = [c for c in chunks if len(c.split()) > int(getattr(__import__('app.core.config', fromlist=['settings']).settings, 'CONTEXT_CHUNK_MIN_WORDS', 40))]
        return filtered[:int(getattr(__import__('app.core.config', fromlist=['settings']).settings, 'MAX_CONTEXT_CHUNKS', 5))]

    context_parts = deduplicate_context(context_parts)
    context_parts = filter_context(context_parts)
    context_str = "\n\n".join(context_parts)

    # Enforce max context tokens (approximate via words)
    try:
        max_tokens = int(getattr(__import__('app.core.config', fromlist=['settings']).settings, 'MAX_CONTEXT_TOKENS', 1200))
        words = context_str.split()
        if len(words) > max_tokens:
            context_str = " ".join(words[:max_tokens])
    except Exception:
        pass
    
    # Add contradiction handling instruction: prefer most relevant/recent; do not merge contradictions
    contradiction_instr = "If retrieved sources conflict, prefer the most relevant and most recent source; do not merge contradictory claims—state the disagreement and cite the preferred source."

    prompt = f"""### ROLE: Expert Learning Assistant (RAG v3.0)
    
### INSTRUCTION (Groundedness: {confidence_label}):
{fallback_instructions}

### CORE TOPIC:
{topic_title}

### STUDENT QUESTION:
"{question}"

### CONTEXT (Retrieved Hits):
{context_str}

### DATA GRAPH CONTEXT:
{graph_hits}

### CONTRADICTION HANDLING:
{contradiction_instr}

### REQUIREMENTS:
1. Structure your answer clearly with markdown formatting.
    2. Maintain natural flow and accuracy.
    3. Use the provided context where relevant, otherwise use your expert knowledge.

    ### Answer:"""

    answer = call_gemini_text(prompt, max_tokens=800) or "No relevant content found."
    citations = [{"file": h["metadata"].get("source", "Unknown"), "page": h["metadata"].get("page")} for h in ranked_hits]
    source_type = "Retrieved documents" if confidence_val > 0.5 else "General Knowledge"

    # Compute confidence_reason
    try:
        top_score = retrieval_result.get('top_score', 0.0)
        max_graph = 0.0
        for dh in retrieval_result.get('detailed_hits', []):
            g = float(dh.get('graph_score', 0) or 0)
            if g > max_graph:
                max_graph = g
        reasons = []
        if top_score >= settings.STRONG_CONTEXT_THRESHOLD:
            reasons.append('High similarity top-hit')
        else:
            reasons.append('Weak top similarity')
        if max_graph >= float(getattr(settings, 'GRAPH_MIN_TRUST', 0.3)):
            reasons.append('strong graph linkage')
        confidence_reason = ", ".join(reasons)
    except Exception:
        confidence_reason = ""

    return format_final_output(answer, citations, confidence_val, source_type, confidence_reason)
