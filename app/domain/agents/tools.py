from typing import List, Dict, Any

# 1. Local Search Tool
local_search_tool = {
    "name": "local_search",
    "description": "Combines vector similarity with graph traversal to answer entity-focused queries. Use this for specific questions about concepts, their definitions, and direct relationships.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "The specific entity-focused query."
            }
        },
        "required": ["query"]
    }
}

# 2. Global Search Tool
global_search_tool = {
    "name": "global_search",
    "description": "Uses community summaries to answer broad, thematic queries through a map-reduce approach. Use this for 'big picture' questions, trends, or summaries across the entire corpus.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "The broad, thematic query."
            }
        },
        "required": ["query"]
    }
}

# 3. Critic Tool
verify_answer_tool = {
    "name": "verify_answer",
    "description": "Critically evaluates a draft answer against the provided context to identify hallucinations, missing facts, or formatting errors.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "draft_answer": {
                "type": "STRING",
                "description": "The draft answer to be evaluated."
            },
            "context": {
                "type": "STRING",
                "description": "The source context used to generate the answer."
            }
        },
        "required": ["draft_answer", "context"]
    }
}

AGENT_TOOLS = [
    {
        "function_declarations": [
            local_search_tool,
            global_search_tool,
            verify_answer_tool
        ]
    }
]
