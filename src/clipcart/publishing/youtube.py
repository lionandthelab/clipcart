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

    def _build_credentials(self) -> Credentials:
        if self.config.token_file.is_file():
            creds = Credentials.from_authorized_user_file(str(self.config.token_file), SCOPES)
        else:
            creds = Credentials(
                token=None,
                refresh_token=self.config.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                scopes=SCOPES,
            )
        if creds.expired or not creds.valid:
            creds.refresh(Request())
            if self.config.token_file.is_file():
                self.config.token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def verify(self) -> dict:
        if not self.is_configured():
            return {"ok": False, "error": "YouTube 미설정 (.youtube-token.json 또는 .env)"}
        try:
            yt = build("youtube", "v3", credentials=self._build_credentials())
            resp = yt.channels().list(part="snippet", mine=True).execute()
            items = resp.get("items", [])
            if not items:
                return {"ok": False, "error": "연결된 YouTube 채널 없음"}
            ch = items[0]
            return {
                "ok": True,
                "channel_id": ch["id"],
                "channel_title": ch["snippet"]["title"],
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:300]}

    def set_thumbnail(self, video_id: str, thumbnail_path: Path) -> bool:
        """커스텀 썸네일 업로드 (채널 미인증 등으로 실패해도 게시는 유지)."""
        try:
            youtube = build("youtube", "v3", credentials=self._build_credentials())
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
            ).execute()
            return True
        except Exception:  # noqa: BLE001
            return False

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
                error="YouTube OAuth 미설정 (clipcart auth youtube)",
            )

        if not video_path.exists():
            return PublishResult(
                platform=self.platform,
                success=False,
                error=f"영상 파일 없음: {video_path}",
            )

        try:
            youtube = build("youtube", "v3", credentials=self._build_credentials())
            body = {
                "snippet": {
                    "title": title[:100],
                    "description": caption[:5000],
                    "tags": tags or [],
                    "categoryId": "26",  # Howto & Style — 생활용품 리뷰에 적합
                },
                "status": {
                    "privacyStatus": self.config.privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }
            media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    pass  # upload progress

            video_id = response["id"]
            return PublishResult(
                platform=self.platform,
                success=True,
                post_id=video_id,
                post_url=f"https://www.youtube.com/shorts/{video_id}",
            )
        except Exception as exc:  # noqa: BLE001
            return PublishResult(
                platform=self.platform,
                success=False,
                error=str(exc),
            )
