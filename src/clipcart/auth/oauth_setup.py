"""OAuth 토큰 발급 헬퍼."""

from __future__ import annotations

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from clipcart.config import PROJECT_ROOT
from clipcart.publishing.youtube import SCOPES

CLIENT_SECRETS_TEMPLATE = {
    "installed": {
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "redirect_uris": ["http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


def setup_youtube_oauth(client_id: str, client_secret: str) -> str:
    secrets_path = PROJECT_ROOT / ".youtube_client_secret.json"
    secrets = CLIENT_SECRETS_TEMPLATE.copy()
    secrets["installed"]["client_id"] = client_id
    secrets["installed"]["client_secret"] = client_secret
    secrets_path.write_text(json.dumps(secrets, indent=2), encoding="utf-8")

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    creds = flow.run_local_server(port=0)
    return creds.refresh_token or ""
