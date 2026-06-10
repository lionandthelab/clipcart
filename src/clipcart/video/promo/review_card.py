"""실데이터 리뷰 요약 카드 — 상품 페이지 캡처풍.

API가 주는 실측치(평점 %, 누적 주문수)만 그린다. 허위 후기 작성은
금지행동(CLAUDE.md 1.2)이므로 사용자 댓글 텍스트를 날조하지 않으며,
데이터가 없으면 카드를 만들지 않는다(None). 출처 라벨을 카드에 명기한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from clipcart.video.fonts import load_font

# promo 에디터 미디어 밴드 크기에 정확히 맞춰 잘림 없이 들어간다
CARD_W, CARD_H = 1080, 1210

_BG = (242, 243, 245)
_CARD = (255, 255, 255)
_INK = (28, 30, 34)
_SUB = (110, 115, 124)
_STAR = (255, 168, 0)
_STAR_DIM = (224, 226, 230)
_ACCENT = (214, 48, 49)


def review_summary(product: dict[str, Any]) -> dict[str, Any] | None:
    """실측치 요약. 평점이 없으면 None — 카드 생성 금지."""
    rating = product.get("rating")
    try:
        rating = float(rating)
    except (TypeError, ValueError):
        return None
    if rating <= 0:
        return None
    orders = int(product.get("review_count") or 0)
    source = (product.get("source") or "").lower()
    platform = "알리익스프레스" if "ali" in source else "쿠팡"
    return {
        "stars": round(rating / 20, 1),  # 95.6% → 4.8/5
        "satisfaction": f"{rating:g}%",
        "orders": orders,
        "platform": platform,
    }


def _stars_row(draw: ImageDraw.ImageDraw, x: int, y: int, stars: float, size: int) -> int:
    font = load_font(size, bold=True)
    full = int(stars)
    for i in range(5):
        color = _STAR if i < full or (i == full and stars - full >= 0.5) else _STAR_DIM
        draw.text((x, y), "★", font=font, fill=color)
        x += int(draw.textlength("★", font=font)) + 6
    return x


def compose_review_card(product: dict[str, Any], out_path: Path) -> Path | None:
    s = review_summary(product)
    if s is None:
        return None

    img = Image.new("RGB", (CARD_W, CARD_H), _BG)
    d = ImageDraw.Draw(img)

    # 흰 카드
    m = 70
    card_box = (m, 150, CARD_W - m, CARD_H - 150)
    d.rounded_rectangle(card_box, radius=36, fill=_CARD, outline=(228, 230, 234), width=2)

    cx0, cy = card_box[0] + 64, card_box[1] + 70

    # 헤더: 라벨 + 플랫폼
    f_label = load_font(40, bold=False)
    d.text((cx0, cy), "구매자 평가", font=f_label, fill=_SUB)
    plat = f"{s['platform']} 상품 페이지"
    pw = int(d.textlength(plat, font=f_label))
    d.text((card_box[2] - 64 - pw, cy), plat, font=f_label, fill=_SUB)
    cy += 96

    # 큰 별점 수치 + 별
    f_big = load_font(150, bold=True)
    num = f"{s['stars']:.1f}"
    d.text((cx0, cy), num, font=f_big, fill=_INK)
    nx = cx0 + int(d.textlength(num, font=f_big)) + 36
    _stars_row(d, nx, cy + 58, s["stars"], 72)
    cy += 220

    # 만족도 / 누적 주문 (실측치)
    f_kv = load_font(56, bold=True)
    f_kv_sub = load_font(42, bold=False)
    d.text((cx0, cy), f"구매자 만족도 {s['satisfaction']}", font=f_kv, fill=_INK)
    cy += 96
    if s["orders"] > 0:
        d.text((cx0, cy), f"누적 주문 {s['orders']:,}건+", font=f_kv, fill=_ACCENT)
        cy += 96
    d.text((cx0, cy + 8), "구매 전 최근 후기와 옵션을 꼭 확인하세요", font=f_kv_sub, fill=_SUB)

    # 출처 명기 (정직성 — 캡처풍이지만 실데이터 출처를 밝힌다)
    f_src = load_font(34, bold=False)
    src_text = f"출처: {s['platform']} 상품 페이지 실측 데이터"
    sw = int(d.textlength(src_text, font=f_src))
    d.text(((CARD_W - sw) // 2, card_box[3] + 44), src_text, font=f_src, fill=_SUB)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path
