"""영상 엔진: 상품 1개 → 쇼츠 mp4 + 썸네일 + 메타데이터.

CLIPCART_ENGINE=promo (기본) → steward-lab 기반 marketing_promo 엔진
(Pexels/Gemini 실영상 + Typecast 한국어 내레이션 + 3단 레이아웃).
CLIPCART_ENGINE=kinetic → 경량 Pillow 카라오케 엔진(폴백).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from clipcart.config import OUTBOX_DIR
from clipcart.video.copywriter import build_creative
from clipcart.video.frames import compose_thumbnail, fetch_image
from clipcart.video.profile import load_profile
from clipcart.video.render import render_video


def make_video(product: dict[str, Any], keep_workdir: bool = False) -> dict[str, Any]:
    if os.getenv("CLIPCART_ENGINE", "promo").lower() == "promo":
        from clipcart.video.promo.engine import make_promo_video

        try:
            return make_promo_video(product, keep_workdir=keep_workdir)
        except Exception as exc:  # noqa: BLE001
            # promo 엔진 실패(네트워크/키/moviepy) 시 경량 kinetic 엔진으로 폴백 — 데일리 무중단
            print(f"[engine] promo 실패, kinetic 폴백: {str(exc)[:160]}")

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
