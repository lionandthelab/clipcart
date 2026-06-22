"""YouTube OAuth — 서비스 계정은 업로드 불가, OAuth 사용자 인증 필요."""

from __future__ import annotations

import json
from pathlib import Path

from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from clipcart.config import PROJECT_ROOT
from clipcart.publishing.youtube import CONSENT_SCOPES, SCOPES

SERVICE_ACCOUNT_NOTE = (
    "YouTube Data API는 서비스 계정 업로드를 지원하지 않습니다. "
    "채널 소유 Google 계정 OAuth가 필요합니다. "
    "같은 GCP 프로젝트에서 OAuth Desktop Client ID를 만든 뒤 브라우저 로그인을 진행합니다."
)


def find_credentials_json(explicit: str | None = None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    env_path = Path(__import__("os").getenv("YOUTUBE_CREDENTIALS_JSON", ""))
    if env_path.is_file():
        return env_path
    for pattern in ("gen-lang-client-*.json", "service-account*.json", "client_secret*.json"):
        matches = sorted(PROJECT_ROOT.glob(pattern))
        if matches:
            return matches[0]
    return None


def read_json_type(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "installed" in data or "web" in data:
        return "oauth_client"
    return str(data.get("type", "unknown"))


def validate_service_account(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "type": "service_account",
        "project_id": data.get("project_id", ""),
        "client_email": data.get("client_email", ""),
        "note": SERVICE_ACCOUNT_NOTE,
    }


def probe_youtube_with_service_account(path: Path) -> dict[str, str]:
    """서비스 계정으로 YouTube 호출 시도 → 실패 메시지 확인용."""
    try:
        creds = service_account.Credentials.from_service_account_file(str(path), scopes=SCOPES)
        yt = build("youtube", "v3", credentials=creds)
        yt.channels().list(part="snippet", mine=True).execute()
        return {"youtube_ok": "true"}
    except Exception as exc:  # noqa: BLE001
        return {"youtube_ok": "false", "error": str(exc)[:300]}


def setup_youtube_oauth(
    client_id: str | None = None,
    client_secret: str | None = None,
    secrets_file: Path | None = None,
    port: int = 8403,
) -> dict[str, str]:
    token_path = PROJECT_ROOT / ".youtube-token.json"

    if secrets_file and secrets_file.is_file():
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), CONSENT_SCOPES)
    elif client_id and client_secret:
        secrets_path = PROJECT_ROOT / ".youtube_client_secret.json"
        secrets_path.write_text(
            json.dumps(
                {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uris": [f"http://localhost:{port}/", "http://localhost"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), CONSENT_SCOPES)
    else:
        raise RuntimeError(
            "YouTube OAuth Client ID/Secret 필요.\n"
            "GCP Console → APIs → Credentials → Create OAuth client ID → Desktop app\n"
            "다운로드한 client_secret_*.json 을 프로젝트 root에 두거나\n"
            "YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET .env 입력"
        )

    creds = flow.run_local_server(port=port, open_browser=True, prompt="consent")
    token_path.write_text(creds.to_json(), encoding="utf-8")

    yt = build("youtube", "v3", credentials=creds)
    channels = yt.channels().list(part="snippet", mine=True).execute()
    items = channels.get("items", [])
    channel_title = items[0]["snippet"]["title"] if items else ""
    channel_id = items[0]["id"] if items else ""

    return {
        "YOUTUBE_CLIENT_ID": client_id or _client_id_from_secrets(secrets_file),
        "YOUTUBE_CLIENT_SECRET": client_secret or _client_secret_from_secrets(secrets_file),
        "YOUTUBE_REFRESH_TOKEN": creds.refresh_token or "",
        "YOUTUBE_TOKEN_PATH": str(token_path),
        "youtube_channel_title": channel_title,
        "youtube_channel_id": channel_id,
    }


def _client_id_from_secrets(path: Path | None) -> str:
    if not path:
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    block = data.get("installed") or data.get("web") or {}
    return block.get("client_id", "")


def _client_secret_from_secrets(path: Path | None) -> str:
    if not path:
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    block = data.get("installed") or data.get("web") or {}
    return block.get("client_secret", "")


def setup_youtube(
    credentials_path: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> dict[str, str]:
    path = find_credentials_json(credentials_path)
    result: dict[str, str] = {}

    if path:
        result["YOUTUBE_CREDENTIALS_JSON"] = str(path.name)
        cred_type = read_json_type(path)

        if cred_type == "service_account":
            result.update(validate_service_account(path))
            result.update(probe_youtube_with_service_account(path))
        elif cred_type == "oauth_client":
            return setup_youtube_oauth(secrets_file=path)

    oauth_secret = next(iter(sorted(PROJECT_ROOT.glob("client_secret*.json"))), None)
    try:
        if oauth_secret and read_json_type(oauth_secret) == "oauth_client":
            return {**result, **setup_youtube_oauth(secrets_file=oauth_secret)}
        return {**result, **setup_youtube_oauth(client_id=client_id, client_secret=client_secret)}
    except RuntimeError as exc:
        result["oauth_required"] = "true"
        result["oauth_error"] = str(exc)
        return result
