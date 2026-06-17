from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("CLIPCART_DATA_DIR", PROJECT_ROOT / "data"))
INBOX_DIR = Path(os.getenv("CLIPCART_INBOX_DIR", PROJECT_ROOT / "inbox" / "videos"))
OUTBOX_DIR = PROJECT_ROOT / "outbox"
LOGS_DIR = PROJECT_ROOT / "logs"
YOUTUBE_TOKEN_FILE = PROJECT_ROOT / ".youtube-token.json"

DEFAULT_DISCLOSURE = os.getenv(
    "AFFILIATE_DEFAULT_DISCLOSURE",
    "이 콘텐츠에는 affiliate 링크가 포함되어 있으며, 구매 시 일정 수수료를 받을 수 있습니다.",
)


@dataclass(frozen=True)
class InstagramConfig:
    app_id: str
    app_secret: str
    access_token: str
    business_account_id: str

    @property
    def configured(self) -> bool:
        return bool(self.access_token and self.business_account_id)


@dataclass(frozen=True)
class TikTokConfig:
    client_key: str
    client_secret: str
    access_token: str
    privacy_level: str

    @property
    def configured(self) -> bool:
        return bool(self.access_token)


@dataclass(frozen=True)
class PinterestConfig:
    app_id: str
    app_secret: str
    access_token: str
    board_id: str
    default_cover_url: str

    @property
    def configured(self) -> bool:
        return bool(self.access_token and self.board_id)


@dataclass(frozen=True)
class YouTubeConfig:
    client_id: str
    client_secret: str
    refresh_token: str
    token_file: Path
    privacy_status: str

    @property
    def configured(self) -> bool:
        if self.token_file.is_file():
            return True
        return bool(self.refresh_token and self.client_id and self.client_secret)


def _youtube_from_token_file() -> dict[str, str]:
    if not YOUTUBE_TOKEN_FILE.is_file():
        return {}
    data = json.loads(YOUTUBE_TOKEN_FILE.read_text(encoding="utf-8"))
    return {
        "client_id": data.get("client_id", ""),
        "client_secret": data.get("client_secret", ""),
        "refresh_token": data.get("refresh_token", ""),
    }


def load_youtube_config() -> YouTubeConfig:
    from_file = _youtube_from_token_file()
    token_path = os.getenv("YOUTUBE_TOKEN_PATH", "")
    token_file = Path(token_path) if token_path else YOUTUBE_TOKEN_FILE
    return YouTubeConfig(
        client_id=os.getenv("YOUTUBE_CLIENT_ID", "") or from_file.get("client_id", ""),
        client_secret=os.getenv("YOUTUBE_CLIENT_SECRET", "") or from_file.get("client_secret", ""),
        refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN", "") or from_file.get("refresh_token", ""),
        token_file=token_file,
        privacy_status=os.getenv("YOUTUBE_PRIVACY_STATUS", "unlisted"),
    )


def load_instagram_config() -> InstagramConfig:
    # Instagram 로그인 전용 자격증명(INSTAGRAM_*) 우선, 레거시 META_* 는 폴백.
    return InstagramConfig(
        app_id=os.getenv("INSTAGRAM_APP_ID", "") or os.getenv("META_APP_ID", ""),
        app_secret=os.getenv("INSTAGRAM_APP_SECRET", "") or os.getenv("META_APP_SECRET", ""),
        access_token=os.getenv("INSTAGRAM_ACCESS_TOKEN", "") or os.getenv("META_ACCESS_TOKEN", ""),
        business_account_id=os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", ""),
    )


def load_tiktok_config() -> TikTokConfig:
    return TikTokConfig(
        client_key=os.getenv("TIKTOK_CLIENT_KEY", ""),
        client_secret=os.getenv("TIKTOK_CLIENT_SECRET", ""),
        access_token=os.getenv("TIKTOK_ACCESS_TOKEN", ""),
        privacy_level=os.getenv("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY"),
    )


def load_pinterest_config() -> PinterestConfig:
    return PinterestConfig(
        app_id=os.getenv("PINTEREST_APP_ID", ""),
        app_secret=os.getenv("PINTEREST_APP_SECRET", ""),
        access_token=os.getenv("PINTEREST_ACCESS_TOKEN", ""),
        board_id=os.getenv("PINTEREST_BOARD_ID", ""),
        default_cover_url=os.getenv("PINTEREST_COVER_IMAGE_URL", ""),
    )
