from __future__ import annotations

import base64
import urllib.parse

import requests

from clipcart.auth.common import collect_oauth, resolve_redirect_uri

API = "https://api.pinterest.com/v5"
SCOPES = ["boards:read", "pins:read", "pins:write", "user_accounts:read"]


def build_auth_url(app_id: str, redirect_uri: str) -> str:
    params = urllib.parse.urlencode(
        {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": ",".join(SCOPES),
        }
    )
    return f"https://www.pinterest.com/oauth/?{params}"


def exchange_code(app_id: str, app_secret: str, code: str, redirect_uri: str) -> dict[str, str]:
    creds = base64.b64encode(f"{app_id}:{app_secret}".encode()).decode()
    resp = requests.post(
        f"{API}/oauth/token",
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "PINTEREST_ACCESS_TOKEN": data["access_token"],
        "PINTEREST_REFRESH_TOKEN": data.get("refresh_token", ""),
    }


def list_boards(access_token: str) -> list[dict]:
    resp = requests.get(
        f"{API}/boards",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"page_size": 25},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def setup_pinterest_oauth(app_id: str, app_secret: str, port: int = 8402) -> dict[str, str]:
    redirect_uri = resolve_redirect_uri(port)
    auth_url = build_auth_url(app_id, redirect_uri)
    params = collect_oauth(auth_url, redirect_uri, port=port, label="Pinterest")
    code = params.get("code")
    if not code:
        raise RuntimeError("authorization code 없음")

    tokens = exchange_code(app_id, app_secret, code, redirect_uri)
    boards = list_boards(tokens["PINTEREST_ACCESS_TOKEN"])
    result = {
        "PINTEREST_APP_ID": app_id,
        "PINTEREST_APP_SECRET": app_secret,
        **tokens,
    }
    if boards:
        result["PINTEREST_BOARD_ID"] = boards[0]["id"]
        result["pinterest_board_name"] = boards[0].get("name", "")
    return result
