from __future__ import annotations

import os
import secrets
import urllib.parse

import requests

from clipcart.auth.common import collect_oauth

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
SCOPES = ["user.info.basic", "video.upload", "video.publish"]

# TikTok 은 redirect_uri 로 localhost 를 허용하지 않는다(https 필수). 그래서 기본값은
# 공개 정적 콜백 페이지(GitHub Pages)이고, 인증 후 그 페이지에 표시되는 code 를
# 사용자가 터미널에 붙여넣는 수동 플로우를 쓴다. 자체 도메인은 CLIPCART_OAUTH_REDIRECT
# (Meta/Pinterest 공용) 또는 TIKTOK_REDIRECT_URI 로 교체.
DEFAULT_REDIRECT_URI = "https://lionandthelab.github.io/clipcart/callback/"


def _redirect_uri() -> str:
    return (
        (os.getenv("TIKTOK_REDIRECT_URI", "") or "").strip()
        or (os.getenv("CLIPCART_OAUTH_REDIRECT", "") or "").strip()
        or DEFAULT_REDIRECT_URI
    )


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
    redirect_uri = _redirect_uri()
    state = secrets.token_urlsafe(16)
    auth_url = build_auth_url(client_key, redirect_uri, state)

    params = collect_oauth(auth_url, redirect_uri, port=port, label="TikTok")

    if params.get("state") and params["state"] != state:
        raise RuntimeError("OAuth state 불일치")
    code = params.get("code")
    if not code:
        raise RuntimeError("authorization code 없음")

    result = exchange_code(client_key, client_secret, code, redirect_uri)
    result["TIKTOK_CLIENT_KEY"] = client_key
    result["TIKTOK_CLIENT_SECRET"] = client_secret
    return result
