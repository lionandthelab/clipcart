from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from clipcart.config import YouTubeConfig, load_youtube_config
from clipcart.publishing.base import PlatformPublisher, PublishResult

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubePublisher(PlatformPublisher):
    platform = "youtube_shorts"

    def __init__(self, config: YouTubeConfig | None = None) -> None:
        self.config = config or load_youtube_config()

    def is_configured(self) -> bool:
        return self.config.configured

    def _build_service(self):
        creds = Credentials(
            token=None,
            refresh_token=self.config.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return build("youtube", "v3", credentials=creds)

    def publish(
        self,
        video_path: Path,
        title: str,
        caption: str,
        tags: list[str] | None = None,
        dry_run: bool = False,
    ) -> PublishResult:
        if dry_run:
            return PublishResult(
                platform=self.platform,
                success=True,
                post_id="dry_run",
                post_url="https://youtube.com/shorts/dry_run",
                dry_run=True,
            )

        if not self.is_configured():
            return PublishResult(
                platform=self.platform,
                success=False,
                error="YouTube OAuth 미설정 (.env 참고, clipcart auth youtube)",
            )

        if not video_path.exists():
            return PublishResult(
                platform=self.platform,
                success=False,
                error=f"영상 파일 없음: {video_path}",
            )

        try:
            youtube = self._build_service()
            body = {
                "snippet": {
                    "title": title[:100],
                    "description": caption[:5000],
                    "tags": tags or [],
                    "categoryId": "22",
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
            }
            media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

            response = None
            while response is None:
                _, response = request.next_chunk()

            video_id = response["id"]
            return PublishResult(
                platform=self.platform,
                success=True,
                post_id=video_id,
                post_url=f"https://www.youtube.com/shorts/{video_id}",
            )
        except Exception as exc:  # noqa: BLE001 — API 오류 메시지 전달
            return PublishResult(
                platform=self.platform,
                success=False,
                error=str(exc),
            )
