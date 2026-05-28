from typing import Optional

from fastapi import HTTPException

from ...core.config import settings
from ...infrastructure.mcp_client import get_mcp_client


async def fetch_gmail_context(query: str) -> Optional[str]:
    """Fetch contextual augmentation from the Gmail MCP tool.

    Returns empty string if not configured or on errors.
    """
    if not settings.GMAIL_MCP_ENABLED:
        return ""
    client = get_mcp_client()
    try:
        out = await client.run(query)
        return out or ""
    except Exception:
        return ""


async def get_gmail_context_if_needed(query: str, user_id: Optional[str] = None) -> str:
    """Keyword-gated helper: only invokes MCP if the query looks email-related.

    This prevents waking the MCP tool for ordinary RAG queries.
    """
    if not query:
        return ""

    # Simple keyword gate; can be extended with heuristics or ML later.
    keywords = ["email", "gmail", "inbox", "mail", "subject", "thread"]
    q = query.lower()
    if not any(k in q for k in keywords):
        return ""

    try:
        return await fetch_gmail_context(query)
    except HTTPException:
        return ""
