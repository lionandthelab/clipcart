"""영상 엔진: 상품 1개 → 쇼츠 mp4 + 썸네일 + 메타데이터."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from clipcart.config import OUTBOX_DIR
from clipcart.video.copywriter import build_creative
from clipcart.video.frames import compose_thumbnail, fetch_image
from clipcart.video.profile import load_profile
from clipcart.video.render import render_video


def make_video(product: dict[str, Any], keep_workdir: bool = False) -> dict[str, Any]:
    profile = load_profile()
    creative = build_creative(product, profile)

    pid = product["product_id"]
    publish_dir = OUTBOX_DIR / "publishing"
    workdir = OUTBOX_DIR / "work" / pid
    video_path = publish_dir / f"{pid}.mp4"
    thumb_path = publish_dir / f"{pid}_thumb.jpg"

    product_img = fetch_image(product["image_url"])

    render_video(
        product_img,
        creative["scenes"],
        workdir,
        video_path,
        voice=creative["tts_voice"],
        rate=creative["tts_rate"],
    )
    compose_thumbnail(
        product_img,
        creative["thumbnail_line1"],
        creative["thumbnail_line2"],
        thumb_path,
    )

    if not keep_workdir:
        shutil.rmtree(workdir, ignore_errors=True)

    return {
        "video_path": video_path,
        "thumbnail_path": thumb_path,
        "creative": creative,
    }
