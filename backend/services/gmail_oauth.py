"""Google OAuth helpers for Gmail inbox access."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")
GMAIL_OAUTH_STATE_SECRET = os.getenv("GMAIL_OAUTH_STATE_SECRET", os.getenv("SUPABASE_SERVICE_ROLE_KEY", "dev-secret"))
GMAIL_OAUTH_SCOPES = os.getenv(
    "GMAIL_OAUTH_SCOPES",
    "openid email profile https://www.googleapis.com/auth/gmail.readonly",
)
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def require_google_config() -> None:
    missing = [name for name, value in {
        "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
        "GOOGLE_REDIRECT_URI": GOOGLE_REDIRECT_URI,
    }.items() if not value]
    if missing:
        raise RuntimeError(f"Missing Google OAuth config: {', '.join(missing)}")


def _sign(value: str) -> str:
    return hmac.new(GMAIL_OAUTH_STATE_SECRET.encode('utf-8'), value.encode('utf-8'), hashlib.sha256).hexdigest()


def build_state(owner_email: str) -> str:
    payload = json.dumps({"owner_email": owner_email, "ts": int(time.time())}, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(payload.encode('utf-8')).decode('ascii').rstrip('=')
    return f"{encoded}.{_sign(encoded)}"


def verify_state(state: str) -> dict[str, Any]:
    try:
        encoded, signature = state.split('.', 1)
    except ValueError as exc:
        raise ValueError("Invalid OAuth state") from exc

    expected = _sign(encoded)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("OAuth state mismatch")

    padding = '=' * (-len(encoded) % 4)
    payload = base64.urlsafe_b64decode((encoded + padding).encode('ascii')).decode('utf-8')
    data = json.loads(payload)
    if not isinstance(data, dict) or not data.get('owner_email'):
        raise ValueError("OAuth state missing owner_email")
    return data


def build_authorize_url(owner_email: str) -> str:
    require_google_config()
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GMAIL_OAUTH_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": build_state(owner_email),
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def _post_form_json(url: str, form: dict[str, str]) -> dict[str, Any]:
    payload = urlencode(form).encode('utf-8')
    request = Request(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    require_google_config()
    token_data = _post_form_json(GOOGLE_TOKEN_URL, {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    })

    access_token = token_data.get("access_token")
    if access_token:
        request = Request(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        with urlopen(request, timeout=30) as response:
            userinfo = json.loads(response.read().decode('utf-8'))
        token_data["email"] = userinfo.get("email")
        token_data["name"] = userinfo.get("name")

    return token_data
