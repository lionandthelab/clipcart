from __future__ import annotations

import os
import secrets
import urllib.parse
import webbrowser

import requests

from clipcart.auth.common import run_oauth_callback

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
SCOPES = ["user.info.basic", "video.upload", "video.publish"]

# TikTok 은 redirect_uri 로 localhost 를 허용하지 않는다(https 필수). 그래서 기본값은
# 공개 정적 콜백 페이지(GitHub Pages)이고, 인증 후 그 페이지에 표시되는 code 를
# 사용자가 터미널에 붙여넣는 수동 플로우를 쓴다. env 로 교체 가능(자체 도메인 등).
DEFAULT_REDIRECT_URI = "https://lionandthelab.github.io/clipcart/callback/"


def _redirect_uri() -> str:
    return (os.getenv("TIKTOK_REDIRECT_URI", "") or "").strip() or DEFAULT_REDIRECT_URI


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


def _parse_pasted(pasted: str) -> dict[str, str]:
    """사용자가 붙여넣은 값(전체 리다이렉트 URL 또는 code 단독)에서 code/state 추출."""
    pasted = pasted.strip()
    if "code=" in pasted or "?" in pasted:
        query = urllib.parse.urlparse(pasted).query or pasted.split("?", 1)[-1]
        parsed = dict(urllib.parse.parse_qsl(query))
        if parsed.get("code"):
            return parsed
    return {"code": pasted}  # code 단독 붙여넣기


def _manual_paste_flow(auth_url: str, redirect_uri: str) -> dict[str, str]:
    """공개 HTTPS 콜백 페이지로 인증 → 표시된 code 를 붙여넣는 수동 플로우."""
    print("\n[TikTok 인증]")
    print("1) 아래 URL 을 브라우저에서 열고 승인하세요(자동으로도 열림):\n")
    print(auth_url + "\n")
    print(f"2) 승인 후 '{redirect_uri}' 페이지로 이동하면 거기 표시된 code(또는 전체 URL)를 복사하세요.\n")
    try:
        webbrowser.open(auth_url)
    except Exception:  # noqa: BLE001
        pass
    pasted = input("3) code 또는 전체 리다이렉트 URL 붙여넣기: ").strip()
    if not pasted:
        raise RuntimeError("입력이 비어 있음")
    return _parse_pasted(pasted)


def setup_tiktok_oauth(client_key: str, client_secret: str, port: int = 8401) -> dict[str, str]:
    redirect_uri = _redirect_uri()
    state = secrets.token_urlsafe(16)
    auth_url = build_auth_url(client_key, redirect_uri, state)

    if redirect_uri.startswith("http://localhost") or redirect_uri.startswith("http://127.0.0.1"):
        params = run_oauth_callback(auth_url, port=port)  # 로컬 loopback(레거시/허용 시)
    else:
        params = _manual_paste_flow(auth_url, redirect_uri)  # 공개 HTTPS 콜백 + 붙여넣기

    if params.get("state") and params["state"] != state:
        raise RuntimeError("OAuth state 불일치")
    code = params.get("code")
    if not code:
        raise RuntimeError("authorization code 없음")

    result = exchange_code(client_key, client_secret, code, redirect_uri)
    result["TIKTOK_CLIENT_KEY"] = client_key
    result["TIKTOK_CLIENT_SECRET"] = client_secret
    return result
