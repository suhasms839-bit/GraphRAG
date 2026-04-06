import asyncio
import json
from collections import defaultdict
from typing import List, Dict, Any
from app.domain.generation.llm_gateway import call_gemini_text
from app.core.logging import logger
from .prompts import COMMUNITY_SUMMARIZATION_PROMPT

class GraphRAGCommunityManager:
    """
    Handles Community Detection (Louvain) and Summarization.
    """
    
    @staticmethod
    def detect_communities_local(entities: List[Dict], relationships: List[Dict]) -> Dict[int, List[str]]:
        """
        Detects communities using NetworkX Louvain implementation.
        """
        try:
            import networkx as nx
            from networkx.algorithms import community
        except ImportError:
            logger.warning("NetworkX not installed. Skipping community detection.")
            return {0: [e["name"] for e in entities]}

        G = nx.Graph()
        for ent in entities:
            G.add_node(ent["name"])
        for rel in relationships:
            G.add_edge(rel["source"], rel["target"], weight=1.0)

        # Louvain community detection
        communities = community.louvain_communities(G)
        
        result = {}
        for i, comm in enumerate(communities):
            result[i] = list(comm)
        return result

    async def summarize_community(self, community_id: int, entity_names: List[str], all_entities: List[Dict], all_relationships: List[Dict]) -> Dict[str, Any]:
        """Generates a summary report for a specific community."""
        # Filter entities and relationships belonging to this community
        comm_entities = [e for e in all_entities if e["name"] in entity_names]
        comm_relationships = [r for r in all_relationships if r["source"] in entity_names and r["target"] in entity_names]
        
        # Ranking mechanism: Select top entities/relationships if community is too large
        # For now, we take all if small, or top 20 by degree if large
        selected_entities = comm_entities[:20] 
        selected_relationships = comm_relationships[:30]

        prompt = COMMUNITY_SUMMARIZATION_PROMPT.format(
            entities=json.dumps(selected_entities, indent=2),
            relationships=json.dumps(selected_relationships, indent=2)
        )
        
        try:
            summary = await asyncio.to_thread(call_gemini_text, prompt)
            return {
                "community_id": community_id,
                "summary": summary,
                "entities": entity_names
            }
        except Exception as e:
            logger.error(f"Community summarization failed for {community_id}: {e}")
            return {"community_id": community_id, "summary": "Error generating summary.", "entities": entity_names}

    async def global_search_map_reduce(self, query: str, communities: List[Dict[str, Any]]) -> str:
        """
        Executes a Map-Reduce search across community summaries.
        """
        # 1. Map Phase: Generate intermediate answers from each community
        map_tasks = []
        for comm in communities:
            map_prompt = f"""
            Question: {query}
            Community Summary: {comm['summary']}
            
            Based ONLY on the community summary above, provide a concise intermediate answer. 
            If the summary is irrelevant, return 'IRRELEVANT'.
            """
            map_tasks.append(asyncio.to_thread(call_gemini_text, map_prompt))
            
        intermediate_answers = await asyncio.gather(*map_tasks)
        relevant_answers = [ans for ans in intermediate_answers if ans and "IRRELEVANT" not in ans.upper()]
        
        if not relevant_answers:
            return "No relevant global information found across communities."
            
        # 2. Reduce Phase: Synthesize intermediate answers
        reduce_prompt = f"""
        You are a Knowledge Architect. Synthesize the following intermediate answers into a single, 
        comprehensive global response for the query: "{query}".
        
        Intermediate Answers:
        {chr(10).join([f"- {ans}" for ans in relevant_answers])}
        
        Final Global Response:
        """
        return call_gemini_text(reduce_prompt) or "Failed to synthesize global response."

    async def process_communities(self, entities: List[Dict], relationships: List[Dict]) -> List[Dict[str, Any]]:
        """Detects, ranks, and summarizes all communities."""
        # Ranking mechanism: Sort entities by degree (connectivity)
        # This handles scaling by ensuring we focus on the most important nodes first
        entity_degrees = defaultdict(int)
        for rel in relationships:
            entity_degrees[rel["source"]] += 1
            entity_degrees[rel["target"]] += 1
            
        ranked_entities = sorted(entities, key=lambda e: entity_degrees[e["name"]], reverse=True)
        
        communities = self.detect_communities_local(ranked_entities, relationships)
        
        tasks = []
        for comm_id, names in communities.items():
            tasks.append(self.summarize_community(comm_id, names, ranked_entities, relationships))
            
        return await asyncio.gather(*tasks)
