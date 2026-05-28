from fastapi import APIRouter, Body, Depends

from ..dependencies import get_db
from ...domain.agents.mcp_context import fetch_gmail_context

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.post("/gmail/context")
async def gmail_context(query: str = Body(..., embed=True)):
    """Return contextual augmentation for a free-text query via Gmail MCP."""
    ctx = await fetch_gmail_context(query)
    return {"context": ctx}
