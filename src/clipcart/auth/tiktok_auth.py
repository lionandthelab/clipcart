from __future__ import annotations

import secrets
import urllib.parse

import requests

from clipcart.auth.common import run_oauth_callback

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
SCOPES = ["user.info.basic", "video.upload", "video.publish"]


def build_auth_url(client_key: str, redirect_uri: str, state: str) -> str:
    params = urllib.parse.urlencode(
        {
            "client_key": client_key,
            "scope": ",".join(SCOPES),
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"https://www.tiktok.com/v2/auth/authorize/?{params}"


def exchange_code(
    client_key: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, str]:
    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(data.get("error_description") or data.get("message") or str(data))
    return {
        "TIKTOK_ACCESS_TOKEN": data["access_token"],
        "TIKTOK_REFRESH_TOKEN": data.get("refresh_token", ""),
        "open_id": data.get("open_id", ""),
    }


def setup_tiktok_oauth(client_key: str, client_secret: str, port: int = 8401) -> dict[str, str]:
    redirect_uri = f"http://localhost:{port}/callback"
    state = secrets.token_urlsafe(16)
    params = run_oauth_callback(
        build_auth_url(client_key, redirect_uri, state),
        port=port,
    )
    if params.get("state") != state:
        raise RuntimeError("OAuth state 불일치")
    code = params.get("code")
    if not code:
        raise RuntimeError("authorization code 없음")

    result = exchange_code(client_key, client_secret, code, redirect_uri)
    result["TIKTOK_CLIENT_KEY"] = client_key
    result["TIKTOK_CLIENT_SECRET"] = client_secret
    return result
