"""Pillow 기반 장면 프레임/썸네일 합성.

흥행 쇼츠 자막 스타일 모방:
- 굵은 고딕 + 흰 글자 + 검정 외곽선
- 핵심 구절 노랑 강조
- 하단 중앙 배치, 훅은 중앙 대형
- 전 장면 좌상단 '광고 · 쿠팡 파트너스' 상시 노출 (공정위 표시)
"""

from __future__ import annotations

import io
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920

FONT_CANDIDATES_BOLD = [
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"C:\Windows\Fonts\malgun.ttf",
]
FONT_CANDIDATES_REGULAR = [
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\malgunbd.ttf",
]

WHITE = "#FFFFFF"
YELLOW = "#FFD400"
BLACK = "#000000"
DARK = "#15171B"
RED = "#FF3B30"


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES_BOLD if bold else FONT_CANDIDATES_REGULAR:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    raise RuntimeError("한글 폰트(맑은 고딕)를 찾을 수 없음")


def fetch_image(url: str) -> Image.Image:
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        timeout=30,
    )
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content))
    return img.convert("RGB")


def _cover_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    ratio = max(w / img.width, h / img.height)
    resized = img.resize((round(img.width * ratio), round(img.height * ratio)), Image.LANCZOS)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _fit_within(img: Image.Image, w: int, h: int) -> Image.Image:
    ratio = min(w / img.width, h / img.height)
    return img.resize((round(img.width * ratio), round(img.height * ratio)), Image.LANCZOS)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            # 단어 자체가 길면 글자 단위로 쪼갬
            while draw.textlength(word, font=font) > max_width and len(word) > 1:
                cut = len(word)
                while cut > 1 and draw.textlength(word[:cut], font=font) > max_width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    y: int,
    fill: str,
    stroke_width: int = 6,
    stroke_fill: str = BLACK,
    spacing: int = 18,
) -> int:
    for line in lines:
        width = draw.textlength(line, font=font)
        x = (W - width) // 2
        draw.text((x, y), line, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
        bbox = draw.textbbox((x, y), line, font=font, stroke_width=stroke_width)
        y = bbox[3] + spacing
    return y


def _bottom_gradient(canvas: Image.Image, height: int = 640, max_alpha: int = 170) -> None:
    overlay = Image.new("RGBA", (W, height), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for i in range(height):
        alpha = int(max_alpha * (i / height) ** 1.3)
        odraw.line([(0, i), (W, i)], fill=(0, 0, 0, alpha))
    canvas.paste(Image.alpha_composite(canvas.crop((0, H - height, W, H)).convert("RGBA"), overlay).convert("RGB"), (0, H - height))


def _pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.FreeTypeFont,
          fg: str, bg: tuple[int, int, int, int] | str, pad: tuple[int, int] = (28, 14)) -> tuple[int, int]:
    tw = draw.textlength(text, font=font)
    bbox = draw.textbbox((0, 0), text, font=font)
    th = bbox[3] - bbox[1]
    x, y = xy
    rect = (x, y, x + tw + pad[0] * 2, y + th + pad[1] * 2)
    draw.rounded_rectangle(rect, radius=(rect[3] - rect[1]) // 2, fill=bg)
    draw.text((x + pad[0], y + pad[1] - bbox[1]), text, font=font, fill=fg)
    return rect[2], rect[3]


def _chrome(canvas: Image.Image) -> None:
    """전 장면 공통: 광고 표시 + 브랜드 (줌 크롭에도 안 잘리는 안전 영역)."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    _pill(draw, (44, 152), "광고 · 쿠팡 파트너스 수수료 지급", _font(34), WHITE, (0, 0, 0, 150))
    brand_font = _font(36)
    brand = "살림해결소"
    bw = draw.textlength(brand, font=brand_font)
    draw.text((W - bw - 48, 158), brand, font=brand_font, fill=WHITE, stroke_width=4, stroke_fill=(0, 0, 0))


def _bg_blur_dark(product_img: Image.Image, dark: int = 150) -> Image.Image:
    bg = _cover_crop(product_img, W, H).filter(ImageFilter.GaussianBlur(20))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, dark))
    return Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")


def _bg_zoom_focus(product_img: Image.Image) -> Image.Image:
    canvas = _cover_crop(product_img, W, H)
    _bottom_gradient(canvas)
    return canvas


def _bg_white_card(product_img: Image.Image) -> Image.Image:
    canvas = Image.new("RGB", (W, H), "#F4F4F1")
    card_w, card_h = 880, 880
    card = Image.new("RGB", (card_w, card_h), WHITE)
    fitted = _fit_within(product_img, card_w - 80, card_h - 80)
    card.paste(fitted, ((card_w - fitted.width) // 2, (card_h - fitted.height) // 2))
    # 그림자
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sx, sy = (W - card_w) // 2, 430
    sdraw.rounded_rectangle((sx + 12, sy + 18, sx + card_w + 12, sy + card_h + 18), radius=48, fill=(0, 0, 0, 60))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow).convert("RGB")
    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w, card_h), radius=48, fill=255)
    canvas.paste(card, (sx, sy), mask)
    return canvas


def compose_scene_frame(product_img: Image.Image, scene: dict, out_path: Path) -> Path:
    """scene: name/style/accent/caption/sub/price_text/rocket/disclosure"""
    style = scene.get("style", "zoom_focus")
    if style == "blur_dark":
        canvas = _bg_blur_dark(product_img)
    elif style == "white_card":
        canvas = _bg_white_card(product_img)
    else:
        canvas = _bg_zoom_focus(product_img)

    draw = ImageDraw.Draw(canvas, "RGBA")
    on_light = style == "white_card"
    primary_fill = DARK if on_light else WHITE
    stroke = 0 if on_light else 7

    name = scene.get("name", "")

    if name == "hook":
        accent_font = _font(104)
        caption_font = _font(82)
        y = 640
        if scene.get("accent"):
            y = _draw_lines(draw, _wrap(draw, scene["accent"], accent_font, W - 140), accent_font, y, YELLOW, 8)
            y += 14
        if scene.get("caption"):
            _draw_lines(draw, _wrap(draw, scene["caption"], caption_font, W - 140), caption_font, y, WHITE, 8)

    elif name == "product":
        title_font = _font(76)
        _draw_lines(draw, _wrap(draw, scene.get("caption", ""), title_font, W - 160), title_font, 200, primary_fill, stroke)
        badge_font = _font(56)
        bx = 280
        if scene.get("price_text"):
            price_w = draw.textlength(scene["price_text"], font=badge_font) + 64
            rocket_w = (draw.textlength("로켓배송", font=badge_font) + 64 + 24) if scene.get("rocket") else 0
            bx = int((W - price_w - rocket_w) // 2)
            end_x, _ = _pill(draw, (bx, 1430), scene["price_text"], badge_font, WHITE, RED, pad=(32, 18))
            if scene.get("rocket"):
                _pill(draw, (end_x + 24, 1430), "로켓배송", badge_font, WHITE, "#1A73E8", pad=(32, 18))
        if scene.get("sub"):
            sub_font = _font(48)
            _draw_lines(draw, _wrap(draw, scene["sub"], sub_font, W - 200), sub_font, 1600, "#444444" if on_light else WHITE, 0 if on_light else 5)

    elif name == "downside_cta":
        accent_font = _font(84)
        body_font = _font(62)
        y = 480
        y = _draw_lines(draw, ["아쉬운 점 하나"], accent_font, y, YELLOW, 8)
        y += 16
        y = _draw_lines(draw, _wrap(draw, scene.get("caption", ""), body_font, W - 150), body_font, y, WHITE, 7)
        cta_font = _font(72)
        _draw_lines(draw, ["구매 링크는 설명란에 ▼"], cta_font, 1430, YELLOW, 8)
        if scene.get("disclosure"):
            disc_font = _font(34, bold=False)
            _draw_lines(draw, _wrap(draw, scene["disclosure"], disc_font, W - 140), disc_font, 1640, "#DDDDDD", 3, spacing=8)

    else:  # problem / usage / result
        caption_font = _font(72)
        lines = _wrap(draw, scene.get("caption", ""), caption_font, W - 130)
        block_h = len(lines) * 100
        _draw_lines(draw, lines, caption_font, H - 360 - block_h, primary_fill, stroke)

    _chrome(canvas)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG")
    return out_path


def compose_thumbnail(product_img: Image.Image, line1: str, line2: str, out_path: Path) -> Path:
    """흥행 스타일 썸네일: 대형 훅 텍스트 + 제품 카드."""
    canvas = _bg_blur_dark(product_img, dark=120)
    card = _fit_within(product_img, 760, 760)
    px, py = (W - card.width) // 2, 760
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *card.size), radius=40, fill=255)
    canvas.paste(card, (px, py), mask)

    draw = ImageDraw.Draw(canvas, "RGBA")
    f1 = _font(120)
    f2 = _font(96)
    y = _draw_lines(draw, _wrap(draw, line1, f1, W - 100), f1, 260, YELLOW, 10)
    _draw_lines(draw, _wrap(draw, line2, f2, W - 100), f2, y + 6, WHITE, 9)
    _chrome(canvas)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "JPEG", quality=90)
    return out_path
