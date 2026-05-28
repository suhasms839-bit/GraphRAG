import json
import os
from typing import Dict, Optional

from .mcp_client import get_mcp_client
from ..core.config import settings


def load_google_oauth_credentials() -> Dict[str, str]:
    """Load Google OAuth2 client id/secret either from env vars or from
    a downloaded client_secret_*.json file.

    Returns a dict with keys: client_id, client_secret, redirect_uris (list)
    """
    # Priority 1: explicit env vars
    if settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET:
        return {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI],
        }

    # Priority 2: JSON file
    path = settings.GOOGLE_OAUTH_CREDENTIALS_PATH
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # file format could be {"installed": {...}} or {"web": {...}}
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
