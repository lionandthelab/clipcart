"""promo 엔진 오케스트레이션: 제품 → marketing_promo 쇼츠 + 썸네일 + 메타데이터."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from clipcart.config import OUTBOX_DIR
from clipcart.disclosure import AD_BADGE
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

    # 실데이터 리뷰 요약 카드(평점/주문수) — 있으면 CTA 장면에 캡처풍으로 노출
    from clipcart.video.promo.review_card import compose_review_card

    card = compose_review_card(product, product_png.parent / "review_card.png")
    if card:
        product = {**product, "review_card_path": str(card)}

    # 메타데이터(제목/설명/태그/고정댓글/썸네일 문구)는 기존 카피라이터 재사용
    creative = build_creative(product, load_profile())
    beats = build_beats(product)
    # 컴플라이언스는 실제 발화되는 promo 내레이션으로 검사
    creative["scenes"] = beats_to_scenes(beats)
    # 사용된 대본 말투 라벨(beats의 pick과 동일 — 상품ID 해시라 재호출해도 일치)
    from clipcart.video.promo.script import pick_script_style

    creative["script_style"] = pick_script_style(product)[0]

    # 실제 리스팅 사진 갤러리 다운로드 — 실사용 느낌(제품 사진 다수 노출)
    image_urls = product.get("image_urls") or [product["image_url"]]
    work_dir = product_png.parent
    image_paths: list[str] = []
    product_img = None
    for i, url in enumerate(image_urls[:6]):
        try:
            im = fetch_image(url)
        except Exception:  # noqa: BLE001
            continue
        p = work_dir / f"p{i}.png"
        im.save(p, "PNG")
        image_paths.append(str(p))
        if product_img is None:
            product_img = im  # 첫 성공컷 = 메인(썸네일/최종 폴백)
    if product_img is None:
        product_img = fetch_image(product["image_url"])
    product_img.save(product_png, "PNG")
    if not image_paths:
        image_paths = [str(product_png)]

    # 제품 영상(있으면) — 실사용 느낌 극대화. soft-fail.
    product_video = None
    if product.get("video_url"):
        try:
            import requests as _rq

            vp = work_dir / "product_vid.mp4"
            r = _rq.get(product["video_url"], timeout=60)
            if r.ok and len(r.content) > 10000:
                vp.write_bytes(r.content)
                product_video = str(vp)
        except Exception:  # noqa: BLE001
            product_video = None

    hook_title = product["niche"]["hook"]
    render_promo(beats, str(product_png), str(video_path), hook_title=hook_title,
                 product_media={"images": image_paths, "video": product_video})

    compose_thumbnail(product_img, creative["thumbnail_line1"], creative["thumbnail_line2"],
                      thumb_path, badge_text=AD_BADGE)

    return {"video_path": video_path, "thumbnail_path": thumb_path, "creative": creative}
