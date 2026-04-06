import json
from typing import Optional, Dict, Any
from app.domain.generation.llm_gateway import call_gemini_text, extract_json_object_text
from app.domain.graph.strategies.schema import GRAPH_SCHEMA, map_terminology
from app.core.logging import logger

class Text2Cypher:
    @staticmethod
    def generate(question: str) -> Optional[str]:
        """
        Converts a natural language question into a Cypher query based on the schema.
        """
        mapped_terms = map_terminology(question)
        schema_str = json.dumps(GRAPH_SCHEMA, indent=2)
        
        prompt = f"""You are a Neo4j Cypher expert. Convert the following natural language question into a read-only Cypher query.
Use ONLY the provided schema.

Schema:
{schema_str}

Mapped Terms: {", ".join(mapped_terms)}

Question: {question}

Rules:
1. Use only 'Chunk' nodes.
2. Focus on 'RELATES_TO' relationships.
3. Return the 'text' property of the nodes.
4. Limit results to 5.
5. Return ONLY a JSON object with the key 'cypher'.

Format: {{"cypher": "MATCH (c:Chunk) WHERE ... RETURN c.text LIMIT 5"}}"""

        try:
            raw_output = call_gemini_text(prompt, max_tokens=200, temperature=0.0, response_mime_type="application/json")
            parsed = extract_json_object_text(raw_output or "")
            if parsed and "cypher" in parsed:
                cypher = parsed["cypher"]
                # Basic safety check
                if "DELETE" in cypher.upper() or "REMOVE" in cypher.upper() or "SET" in cypher.upper():
                    logger.warning(f"Unsafe Cypher generated: {cypher}")
                    return None
                return cypher
        except Exception as e:
            logger.error(f"Text2Cypher generation failed: {e}")
        
        return None
