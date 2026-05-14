import re
import json
import asyncio
from typing import List, Dict, Any, Optional
from app.domain.generation.llm_gateway import call_gemini_text, extract_json_object_text
from app.core.logging import logger
from .prompts import ENTITY_TYPES, EXTRACTION_PROMPT, SUMMARIZATION_PROMPT

class GraphRAGIndexer:
    def __init__(self, token_limit: int = 600):
        self.token_limit = token_limit

    def preprocess(self, text: str) -> str:
        """Removes prefaces, footnotes, and common PDF artifacts."""
        # Remove common "Preface" or "Introduction" headers if they appear at the start
        text = re.sub(r"^(Preface|Introduction|Foreword).*?\n", "", text, flags=re.IGNORECASE | re.DOTALL)
        # Remove footnotes (e.g., [1], [2] or small superscript-like numbers at line ends)
        text = re.sub(r"\[\d+\]", "", text)
        # Remove raw headers/footers
        text = re.sub(r"PAGE \d+", "", text, flags=re.IGNORECASE)
        return text.strip()

    def chunk_text(self, text: str) -> List[str]:
        """Divide text into chunks based on token-ish count (words for simplicity here)."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), self.token_limit):
            chunks.append(" ".join(words[i : i + self.token_limit]))
        return chunks

    async def extract_entities_and_relationships(self, chunk: str) -> Dict[str, Any]:
        """Calls LLM to extract structured data from a chunk."""
        prompt = EXTRACTION_PROMPT.format(entity_types=", ".join(ENTITY_TYPES))
        user_input = f"Text:\n{chunk}"
        
        # Simple local heuristic extraction when LLM is rate limited
        local_entities = []
        local_rels = []
        
        # Heuristic for Topologies
        topology_matches = re.findall(r"(Mesh|Star|Bus|Ring)\s+Topology", chunk, re.I)
        for t in set(topology_matches):
            local_entities.append({"name": f"{t.upper()} TOPOLOGY", "type": "CONCEPT", "description": f"A network topology of type {t}."})
            
        if "hub" in chunk.lower() or "switch" in chunk.lower():
            local_entities.append({"name": "CENTRAL CONTROLLER", "type": "COMPONENT", "description": "A hub or switch."})
            if topology_matches:
                local_rels.append({"source": f"{topology_matches[0].upper()} TOPOLOGY", "target": "CENTRAL CONTROLLER", "type": "USES", "description": "Requires a central device."})

        try:
            raw_output = call_gemini_text(f"{prompt}\n\n{user_input}", response_mime_type="application/json")
            if "LLM Error" in str(raw_output) and local_entities:
                return {"entities": local_entities, "relationships": local_rels}
            return extract_json_object_text(raw_output or "") or {"entities": local_entities, "relationships": local_rels}
        except Exception as e:
            logger.error(f"Extraction failed, returning heuristics: {e}")
            return {"entities": local_entities, "relationships": local_rels}

    async def summarize_descriptions(self, target: str, descriptions: List[str]) -> str:
        """Summarizes multiple descriptions for a single entity or relationship."""
        if not descriptions:
            return ""
        if len(descriptions) == 1:
            return descriptions[0]
            
        prompt = SUMMARIZATION_PROMPT.format(target=target, descriptions="\n- ".join(descriptions))
        try:
            return call_gemini_text(prompt) or descriptions[0]
        except Exception as e:
            logger.error(f"Summarization failed for {target}: {e}")
            return descriptions[0]

    async def process_document(self, text: str) -> Dict[str, Any]:
        """Full pipeline for a single document."""
        clean_text = self.preprocess(text)
        chunks = self.chunk_text(clean_text)
        
        all_entities = {}
        all_relationships = []
        
        # 1. Extraction Phase
        tasks = [self.extract_entities_and_relationships(c) for c in chunks]
        results = await asyncio.gather(*tasks)
        
        for res in results:
            for ent in res.get("entities", []):
                name = ent["name"].strip().upper()
                if name not in all_entities:
                    all_entities[name] = {"type": ent["type"], "descriptions": []}
                all_entities[name]["descriptions"].append(ent["description"])
            
            all_relationships.extend(res.get("relationships", []))
            
        # 2. Summarization Phase (Entities)
        summarized_entities = []
        for name, data in all_entities.items():
            summary = await self.summarize_descriptions(name, data["descriptions"])
            summarized_entities.append({
                "name": name,
                "type": data["type"],
                "description": summary
            })
            
        return {
            "entities": summarized_entities,
            "relationships": all_relationships
        }
