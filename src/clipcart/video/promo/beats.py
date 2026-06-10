"""marketing_promo 비트 생성 — 제품+니치 → hook→problem→product→proof→cta.

steward-lab video_engine 의 Beat/ShortScript 구조를 clipcart로 단순화.
각 비트: role, narration(KO/TTS), caption(자막), tone(감정), source(미디어 소스),
emphasis(슬램 단어), color. source는 'pexels:<query>' | 'product' | 'gemini:<subject>'.
내레이션은 살림해결소 문체 규칙 준수(과장 금지, 단점 1개, 확정형 고지).
"""

from __future__ import annotations

from typing import Any

from clipcart.coupang import COUPANG_DISCLOSURE
from clipcart.research.auto_select import short_product_name
from clipcart.video.promo.broll import get_broll


def build_beats(product: dict[str, Any]) -> list[dict[str, Any]]:
    niche = product["niche"]
    name = short_product_name(product)
    price = product["price"]
    rocket = product.get("is_rocket", False)
    br = get_broll(niche)

    rocket_line = "심지어 로켓배송이라 내일 와요." if rocket else "가격도 부담 없죠."

    beats: list[dict[str, Any]] = [
        {
            "role": "hook",
            "tone": "hook",
            "narration": niche["hook"],
            "caption": niche["hook"],
            "source": f"pexels:{br['pain']}",
            "emphasis": niche["title_keyword"],
            "color": "yellow",
        },
        {
            "role": "problem",
            "tone": "problem",
            "narration": niche["problem"],
            "caption": niche["problem"],
            "source": f"pexels:{br['pain']}",
            "color": "white",
        },
        {
            "role": "product",
            "tone": "product",
            "narration": f"해결책은 간단해요. {name}. 단돈 {price:,}원. {rocket_line}",
            "caption": f"{name} · {price:,}원",
            "source": "product",
            "emphasis": f"{price:,}원",
            "color": "red",
        },
        {
            "role": "usage",
            "tone": "usage",
            "narration": f"쓰는 법도 쉬워요. {niche['usage']}",
            "caption": niche["usage"],
            "source": f"pexels:{br['use']}",
            "color": "white",
        },
        {
            "role": "result",
            "tone": "result",
            "narration": f"{niche['benefit']} 이게 {price:,}원이면, 장바구니 안 담을 이유가 없죠.",
            "caption": niche["benefit"],
            "source": f"pexels:{br['clean']}",
            "emphasis": "장바구니",
            "color": "yellow",
        },
        {
            "role": "cta",
            "tone": "cta",
            "narration": f"단점도 솔직히 말할게요. {niche['downside']}. 그래도 끌린다면, 링크는 고정 댓글에 있어요.",
            "caption": "링크는 고정 댓글에 ▼",
            "source": "product",
            "color": "white",
            "disclosure": COUPANG_DISCLOSURE,
        },
    ]
    return beats


def beats_to_scenes(beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """컴플라이언스 검사가 쓰는 scenes 형태로 변환(narration/caption/disclosure)."""
    return [
        {
            "name": b["role"],
            "narration": b["narration"],
            "caption": b.get("caption", ""),
            "disclosure": b.get("disclosure"),
        }
        for b in beats
    ]
