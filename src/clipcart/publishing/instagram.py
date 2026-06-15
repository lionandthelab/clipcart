from __future__ import annotations

import time
from pathlib import Path

import requests

from clipcart.config import InstagramConfig, load_instagram_config
from clipcart.publishing.base import PlatformPublisher, PublishResult

GRAPH_BASE = "https://graph.facebook.com/v21.0"


class InstagramPublisher(PlatformPublisher):
    platform = "instagram_reels"

    def __init__(self, config: InstagramConfig | None = None) -> None:
        self.config = config or load_instagram_config()

    def is_configured(self) -> bool:
        return self.config.configured

    def verify(self) -> dict:
        if not self.is_configured():
            return {"ok": False, "error": "미설정"}
        resp = requests.get(
            f"{GRAPH_BASE}/{self.config.business_account_id}",
            params={
                "fields": "username,name,profile_picture_url",
                "access_token": self.config.access_token,
            },
            timeout=30,
        )
        if resp.ok:
            data = resp.json()
            return {"ok": True, "username": data.get("username"), "name": data.get("name")}
        return {"ok": False, "error": resp.text[:300]}

    def publish(
        self,
        video_path: Path,
        title: str,
        caption: str,
        tags: list[str] | None = None,
        dry_run: bool = False,
        *,
        video_url: str | None = None,
    ) -> PublishResult:
        if dry_run:
            return PublishResult(
                platform=self.platform,
                success=True,
                post_id="dry_run",
                post_url="https://instagram.com/reel/dry_run",
                dry_run=True,
            )

        if not self.is_configured():
            return PublishResult(
                platform=self.platform,
                success=False,
                error="Instagram/Meta API 미설정 (clipcart auth instagram)",
            )

        # 공개 video_url 자동 확보: 미지정 시 S3 호환 스토리지(R2 등)에 자동 업로드
        if not video_url:
            from clipcart.publishing import media_host

            video_url = media_host.host_video(video_path)

        if video_url:
            return self.publish_reel(video_url, caption, dry_run=False)

        return PublishResult(
            platform=self.platform,
            success=False,
            error=(
                "Instagram Reels API는 공개 video_url이 필요합니다. "
                "CLIPCART_S3_*(R2 등) 설정 시 자동 업로드되며, 아니면 "
                "clipcart publish --video-url URL 로 직접 지정하세요."
            ),
        )

    def publish_reel(self, video_url: str, caption: str, dry_run: bool = False) -> PublishResult:
        if dry_run:
            return PublishResult(
                platform=self.platform,
                success=True,
                post_id="dry_run",
                post_url="https://instagram.com/reel/dry_run",
                dry_run=True,
            )

        if not self.is_configured():
            return PublishResult(
                platform=self.platform,
                success=False,
                error="Instagram/Meta API 미설정",
            )

        ig_id = self.config.business_account_id
        token = self.config.access_token

        try:
            create_resp = requests.post(
                f"{GRAPH_BASE}/{ig_id}/media",
                data={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": caption,
                    "access_token": token,
                },
                timeout=60,
            )
            create_resp.raise_for_status()
            creation_id = create_resp.json()["id"]

            for _ in range(36):
                status_resp = requests.get(
                    f"{GRAPH_BASE}/{creation_id}",
                    params={"fields": "status_code", "access_token": token},
                    timeout=30,
                )
                status_resp.raise_for_status()
                status = status_resp.json().get("status_code")
                if status == "FINISHED":
                    break
                if status == "ERROR":
                    return PublishResult(
                        platform=self.platform,
                        success=False,
                        error="Instagram 미디어 처리 실패",
                    )
                time.sleep(5)

            publish_resp = requests.post(
                f"{GRAPH_BASE}/{ig_id}/media_publish",
                data={"creation_id": creation_id, "access_token": token},
                timeout=60,
            )
            publish_resp.raise_for_status()
            media_id = publish_resp.json()["id"]

            return PublishResult(
                platform=self.platform,
                success=True,
                post_id=media_id,
                post_url=f"https://www.instagram.com/reel/{media_id}/",
            )
        except requests.RequestException as exc:
            body = ""
            if exc.response is not None:
                body = exc.response.text[:500]
            return PublishResult(
                platform=self.platform,
                success=False,
                error=f"{exc} {body}".strip(),
            )
