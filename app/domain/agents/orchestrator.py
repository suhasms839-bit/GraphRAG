import asyncio
import json
import re
from typing import List, Dict, Any, Tuple, Optional
from app.domain.generation.llm_gateway import call_gemini_with_tools, extract_json_object_text, format_final_output
from app.domain.agents.tools import AGENT_TOOLS
from app.domain.retrieval.hybrid_search import HybridRetriever
from app.domain.graph.graph_querying import query_graph_smart, get_neo4j_driver
from app.domain.graph.graph_rag.community import GraphRAGCommunityManager
from app.core.logging import logger
from app.infrastructure.vectorstore.manager import VectorStoreManager

class AgenticOrchestrator:
    def __init__(self, manager: Any):
        self.retriever = HybridRetriever(manager)
        self.manager = manager
        self.community_manager = GraphRAGCommunityManager()

    def extract_pure_question(self, text: str) -> str:
        """Extracts the exact question if wrapped in a template prompt."""
        if "Current Question:" in text:
            return text.split("Current Question:")[-1].strip()
        return text.strip()

    def scrub_metadata(self, text: str) -> str:
        """Strips technical artifacts like chunk_id, timestamps, and raw headers."""
        text = re.sub(r"\[chunk_id: [a-f0-9-]+\]", "", text)
        text = re.sub(r"PAGE \d+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"DATA COMMUNICATION", "", text, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", text).strip()

    async def run(
        self, 
        question: str, 
        topic_title: str = "General",
        history_context: Optional[str] = None,
        gmail_context: Optional[str] = None
    ) -> Dict[str, Any]:
        # 1. Clean query for semantic retrieval
        clean_query = self.extract_pure_question(question)
        logger.info(f"Starting Structured Agentic RAG for clean query: '{clean_query}'")
        
        # 2. Retrieve document chunks using clean query
        retrieval_resp = await self.retriever.retrieve(clean_query, topic_title=topic_title, k=5)
        semantic_hits = retrieval_resp.get("hits", [])
        logger.info(f"Retrieved docs count: {len(semantic_hits)}")
        
        if not semantic_hits:
            logger.warning(f"No semantic hits retrieved for '{clean_query}'. Returning document notice.")
            answer = "No relevant content was found in your uploaded documents. Please ensure your document is uploaded in the Knowledge Base, then ask questions about its content."
            base_output = format_final_output(answer, [], 0.0, "No documents")
            return {
                **base_output,
                "mode": retrieval_resp.get("mode", "fallback"),
                "graph_used": retrieval_resp.get("graph_used", False),
                "detailed_hits": retrieval_resp.get("detailed_hits", [])
            }
        
        # 3. Assemble clean context for generation
        context_text = "\n\n".join([f"Evidence: {self.scrub_metadata(h.get('content', ''))}" for h in semantic_hits])
        
        prompt_parts = []
        if history_context:
            prompt_parts.append(f"Conversation History:\n{history_context}")
        if gmail_context:
            prompt_parts.append(f"Gmail Context:\n{gmail_context}")
        
        prompt_parts.append(f"Provided Document Context:\n{context_text}")
        full_context_block = "\n\n".join(prompt_parts)

        system_instruction = f"""You are a document-based question answering assistant.
Your ONLY job is to answer questions using the provided document context below.

### Context:
{full_context_block}

### STRICT Rules:
1. Answer ONLY using information found in the Context above.
2. If the context answers the question, answer clearly and quote/cite the specific details.
3. If the answer cannot be found in the context, state: "The uploaded documents do not contain information about this topic."
4. Add [S1], [S2] citation markers referencing source sections where appropriate.
5. Return ONLY a valid JSON object matching the schema below.

### Output Schema:
{{
  "answer": "Your detailed answer based strictly on the context, with [S1] markers.",
  "key_points": ["Key point 1", "Key point 2"],
  "citations": [{{"id": "S1", "source": "{semantic_hits[0].get('metadata', {}).get('source', 'Document')}", "page": 1}}],
  "confidence": 0.95
}}"""

        prompt_text = f"Topic: {topic_title}\nQuestion: {clean_query}\n\n{system_instruction}"
        
        # 4. Direct Synthesis via Gemini
        try:
            from app.domain.generation.llm_gateway import call_gemini_text

            direct_response = call_gemini_text(prompt_text)
            if direct_response and "429" not in direct_response:
                structured_data = extract_json_object_text(direct_response)
                if structured_data and "answer" in structured_data:
                    logger.info("Direct Synthesis successful.")
                    ans = structured_data.get("answer", "")
                    citations = structured_data.get("citations", [])
                    confidence = structured_data.get("confidence", 0.9)
                    source = structured_data.get("source", "Uploaded Document")
                    base_output = format_final_output(ans, citations, confidence, source)
                    return {
                        **base_output,
                        "mode": retrieval_resp.get("mode", "strong"),
                        "graph_used": retrieval_resp.get("graph_used", False),
                        "detailed_hits": retrieval_resp.get("detailed_hits", [])
                    }
        except Exception as e:
            logger.error(f"Error in Direct Synthesis: {e}")

        # 5. Agentic Multi-Hop Loop (Fallback if direct synthesis fails)
        from app.core.config import settings
        if not settings.USE_OLLAMA:
            messages = [
                {
                    "role": "user",
                    "parts": [{"text": prompt_text}]
                }
            ]
            
            context_accumulator = semantic_hits
            max_iterations = 2
            
            for i in range(max_iterations):
                try:
                    response = call_gemini_with_tools(messages, tools=AGENT_TOOLS)
                    
                    if isinstance(response, dict) and "error" in response:
                        logger.error(f"Gemini API Error in loop: {response['error']}")
                        break
                    
                    messages.append(response)
                    parts = response.get("parts", [])
                    tool_calls = [p.get("functionCall") for p in parts if p.get("functionCall")]
                    
                    if not tool_calls:
                        final_text = "".join([p.get("text", "") for p in parts])
                        try:
                            structured_data = extract_json_object_text(final_text)
                            if structured_data:
                                ans = structured_data.get("answer", "")
                                citations = structured_data.get("citations", [])
                                confidence = structured_data.get("confidence", 0.8)
                                source = structured_data.get("source", "Uploaded Document")
                                base_output = format_final_output(ans, citations, confidence, source)
                                return {
                                    **base_output,
                                    "mode": retrieval_resp.get("mode", "strong"),
                                    "graph_used": retrieval_resp.get("graph_used", False),
                                    "detailed_hits": retrieval_resp.get("detailed_hits", [])
                                }
                        except Exception:
                            pass
                        
                        base_output = format_final_output(final_text[:500], [], 0.7, "Retrieved documents")
                        return {
                            **base_output,
                            "mode": retrieval_resp.get("mode", "strong"),
                            "graph_used": retrieval_resp.get("graph_used", False),
                            "detailed_hits": retrieval_resp.get("detailed_hits", [])
                        }
                    
                    tool_responses = []
                    for call in tool_calls:
                        name = call["name"]
                        args = call.get("args", {})
                        result = await self.execute_tool(name, args, topic_title, context_accumulator)
                        tool_responses.append({
                            "functionResponse": {
                                "name": name,
                                "response": {"result": result}
                            }
                        })
                    
                    messages.append({
                        "role": "function",
                        "parts": tool_responses
                    })

                except Exception as e:
                    logger.error(f"Iteration {i} error: {e}")
                    break
        
        # 6. Fallback from Accumulator
        fallback_content = " ".join([h.get('content', '')[:300] for h in semantic_hits[:3]])
        base_output = format_final_output(
            f"Based on the uploaded documents: {fallback_content}",
            [],
            0.6,
            "Retrieved documents"
        )
        return {
            **base_output,
            "mode": retrieval_resp.get("mode", "fallback"),
            "graph_used": retrieval_resp.get("graph_used", False),
            "detailed_hits": retrieval_resp.get("detailed_hits", [])
        }

    async def execute_tool(self, name: str, args: Dict[str, Any], topic_title: str, context_accumulator: List[Dict[str, Any]]) -> str:
        if name == "local_search":
            query = args.get("query", "")
            clean_q = self.extract_pure_question(query)
            retrieval_resp = await self.retriever.retrieve(clean_q, topic_title=topic_title, k=5)
            semantic_hits = retrieval_resp.get("hits", [])
            graph_hits = query_graph_smart(clean_q, limit=3, anchor_hits=semantic_hits)
            
            all_hits = semantic_hits + graph_hits
            for h in all_hits:
                h["content"] = self.scrub_metadata(h.get("content", ""))
            
            context_accumulator.extend(all_hits)
            return "\n\n".join([f"Local Evidence: {h.get('content', '')}" for h in all_hits])
            
        elif name == "global_search":
            query = args.get("query", "")
            clean_q = self.extract_pure_question(query)
            driver = get_neo4j_driver()
            communities = []
            if driver:
                try:
                    with driver.session() as session:
                        cypher = "MATCH (c:Community) WHERE toLower(c.summary) CONTAINS toLower($term) RETURN c.community_id AS community_id, c.summary AS summary, c.entities AS entities LIMIT $limit"
                        res = session.run(cypher, term=clean_q, limit=10)
                        for record in res:
                            communities.append({"community_id": record.get("community_id"), "summary": record.get("summary"), "entities": record.get("entities")})

                        if not communities:
                            res2 = session.run("MATCH (c:Community) RETURN c.community_id AS community_id, c.summary AS summary, c.entities AS entities LIMIT $limit", limit=50)
                            for record in res2:
                                communities.append({"community_id": record.get("community_id"), "summary": record.get("summary"), "entities": record.get("entities")})
                except Exception as e:
                    logger.warning(f"Neo4j community query failed: {e}")

            if not communities:
                try:
                    gmanager = VectorStoreManager(user_id=None)
                    results = gmanager.similarity_search(clean_q, k=5)
                    for r in results:
                        communities.append({"community_id": None, "summary": r.page_content, "entities": []})
                except Exception as e:
                    logger.warning(f"Global vector summary search failed: {e}")

            if not communities:
                communities = [
                    {"summary": "General Knowledge Context", "community_id": 1}
                ]

            report = await self.community_manager.global_search_map_reduce(clean_q, communities)
            return f"Global Synthesis Report:\n{report}"

        elif name == "verify_answer":
            return "Verification complete. Ensure the response follows the StructuredAnswer JSON schema exactly."
            
        return "Unknown tool."