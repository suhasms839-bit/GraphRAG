import asyncio
import json
import re
from typing import List, Dict, Any, Optional
from app.domain.generation.llm_gateway import call_gemini_text, extract_json_object_text, format_final_output
from app.domain.retrieval.hybrid_search import HybridRetriever
from app.core.logging import logger

class AgenticOrchestrator:
    def __init__(self, manager: Any):
        self.retriever = HybridRetriever(manager)
        self.manager = manager

    def extract_pure_question(self, text: str) -> str:
        if "Current Question:" in text:
            return text.split("Current Question:")[-1].strip()
        return text.strip()

    def scrub_metadata(self, text: str) -> str:
        text = re.sub(r"\[chunk_id: [a-f0-9-]+\]", "", text)
        text = re.sub(r"PAGE \d+", "", text, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", text).strip()

    async def run(
        self, 
        question: str, 
        topic_title: str = "General",
        history_context: Optional[str] = None,
        gmail_context: Optional[str] = None
    ) -> Dict[str, Any]:
        clean_query = self.extract_pure_question(question)
        logger.info(f"Starting Structured Agentic RAG for: '{clean_query}'")
        
        # 1. Retrieve context
        retrieval_resp = await self.retriever.retrieve(clean_query, topic_title=topic_title, k=5)
        semantic_hits = retrieval_resp.get("hits", [])
        
        if not semantic_hits:
            answer = "No relevant content was found in your uploaded documents. Please ensure your document is uploaded in the Knowledge Base, then ask questions about its content."
            return {
                **format_final_output(answer, [], 0.0, "No documents"),
                "mode": "fallback",
                "graph_used": False,
                "detailed_hits": []
            }
        
        # 2. Prepare Context Excerpts
        context_text = "\n\n".join([f"[S{i+1}] {self.scrub_metadata(h.get('content', ''))}" for i, h in enumerate(semantic_hits)])
        primary_source = semantic_hits[0].get("metadata", {}).get("source", "Document")

        system_prompt = f"""You are an expert AI tutor. Answer the user's question clearly, thoroughly, and factually using ONLY the provided document excerpts.

### Document Excerpts:
{context_text}

### Instructions:
1. Answer the question completely using the excerpts above.
2. Structure your answer using clear paragraphs and bullet points where helpful.
3. Cite sources using [S1], [S2] markers matching the excerpts.
4. Return your response as a valid JSON object matching the schema below.

### Output JSON Format:
{{
  "answer": "Comprehensive answer with [S1] citations.",
  "key_points": ["Key point 1", "Key point 2", "Key point 3"],
  "citations": [{{"id": "S1", "source": "{primary_source}", "page": 1}}],
  "confidence": 0.95
}}"""

        prompt_text = f"Question: {clean_query}\n\n{system_prompt}"
        
        # 3. Call LLM for Structured Synthesis
        direct_response = call_gemini_text(prompt_text, temperature=0.2)
        
        # Debug logging to see why it fell through:
        logger.info(f"Gemini Raw Response: {str(direct_response)[:200]}")

        if direct_response and not direct_response.startswith("LLM"):
            data = extract_json_object_text(direct_response)
            if data and "answer" in data:
                logger.info("Direct Synthesis successful.")
                return {
                    **format_final_output(
                        answer=data.get("answer", ""),
                        citations=data.get("citations", [{"id": "S1", "source": primary_source, "page": 1}]),
                        confidence=data.get("confidence", 0.95),
                        source=primary_source,
                        key_points=data.get("key_points", [])
                    ),
                    "mode": "strong",
                    "graph_used": retrieval_resp.get("graph_used", False),
                    "detailed_hits": retrieval_resp.get("detailed_hits", [])
                }
            else:
                # If Gemini returned plain text instead of JSON, use the generated text directly!
                logger.warning("Gemini returned non-JSON text. Using raw text response.")
                return {
                    **format_final_output(
                        answer=direct_response,
                        citations=[{"id": "S1", "source": primary_source, "page": 1}],
                        confidence=0.90,
                        source=primary_source,
                        key_points=[]
                    ),
                    "mode": "strong",
                    "graph_used": False,
                    "detailed_hits": retrieval_resp.get("detailed_hits", [])
                }

        # 4. Fallback if Gemini network call completely failed
        logger.error(f"Gemini generation failed: {direct_response}")
        return {
            **format_final_output(
                answer=f"Could not contact Gemini API ({direct_response}). Excerpt from document:\n\n{semantic_hits[0].get('content', '')}",
                citations=[{"id": "S1", "source": primary_source, "page": 1}],
                confidence=0.50,
                source=primary_source,
                key_points=[]
            ),
            "mode": "fallback",
            "graph_used": False,
            "detailed_hits": retrieval_resp.get("detailed_hits", [])
        }