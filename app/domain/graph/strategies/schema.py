from typing import Dict, List

# Define the Knowledge Graph Schema
GRAPH_SCHEMA = {
    "nodes": {
        "Chunk": {
            "properties": ["chunk_id", "text", "source", "page", "title", "chapter_title", "section_title", "subsection_title", "document_type", "last_indexed"]
        }
    },
    "relationships": {
        "RELATES_TO": {
            "source": "Chunk",
            "target": "Chunk",
            "properties": ["weight", "type"]
        }
    }
}

# Terminology Mapping for Semantic Alignment
TERMINOLOGY_MAP = {
    "ring topology": ["ring", "unidirectional", "token ring", "repeater"],
    "star topology": ["star", "hub", "central controller", "switch"],
    "bus topology": ["bus", "backbone", "multipoint", "drop line", "tap"],
    "mesh topology": ["mesh", "point-to-point", "fully connected", "dedicated link"],
    "reliability": ["robustness", "fault tolerance", "failure"],
    "cost": ["expensive", "cabling", "installation"],
    "performance": ["traffic", "congestion", "speed"]
}

def map_terminology(question: str) -> List[str]:
    """Maps user question terms to canonical schema terms."""
    mapped_terms = []
    q_lower = question.lower()
    for canonical, variants in TERMINOLOGY_MAP.items():
        if canonical in q_lower or any(v in q_lower for v in variants):
            mapped_terms.append(canonical)
    return mapped_terms
