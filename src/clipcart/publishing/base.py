from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PublishResult:
    platform: str
    success: bool
    post_id: str | None = None
    post_url: str | None = None
    error: str | None = None
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "success": self.success,
            "post_id": self.post_id,
            "post_url": self.post_url,
            "error": self.error,
            "dry_run": self.dry_run,
        }


class PlatformPublisher:
    platform: str

    def is_configured(self) -> bool:
        raise NotImplementedError

    def publish(
        self,
        video_path: Path,
        title: str,
        caption: str,
        tags: list[str] | None = None,
        dry_run: bool = False,
    ) -> PublishResult:
        raise NotImplementedError
