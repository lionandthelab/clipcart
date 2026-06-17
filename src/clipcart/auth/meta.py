"""Instagram API with Instagram Login (2024+).

구 방식(Facebook Login + Page 연결, scope=instagram_basic/instagram_content_publish)은
Meta 가 2025-01-27 자로 폐기했다. 현재는 Instagram 전용 앱 자격증명으로 인스타에 직접
로그인하고 graph.instagram.com 으로 게시한다. 페이스북 페이지 연결이 필요 없다.

자격증명: App Dashboard > Instagram > API setup with Instagram business login >
Business login settings 의 **Instagram App ID / Instagram App Secret**(= META_APP_ID/SECRET
과 별개). 같은 화면의 OAuth redirect URIs 에 콜백을 등록한다.
"""

from __future__ import annotations

import urllib.parse

import requests

from clipcart.auth.common import collect_oauth, resolve_redirect_uri

AUTH_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH = "https://graph.instagram.com"
SCOPES = [
    "instagram_business_basic",
    "instagram_business_content_publish",
]


def build_auth_url(app_id: str, redirect_uri: str) -> str:
    params = urllib.parse.urlencode(
        {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": ",".join(SCOPES),
        }
    )
    return f"{AUTH_URL}?{params}"


def exchange_code(app_id: str, app_secret: str, code: str, redirect_uri: str) -> dict:
    """authorization code → 단기 토큰. 응답에 access_token, user_id 포함."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def to_long_lived_token(app_secret: str, short_token: str) -> str:
    """단기 토큰 → 60일 장기 토큰(graph.instagram.com)."""
    resp = requests.get(
        f"{GRAPH}/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_account(access_token: str) -> tuple[str, str]:
    """(user_id, username) — 게시에 쓸 IG 비즈니스 계정 ID 와 핸들."""
    resp = requests.get(
        f"{GRAPH}/me",
        params={"fields": "user_id,username", "access_token": access_token},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return str(data.get("user_id", "")), data.get("username", "")


def setup_instagram_oauth(app_id: str, app_secret: str, port: int = 8400) -> dict[str, str]:
    redirect_uri = resolve_redirect_uri(port)
    auth_url = build_auth_url(app_id, redirect_uri)
    params = collect_oauth(auth_url, redirect_uri, port=port, label="Instagram")
    code = params.get("code")
    if not code:
        raise RuntimeError("authorization code 없음")
    code = code.split("#")[0]  # Instagram 은 code 끝에 '#_' 를 붙이기도 함

    short = exchange_code(app_id, app_secret, code, redirect_uri)
    short_token = short.get("access_token")
    if not short_token:
        raise RuntimeError(f"토큰 교환 실패: {short}")
    user_id = str(short.get("user_id", ""))
    token = to_long_lived_token(app_secret, short_token)

    me_id, username = fetch_account(token)
    return {
        "INSTAGRAM_APP_ID": app_id,
        "INSTAGRAM_APP_SECRET": app_secret,
        "INSTAGRAM_ACCESS_TOKEN": token,
        "INSTAGRAM_BUSINESS_ACCOUNT_ID": me_id or user_id,
        "instagram_page": username,  # CLI 표시용(자동 .env 저장 제외)
    }
