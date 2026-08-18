import asyncio
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.mcp_auth import gmail_oauth_callback, start_gmail_oauth
from app.core.config import settings
from app.core.models import Base, User, UserMcpToken
from app.infrastructure.google_oauth import build_google_oauth_state, upsert_user_mcp_token


TEST_CREDENTIALS = {
    "client_id": "client-id-123",
    "client_secret": "client-secret-abc",
    "redirect_uris": ["http://localhost:8080/"],
}


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_upsert_user_mcp_token_persists_and_updates():
    db = _make_session()
    with patch("app.infrastructure.google_oauth.load_google_oauth_credentials", return_value=TEST_CREDENTIALS):
        first = upsert_user_mcp_token(
            db,
            42,
            {
                "access_token": "token-one",
                "refresh_token": "refresh-one",
                "expires_in": 120,
                "scope": "https://www.googleapis.com/auth/gmail.readonly",
            },
        )
        second = upsert_user_mcp_token(
            db,
            42,
            {
                "access_token": "token-two",
                "refresh_token": "refresh-two",
                "expires_in": 240,
                "scope": "https://www.googleapis.com/auth/gmail.readonly",
            },
        )

    assert first.user_id == "42"
    assert second.access_token == "token-two"
    assert second.refresh_token == "refresh-two"
    assert second.client_id == TEST_CREDENTIALS["client_id"]
    assert db.query(UserMcpToken).count() == 1


def test_start_gmail_oauth_builds_state_and_url():
    user = User(id=7, email="user@example.com", username="user")
    with patch("app.api.routes.mcp_auth.is_google_oauth_configured", return_value=True):
        with patch("app.api.routes.mcp_auth.build_google_oauth_consent_url", return_value="https://example.com/auth") as build_url:
            response = asyncio.run(start_gmail_oauth(current_user=user))

    assert response["auth_url"] == "https://example.com/auth"
    assert response["state"]
    build_url.assert_called_once()


def test_gmail_oauth_callback_persists_token():
    db = _make_session()
    user = User(id=9, email="user9@example.com", username="user9")
    db.add(user)
    db.commit()

    state = build_google_oauth_state(user.id)
    token_payload = {
        "access_token": "access-xyz",
        "refresh_token": "refresh-xyz",
        "expires_in": 300,
        "scope": "https://www.googleapis.com/auth/gmail.readonly",
    }

    with patch("app.api.routes.mcp_auth.is_google_oauth_configured", return_value=True):
        with patch("app.api.routes.mcp_auth.exchange_google_code_for_tokens", return_value=token_payload) as exchange:
            result = asyncio.run(gmail_oauth_callback(code="auth-code", state=state, db=db))

    assert result["status"] == "connected"
    assert result["user_id"] == str(user.id)
    exchange.assert_called_once_with("auth-code", redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI)
    stored = db.query(UserMcpToken).filter(UserMcpToken.user_id == str(user.id)).one()
    assert stored.access_token == "access-xyz"
    assert stored.refresh_token == "refresh-xyz"
    assert stored.scopes == "https://www.googleapis.com/auth/gmail.readonly"
