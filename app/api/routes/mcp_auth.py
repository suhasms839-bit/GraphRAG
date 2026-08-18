from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.models import User
from app.infrastructure.google_oauth import (
    build_google_oauth_consent_url,
    build_google_oauth_state,
    exchange_google_code_for_tokens,
    is_google_oauth_configured,
    parse_google_oauth_state,
    upsert_user_mcp_token,
)

router = APIRouter(prefix="/api/mcp/auth", tags=["mcp-auth"])


@router.get("/start")
async def start_gmail_oauth(
    current_user: User = Depends(get_current_user),
):
    if not is_google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )

    state = build_google_oauth_state(current_user.id)
    auth_url = build_google_oauth_consent_url(state=state)
    return {"auth_url": auth_url, "state": state, "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI}


@router.get("/callback")
async def gmail_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    if not is_google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )

    state_payload = parse_google_oauth_state(state)
    if not state_payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    user_id = state_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing user context")

    tokens = exchange_google_code_for_tokens(code, redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI)
    token_row = upsert_user_mcp_token(db, user_id, tokens)

    return {
        "status": "connected",
        "user_id": token_row.user_id,
        "scopes": token_row.scopes.split(),
        "expires_at": token_row.expiry.isoformat(),
    }