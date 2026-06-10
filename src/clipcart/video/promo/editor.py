"""3단 레이아웃 moviepy 에디터 — steward-lab video_engine/editor.py 포팅(한글/쿠팡).

  ┌──────────────────────────────┐
  │ TOP  광고배너 + 지속 훅 타이틀  │  ink band
  ├──────────────────────────────┤
  │ MEDIA  Pexels/Gemini/제품이미지 │  footage band; emphasis 슬램
  ├──────────────────────────────┤
  │ BOTTOM 빠른 내레이션 자막        │  ink band; 의미 단위 청크
  └──────────────────────────────┘
아웃트로: 살림해결소 로고 ~2s.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from moviepy import (
    AudioFileClip, CompositeAudioClip, CompositeVideoClip, ColorClip,
    ImageClip, VideoFileClip, afx, concatenate_videoclips, vfx,
)

from clipcart.config import PROJECT_ROOT
from clipcart.video import sfx
from clipcart.video.promo import sources

W, H = 1080, 1920
TOP_H = int(0.17 * H)
BOTTOM_Y = int(0.80 * H)
MEDIA_Y = TOP_H
MEDIA_H = BOTTOM_Y - MEDIA_Y
BANNER_H = 70

_FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
_FONT_REG = r"C:\Windows\Fonts\malgun.ttf"

WHITE = (245, 245, 245)
YELLOW = (255, 209, 0)
RED = (232, 38, 38)
INK = (10, 11, 14)
DIM = (200, 200, 205)
_COLORS = {"red": RED, "yellow": YELLOW, "white": WHITE}

BANNER_TEXT = "광고 · 쿠팡 파트너스 수수료 지급"
BRAND = "살림해결소"


def _color(name: str):
    return _COLORS.get(name, WHITE)


# --------------------------------------------------------------------------- #
# Sourcing
# --------------------------------------------------------------------------- #
def _try_one(pex, token: str, index: int) -> tuple[str | None, str | None]:
    """단일 source 토큰 시도 → (path, kind) 또는 (None, None)."""
    if token == "product":
        return None, None  # product는 호출부에서 최종 폴백으로만
    if token.startswith("gemini:"):
        g = sources.gemini_still(token[7:], "cinematic", index)
        return (g, "image") if g else (None, None)
    if token.startswith("pexels:"):
        q = token[7:]
        if pex and pex.enabled:
            v = pex.fetch_video(q, index=index)
            if v:
                return v, "video"
            p = pex.fetch_photo(q, index=index)
            if p:
                return p, "image"
        return None, None
    return None, None


def _resolve_media(pex, tokens: list[str], product_img_path: str, index: int) -> tuple[str, str]:
    """후보 토큰 순서대로 시도, 모두 실패 시 제품 이미지."""
    for tok in tokens:
        if tok == "product":
            return product_img_path, "product"
        p, k = _try_one(pex, tok, index)
        if p:
            return p, k
    return product_img_path, "product"


# --------------------------------------------------------------------------- #
# Media clips (cover-crop to W x MEDIA_H)
# --------------------------------------------------------------------------- #
def _cover(w, h, tw=W, th=MEDIA_H):
    s = max(tw / w, th / h)
    return max(tw, int(round(w * s))), max(th, int(round(h * s)))


def _media_video(path: str, dur: float):
    clip = VideoFileClip(path).without_audio()
    nw, nh = _cover(clip.w, clip.h)
    clip = clip.with_effects([vfx.Resize(new_size=(nw, nh)),
                              vfx.Crop(x_center=nw // 2, y_center=nh // 2, width=W, height=MEDIA_H)])
    if clip.duration >= dur:
        start = min(0.4, max(0.0, clip.duration - dur))
        clip = clip.subclipped(start, start + dur)
    else:
        clip = clip.with_effects([vfx.Loop(duration=dur)])
    return clip.with_duration(dur)


def _media_image(path: str, dur: float, z0=1.04, z1=1.13):
    img = Image.open(path).convert("RGB")
    nw, nh = _cover(*img.size)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    x0, y0 = (nw - W) // 2, (nh - MEDIA_H) // 2
    img = img.crop((x0, y0, x0 + W, y0 + MEDIA_H))
    base = ImageClip(np.array(img)).with_duration(dur)

    def tf(get_frame, t):
        fr = get_frame(t)
        z = z0 + (z1 - z0) * (t / max(dur, 0.01))
        h, w = fr.shape[:2]
        nh2, nw2 = int(h / z), int(w / z)
        yy, xx = (h - nh2) // 2, (w - nw2) // 2
        return np.array(Image.fromarray(fr[yy:yy + nh2, xx:xx + nw2]).resize((w, h), Image.BILINEAR))
    return base.transform(tf)


def _media_product(path: str, dur: float):
    """제품 이미지를 흰 카드 위에 contain 배치(잘림 없음) + 살짝 줌."""
    src = Image.open(path).convert("RGB")
    canvas = Image.new("RGB", (W, MEDIA_H), (244, 244, 241))
    pad = 90
    fit_w, fit_h = W - pad * 2, MEDIA_H - pad * 2
    ratio = min(fit_w / src.width, fit_h / src.height)
    fitted = src.resize((max(1, int(src.width * ratio)), max(1, int(src.height * ratio))), Image.Resampling.LANCZOS)
    canvas.paste(fitted, ((W - fitted.width) // 2, (MEDIA_H - fitted.height) // 2))
    base = ImageClip(np.array(canvas)).with_duration(dur)

    def tf(get_frame, t):
        fr = get_frame(t)
        z = 1.0 + 0.06 * (t / max(dur, 0.01))
        h, w = fr.shape[:2]
        nh2, nw2 = int(h / z), int(w / z)
        yy, xx = (h - nh2) // 2, (w - nw2) // 2
        return np.array(Image.fromarray(fr[yy:yy + nh2, xx:xx + nw2]).resize((w, h), Image.BILINEAR))
    return base.transform(tf)


def _media_clip(path, kind, dur):
    try:
        if kind == "video":
            return _media_video(path, dur)
        if kind == "product":
            return _media_product(path, dur)
        return _media_image(path, dur)
    except Exception as e:  # noqa: BLE001
        print(f"  [clip] {kind} failed ({str(e)[:80]}); solid bg")
        return ColorClip((W, MEDIA_H), color=INK, duration=dur)


# --------------------------------------------------------------------------- #
# Text rendering
# --------------------------------------------------------------------------- #
def _wrap(draw, words, font, max_w, stroke):
    lines, cur = [], []
    for w in words:
        bb = draw.textbbox((0, 0), " ".join(cur + [w]), font=font, stroke_width=stroke)
        if bb[2] - bb[0] <= max_w or not cur:
            cur.append(w)
        else:
            lines.append(cur); cur = [w]
    if cur:
        lines.append(cur)
    return lines


def _fit(text, font_path, box_w, box_h, max_size, min_size, stroke, max_lines):
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    words = text.split()
    for size in range(max_size, min_size - 1, -3):
        font = ImageFont.truetype(font_path, size)
        lines = _wrap(tmp, words, font, box_w, stroke)
        widest = max(tmp.textbbox((0, 0), " ".join(lw), font=font, stroke_width=stroke)[2] for lw in lines)
        if len(lines) <= max_lines and int(size * 1.2) * len(lines) <= box_h and widest <= box_w:
            return font, size, lines
    font = ImageFont.truetype(font_path, min_size)
    return font, min_size, _wrap(tmp, words, font, box_w, stroke)


def _draw_block(text, font_path, zone_y0, zone_y1, max_size, min_size,
                color=WHITE, accent=None, accent_color=YELLOW, stroke=6):
    box_w = int(W * 0.88)
    box_h = (zone_y1 - zone_y0) - 20
    max_lines = 2 if (zone_y1 - zone_y0) < 0.25 * H else 3
    font, size, lines = _fit(text, font_path, box_w, box_h, max_size, min_size, stroke, max_lines)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    line_h = int(size * 1.2)
    block_h = line_h * len(lines)
    y0 = zone_y0 + ((zone_y1 - zone_y0) - block_h) // 2
    space = d.textbbox((0, 0), " ", font=font, stroke_width=stroke)[2]
    accent_l = (accent or "").strip().lower() or None
    for li, lw in enumerate(lines):
        ws = [d.textbbox((0, 0), w, font=font, stroke_width=stroke) for w in lw]
        widths = [b[2] - b[0] for b in ws]
        total = sum(widths) + space * (len(lw) - 1)
        x = (W - total) // 2
        y = y0 + li * line_h
        for w, wd in zip(lw, widths):
            clean = w.strip(",.!?;:'\"()").lower()
            fill = accent_color if accent_l and accent_l in clean else color
            d.text((x, y), w, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))
            x += wd + space
    return np.array(img)


# --------------------------------------------------------------------------- #
# Korean meaning-unit splitter (bottom narration)
# --------------------------------------------------------------------------- #
def _meaning_units(text: str, max_eojeol: int = 5) -> list[str]:
    segs = re.split(r"(?<!\d)[.,!?·](?!\d)\s*", text)
    units: list[str] = []
    for seg in segs:
        words = seg.split()
        if not words:
            continue
        cur: list[str] = []
        for w in words:
            cur.append(w)
            if len(cur) >= max_eojeol:
                units.append(" ".join(cur)); cur = []
        if cur:
            units.append(" ".join(cur))
    return units or [text]


# --------------------------------------------------------------------------- #
# Overlay
# --------------------------------------------------------------------------- #
def _overlay(rgba, t_in, dur, fi=0.1, fo=0.1):
    mask = ImageClip(rgba[:, :, 3].astype(np.float32) / 255.0, is_mask=True, duration=dur)
    clip = ImageClip(rgba[:, :, :3], duration=dur).with_mask(mask).with_start(t_in)
    if fi or fo:
        clip = clip.with_effects([vfx.CrossFadeIn(fi), vfx.CrossFadeOut(fo)])
    return clip


def _ad_badge_png() -> np.ndarray:
    """최소 '광고' 뱃지 — 투명 배경에 작은 반투명 펠릿(적대감 최소화)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(_FONT_BOLD, 32)
    text = "광고"
    x, y = 40, 44
    pad_x, pad_y = 22, 11
    bb = d.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    rect = (x, y, x + tw + pad_x * 2, y + th + pad_y * 2)
    d.rounded_rectangle(rect, radius=(rect[3] - rect[1]) // 2, fill=(0, 0, 0, 110))
    d.text((x + pad_x, y + pad_y - bb[1]), text, font=f, fill=(255, 255, 255, 235))
    return np.array(img)


def _float_logo_overlay(t_in: float, dur: float):
    """살림해결소 로고를 우상단에 플로팅(레이어 띠 없이)."""
    logo_path = PROJECT_ROOT / "logo.png"
    if not logo_path.exists():
        return None
    logo = Image.open(logo_path).convert("RGBA")
    scale = 118 / max(logo.size)
    logo = logo.resize((int(logo.width * scale), int(logo.height * scale)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # 가벼운 그림자
    shadow = Image.new("RGBA", logo.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 120), (0, 0), logo.split()[-1])
    px, py = W - logo.width - 38, 40
    canvas.alpha_composite(shadow, (px + 3, py + 3))
    canvas.alpha_composite(logo, (px, py))
    return _overlay(np.array(canvas), t_in, dur, fi=0.25, fo=0.2)


def _sfx_clip(path, t_in, vol):
    if path and os.path.exists(str(path)):
        try:
            c = AudioFileClip(str(path))
            dur = c.duration
            # end를 명시적으로 고정(미설정 시 composite가 파일 너머를 읽는 moviepy 버그 회피)
            return c.with_effects([afx.MultiplyVolume(vol)]).with_duration(dur).with_start(t_in)
        except Exception:  # noqa: BLE001
            return None
    return None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def render_promo(beats: list[dict[str, Any]], product_img_path: str, out_path: str,
                 *, hook_title: str, fps: int = 30, end_card_dur: float = 2.0) -> Path:
    from clipcart.video.promo import tts_typecast

    pex = sources.Pexels()
    print(f"  [promo] pexels={'on' if pex.enabled else 'off'} typecast={'on' if tts_typecast.available() else 'edge-fallback'}")

    # TTS per beat
    tts = []
    for b in beats:
        path, dur = tts_typecast.synth_or_edge(b["narration"].strip(), b.get("tone", "neutral"))
        tts.append((str(path), dur))

    media_segs, overlays, audio_segs, sfx_cues = [], [], [], []
    t = 0.0
    for i, (b, (apath, adur)) in enumerate(zip(beats, tts)):
        post = 0.12 if b["role"] == "hook" else 0.2
        beat_dur = adur + post
        col = _color(b.get("color", "white"))

        # media — source 후보 + fallback 순서로 해결
        tokens = [b["source"]] + ([b["fallback"]] if b.get("fallback") else [])
        path, kind = _resolve_media(pex, tokens, product_img_path, 0)
        media_segs.append(_media_clip(path, kind, beat_dur))

        # SFX: whoosh on cut, impact on hook/emphasis
        if i > 0:
            sfx_cues.append((sfx.whoosh(), t, 0.5))
        if b["role"] == "hook":
            sfx_cues.append((sfx.riser(), t + 0.02, 0.45))

        # bottom narration — meaning-unit chunks
        units = _meaning_units(b.get("caption") or b["narration"])
        wsum = sum(len(u.split()) for u in units) or 1
        ut = t
        for u in units:
            ud = beat_dur * (len(u.split()) / wsum)
            png = _draw_block(u, _FONT_BOLD, BOTTOM_Y + 16, H - 26, max_size=80, min_size=44,
                              stroke=6, color=WHITE)
            overlays.append(_overlay(png, ut, ud + 0.05, fi=0.05, fo=0.05))
            ut += ud

        # emphasis slam in media band (rare → impact)
        emp = b.get("emphasis")
        if emp:
            png = _draw_block(emp, _FONT_BOLD, MEDIA_Y + int(MEDIA_H * 0.30),
                              MEDIA_Y + int(MEDIA_H * 0.70), max_size=190, min_size=80,
                              stroke=8, color=col)
            est = t + min(0.4, beat_dur * 0.2)
            overlays.append(_overlay(png, est, min(1.1, beat_dur * 0.5), fi=0.05, fo=0.16))
            sfx_cues.append((sfx.pop(), est, 0.5))

        # CTA disclosure (baked, bottom) — 비트가 들고 있는 소스별 고지를 그린다
        if b.get("disclosure"):
            disc = _draw_block(b["disclosure"], _FONT_REG, int(0.70 * H), int(0.78 * H),
                               max_size=34, min_size=24, stroke=3, color=DIM)
            overlays.append(_overlay(disc, t + 0.1, beat_dur - 0.15, fi=0.1, fo=0.1))

        audio_segs.append(AudioFileClip(apath).with_start(t))
        t += beat_dur

    total_narr = t
    end_start = t
    total = t + end_card_dur

    # compose
    ink_bg = ColorClip((W, H), color=INK, duration=total)
    media_track = (concatenate_videoclips(media_segs, method="chain")
                   .with_position((0, MEDIA_Y)).with_start(0))

    title_png = _draw_block(hook_title, _FONT_BOLD, BANNER_H + 6, TOP_H - 6,
                            max_size=66, min_size=38, stroke=5, color=WHITE)
    title_clip = _overlay(title_png, 0.0, total_narr, fi=0.2, fo=0.15)
    ad_badge = _overlay(_ad_badge_png(), 0.0, total, fi=0.0, fo=0.0)

    layers = [ink_bg, media_track, title_clip, *overlays, ad_badge]
    flogo = _float_logo_overlay(0.0, total_narr)
    if flogo is not None:
        layers.append(flogo)

    # outro: logo
    logo = PROJECT_ROOT / "logo.png"
    if logo.exists():
        layers.append(_logo_overlay(str(logo), end_start + 0.1, end_card_dur - 0.2))
    else:
        layers.append(_overlay(_draw_block(BRAND, _FONT_BOLD, int(0.42 * H), int(0.58 * H),
                      96, 54, color=YELLOW), end_start + 0.1, end_card_dur - 0.2))

    final = CompositeVideoClip(layers, size=(W, H)).with_duration(total).with_fps(fps)

    # 내레이션만 moviepy로 합성(SFX는 렌더 후 ffmpeg로 — moviepy 짧은클립 over-read 회피)
    final = final.with_audio(CompositeAudioClip(audio_segs))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".narr.mp4")
    final.write_videofile(str(tmp), codec="libx264", audio_codec="aac", fps=fps,
                          bitrate="7M", preset="medium",
                          temp_audiofile=str(out.with_suffix(".tmpaudio.m4a")),
                          ffmpeg_params=["-movflags", "+faststart"], threads=4, logger=None)

    sfx_cues.append((sfx.thud(), end_start + 0.05, 0.5))
    _mix_sfx(tmp, sfx_cues, out)
    tmp.unlink(missing_ok=True)
    return out


def _mix_sfx(video: Path, cues: list, out: Path) -> None:
    """렌더된 영상 오디오 위에 SFX 큐를 ffmpeg amix로 입힘."""
    from clipcart.video.ff import run_ffmpeg

    cues = [(str(p), t, v) for (p, t, v) in cues if p and os.path.exists(str(p))]
    if not cues:
        import shutil

        shutil.copyfile(video, out)
        return
    inputs = ["-i", str(video)]
    for p, _, _ in cues:
        inputs += ["-i", p]
    parts, labels = [], []
    for k, (_, t_in, vol) in enumerate(cues):
        ms = max(0, int(t_in * 1000))
        parts.append(f"[{k+1}:a]adelay={ms}|{ms},volume={vol:.2f}[s{k}]")
        labels.append(f"[s{k}]")
    n = len(cues) + 1
    fil = ";".join(parts) + f";[0:a]{''.join(labels)}amix=inputs={n}:duration=first:normalize=0[a]"
    run_ffmpeg([*inputs, "-filter_complex", fil, "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(out)], timeout=300)


def _logo_overlay(path, t_in, dur):
    logo = Image.open(path).convert("RGBA")
    scale = 520 / max(logo.size)
    logo = logo.resize((int(logo.width * scale), int(logo.height * scale)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(logo, ((W - logo.width) // 2, (H - logo.height) // 2))
    return _overlay(np.array(canvas), t_in, dur, fi=0.3, fo=0.25)
