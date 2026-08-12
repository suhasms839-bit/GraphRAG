import json
import os
import urllib.error
import urllib.parse
import urllib.request
import base64
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Optional

from .mcp_client import get_mcp_client
from ..core.config import settings
from ..core.models import UserMcpToken
from ..core.security import create_access_token, verify_token

# Optional encryption support for client_secret storage.
try:
    from cryptography.fernet import Fernet, InvalidToken
    HAS_CRYPTO = True
except Exception:
    Fernet = None
    InvalidToken = Exception
    HAS_CRYPTO = False

logger = logging.getLogger(__name__)


def _derive_fernet(secret: Optional[str] = None) -> Optional[Fernet]:
    key_source = secret or getattr(settings, "GOOGLE_OAUTH_ENCRYPTION_KEY", None) or getattr(settings, "SECRET_KEY", None)
    if not key_source or not HAS_CRYPTO:
        if not HAS_CRYPTO:
            logger.debug("cryptography not available; storing secrets in plaintext")
        return None
    digest = hashlib.sha256(key_source.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    f = _derive_fernet()
    if not f:
        return value
    try:
        return f.encrypt(value.encode("utf-8")).decode("utf-8")
    except Exception:
        return value


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    f = _derive_fernet()
    if not f:
        return value
    try:
        return f.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Assume value was stored plaintext
        return value
    except Exception:
        return value

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def load_google_oauth_credentials() -> Dict[str, str]:
    """Load Google OAuth2 client id/secret from env vars or a credentials JSON file."""
    if settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET:
        return {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI],
        }

    path = settings.GOOGLE_OAUTH_CREDENTIALS_PATH
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entry = data.get("installed") or data.get("web") or {}
            return {
                "client_id": entry.get("client_id", ""),
                "client_secret": entry.get("client_secret", ""),
                "redirect_uris": entry.get("redirect_uris", [settings.GOOGLE_OAUTH_REDIRECT_URI]),
            }
        except Exception:
            return {"client_id": "", "client_secret": "", "redirect_uris": []}

    return {"client_id": "", "client_secret": "", "redirect_uris": []}


def is_google_oauth_configured() -> bool:
    creds = load_google_oauth_credentials()
    return bool(creds.get("client_id") and creds.get("client_secret"))


def build_google_oauth_state(user_id: int | str, scopes: Optional[Iterable[str]] = None) -> str:
    scope_list = list(scopes or GOOGLE_GMAIL_SCOPES)
    return create_access_token(
        data={
            "sub": str(user_id),
            "purpose": "gmail_oauth",
            "scopes": " ".join(scope_list),
        }
    )


def parse_google_oauth_state(state: str) -> Optional[Dict[str, str]]:
    payload = verify_token(state)
    if not payload or payload.get("purpose") != "gmail_oauth":
        return None
    return payload


def build_google_oauth_consent_url(
    state: str,
    scopes: Optional[Iterable[str]] = None,
    redirect_uri: Optional[str] = None,
) -> str:
    creds = load_google_oauth_credentials()
    scope_list = list(scopes or GOOGLE_GMAIL_SCOPES)
    params = {
        "client_id": creds.get("client_id", ""),
        "redirect_uri": redirect_uri or settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scope_list),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URI}?{urllib.parse.urlencode(params)}"


def _post_form(url: str, data: Dict[str, str]) -> Dict[str, str]:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(body or f"OAuth request failed with HTTP {exc.code}") from exc


def exchange_google_code_for_tokens(
    code: str,
    redirect_uri: Optional[str] = None,
    token_uri: str = GOOGLE_TOKEN_URI,
) -> Dict[str, str]:
    creds = load_google_oauth_credentials()
    if not creds.get("client_id") or not creds.get("client_secret"):
        raise RuntimeError("Google OAuth credentials are not configured")

    return _post_form(
        token_uri,
        {
            "code": code,
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "redirect_uri": redirect_uri or settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )


def refresh_google_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    token_uri: str = GOOGLE_TOKEN_URI,
) -> Dict[str, str]:
    return _post_form(
        token_uri,
        {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        },
    )


def build_gmail_mcp_env(token_row: UserMcpToken) -> Dict[str, str]:
    return {
        "GOOGLE_OAUTH_CLIENT_ID": token_row.client_id,
        "GOOGLE_OAUTH_CLIENT_SECRET": token_row.client_secret,
        "GOOGLE_OAUTH_ACCESS_TOKEN": token_row.access_token,
        "GOOGLE_OAUTH_REFRESH_TOKEN": token_row.refresh_token or "",
        "GOOGLE_OAUTH_TOKEN_URI": token_row.token_uri,
        "GOOGLE_OAUTH_SCOPES": token_row.scopes,
        "GOOGLE_OAUTH_USER_ID": token_row.user_id,
        "GOOGLE_OAUTH_EXPIRY": token_row.expiry.isoformat(),
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_active_user_mcp_token(db, user_id: int | str, refresh_leeway_seconds: int = 60) -> Optional[UserMcpToken]:
    token_row = get_user_mcp_token(db, user_id)
    if token_row is None:
        return None

    expiry = token_row.expiry
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if expiry <= _utcnow() + timedelta(seconds=refresh_leeway_seconds):
        if not token_row.refresh_token:
            return token_row

        refreshed = refresh_google_access_token(
            token_row.refresh_token,
            token_row.client_id,
            token_row.client_secret,
            token_uri=token_row.token_uri,
        )
        token_row.access_token = refreshed.get("access_token", token_row.access_token)
        token_row.refresh_token = refreshed.get("refresh_token") or token_row.refresh_token
        expires_in = int(refreshed.get("expires_in", 0) or 0)
        if expires_in > 0:
            token_row.expiry = _utcnow() + timedelta(seconds=expires_in)
        db.commit()
        db.refresh(token_row)

    return token_row


def upsert_user_mcp_token(
    db,
    user_id: int | str,
    token_payload: Dict[str, str],
) -> UserMcpToken:
    user_key = str(user_id)
    token_row = db.query(UserMcpToken).filter(UserMcpToken.user_id == user_key).one_or_none()
    expiry_seconds = int(token_payload.get("expires_in", 0) or 0)
    expiry = _utcnow() + timedelta(seconds=max(expiry_seconds, 0))
    creds = load_google_oauth_credentials()
    scopes = token_payload.get("scope") or " ".join(GOOGLE_GMAIL_SCOPES)

    values = {
        "access_token": token_payload.get("access_token", ""),
        "refresh_token": token_payload.get("refresh_token"),
        "token_uri": token_payload.get("token_uri", GOOGLE_TOKEN_URI),
        "client_id": token_payload.get("client_id") or creds.get("client_id", ""),
        "client_secret": encrypt_secret(token_payload.get("client_secret") or creds.get("client_secret", "")),
        "scopes": scopes,
        "expiry": expiry,
    }

    if token_row is None:
        token_row = UserMcpToken(user_id=user_key, **values)
        db.add(token_row)
    else:
        for field, value in values.items():
            setattr(token_row, field, value)

    db.commit()
    db.refresh(token_row)
    return token_row


def get_user_mcp_token(db, user_id: int | str) -> Optional[UserMcpToken]:
    row = db.query(UserMcpToken).filter(UserMcpToken.user_id == str(user_id)).one_or_none()
    if row and row.client_secret:
        try:
            row.client_secret = decrypt_secret(row.client_secret)
        except Exception:
            pass
    return row


def get_active_user_mcp_token(db, user_id: int | str, refresh_threshold_seconds: int = 60) -> Optional[UserMcpToken]:
    """Return a UserMcpToken ensuring the access token is valid. Refreshes if near expiry."""
    try:
        token_row = get_user_mcp_token(db, user_id)
    except Exception:
        return None
    if not token_row:
        return None

    # If token is expired or about to expire, try to refresh
    now = datetime.now(timezone.utc)
    if token_row.expiry <= now + timedelta(seconds=refresh_threshold_seconds):
        if not token_row.refresh_token:
            return None
        try:
            refreshed = refresh_google_access_token(
                token_row.refresh_token, token_row.client_id, token_row.client_secret
            )
        except Exception:
            return None

        # Merge refreshed payload and persist
        merged = {**refreshed}
        if "client_id" not in merged:
            merged["client_id"] = token_row.client_id
        if "client_secret" not in merged:
            merged["client_secret"] = token_row.client_secret
        merged["refresh_token"] = merged.get("refresh_token") or token_row.refresh_token
        try:
            upsert_user_mcp_token(db, user_id, merged)
            token_row = get_user_mcp_token(db, user_id)
        except Exception:
            return None

    return token_row


def build_gmail_mcp_env(token_row: UserMcpToken) -> Dict[str, str]:
    """Build env vars to inject into the Gmail MCP subprocess for a user."""
    return {
        "GOOGLE_OAUTH_USER_ID": str(token_row.user_id),
        "GMAIL_MCP_ACCESS_TOKEN": token_row.access_token or "",
        "GMAIL_MCP_REFRESH_TOKEN": token_row.refresh_token or "",
        "GMAIL_MCP_TOKEN_URI": token_row.token_uri or GOOGLE_TOKEN_URI,
        "GMAIL_MCP_CLIENT_ID": token_row.client_id or "",
        "GMAIL_MCP_CLIENT_SECRET": token_row.client_secret or "",
        "GMAIL_MCP_SCOPES": token_row.scopes or "",
    }
