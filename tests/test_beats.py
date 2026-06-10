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


def test_problem_scene_is_candid_without_people():
    # AI 특유의 사람 등장 금지 — 배경/상황만 실사 폰카풍
    beats = build_beats(_product())
    problem = next(b for b in beats if b["role"] == "problem")
    assert problem["source"].startswith("gemini:")
    prompt = problem["source"]
    assert "no people" in prompt
    assert "person" not in prompt.lower().replace("no people", "")


def test_usage_beat_has_multi_shots():
    # 실사용 장면: 짧게 여러 구도(2개 이상 샷) 퀵컷
    beats = build_beats(_product())
    usage = next(b for b in beats if b["role"] == "usage")
    shots = usage.get("shots")
    assert shots and len(shots) >= 2
    assert any(s.startswith("pexels:") for s in shots)


def test_product_beat_uses_styled_product_shot():
    # 제품 추출 → 예쁜 배경/구도 화보샷 토큰, 실패 폴백은 원본 제품컷
    beats = build_beats(_product())
    product_beat = next(b for b in beats if b["role"] == "product")
    assert product_beat["source"].startswith("productshot:")
    assert product_beat.get("fallback") == "product"


def test_cta_uses_review_card_when_available():
    p = {**_product(), "review_card_path": "/tmp/card.png"}
    beats = build_beats(p)
    cta = next(b for b in beats if b["role"] == "cta")
    assert cta["source"] == "file:/tmp/card.png"
    assert cta.get("fallback") == "product"


def test_cta_falls_back_to_product_without_review_card():
    beats = build_beats(_product())
    cta = next(b for b in beats if b["role"] == "cta")
    assert cta["source"] == "product"
