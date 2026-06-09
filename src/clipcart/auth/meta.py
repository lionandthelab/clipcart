from __future__ import annotations

import urllib.parse

import requests

from clipcart.auth.common import run_oauth_callback

GRAPH = "https://graph.facebook.com/v21.0"
SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "pages_read_engagement",
]


def build_auth_url(app_id: str, redirect_uri: str) -> str:
    params = urllib.parse.urlencode(
        {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "scope": ",".join(SCOPES),
            "response_type": "code",
        }
    )
    return f"https://www.facebook.com/v21.0/dialog/oauth?{params}"


def exchange_code(app_id: str, app_secret: str, code: str, redirect_uri: str) -> str:
    resp = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "client_id": app_id,
            "client_secret": app_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def to_long_lived_token(app_id: str, app_secret: str, short_token: str) -> str:
    resp = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def discover_instagram_account(access_token: str) -> tuple[str, str]:
    pages = requests.get(
        f"{GRAPH}/me/accounts",
        params={"access_token": access_token},
        timeout=30,
    )
    pages.raise_for_status()
    data = pages.json().get("data", [])
    for page in data:
        page_id = page["id"]
        detail = requests.get(
            f"{GRAPH}/{page_id}",
            params={
                "fields": "instagram_business_account,name",
                "access_token": access_token,
            },
            timeout=30,
        )
        detail.raise_for_status()
        ig = detail.json().get("instagram_business_account")
        if ig:
            return str(ig["id"]), page.get("name", "")
    raise RuntimeError(
        "Instagram Business/Creator 계정을 찾지 못했습니다. "
        "Facebook 페이지와 IG 프로페셔널 계정 연결을 확인하세요."
    )


def setup_instagram_oauth(app_id: str, app_secret: str, port: int = 8400) -> dict[str, str]:
    redirect_uri = f"http://localhost:{port}/callback"
    params = run_oauth_callback(build_auth_url(app_id, redirect_uri), port=port)
    code = params.get("code")
    if not code:
        raise RuntimeError("authorization code 없음")

    short = exchange_code(app_id, app_secret, code, redirect_uri)
    token = to_long_lived_token(app_id, app_secret, short)
    ig_id, page_name = discover_instagram_account(token)
    return {
        "META_APP_ID": app_id,
        "META_APP_SECRET": app_secret,
        "META_ACCESS_TOKEN": token,
        "INSTAGRAM_BUSINESS_ACCOUNT_ID": ig_id,
        "instagram_page": page_name,
    }
