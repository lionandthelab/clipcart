from __future__ import annotations

import time
from pathlib import Path

import requests

from clipcart.config import PinterestConfig, load_pinterest_config
from clipcart.publishing.base import PlatformPublisher, PublishResult

API = "https://api.pinterest.com/v5"


class PinterestPublisher(PlatformPublisher):
    platform = "pinterest"

    def __init__(self, config: PinterestConfig | None = None) -> None:
        self.config = config or load_pinterest_config()

    def is_configured(self) -> bool:
        return self.config.configured

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.access_token}"}

    def publish(
        self,
        video_path: Path,
        title: str,
        caption: str,
        tags: list[str] | None = None,
        dry_run: bool = False,
        *,
        cover_image_url: str | None = None,
        link: str | None = None,
    ) -> PublishResult:
        if dry_run:
            return PublishResult(
                platform=self.platform,
                success=True,
                post_id="dry_run",
                post_url="https://pinterest.com/pin/dry_run",
                dry_run=True,
            )

        if not self.is_configured():
            return PublishResult(
                platform=self.platform,
                success=False,
                error="Pinterest API 미설정 (.env 참고, clipcart auth pinterest)",
            )

        if not video_path.exists():
            return PublishResult(
                platform=self.platform,
                success=False,
                error=f"영상 파일 없음: {video_path}",
            )

        cover = cover_image_url or self.config.default_cover_url
        if not cover:
            return PublishResult(
                platform=self.platform,
                success=False,
                error=(
                    "Pinterest 비디오 Pin은 cover_image_url이 필요합니다. "
                    ".env에 PINTEREST_COVER_IMAGE_URL 설정 또는 --cover-url 전달"
                ),
            )

        try:
            media_id = self._register_and_upload(video_path)
            pin_id = self._create_pin(media_id, title, caption, cover, link)
            return PublishResult(
                platform=self.platform,
                success=True,
                post_id=pin_id,
                post_url=f"https://www.pinterest.com/pin/{pin_id}/",
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

    def _register_and_upload(self, video_path: Path) -> str:
        reg = requests.post(
            f"{API}/media",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={"media_type": "video"},
            timeout=60,
        )
        reg.raise_for_status()
        reg_data = reg.json()
        media_id = reg_data["media_id"]
        upload_url = reg_data["upload_url"]
        upload_params = reg_data.get("upload_parameters", {})

        with video_path.open("rb") as f:
            files = {"file": (video_path.name, f, "video/mp4")}
            data = {k: str(v) for k, v in upload_params.items()}
            up = requests.post(upload_url, data=data, files=files, timeout=300)
        up.raise_for_status()

        for _ in range(60):
            status_resp = requests.get(
                f"{API}/media/{media_id}",
                headers=self._headers(),
                timeout=30,
            )
            status_resp.raise_for_status()
            status = status_resp.json().get("status")
            if status == "succeeded":
                return media_id
            if status == "failed":
                raise RuntimeError("Pinterest 비디오 업로드 실패")
            time.sleep(5)

        raise TimeoutError("Pinterest 미디어 처리 타임아웃")

    def _create_pin(
        self,
        media_id: str,
        title: str,
        caption: str,
        cover_url: str,
        link: str | None,
    ) -> str:
        body: dict = {
            "title": title[:100],
            "description": caption[:500],
            "board_id": self.config.board_id,
            "media_source": {
                "source_type": "video_id",
                "cover_image_url": cover_url,
                "media_id": media_id,
            },
        }
        if link:
            body["link"] = link

        resp = requests.post(
            f"{API}/pins",
            headers={**self._headers(), "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["id"]
