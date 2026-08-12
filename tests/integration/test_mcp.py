import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.domain.agents.mcp_context import get_gmail_context_if_needed
from app.infrastructure.mcp_client import get_mcp_client


def test_mcp_client_disabled_by_default_fallback():
    """
    Ensures that if GMAIL_MCP_ENABLED is False or settings are empty,
    the client manager gracefully returns an empty string or handles opt-out without crashing.
    """
    with patch("app.core.config.settings.GMAIL_MCP_ENABLED", False):
        context = asyncio.run(get_gmail_context_if_needed("Check my recent emails", user_id="test_user"))
        assert context == ""


def test_gmail_context_keyword_gating_triggers_mcp():
    """
    Validates that the domain routing helper intercepts keywords like 'email' or 'gmail'
    and successfully invokes the underlying MCP client tool.
    """
    sample_out = "From: professor@jssstuniv.in\nSubject: Assignment Update\nBody: Deadline extended to Friday."

    async_mock = AsyncMock(return_value=sample_out)
    with patch("app.domain.agents.mcp_context.get_mcp_client") as mock_get_client:
        mock_get_client.return_value.run = async_mock
        with patch("app.core.config.settings.GMAIL_MCP_ENABLED", True):
            query_with_keyword = "Did I get any email updates from my professor about the assignment?"
            context = asyncio.run(get_gmail_context_if_needed(query_with_keyword, user_id="test_user"))

            assert context != ""
            assert "Assignment Update" in context
            async_mock.assert_awaited_once_with(query_with_keyword)


def test_gmail_context_ignores_non_mail_queries():
    """
    Ensures standard local RAG queries do not wake up the MCP subsystem unnecessarily.
    """
    async_mock = AsyncMock(return_value="")
    with patch("app.domain.agents.mcp_context.get_mcp_client") as mock_get_client:
        mock_get_client.return_value.run = async_mock
        with patch("app.core.config.settings.GMAIL_MCP_ENABLED", True):
            query_without_keyword = "What is the time complexity of building a balanced binary search tree?"
            context = asyncio.run(get_gmail_context_if_needed(query_without_keyword, user_id="test_user"))

            assert context == ""
            async_mock.assert_not_awaited()


def test_gmail_context_uses_per_user_token_env():
    token_row = SimpleNamespace(
        client_id="client-id",
        client_secret="client-secret",
        access_token="access-token",
        refresh_token="refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        scopes="https://www.googleapis.com/auth/gmail.readonly",
        user_id="42",
        expiry=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00+00:00"),
    )
    async_mock = AsyncMock(return_value="Inbox update")

    class DummyDb:
        def close(self):
            return None

    with patch("app.domain.agents.mcp_context.SessionLocal", return_value=DummyDb()):
        with patch("app.domain.agents.mcp_context.get_active_user_mcp_token", return_value=token_row):
            with patch("app.domain.agents.mcp_context.get_mcp_client") as mock_get_client:
                mock_get_client.return_value.run = async_mock
                with patch("app.core.config.settings.GMAIL_MCP_ENABLED", True):
                    context = asyncio.run(
                        get_gmail_context_if_needed("Any email from finance?", user_id="42")
                    )

    assert context == "Inbox update"
    _, kwargs = async_mock.await_args
    assert kwargs["env_overrides"]["GOOGLE_OAUTH_USER_ID"] == "42"
