"""'model' 템플릿 — 미모 여성이 제품을 소개하는 풀블리드 패션광고.

흐름: GPT-image-2(OpenRouter)로 인물+제품을 레퍼런스 일관성 있게 생성 → Kling
I2V로 모션 → 풀블리드로 이어붙임. ≤15초, 말 적게(훅+마무리 2줄), 모던/쿨한
아름다운 각도. 비용이 크므로(이미지+영상 과금) 장면 수를 제한하고 캐시한다.

일관성: 제품은 원본 제품컷을 레퍼런스로 박아 동일 유지. 인물은 첫 컷(hero)을
다음 컷의 추가 레퍼런스로 넘겨 같은 여성·의상을 유지한다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from clipcart.config import OUTBOX_DIR
from clipcart.disclosure import AD_BADGE, disclosure_for
from clipcart.video.compliance import sanitize_text
from clipcart.video.copywriter import build_creative
from clipcart.video.fonts import load_font
from clipcart.video.frames import compose_thumbnail, fetch_image
from clipcart.video.profile import load_profile
from clipcart.research.auto_select import short_product_name
from clipcart.video.promo.pricing import parse_pack, unit_phrase

# 일관된 광고 모델 페르소나 — 매 컷 동일 인물이 나오도록 고정 묘사.
PERSONA = (
    "a strikingly elegant Korean woman in her late twenties, clean natural glam makeup, "
    "soft modern beauty-commercial aesthetic, tasteful minimalist outfit"
)


def _gen_prompt(scene_desc: str) -> str:
    """인물+제품 생성 프롬프트. 제품은 입력 사진과 동일하게, 인물은 페르소나 고정."""
    return (
        f"High-end vertical beauty/product commercial still. {PERSONA}, {scene_desc}. "
        "She presents the product shown in the reference photo. Keep the product "
        "COMPLETELY IDENTICAL to the reference — same shape, colors, logos and printing; "
        "do not redesign or beautify the product itself. Modern cool editorial lighting, "
        "a beautiful flattering camera angle, shallow depth of field, premium minimalist "
        "set, photorealistic. Vertical 9:16. No text, no captions, no watermark."
    )


def model_scenes(product: dict[str, Any]) -> list[dict[str, str]]:
    """3개 장면(hero/lifestyle/closing) 계획. 순수 함수(생성 호출 없음)."""
    niche = product["niche"]
    name = short_product_name(product)
    price = int(product.get("price") or 0)
    cnt, _unit = parse_pack(product.get("product_name", ""))
    up = unit_phrase(price, cnt)
    price_line = f"{name}, {up}." if up else f"{name}, {price:,}원."

    return [
        {
            "role": "hero",
            "gen": _gen_prompt(
                "holding and presenting the product toward the camera, confident soft "
                "smile, looking at camera"
            ),
            "motion": (
                "slow elegant push-in, she gently turns the product toward camera, hair "
                "and fabric move softly, the product stays identical, no text"
            ),
            "narration": sanitize_text(niche["hook"]),
        },
        {
            "role": "lifestyle",
            "gen": _gen_prompt(
                "using the product naturally in a bright modern 2020s Korean apartment, "
                "candid editorial three-quarter angle"
            ),
            "motion": (
                "smooth slow dolly around her as she uses the product, cinematic, the "
                "product stays identical, no text"
            ),
            "narration": "",  # 비주얼 순간(무음) — 말 적게
        },
        {
            "role": "closing",
            "gen": _gen_prompt(
                "presenting the product close to camera at a beautiful three-quarter "
                "angle, the product in sharp focus"
            ),
            "motion": (
                "slow zoom toward the product in her hands, soft focus pull, the product "
                "stays identical, no text"
            ),
            "narration": sanitize_text(f"{price_line} 자세한 건 프로필 링크에서."),
        },
    ]


def model_compliance_scenes(
    product: dict[str, Any], scenes: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """check_texts용 scenes — 첫·끝 장면에 소스별 고지를 실어 시작/끝 표시 요건 충족."""
    disc = disclosure_for(product)
    out = []
    for i, s in enumerate(scenes):
        out.append(
            {
                "name": s["role"],
                "narration": s["narration"],
                "caption": "",
                "disclosure": disc if (i == 0 or i == len(scenes) - 1) else None,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# 렌더링 (풀블리드)
# --------------------------------------------------------------------------- #
W, H = 1080, 1920
SCENE_DUR = int((os.getenv("CLIPCART_MODEL_SCENE_DUR", "") or "5").split("#")[0])


def _fullbleed_clip(path: str, kind: str, dur: float):
    """영상/이미지를 전체화면(W×H) cover-crop. 이미지면 느린 줌(켄번스)."""
    from moviepy import ImageClip, VideoFileClip, vfx

    if kind == "video":
        clip = VideoFileClip(path).without_audio()
        s = max(clip.w / W, clip.h / H)
        nw, nh = max(W, int(clip.w * s)), max(H, int(clip.h * s))
        clip = clip.with_effects(
            [vfx.Resize(new_size=(nw, nh)), vfx.Crop(x_center=nw // 2, y_center=nh // 2, width=W, height=H)]
        )
        if clip.duration >= dur:
            clip = clip.subclipped(0, dur)
        else:
            clip = clip.with_effects([vfx.Loop(duration=dur)])
        return clip.with_duration(dur)

    img = Image.open(path).convert("RGB")
    s = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * s), int(img.height * s)), Image.Resampling.LANCZOS)
    x0, y0 = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((x0, y0, x0 + W, y0 + H))
    base = ImageClip(np.array(img)).with_duration(dur)

    def tf(get_frame, t):
        fr = get_frame(t)
        z = 1.0 + 0.08 * (t / max(dur, 0.01))
        hh, ww = fr.shape[:2]
        nh2, nw2 = int(hh / z), int(ww / z)
        yy, xx = (hh - nh2) // 2, (ww - nw2) // 2
        return np.array(Image.fromarray(fr[yy : yy + nh2, xx : xx + nw2]).resize((ww, hh), Image.BILINEAR))

    return base.transform(tf)


def _lower_third_png(text: str) -> np.ndarray:
    """모던/쿨한 하단 제3 자막 — 흰 글씨 + 부드러운 그림자, 띠 없이 미니멀."""
    from PIL import ImageDraw

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = load_font(64, bold=True, display=True)
    box_w = int(W * 0.86)
    # 한 줄에 안 맞으면 줄바꿈(최대 2줄)
    words, lines, cur = text.split(), [], []
    for w in words:
        if d.textlength(" ".join(cur + [w]), font=font) <= box_w or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur)); cur = [w]
    if cur:
        lines.append(" ".join(cur))
    lines = lines[:2]
    lh = int(64 * 1.25)
    y = int(H * 0.80) - lh * len(lines) // 2
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((W - w) // 2, y), ln, font=font, fill=(255, 255, 255),
               stroke_width=5, stroke_fill=(0, 0, 0, 200))
        y += lh
    return np.array(img)


def _disclosure_png(text: str) -> np.ndarray:
    from PIL import ImageDraw

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = load_font(30, bold=False)
    w = d.textlength(text, font=font)
    d.text(((W - w) // 2, int(H * 0.90)), text, font=font, fill=(240, 240, 240),
           stroke_width=3, stroke_fill=(0, 0, 0))
    return np.array(img)


def render_model(
    scenes: list[dict[str, str]],
    clips: list[tuple[str, str]],
    out_path: str,
    *,
    disclosure: str,
    fps: int = 30,
    end_card_dur: float = 1.2,
) -> Path:
    """풀블리드 모델 광고 합성: 장면 클립 이어붙임 + 최소 자막 + 시작/끝 고지 + 로고."""
    from moviepy import (
        AudioFileClip, ColorClip, CompositeAudioClip, CompositeVideoClip,
        concatenate_videoclips, vfx,
    )

    from clipcart.config import PROJECT_ROOT
    from clipcart.video import sfx
    from clipcart.video.promo import tts_typecast
    from clipcart.video.promo.editor import _ad_badge_png, _logo_overlay, _mix_sfx, _overlay

    media_segs, overlays, audio_segs, sfx_cues = [], [], [], []
    t = 0.0
    for i, ((path, kind), scene) in enumerate(zip(clips, scenes)):
        seg = _fullbleed_clip(path, kind, SCENE_DUR).with_effects(
            [vfx.CrossFadeIn(0.3)] if i else []
        )
        media_segs.append(seg)
        # 최소 내레이션 — 있는 장면만 TTS, 모던 하단 자막
        narr = scene.get("narration", "").strip()
        if narr:
            apath, adur = tts_typecast.synth_or_edge(narr, "cta")
            audio_segs.append(AudioFileClip(str(apath)).with_start(t + 0.2))
            overlays.append(_overlay(_lower_third_png(narr), t + 0.2, min(SCENE_DUR - 0.2, adur + 1.2), fi=0.25, fo=0.3))
        if i:
            sfx_cues.append((sfx.whoosh(), t, 0.3))
        t += SCENE_DUR

    total_narr = t
    total = t + end_card_dur

    bg = ColorClip((W, H), color=(8, 8, 10), duration=total)
    media = concatenate_videoclips(media_segs, method="chain").with_start(0)
    # 시작·끝 고지 베이크(공정위 시작/끝 표시)
    disc_start = _overlay(_disclosure_png(disclosure), 0.0, min(3.0, SCENE_DUR), fi=0.2, fo=0.3)
    disc_end = _overlay(_disclosure_png(disclosure), max(0.0, total_narr - 3.0), 3.0, fi=0.3, fo=0.2)
    ad_badge = _overlay(_ad_badge_png(), 0.0, total, fi=0.0, fo=0.0)

    layers = [bg, media, *overlays, disc_start, disc_end, ad_badge]
    logo = PROJECT_ROOT / "logo.png"
    if logo.exists():
        layers.append(_logo_overlay(str(logo), total_narr + 0.1, end_card_dur - 0.2))

    final = CompositeVideoClip(layers, size=(W, H)).with_duration(total).with_fps(fps)
    if audio_segs:
        final = final.with_audio(CompositeAudioClip(audio_segs))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".narr.mp4")
    final.write_videofile(
        str(tmp), codec="libx264", audio_codec="aac", fps=fps, bitrate="7M",
        preset="medium", temp_audiofile=str(out.with_suffix(".tmpaudio.m4a")),
        ffmpeg_params=["-movflags", "+faststart"], threads=4, logger=None,
    )
    _mix_sfx(tmp, sfx_cues, out)
    tmp.unlink(missing_ok=True)
    return out


def make_model_video(product: dict[str, Any], keep_workdir: bool = False) -> dict[str, Any]:
    """model 템플릿 오케스트레이션 — make_promo_video와 동일한 패키지를 반환."""
    from clipcart.video.promo import kling, sources

    pid = product["product_id"]
    publish_dir = OUTBOX_DIR / "publishing"
    publish_dir.mkdir(parents=True, exist_ok=True)
    video_path = publish_dir / f"{pid}.mp4"
    thumb_path = publish_dir / f"{pid}_thumb.jpg"
    work = OUTBOX_DIR / "work" / pid
    work.mkdir(parents=True, exist_ok=True)

    creative = build_creative(product, load_profile())
    scenes = model_scenes(product)
    # 비용 절감 노브: 2면 hero+closing만(가격·CTA·끝고지 보존). 기본 3(풀 광고).
    budget = int((os.getenv("CLIPCART_MODEL_SCENES", "") or "3").split("#")[0])
    if budget <= 2:
        scenes = [scenes[0], scenes[-1]]
    creative["scenes"] = model_compliance_scenes(product, scenes)
    creative["script_style"] = "model"

    # 제품 레퍼런스 컷 확보
    product_png = work / "product.png"
    product_img = fetch_image(product["image_url"])
    product_img.save(product_png, "PNG")

    # 장면별: 인물+제품 생성(제품 + 직전 hero 컷을 레퍼런스로) → Kling 모션 → 클립
    clips: list[tuple[str, str]] = []
    hero_ref: str | None = None
    hero_still_img = product_img
    for i, scene in enumerate(scenes):
        refs = [str(product_png)] + ([hero_ref] if hero_ref else [])
        still = sources.openrouter_compose(scene["gen"], refs, f"model|{pid}|{scene['role']}")
        if not still:
            # 생성 실패 — 제품컷으로라도 풀블리드(켄번스) 진행(soft-fail)
            clips.append((str(product_png), "image"))
            continue
        if hero_ref is None:
            hero_ref = still  # 첫 인물 컷을 이후 장면 일관성 레퍼런스로
            hero_still_img = Image.open(still).convert("RGB")
        motion = kling.animate(still, scene["motion"], duration=SCENE_DUR)
        clips.append((motion, "video") if motion else (still, "image"))

    render_model(scenes, clips, str(video_path), disclosure=disclosure_for(product))

    # 썸네일 — hero 컷(인물+제품)으로 흥행 훅 텍스트
    compose_thumbnail(
        hero_still_img, creative["thumbnail_line1"], creative["thumbnail_line2"],
        thumb_path, badge_text=AD_BADGE,
    )
    return {"video_path": video_path, "thumbnail_path": thumb_path, "creative": creative}
