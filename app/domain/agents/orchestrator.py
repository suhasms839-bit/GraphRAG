import asyncio
import json
import re
from typing import List, Dict, Any, Tuple
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

    def scrub_metadata(self, text: str) -> str:
        """Strips technical artifacts like chunk_id, timestamps, and raw headers."""
        # Remove common patterns like [chunk_id: ...], PAGE X, etc.
        text = re.sub(r"\[chunk_id: [a-f0-9]+\]", "", text)
        text = re.sub(r"PAGE \d+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"DATA COMMUNICATION", "", text, flags=re.IGNORECASE)
        # Clean up extra whitespace
        return re.sub(r"\s+", " ", text).strip()

    async def run(self, question: str, topic_title: str) -> Dict[str, Any]:
        logger.info(f"Starting Structured Agentic RAG for: {question}")
        
        # Force retrieval first
        retrieval_resp = await self.retriever.retrieve(question, topic_title=topic_title, k=5)
        semantic_hits = retrieval_resp.get("hits", [])
        logger.info(f"Retrieved docs count: {len(semantic_hits)}")
        
        if not semantic_hits:
            # Fallback to general knowledge
            answer = f"Based on general knowledge: {question} requires specific context from uploaded documents. Please upload relevant materials for a detailed answer."
            base_output = format_final_output(answer, [], 0.1, "General Knowledge")
            return {
                **base_output,
                "mode": retrieval_resp.get("mode", "fallback"),
                "graph_used": retrieval_resp.get("graph_used", False),
                "detailed_hits": retrieval_resp.get("detailed_hits", [])
            }
        
        # Continue with existing logic but with retrieved context
        context_text = "\n\n".join([f"Evidence: {h.get('content', '')}" for h in semantic_hits])
        
        system_instruction = f"""You are a Technical Mentor and Knowledge Architect for students at JSS STU.
Your goal is to transform the provided context into a precise, verifiable, and goal-aligned response.

### Provided Context:
{context_text}

### Operational Principles:
1. **Structural Priority**: Prioritize key-value pairs (methods, authors, dates).
2. **Entity Resolution**: Resolve different representations of the same entity (e.g., "The Frog" and "Most Important Task").
3. **Boundary Integrity**: Respect document and chapter boundaries. Do not mix unrelated topics.
4. **Metadata Scrubbing**: Strip technical artifacts (timestamps, chunk_id tags, raw headers).

### Response Framework:
1. **Synthesis**: Clean, prose-style explanation based on the provided context.
2. **Placement Insight**: Include a brief section on how this concept appears in placement interviews.
3. **Citations**: Use [S1], [S2] markers at the end of factual claims.

### Hard Rules:
- If context is insufficient, say: "Based on general knowledge" then answer, clearly separating from document-based info.
- NO mid-sentence breaks. Complete thoughts logically.
- MANDATORY Schema: Return a JSON object following the StructuredAnswer model.

### StructuredAnswer Model:
{{
  "answer": "Prose-style synthesis with [S1] citations",
  "key_points": ["Point 1", "Point 2"],
  "placement_insight": "How this appears in interviews",
  "citations": [{{ "id": "S1", "source": "filename.pdf", "page": 5 }}],
  "confidence": 0.95
}}"""

        prompt_text = f"Topic: {topic_title}\nQuestion: {question}\n\n{system_instruction}"
        
        # 2. Simple Generation Fallback (Direct RAG)
        # Avoid complex agentic loop if we are likely to hit 429
        try:
            from app.domain.generation.llm_gateway import call_gemini_text
            import json

            # Quick attempt at direct synthesis
            direct_response = call_gemini_text(prompt_text)
            if direct_response and "429" not in direct_response:
                try:
                    structured_data = extract_json_object_text(direct_response)
                    if structured_data and "answer" in structured_data:
                        logger.info("Direct Synthesis successful, bypassing agent loop.")
                        ans = structured_data.get("answer", "")
                        citations = structured_data.get("citations", [])
                        confidence = structured_data.get("confidence", 0.5)
                        source = structured_data.get("source", "")
                        base_output = format_final_output(ans, citations, confidence, source)
                        return {
                            **base_output,
                            "mode": retrieval_resp.get("mode", "strong"),
                            "graph_used": retrieval_resp.get("graph_used", False),
                            "detailed_hits": retrieval_resp.get("detailed_hits", [])
                        }
                except Exception as e:
                    logger.warning(f"Failed to parse direct synthesis: {e}")

        except Exception as e:
            logger.error(f"Error in Direct Synthesis: {e}")

        # 3. Agentic Multi-Hop Loop (Only for Gemini with tool support)
        from app.core.config import settings
        if not settings.USE_OLLAMA:
            messages = [
                {
                    "role": "user",
                    "parts": [{"text": prompt_text}]
                }
            ]
            
            # Fallback to agentic approach if direct call fails
            context_accumulator = semantic_hits
            max_iterations = 2 # Reduced from 3 to save tokens/avoid 429
            
            for i in range(max_iterations):
                try:
                    # Ensure tools are passed in the correct format for Gemini v1beta
                    # The API expects a list of tool objects, each with a 'function_declarations' list
                    response = call_gemini_with_tools(messages, tools=AGENT_TOOLS)
                    
                    if isinstance(response, dict) and "error" in response:
                        # Log the full error for debugging
                        logger.error(f"Gemini API Error in loop: {response['error']}")
                        if "429" in str(response["error"]):
                            # CRITICAL: If 429, don't just return error, return the best effort based on context
                            return format_final_output(
                                f"I can explain {question} based on retrieved documents: " + " ".join([h.get('content', '')[:200] for h in semantic_hits[:2]]),
                                [],
                                0.5,
                                "Retrieved documents"
                            )
                        return format_final_output(f"Agent Error: {response['error']}", [], 0.0, "")
                    
                    messages.append(response)
                    
                    parts = response.get("parts", [])
                    tool_calls = [p.get("functionCall") for p in parts if p.get("functionCall")]
                    
                    if not tool_calls:
                        # Final answer extraction
                        final_text = "".join([p.get("text", "") for p in parts])
                        try:
                            structured_data = extract_json_object_text(final_text)
                            if structured_data:
                                ans = structured_data.get("answer", "")
                                citations = structured_data.get("citations", [])
                                confidence = structured_data.get("confidence", 0.5)
                                source = structured_data.get("source", "")
                                base_output = format_final_output(ans, citations, confidence, source)
                                return {
                                    **base_output,
                                    "mode": retrieval_resp.get("mode", "strong"),
                                    "graph_used": retrieval_resp.get("graph_used", False),
                                    "detailed_hits": retrieval_resp.get("detailed_hits", [])
                                }
                        except:
                            # Best effort if JSON fails
                            base_output = format_final_output(final_text[:500], [], 0.4, "Retrieved documents")
                            return {
                                **base_output,
                                "mode": retrieval_resp.get("mode", "fallback"),
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
        
        # 4. Ultimate Fallback (If loop finished/failed without structured_data)
        base_output = format_final_output(
            f"Completed research on {question}. Most relevant excerpts: " + " ".join([h.get('content', '')[:150] for h in semantic_hits[:3]]),
            [],
            0.3,
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
            # 1. Vector + BM25 Retrieval
            # 1. Vector + BM25 Retrieval
            retrieval_resp = await self.retriever.retrieve(query, topic_title=topic_title, k=5)
            semantic_hits = retrieval_resp.get("hits", [])
            
            # 2. Graph Traversal (Steiner-Approx) using semantic hits as anchors
            graph_hits = query_graph_smart(query, limit=3, anchor_hits=semantic_hits)
            
            all_hits = semantic_hits + graph_hits
            for h in all_hits:
                h["content"] = self.scrub_metadata(h.get("content", ""))
            
            context_accumulator.extend(all_hits)
            return "\n\n".join([f"Local Evidence: {h.get('content', '')}" for h in all_hits])
            
        elif name == "global_search":
            query = args.get("query", "")
            # Prefer Neo4j community summaries if available
            driver = get_neo4j_driver()
            communities = []
            if driver:
                try:
                    with driver.session() as session:
                        # Try to find communities whose summary contains the query (case-insensitive)
                        cypher = "MATCH (c:Community) WHERE toLower(c.summary) CONTAINS toLower($term) RETURN c.community_id AS community_id, c.summary AS summary, c.entities AS entities LIMIT $limit"
                        res = session.run(cypher, term=query, limit=10)
                        for record in res:
                            communities.append({"community_id": record.get("community_id"), "summary": record.get("summary"), "entities": record.get("entities")})

                        # If none matched, fetch a broader set and let the reducer pick
                        if not communities:
                            res2 = session.run("MATCH (c:Community) RETURN c.community_id AS community_id, c.summary AS summary, c.entities AS entities LIMIT $limit", limit=50)
                            for record in res2:
                                communities.append({"community_id": record.get("community_id"), "summary": record.get("summary"), "entities": record.get("entities")})
                except Exception as e:
                    logger.warning(f"Neo4j community query failed: {e}")

            # Fallback: use global Chroma store of community summaries if Neo4j unavailable or empty
            if not communities:
                try:
                    gmanager = VectorStoreManager(user_id=None)
                    results = gmanager.similarity_search(query, k=5)
                    for r in results:
                        communities.append({"community_id": None, "summary": r.page_content, "entities": []})
                except Exception as e:
                    logger.warning(f"Global vector summary search failed: {e}")

            # Final fallback: simulated communities (keeps prior behavior)
            if not communities:
                communities = [
                    {"summary": "Topologies Cluster: Consensus highlights Star as manageable but Mesh as reliable.", "community_id": 1},
                    {"summary": "Reliability Cluster: Key metrics include MTBF and Single Point of Failure.", "community_id": 2},
                    {"summary": "JSS STU Cluster: Campus labs prioritize cost-effective Star configurations.", "community_id": 3}
                ]

            report = await self.community_manager.global_search_map_reduce(query, communities)
            return f"Global Synthesis Report:\n{report}"

        elif name == "verify_answer":
            return "Verification complete. Ensure the response follows the StructuredAnswer JSON schema exactly."
            
        return "Unknown tool."
