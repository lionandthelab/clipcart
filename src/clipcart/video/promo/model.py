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

# 페르소나 — 30대 후반의 우아한 여성이 '가정일을 우아하게' 하는 모습(운영자 지시
# 2026-06-19: 생활용품에 어울리게). 매 컷 동일 인물이 나오도록 고정 묘사.
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
    """3개 장면(hero/explain/closing) 계획. 인물이 제품을 '쓰는 모습' 위주 + 제품 설명
    유지. 순수 함수(생성 호출 없음)."""
    niche = product["niche"]
    name = short_product_name(product)
    price = int(product.get("price") or 0)
    cnt, _unit = parse_pack(product.get("product_name", ""))
    up = unit_phrase(price, cnt)
    price_line = f"{name}, {up}." if up else f"{name}, {price:,}원."
    benefit = sanitize_text(niche.get("benefit", ""))
    if len(benefit) > 62:
        benefit = benefit[:60].rstrip() + "…"

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
            "narration": sanitize_text(niche["hook"]),
            "voice": "main",
        },
        {
            "role": "explain",
            "gen": _gen_prompt(
                "mid-action using the product in a bright modern 2020s Korean apartment, "
                "calm elegant three-quarter angle, the product clearly visible in use"
            ),
            "motion": (
                "smooth slow dolly as she keeps using the product, cinematic, the product "
                "stays identical, no text"
            ),
            "narration": benefit,  # 제품 설명/가치 — 유지(운영자 지시)
            "voice": "testimony",  # 체감/설명 라인은 증언 보이스(두 목소리)
        },
        {
            "role": "closing",
            "gen": _gen_prompt(
                "holding the product at a beautiful three-quarter angle after finishing "
                "the task, serene satisfied mood, the product in sharp focus"
            ),
            "motion": (
                "slow zoom toward the product in her hands, soft focus pull, the product "
                "stays identical, no text"
            ),
            "narration": sanitize_text(f"{price_line} 자세한 건 프로필 링크에서."),
            "voice": "main",
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


def _video_window(path: str, start: float, dur: float):
    """모델 사용 영상에서 [start, start+dur] 구간을 풀블리드로 잘라낸다."""
    from moviepy import VideoFileClip, vfx

    clip = VideoFileClip(path).without_audio()
    cd = float(clip.duration or dur)
    if cd >= dur:
        s = min(max(start, 0.0), max(cd - dur, 0.0))
        sub = clip.subclipped(s, s + dur)
    else:
        sub = clip.with_effects([vfx.Loop(duration=dur)])
    sw = max(W / sub.w, H / sub.h)
    nw, nh = max(W, int(sub.w * sw)), max(H, int(sub.h * sw))
    return sub.with_effects(
        [vfx.Resize(new_size=(nw, nh)), vfx.Crop(x_center=nw // 2, y_center=nh // 2, width=W, height=H)]
    ).with_duration(dur)


# 몽타주 컷 길이 — '잠깐씩 1~2초'(운영자 지시 2026-06-19). 하드컷으로 리드미컬하게.
MODEL_CUT = 1.9
PROD_CUT = 1.6
MONTAGE_TARGET = 15.6  # 컴플라이언스 최소 15초 + 아웃트로 여유


def _montage_plan(model_clips: list[tuple[str, str]], product_img_path: str) -> list[tuple]:
    """모델 사용 컷과 제품 컷을 번갈아 배치. 모델 영상은 구간을 옮겨가며 다른 부분을 쓴다."""
    cuts: list[tuple] = []
    t, mi = 0.0, 0
    offsets: dict[int, float] = {}
    use_model = bool(model_clips)
    while t < MONTAGE_TARGET:
        if use_model and model_clips:
            path, kind = model_clips[mi % len(model_clips)]
            ci = mi % len(model_clips)
            if kind == "video":
                off = offsets.get(ci, 0.0)
                cuts.append(("video", path, off, MODEL_CUT))
                offsets[ci] = off + MODEL_CUT + 0.4
            else:
                cuts.append(("image", path, 0.0, MODEL_CUT))
            mi += 1
            t += MODEL_CUT
        else:
            cuts.append(("image", product_img_path, 0.0, PROD_CUT))
            t += PROD_CUT
        use_model = not use_model
    return cuts


def render_model(
    scenes: list[dict[str, str]],
    model_clips: list[tuple[str, str]],
    product_img_path: str,
    out_path: str,
    *,
    disclosure: str,
    fps: int = 30,
    end_card_dur: float = 1.2,
) -> Path:
    """풀블리드 모델 광고: 사용 모습 짧은 컷 + 제품 컷을 번갈아(하드컷 몽타주),
    그 위에 최소 내레이션(훅·설명·가격) + 시작/끝 고지 + 로고 아웃트로."""
    from moviepy import (
        AudioFileClip, ColorClip, CompositeAudioClip, CompositeVideoClip,
        concatenate_videoclips,
    )

    from clipcart.config import PROJECT_ROOT
    from clipcart.video import sfx
    from clipcart.video.promo import tts_typecast
    from clipcart.video.promo.editor import _ad_badge_png, _logo_overlay, _mix_sfx, _overlay

    cuts = _montage_plan(model_clips, product_img_path)
    media_segs, sfx_cues = [], []
    t = 0.0
    for c in cuts:
        seg = _video_window(c[1], c[2], c[3]) if c[0] == "video" else _fullbleed_clip(c[1], "image", c[3])
        media_segs.append(seg)
        if t > 0:
            sfx_cues.append((sfx.whoosh(), t, 0.22))  # 컷 전환 리듬
        t += c[3]
    montage_dur = t
    media = concatenate_videoclips(media_segs, method="chain").with_start(0)

    # 내레이션(훅→설명→가격) 순차 — 인물이 '쓰는 모습' 위에 얹어 립싱크 불일치 없음
    overlays, audio_segs = [], []
    at = 0.4
    for scene in scenes:
        narr = (scene.get("narration") or "").strip()
        if not narr or at >= montage_dur - 0.5:
            continue
        apath, adur = tts_typecast.synth_or_edge(narr, "cta", scene.get("voice", "main"))
        audio_segs.append(AudioFileClip(str(apath)).with_start(at))
        cap_dur = min(adur + 0.8, montage_dur - at)
        overlays.append(_overlay(_lower_third_png(narr), at, max(0.6, cap_dur), fi=0.2, fo=0.3))
        at += adur + 0.5

    total = montage_dur + end_card_dur
    bg = ColorClip((W, H), color=(8, 8, 10), duration=total)
    disc_start = _overlay(_disclosure_png(disclosure), 0.0, 3.0, fi=0.2, fo=0.3)
    disc_end = _overlay(_disclosure_png(disclosure), max(0.0, montage_dur - 3.0), 3.0, fi=0.3, fo=0.2)
    ad_badge = _overlay(_ad_badge_png(), 0.0, total, fi=0.0, fo=0.0)

    layers = [bg, media, *overlays, disc_start, disc_end, ad_badge]
    logo = PROJECT_ROOT / "logo.png"
    if logo.exists():
        layers.append(_logo_overlay(str(logo), montage_dur + 0.1, end_card_dur - 0.2))

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

    # 장면별: 인물이 제품 쓰는 모습 생성(제품 + 직전 hero 컷 레퍼런스로 일관성) →
    # Kling 모션 → 모델 사용 클립. 이 클립들을 몽타주에서 짧게 잘라 쓴다.
    model_clips: list[tuple[str, str]] = []
    hero_ref: str | None = None
    hero_still_img = product_img
    for scene in scenes:
        refs = [str(product_png)] + ([hero_ref] if hero_ref else [])
        still = sources.openrouter_compose(scene["gen"], refs, f"model|{pid}|{scene['role']}")
        if not still:
            continue  # 생성 실패분은 건너뜀(몽타주가 제품 컷으로 채움)
        if hero_ref is None:
            hero_ref = still  # 첫 인물 컷을 이후 장면 일관성 레퍼런스로
            hero_still_img = Image.open(still).convert("RGB")
        motion = kling.animate(still, scene["motion"], duration=SCENE_DUR)
        model_clips.append((motion, "video") if motion else (still, "image"))

    render_model(
        scenes, model_clips, str(product_png), str(video_path),
        disclosure=disclosure_for(product),
    )

    # 썸네일 — hero 컷(인물+제품)으로 흥행 훅 텍스트
    compose_thumbnail(
        hero_still_img, creative["thumbnail_line1"], creative["thumbnail_line2"],
        thumb_path, badge_text=AD_BADGE,
    )
    return {"video_path": video_path, "thumbnail_path": thumb_path, "creative": creative}
