"""promo 비트 생성 테스트 — 강조 자막(emphasis) 규칙."""

from __future__ import annotations

from clipcart.research.niches import NICHES
from clipcart.video.promo.beats import build_beats


def _product():
    niche = next(n for n in NICHES if n["keyword"] == "멀티탭 정리함")
    return {
        "product_id": "AE1",
        "product_name": "Toocki 사무실용 멀티탭 거치대 벽걸이 플러그, 무펀치",
        "display_name": niche["title_keyword"],
        "source": "aliexpress",
        "price": 2780,
        "niche": niche,
    }


def test_result_beat_emphasis_is_product_name_not_cart():
    beats = build_beats(_product())
    result = next(b for b in beats if b["role"] == "result")
    # 모든 영상에 '장바구니' 대형 자막이 박혀 썸네일처럼 노출되던 문제 —
    # 제품명(짧은 이름)이 나와야 한다.
    assert result.get("emphasis") != "장바구니"
    assert result.get("emphasis") == "멀티탭 정리함"


def test_hook_beat_emphasis_is_title_keyword():
    beats = build_beats(_product())
    hook = next(b for b in beats if b["role"] == "hook")
    assert hook.get("emphasis") == "멀티탭 정리함"
