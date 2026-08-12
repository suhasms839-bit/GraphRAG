from typing import Optional

from fastapi import HTTPException

from ...core.config import settings
from ...core.database import SessionLocal
from ...infrastructure.google_oauth import build_gmail_mcp_env, get_active_user_mcp_token
from ...infrastructure.mcp_client import get_mcp_client


async def fetch_gmail_context(query: str, user_id: Optional[str] = None) -> Optional[str]:
    """Fetch contextual augmentation from the Gmail MCP tool.

    Returns empty string if not configured or on errors.
    """
    if not settings.GMAIL_MCP_ENABLED:
        return ""
    if not user_id:
        return ""
    client = get_mcp_client()
    try:
        db = SessionLocal()
        try:
            try:
                token_row = get_active_user_mcp_token(db, user_id)
            except Exception:
                token_row = None

            if not token_row:
                out = await client.run(query)
                return out or ""
            out = await client.run(query, env_overrides=build_gmail_mcp_env(token_row))
            return out or ""
        finally:
            db.close()
    except Exception:
        return ""


async def get_gmail_context_if_needed(query: str, user_id: Optional[str] = None) -> str:
    """Keyword-gated helper: only invokes MCP if the query looks email-related.

    This prevents waking the MCP tool for ordinary RAG queries.
    """
    if not query:
        return ""

    if not user_id:
        return ""

    # Simple keyword gate; can be extended with heuristics or ML later.
    keywords = ["email", "gmail", "inbox", "mail", "subject", "thread"]
    q = query.lower()
    if not any(k in q for k in keywords):
        return ""

    return await fetch_gmail_context(query, user_id=user_id) or ""
