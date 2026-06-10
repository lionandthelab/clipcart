"""promo 엔진 오케스트레이션: 제품 → marketing_promo 쇼츠 + 썸네일 + 메타데이터."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from clipcart.config import OUTBOX_DIR
from clipcart.video.copywriter import build_creative
from clipcart.video.frames import compose_thumbnail, fetch_image
from clipcart.video.profile import load_profile
from clipcart.video.promo.beats import beats_to_scenes, build_beats
from clipcart.video.promo.editor import render_promo


def make_promo_video(product: dict[str, Any], keep_workdir: bool = False) -> dict[str, Any]:
    pid = product["product_id"]
    publish_dir = OUTBOX_DIR / "publishing"
    publish_dir.mkdir(parents=True, exist_ok=True)
    video_path = publish_dir / f"{pid}.mp4"
    thumb_path = publish_dir / f"{pid}_thumb.jpg"
    product_png = OUTBOX_DIR / "work" / pid / "product.png"
    product_png.parent.mkdir(parents=True, exist_ok=True)

    # 메타데이터(제목/설명/태그/고정댓글/썸네일 문구)는 기존 카피라이터 재사용
    creative = build_creative(product, load_profile())
    beats = build_beats(product)
    # 컴플라이언스는 실제 발화되는 promo 내레이션으로 검사
    creative["scenes"] = beats_to_scenes(beats)

    product_img = fetch_image(product["image_url"])
    product_img.save(product_png, "PNG")

    hook_title = product["niche"]["hook"]
    render_promo(beats, str(product_png), str(video_path), hook_title=hook_title)

    compose_thumbnail(product_img, creative["thumbnail_line1"], creative["thumbnail_line2"], thumb_path)

    return {"video_path": video_path, "thumbnail_path": thumb_path, "creative": creative}
