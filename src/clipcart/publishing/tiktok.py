from __future__ import annotations

import time
from pathlib import Path

import requests

from clipcart.config import TikTokConfig, load_tiktok_config
from clipcart.publishing.base import PlatformPublisher, PublishResult

TIKTOK_API = "https://open.tiktokapis.com/v2"


class TikTokPublisher(PlatformPublisher):
    platform = "tiktok"

    def __init__(self, config: TikTokConfig | None = None) -> None:
        self.config = config or load_tiktok_config()

    def is_configured(self) -> bool:
        return self.config.configured

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
                post_url="https://tiktok.com/@user/video/dry_run",
                dry_run=True,
            )

        if not self.is_configured():
            return PublishResult(
                platform=self.platform,
                success=False,
                error="TikTok Content Posting API 미설정 (clipcart auth tiktok)",
            )

        if not video_path.exists():
            return PublishResult(
                platform=self.platform,
                success=False,
                error=f"영상 파일 없음: {video_path}",
            )

        try:
            privacy = self.config.privacy_level or "SELF_ONLY"
            video_size = video_path.stat().st_size
            chunk_size = min(10 * 1024 * 1024, video_size)
            total_chunks = max(1, (video_size + chunk_size - 1) // chunk_size)

            init_resp = requests.post(
                f"{TIKTOK_API}/post/publish/video/init/",
                headers={
                    "Authorization": f"Bearer {self.config.access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                json={
                    "post_info": {
                        "title": caption[:2200],
                        "privacy_level": privacy,
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": video_size,
                        "chunk_size": chunk_size,
                        "total_chunk_count": total_chunks,
                    },
                },
                timeout=60,
            )
            init_resp.raise_for_status()
            init_body = init_resp.json()
            if init_body.get("error", {}).get("code") not in (None, "ok"):
                return PublishResult(
                    platform=self.platform,
                    success=False,
                    error=init_body["error"].get("message", str(init_body)),
                )

            init_data = init_body.get("data", {})
            upload_url = init_data.get("upload_url")
            publish_id = init_data.get("publish_id")

            if not upload_url:
                return PublishResult(
                    platform=self.platform,
                    success=False,
                    error="TikTok upload_url 없음 — video.publish 권한·앱 심사 확인",
                )

            with video_path.open("rb") as f:
                video_bytes = f.read()

            upload_resp = requests.put(
                upload_url,
                headers={
                    "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
                    "Content-Length": str(video_size),
                    "Content-Type": "video/mp4",
                },
                data=video_bytes,
                timeout=300,
            )
            upload_resp.raise_for_status()

            status = self._wait_publish_status(publish_id)
            return PublishResult(
                platform=self.platform,
                success=True,
                post_id=publish_id,
                post_url=status.get("share_url") or f"https://www.tiktok.com (publish_id={publish_id})",
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

    def _wait_publish_status(self, publish_id: str) -> dict:
        for _ in range(30):
            resp = requests.post(
                f"{TIKTOK_API}/post/publish/status/fetch/",
                headers={
                    "Authorization": f"Bearer {self.config.access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                json={"publish_id": publish_id},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            status = data.get("status")
            if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
                return data
            if status == "FAILED":
                raise RuntimeError(data.get("fail_reason", "TikTok 게시 실패"))
            time.sleep(5)
        return {}
