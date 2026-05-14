from typing import List, Dict, Any

# Domain-specific entity types for JSS STU (CS/Engineering focus)
ENTITY_TYPES = [
    "CONCEPT",      # Technical concepts, theories, algorithms
    "PROTOCOL",     # Network protocols, communication standards
    "COMPONENT",    # Hardware or software components (Hub, Router, CPU)
    "METRIC",       # Performance metrics (Latency, Throughput, Reliability)
    "ORGANIZATION", # Universities (JSS STU), Companies (Cisco, Google)
    "PERSON",       # Authors, researchers, professors
    "COURSE",       # Specific subjects or modules
]

# 1. Entity & Relationship Extraction Prompt
EXTRACTION_PROMPT = """
You are a Knowledge Graph Architect. Extract entities and relationships from the text below.
Focus on the following entity types: {entity_types}

Rules:
1. Resolve coreferences (e.g., "it" or "the hub" should map to the specific entity).
2. Extract relationships as (source, type, target, description).
3. Keep descriptions technical and concise.
4. Return ONLY a JSON object.

Format:
{{
  "entities": [{{ "name": "Entity Name", "type": "TYPE", "description": "..." }}],
  "relationships": [{{ "source": "...", "target": "...", "type": "...", "description": "..." }}]
}}
"""

# 2. Entity & Relationship Summarization Prompt
SUMMARIZATION_PROMPT = """
You are a Technical Editor. Summarize the following descriptions for the entity/relationship: "{target}".
Combine multiple observations into a single, concise, and informative summary.
Prioritize technical accuracy and remove redundant information.

Descriptions:
{descriptions}

Summary:
"""

# 3. Community Summarization Prompt
COMMUNITY_SUMMARIZATION_PROMPT = """
You are a Knowledge Architect. Generate a comprehensive summary for this community of entities.
Identify the core theme, key technical relationships, and how these concepts relate to the broader course.

Entities in Community:
{entities}

Relationships in Community:
{relationships}

Community Report:
"""
