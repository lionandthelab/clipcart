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
from PIL import Image, ImageDraw

from moviepy import (
    AudioFileClip, CompositeAudioClip, CompositeVideoClip, ColorClip,
    ImageClip, VideoFileClip, afx, concatenate_videoclips, vfx,
)

from clipcart.config import PROJECT_ROOT
from clipcart.video import sfx
from clipcart.video.fonts import load_font
from clipcart.video.promo import sources
from clipcart.video.promo.template import is_story

W, H = 1080, 1920
# 상단=자막(이전 제목 자리), 하단=브랜드바(살림해결소+로고). 미디어 밴드를 키워
# 제품 영상을 더 메인으로(운영자 지시 2026-06-13).
TOP_H = int(0.165 * H)       # 상단 자막 밴드
BRAND_H = int(0.115 * H)     # 하단 브랜드 바
BOTTOM_Y = H - BRAND_H
MEDIA_Y = TOP_H
MEDIA_H = BOTTOM_Y - MEDIA_Y
BANNER_H = 70

# 폰트는 bold 여부 플래그로 다루고 실제 해석은 크로스플랫폼 로더에 위임한다
_FONT_BOLD = True
_FONT_REG = False

WHITE = (245, 245, 245)
YELLOW = (255, 209, 0)
RED = (232, 38, 38)
INK = (10, 11, 14)
DIM = (200, 200, 205)
_COLORS = {"red": RED, "yellow": YELLOW, "white": WHITE}

# story 템플릿 팔레트 — 밝고 화사한 크림 톤(검정 광고 톤과 대비)
CREAM = (247, 243, 236)
CHARCOAL = (44, 46, 51)
SAGE = (126, 155, 122)
# story에서 강조어 색(promo 노랑/빨강)을 차콜/세이지로 순화
_STORY_COLOR = {"red": SAGE, "yellow": SAGE, "white": CHARCOAL}

BANNER_TEXT = "광고 · 쿠팡 파트너스 수수료 지급"
BRAND = "살림해결소"


def _color(name: str):
    return _COLORS.get(name, WHITE)


# --------------------------------------------------------------------------- #
# Sourcing
# --------------------------------------------------------------------------- #
def _try_one(pex, token: str, index: int, product_img_path: str = "",
             images: list[str] | None = None, video: str | None = None) -> tuple[str | None, str | None]:
    """단일 source 토큰 시도 → (path, kind) 또는 (None, None)."""
    if token == "product":
        return None, None  # product는 호출부에서 최종 폴백으로만
    if token.startswith("productimg:"):
        # 실제 리스팅 사진 갤러리의 N번째. 없으면 None(다음 폴백으로).
        try:
            idx = int(token[len("productimg:"):] or 0)
        except ValueError:
            idx = 0
        imgs = images or []
        if 0 <= idx < len(imgs) and imgs[idx] and Path(imgs[idx]).exists():
            return imgs[idx], "image"
        return None, None
    if token == "productvideo":
        # 셀러 제공 영상 — 중국어 자막 회피 편집을 위해 전용 kind로 분기
        if video and Path(video).exists():
            return video, "sellervideo"
        return None, None
    if token.startswith("file:"):
        p = token[5:]
        return (p, "image") if p and Path(p).exists() else (None, None)
    if token.startswith("productshot:"):
        g = sources.generate_product_shot(product_img_path, token[12:], index)
        return (g, "image") if g else (None, None)
    if token.startswith("motionshot:"):
        # 화보샷 정지 이미지 → Kling I2V로 미세 무빙 클립. 실패 시 정지 화보샷.
        from clipcart.video.promo import kling

        scene = token[11:]
        still = sources.generate_product_shot(product_img_path, scene, index)
        if not still:
            return None, None
        if kling.enabled():
            motion_prompt = (
                "subtle slow camera push-in with gentle parallax, the product stays "
                "perfectly still and completely identical, soft natural light, "
                "photorealistic, no text, no people"
            )
            v = kling.animate(still, motion_prompt, duration=5)
            if v:
                return v, "video"
        return still, "image"
    if token.startswith("gemini:"):
        # candid: 사람/손 없는 실사 폰카풍 (AI티 방지). story: 밝고 화사한 모던 톤.
        # OpenRouter 이미지 모델이 켜져 있으면 그쪽(실사 품질), 아니면 Gemini.
        g = sources.generate_still(token[7:], "story" if is_story() else "candid", index)
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


def _resolve_media(pex, tokens: list[str], product_img_path: str, index: int,
                   images: list[str] | None = None, video: str | None = None) -> tuple[str, str]:
    """후보 토큰 순서대로 시도, 모두 실패 시 제품 이미지."""
    for tok in tokens:
        if tok == "product":
            return product_img_path, "product"
        p, k = _try_one(pex, tok, index, product_img_path, images, video)
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


def _seller_subclip(clip, s: float, e: float, dur: float):
    """셀러 영상 구간 [s,e]를 미디어 밴드로 — 줌으로 여유를 주고 상단을 남겨
    하단 자막(중국어)을 프레임 밖으로 밀어낸다."""
    end = min(clip.duration, max(s + dur, e))
    sub = clip.subclipped(max(0.0, s), end)
    nw, nh = _cover(sub.w, sub.h)
    nw, nh = int(nw * 1.18), int(nh * 1.18)  # 크롭 여유(하단을 더 잘라낼 공간)
    sub = sub.with_effects([vfx.Resize(new_size=(nw, nh))])
    # y_center를 위로 당겨 상단 위주로 크롭(하단 자막 띠 제거)
    y_center = min(max(int(nh * 0.42), MEDIA_H // 2), nh - MEDIA_H // 2)
    sub = sub.with_effects([vfx.Crop(x_center=nw // 2, y_center=y_center, width=W, height=MEDIA_H)])
    if sub.duration >= dur:
        sub = sub.subclipped(0, dur)
    else:
        sub = sub.with_effects([vfx.Loop(duration=dur)])
    return sub.with_duration(dur)


class SellerVideo:
    """셀러 제품 영상 — 한 번 열어 텍스트 점수를 매기고 깨끗한 구간을 순서대로 제공.

    같은 영상을 product·usage 장면에 쓰되, 매 호출마다 다른 깨끗한 구간을
    돌려줘 반복 인상을 줄인다. 렌더가 끝날 때까지 열어둔다(지연 디코드).
    """

    # 중앙 영역(크롭으로 못 지움) 점수가 이 값을 넘으면 자막투성이로 보고 셀러영상을 안 쓴다
    SKIP_SCORE = 6.0

    def __init__(self, path: str, n: int = 14):
        from clipcart.video.promo.clean import CENTER_BAND, score_timeline

        self.clip = VideoFileClip(path).without_audio()
        self.dur = float(self.clip.duration or 0.0)
        safe = max(self.dur - 0.05, 0.0)
        try:
            # 하단 자막은 크롭이 처리하므로, 크롭으로 못 지우는 '중앙' 영역만 점수화한다.
            self.scored = score_timeline(
                lambda t: np.asarray(self.clip.get_frame(min(t, safe))),
                self.dur, n=n, band=CENTER_BAND,
            )
        except Exception:  # noqa: BLE001
            self.scored = []
        self._occ = 0

    @property
    def usable(self) -> bool:
        """중앙에 글자 없는 깨끗한 순간이 하나도 없으면(전체 자막) 쓰지 않는다."""
        if not self.scored:
            return False
        return min(s for _, s in self.scored) < self.SKIP_SCORE

    def next_segment(self, dur: float):
        from clipcart.video.promo.clean import pick_clean_windows

        wins = (
            pick_clean_windows(self.scored, want=min(dur, self.dur), k=2, total=self.dur)
            if self.scored
            else [(0.0, self.dur)]
        )
        s, e = wins[self._occ % len(wins)]
        self._occ += 1
        return _seller_subclip(self.clip, s, e, dur)

    def close(self) -> None:
        try:
            self.clip.close()
        except Exception:  # noqa: BLE001
            pass


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


def _fit(text, bold, box_w, box_h, max_size, min_size, stroke, max_lines, display=False, modern=False):
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    words = text.split()
    for size in range(max_size, min_size - 1, -3):
        font = load_font(size, bold=bold, display=display, modern=modern)
        lines = _wrap(tmp, words, font, box_w, stroke)
        widest = max(tmp.textbbox((0, 0), " ".join(lw), font=font, stroke_width=stroke)[2] for lw in lines)
        if len(lines) <= max_lines and int(size * 1.2) * len(lines) <= box_h and widest <= box_w:
            return font, size, lines
    font = load_font(min_size, bold=bold, display=display, modern=modern)
    return font, min_size, _wrap(tmp, words, font, box_w, stroke)


def _draw_block(text, bold, zone_y0, zone_y1, max_size, min_size,
                color=WHITE, accent=None, accent_color=YELLOW, stroke=6, display=False, modern=False):
    box_w = int(W * 0.88)
    box_h = (zone_y1 - zone_y0) - 20
    max_lines = 2 if (zone_y1 - zone_y0) < 0.25 * H else 3
    font, size, lines = _fit(text, bold, box_w, box_h, max_size, min_size, stroke, max_lines, display, modern)
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


def _korlen(s: str) -> int:
    """공백 제외 글자수 — 한국어 발화시간 근사(자막 타이밍 비례용)."""
    return len(s.replace(" ", "")) or 1


# 하단 자막: 또렷한 배경 칩(검정 띠 위에서도 보이게 밝은 차콜) + 디스플레이 폰트, 가능하면 한 줄.
SUB_MAX_SIZE, SUB_MIN_SIZE = 78, 42
SUB_BG = (44, 47, 60, 235)
SUB_BORDER = (255, 255, 255, 60)


def _subtitle_png(text: str) -> np.ndarray:
    text = text.strip()
    story = is_story()
    box_w = int(W * 0.90)
    # story: 차콜 텍스트 + 부드러운 오프화이트 칩(검정 외곽선 없이), 모던 폰트
    stroke = 0 if story else 5
    chip_bg = (250, 248, 244, 232) if story else SUB_BG
    chip_border = (44, 46, 51, 55) if story else SUB_BORDER
    txt_fill = CHARCOAL if story else WHITE
    stroke_fill = (255, 255, 255, 0) if story else (0, 0, 0)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    font = None
    size = SUB_MIN_SIZE
    lines = [text]
    # 한 줄 우선: 큰 사이즈부터 줄여가며 한 줄에 맞으면 채택
    for s in range(SUB_MAX_SIZE, SUB_MIN_SIZE - 1, -2):
        f = load_font(s, bold=True, display=not story, modern=story)
        if tmp.textbbox((0, 0), text, font=f, stroke_width=stroke)[2] <= box_w:
            font, size, lines = f, s, [text]
            break
    if font is None:  # 한 줄 불가 → 최소 사이즈 2줄
        font = load_font(SUB_MIN_SIZE, bold=True, display=not story, modern=story)
        size = SUB_MIN_SIZE
        lines = [" ".join(w) for w in _wrap(tmp, text.split(), font, box_w, stroke)][:2]

    line_h = int(size * 1.16)
    widths = [tmp.textbbox((0, 0), ln, font=font, stroke_width=stroke)[2] for ln in lines]
    text_w, text_h = max(widths), line_h * len(lines)
    pad_x, pad_y = 52, 26
    bw, bh = text_w + pad_x * 2, text_h + pad_y * 2
    bx0 = (W - bw) // 2
    # 자막을 화면 위에서 ~20% 지점에 배치 — 맨 위는 가독성이 떨어진다(운영자 지시
    # 2026-06-19). 미디어 위로 칩 배경이 깔려 대비가 확보된다.
    by0 = int(0.20 * H) - bh // 2

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((bx0, by0, bx0 + bw, by0 + bh), radius=28, fill=chip_bg,
                        outline=chip_border, width=3)
    ty = by0 + pad_y
    for ln, lw in zip(lines, widths):
        d.text(((W - lw) // 2, ty), ln, font=font, fill=txt_fill, stroke_width=stroke, stroke_fill=stroke_fill)
        ty += line_h
    return np.array(img)


def _story_emph_png(text: str, max_size: int = 120, min_size: int = 72) -> np.ndarray:
    """story 중앙 강조 — 흰 배경 라운드 칩 + 검정 글씨(모던 폰트)."""
    text = text.strip()
    box_w = int(W * 0.84)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    font = load_font(min_size, bold=True, modern=True)
    size = min_size
    lines = [text]
    for s in range(max_size, min_size - 1, -3):
        f = load_font(s, bold=True, modern=True)
        if tmp.textbbox((0, 0), text, font=f)[2] <= box_w:
            font, size, lines = f, s, [text]
            break
    else:
        lines = [" ".join(w) for w in _wrap(tmp, text.split(), font, box_w, 0)][:2]
    line_h = int(size * 1.18)
    widths = [tmp.textbbox((0, 0), ln, font=font)[2] for ln in lines]
    tw, th = max(widths), line_h * len(lines)
    pad_x, pad_y = 48, 26
    bw, bh = tw + pad_x * 2, th + pad_y * 2
    bx0 = (W - bw) // 2
    by0 = MEDIA_Y + (MEDIA_H - bh) // 2
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((bx0, by0, bx0 + bw, by0 + bh), radius=28, fill=(255, 255, 255, 245))
    ty = by0 + pad_y
    for ln, lw in zip(lines, widths):
        d.text(((W - lw) // 2, ty), ln, font=font, fill=(18, 18, 20))
        ty += line_h
    return np.array(img)


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
    f = load_font(32, bold=True)
    text = "광고"
    x, y = 40, 44
    pad_x, pad_y = 22, 11
    bb = d.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    rect = (x, y, x + tw + pad_x * 2, y + th + pad_y * 2)
    d.rounded_rectangle(rect, radius=(rect[3] - rect[1]) // 2, fill=(0, 0, 0, 110))
    d.text((x + pad_x, y + pad_y - bb[1]), text, font=f, fill=(255, 255, 255, 235))
    return np.array(img)


def _brand_bar_overlay(t_in: float, dur: float):
    """하단 브랜드 바: 살림해결소 로고 + 글자(운영자 지시 — 자막은 상단으로 이동)."""
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    band_cy = (BOTTOM_Y + H) // 2
    font = load_font(56, bold=True, display=True)
    brand = BRAND
    tw = d.textlength(brand, font=font)

    logo_path = PROJECT_ROOT / "logo.png"
    logo_w = 0
    logo_img = None
    if logo_path.exists():
        logo_img = Image.open(logo_path).convert("RGBA")
        scale = int(BRAND_H * 0.56) / max(logo_img.size)
        logo_img = logo_img.resize(
            (int(logo_img.width * scale), int(logo_img.height * scale)), Image.Resampling.LANCZOS
        )
        logo_w = logo_img.width + 22

    total_w = logo_w + int(tw)
    x = (W - total_w) // 2
    if logo_img is not None:
        canvas.alpha_composite(logo_img, (x, band_cy - logo_img.height // 2))
        x += logo_w
    bb = d.textbbox((0, 0), brand, font=font)
    d.text((x, band_cy - (bb[3] - bb[1]) // 2 - bb[1]), brand, font=font, fill=WHITE,
           stroke_width=4, stroke_fill=(0, 0, 0))
    return _overlay(np.array(canvas), t_in, dur, fi=0.2, fo=0.2)


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
                 *, hook_title: str, fps: int = 30, end_card_dur: float = 1.0,
                 product_media: dict[str, Any] | None = None) -> Path:
    from clipcart.video.promo import tts_typecast

    pm = product_media or {}
    images = [p for p in (pm.get("images") or []) if p] or [product_img_path]
    video = pm.get("video")
    seller = None
    if video and Path(video).exists():
        try:
            seller = SellerVideo(video)
            if not seller.usable:
                # 자막투성이 영상 — 쓰지 않는다. video=None이면 productvideo 토큰이
                # None을 반환해 자연히 다음 소스(모션샷/실영상)로 폴백된다.
                print("  [promo] seller video too subtitled — fallback to other media")
                seller.close()
                seller, video = None, None
        except Exception as exc:  # noqa: BLE001 — 셀러영상 실패는 다른 소스로 폴백
            print(f"  [promo] seller video skipped ({str(exc)[:80]})")
            seller, video = None, None
    pex = sources.Pexels()
    print(f"  [promo] pexels={'on' if pex.enabled else 'off'} typecast={'on' if tts_typecast.available() else 'edge-fallback'}")

    # TTS per beat
    tts = []
    for b in beats:
        path, dur = tts_typecast.synth_or_edge(
            b["narration"].strip(), b.get("tone", "neutral"), voice=b.get("voice", "main")
        )
        tts.append((str(path), dur))

    def make_clip(path, kind, dur):
        # 셀러영상은 깨끗한(자막 적은) 구간을 매번 다르게 뽑아 쓴다
        if kind == "sellervideo" and seller is not None:
            try:
                return seller.next_segment(dur)
            except Exception as exc:  # noqa: BLE001
                print(f"  [promo] seller segment failed ({str(exc)[:80]})")
                return _media_clip(path, "video", dur)
        return _media_clip(path, kind, dur)

    STORY = is_story()
    media_segs, overlays, audio_segs, sfx_cues = [], [], [], []
    t = 0.0
    for i, (b, (apath, adur)) in enumerate(zip(beats, tts)):
        if STORY:
            # 컴팩트·박진감 — 증언↔메인 간격을 바짝 좁힌다(이전 0.30/0.42에서 축소)
            post = 0.10 if b["role"] == "hook" else 0.13
        else:
            post = 0.08 if b["role"] == "hook" else 0.12
        beat_dur = adur + post
        col = (_STORY_COLOR.get(b.get("color", "white"), CHARCOAL) if STORY
               else _color(b.get("color", "white")))

        # media — 멀티샷(shots)이면 비트 시간을 나눠 퀵컷, 아니면 단일 소스
        shots = b.get("shots")
        if shots:
            # 샷당 최소 0.8초 확보 (짧으면 샷 수 축소)
            n = max(1, min(len(shots), int(beat_dur // 0.8) or 1))
            sub_dur = beat_dur / n
            sub_clips = []
            for si in range(n):
                tokens = [shots[si]] + ([b["fallback"]] if b.get("fallback") else [])
                path, kind = _resolve_media(pex, tokens, product_img_path, si, images, video)
                sub_clips.append(make_clip(path, kind, sub_dur))
                if si > 0 and not STORY:
                    sfx_cues.append((sfx.whoosh(), t + si * sub_dur, 0.35))
            media_segs.append(concatenate_videoclips(sub_clips, method="chain").with_duration(beat_dur))
        else:
            tokens = [b["source"]] + ([b["fallback"]] if b.get("fallback") else [])
            path, kind = _resolve_media(pex, tokens, product_img_path, 0, images, video)
            media_segs.append(make_clip(path, kind, beat_dur))

        # SFX: whoosh on cut, impact on hook/emphasis (story는 부드러운 톤 — 생략)
        if i > 0 and not STORY:
            sfx_cues.append((sfx.whoosh(), t, 0.5))
        if b["role"] == "hook" and not STORY:
            sfx_cues.append((sfx.riser(), t + 0.02, 0.45))

        # bottom narration — 실제 나레이션을 의미단위로, 음성에 맞춰(글자수 비례) 노출
        units = _meaning_units(b["narration"], max_eojeol=4)
        csum = sum(_korlen(u) for u in units)
        ut = t
        for u in units:
            ud = beat_dur * (_korlen(u) / csum)
            png = _subtitle_png(u)
            overlays.append(_overlay(png, ut, ud + 0.04, fi=0.03, fo=0.03))
            ut += ud

        # emphasis slam — 강조어가 실제 발화되는 시점(글자 위치 비례)에 크게 꽝
        emp = b.get("emphasis")
        if emp:
            narr = b["narration"]
            pos = narr.find(emp)
            frac = (_korlen(narr[:pos]) / _korlen(narr)) if pos >= 0 else 0.35
            hold = min(1.1, max(0.7, beat_dur * 0.4))
            est = max(t + 0.1, min(t + beat_dur * frac, t + beat_dur - hold))
            if STORY:
                # 중앙 강조 — 흰 배경 칩 + 검정 글씨(모던), 부드러운 페이드 + 약한 팝
                png = _story_emph_png(emp, max_size=120, min_size=72)
                overlays.append(_overlay(png, est, hold, fi=0.2, fo=0.18))
                sfx_cues.append((sfx.pop(), est, 0.16))
            else:
                png = _draw_block(emp, _FONT_BOLD, MEDIA_Y + int(MEDIA_H * 0.28),
                                  MEDIA_Y + int(MEDIA_H * 0.72), max_size=220, min_size=96,
                                  stroke=12, color=col, display=True)
                overlays.append(_overlay(png, est, hold, fi=0.05, fo=0.12))
                sfx_cues.append((sfx.pop(), est, 0.55))

        # 고지(baked, bottom) — 훅(시작)·cta(끝) 비트의 소스별 고지를 그린다
        if b.get("disclosure"):
            if STORY:
                disc = _draw_block(b["disclosure"], _FONT_REG, int(0.70 * H), int(0.78 * H),
                                   max_size=32, min_size=22, stroke=2, color=CHARCOAL, modern=True)
            else:
                disc = _draw_block(b["disclosure"], _FONT_REG, int(0.70 * H), int(0.78 * H),
                                   max_size=34, min_size=24, stroke=3, color=DIM)
            overlays.append(_overlay(disc, t + 0.1, beat_dur - 0.15, fi=0.1, fo=0.1))

        audio_segs.append(AudioFileClip(apath).with_start(t))
        t += beat_dur

    total_narr = t
    end_start = t
    total = t + end_card_dur

    # compose — story는 크림 배경, promo는 검정(ink)
    ink_bg = ColorClip((W, H), color=(CREAM if STORY else INK), duration=total)

    # 상단=자막(overlays), 하단=브랜드 바. 지속 훅 타이틀은 제거(첫 자막이 훅을 그대로 노출).
    ad_badge = _overlay(_ad_badge_png(), 0.0, total, fi=0.0, fo=0.0)
    brand_bar = _brand_bar_overlay(0.0, total_narr)

    # story: 하드컷+휘익 대신 부드러운 크로스디졸브(미디어 세그먼트를 개별 레이어로 배치,
    # 각 세그 CrossFadeIn/Out → 배경 크림으로 살짝 녹았다 나오는 소프트 전환). 오디오
    # 타임라인은 비트 경계 t 그대로라 A/V 싱크·총길이 보존. 실패 시 하드컷 폴백.
    media_layers = None
    if STORY:
        try:
            ov = 0.22
            media_layers = []
            tcur = 0.0
            for seg in media_segs:
                clip = (seg.with_position((0, MEDIA_Y)).with_start(tcur)
                        .with_effects([vfx.CrossFadeIn(ov), vfx.CrossFadeOut(ov)]))
                media_layers.append(clip)
                tcur += float(seg.duration)
        except Exception as exc:  # noqa: BLE001 — 크로스페이드 실패 시 하드컷 폴백
            print(f"  [promo] story crossfade failed ({str(exc)[:80]}); hard-cut fallback")
            media_layers = None

    if media_layers is not None:
        layers = [ink_bg, *media_layers, brand_bar, *overlays, ad_badge]
    else:
        media_track = (concatenate_videoclips(media_segs, method="chain")
                       .with_position((0, MEDIA_Y)).with_start(0))
        layers = [ink_bg, media_track, brand_bar, *overlays, ad_badge]

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

    if not STORY:
        sfx_cues.append((sfx.thud(), end_start + 0.05, 0.5))
    _mix_sfx(tmp, sfx_cues, out)
    tmp.unlink(missing_ok=True)
    if seller is not None:
        seller.close()
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
