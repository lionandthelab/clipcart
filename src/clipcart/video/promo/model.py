"""'model' 템플릿 — 미모 모델이 제품을 쓰는 클립을 일반 promo 구성에 끼워넣는다.

운영자 지시(2026-06-19): 별도 풀블리드 몽타주(짧은 하드컷)는 깜빡여서 별로.
대신 기존 promo 구성(pexels/gpt이미지/제품샷 + 3단 자막 레이아웃 + 두 보이스 +
리뷰카드 CTA)을 그대로 쓰고, 모델 사용 영상을 '처음(hook)·중간(usage)'에만
끼워넣는다(beats가 modelclip 토큰을 배치, editor가 미디어로 해석).

모델: 30대 후반의 우아한 여성이 가정일을 우아하게 하는 모습. 제품은 원본
제품컷을 레퍼런스로 박아 동일 유지, 인물은 첫 컷을 다음 컷 레퍼런스로 넘겨
같은 사람을 유지한다. 생성/모션 실패분은 해당 비트의 일반 소스로 자연 폴백.
"""

from __future__ import annotations

import os
from typing import Any

from PIL import Image

from clipcart.config import OUTBOX_DIR
from clipcart.disclosure import AD_BADGE
from clipcart.video.copywriter import build_creative
from clipcart.video.frames import compose_thumbnail, fetch_image
from clipcart.video.profile import load_profile


def _clip_dur() -> int:
    """Kling 모션 클립 길이(초). 비트 길이에 맞춰 editor가 잘라 쓴다."""
    return int((os.getenv("CLIPCART_MODEL_CLIP_DUR", "") or "5").split("#")[0])


# 페르소나 — 30대 후반의 우아한 여성이 '가정일을 우아하게'(운영자 지시 2026-06-19).
PERSONA = (
    "an elegant, graceful Korean woman in her late thirties, refined and classy, warm "
    "tasteful styling, doing household chores beautifully and effortlessly"
)


def _gen_prompt(scene_desc: str) -> str:
    """인물+제품 생성 프롬프트. 제품은 입력 사진과 동일하게, 인물은 '사용하는 모습'."""
    return (
        f"High-end vertical lifestyle commercial still. {PERSONA}, {scene_desc}. "
        "She uses the product shown in the reference photo as a natural part of the scene. "
        "Keep the product COMPLETELY IDENTICAL to the reference — same shape, colors, logos "
        "and printing; do not redesign or beautify the product itself. Warm modern elegant "
        "editorial lighting, a beautiful flattering camera angle, shallow depth of field, "
        "premium tasteful Korean home, photorealistic. Vertical 9:16. No text, no captions, "
        "no watermark."
    )


def model_scenes(product: dict[str, Any]) -> list[dict[str, str]]:
    """모델 사용 클립 2개의 생성/모션 프롬프트(처음·중간). 순수 함수."""
    return [
        {
            "role": "hero",
            "gen": _gen_prompt(
                "gracefully using the product to do a household task, hands and product in "
                "focus, candid editorial side angle, not looking at the camera"
            ),
            "motion": (
                "natural mid-action motion of her hands using the product, soft slow "
                "camera move, the product stays identical, no text"
            ),
        },
        {
            "role": "use",
            "gen": _gen_prompt(
                "mid-action using the product in a bright modern 2020s Korean apartment, "
                "calm elegant three-quarter angle, the product clearly visible in use"
            ),
            "motion": (
                "smooth slow dolly as she keeps using the product, cinematic, the product "
                "stays identical, no text"
            ),
        },
    ]


def make_model_video(product: dict[str, Any], keep_workdir: bool = False) -> dict[str, Any]:
    """model 템플릿 — 일반 promo 렌더에 모델 사용 클립(처음·중간)을 주입.
    make_promo_video와 동일한 패키지를 반환한다."""
    from clipcart.video.frames import fetch_image as _fetch
    from clipcart.video.promo import kling, sources
    from clipcart.video.promo.beats import beats_to_scenes, build_beats
    from clipcart.video.promo.editor import render_promo
    from clipcart.video.promo.review_card import compose_review_card
    from clipcart.video.promo.script import pick_script_style

    pid = product["product_id"]
    publish_dir = OUTBOX_DIR / "publishing"
    publish_dir.mkdir(parents=True, exist_ok=True)
    video_path = publish_dir / f"{pid}.mp4"
    thumb_path = publish_dir / f"{pid}_thumb.jpg"
    work = OUTBOX_DIR / "work" / pid
    work.mkdir(parents=True, exist_ok=True)
    product_png = work / "product.png"

    # 리뷰 요약 카드(있으면 CTA 장면에 — promo와 동일)
    card = compose_review_card(product, work / "review_card.png")
    if card:
        product = {**product, "review_card_path": str(card)}

    # 메타·비트(beats가 is_model() 감지 → hook/usage에 modelclip 토큰 배치)
    creative = build_creative(product, load_profile())
    beats = build_beats(product)
    creative["scenes"] = beats_to_scenes(beats)
    creative["script_style"] = pick_script_style(product)[0]

    # 제품 사진 갤러리(promo와 동일)
    image_urls = product.get("image_urls") or [product["image_url"]]
    image_paths: list[str] = []
    product_img = None
    for i, url in enumerate(image_urls[:6]):
        try:
            im = _fetch(url)
        except Exception:  # noqa: BLE001
            continue
        p = work / f"p{i}.png"
        im.save(p, "PNG")
        image_paths.append(str(p))
        if product_img is None:
            product_img = im
    if product_img is None:
        product_img = fetch_image(product["image_url"])
    product_img.save(product_png, "PNG")
    if not image_paths:
        image_paths = [str(product_png)]

    # 셀러 제품 영상(있으면, promo와 동일)
    product_video = None
    if product.get("video_url"):
        try:
            import requests as _rq

            vp = work / "product_vid.mp4"
            r = _rq.get(product["video_url"], timeout=60)
            if r.ok and len(r.content) > 10000:
                vp.write_bytes(r.content)
                product_video = str(vp)
        except Exception:  # noqa: BLE001
            product_video = None

    # 모델 사용 클립 2개(처음·중간): 인물이 제품 쓰는 컷 생성 → Kling 모션.
    # 인물 일관성: 첫 컷(hero)을 다음 컷의 추가 레퍼런스로. 실패분은 자연 폴백.
    model_clips: list[str] = []
    hero_ref: str | None = None
    hero_still_img = product_img
    for scene in model_scenes(product):
        refs = [str(product_png)] + ([hero_ref] if hero_ref else [])
        still = sources.openrouter_compose(scene["gen"], refs, f"model|{pid}|{scene['role']}")
        if not still:
            model_clips.append("")  # 자리 유지 — 해당 modelclip:N은 폴백된다
            continue
        if hero_ref is None:
            hero_ref = still
            hero_still_img = Image.open(still).convert("RGB")
        motion = kling.animate(still, scene["motion"], duration=_clip_dur())
        model_clips.append(motion or still)  # 모션이면 mp4, 실패 시 정지컷(켄번스)

    hook_title = product["niche"]["hook"]
    render_promo(
        beats, str(product_png), str(video_path), hook_title=hook_title,
        header_title=creative.get("header_title", ""),
        product_media={"images": image_paths, "video": product_video, "model_clips": model_clips},
    )

    compose_thumbnail(
        hero_still_img, creative["thumbnail_line1"], creative["thumbnail_line2"],
        thumb_path, badge_text=AD_BADGE,
    )
    return {"video_path": video_path, "thumbnail_path": thumb_path, "creative": creative}
