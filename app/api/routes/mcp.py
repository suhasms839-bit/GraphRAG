from fastapi import APIRouter, Body, Depends

from app.api.routes.auth import get_current_user
from app.core.models import User
from ...domain.agents.mcp_context import fetch_gmail_context

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.post("/gmail/context")
async def gmail_context(
    query: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
):
    """Return contextual augmentation for a free-text query via Gmail MCP."""
    ctx = await fetch_gmail_context(query, user_id=str(current_user.id))
    return {"context": ctx}
