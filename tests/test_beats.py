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


def test_product_beat_uses_motion_product_shot():
    # 제품 추출 → 화보샷 → Kling 모션 클립. 실패 폴백 체인은 화보샷 → 원본 제품컷
    beats = build_beats(_product())
    product_beat = next(b for b in beats if b["role"] == "product")
    assert product_beat["source"].startswith("motionshot:")
    assert product_beat.get("fallback") == "product"


def test_usage_includes_motion_shot():
    beats = build_beats(_product())
    usage = next(b for b in beats if b["role"] == "usage")
    assert any(s.startswith("motionshot:") for s in usage["shots"])


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


def test_switch_beat_between_problem_and_product():
    # "다른 제품/방법 써봤지만 실망 → 이번엔 다르다" 전환 비트로 구매의욕 자극
    beats = build_beats(_product())
    roles = [b["role"] for b in beats]
    assert "switch" in roles
    assert roles.index("problem") < roles.index("switch") < roles.index("product")


def test_switch_narration_references_old_way_naturally():
    beats = build_beats(_product())
    switch = next(b for b in beats if b["role"] == "switch")
    niche_old_way = "바닥 멀티탭 먼지 방치"
    assert niche_old_way in switch["narration"]
    # 명사구 old_way에 어색하게 '해보셨죠?'를 붙이지 않는다(2026-06-14 피드백)
    assert "해보셨죠" not in switch["narration"]
    # 과장/보장 금지 표현이 들어가면 안 된다
    for banned in ("무조건", "100%", "완벽", "효과 보장"):
        assert banned not in switch["narration"]


def test_switch_scene_shows_product_or_usage():
    # 전환은 거부감 대신 제품/사용 모습으로(운영자 지시 2026-06-19)
    beats = build_beats(_product())
    switch = next(b for b in beats if b["role"] == "switch")
    blob = (switch.get("source", "") + " " + " ".join(switch.get("shots") or [])).lower()
    assert any(k in blob for k in ("product", "use"))


def test_big_discount_pops_in_product_beat():
    p = {**_product(), "original_price": 5560, "discount_pct": 50}
    beats = build_beats(p)
    product_beat = next(b for b in beats if b["role"] == "product")
    assert "50%" in product_beat["narration"]
    assert product_beat["emphasis"] == "50% 할인"
    # 정가도 실측치 그대로 노출
    assert "5,560" in product_beat["narration"]


def test_without_discount_price_emphasis_as_before():
    beats = build_beats(_product())
    product_beat = next(b for b in beats if b["role"] == "product")
    assert product_beat["emphasis"] == "2,780원"


def test_high_satisfaction_and_orders_pop_in_result_beat():
    p = {**_product(), "rating": 95.6, "review_count": 396}
    beats = build_beats(p)
    result = next(b for b in beats if b["role"] == "result")
    assert "95.6%" in result["narration"]
    assert "396" in result["narration"]
    # 숫자 팡: result 강조는 만족도 수치
    assert result["emphasis"] == "만족도 95.6%"


def test_weak_stats_are_not_woven_into_script():
    # 낮은 수치는 날조/과장 인상만 주므로 대본에 넣지 않는다
    p = {**_product(), "rating": 78.0, "review_count": 12}
    beats = build_beats(p)
    result = next(b for b in beats if b["role"] == "result")
    assert "78%" not in result["narration"]
    assert "만족도" not in result["narration"]
    assert result["emphasis"] == "멀티탭 정리함"  # 제품명 유지(썸네일 프레임)


def test_testimony_voice_in_front_problem_not_on_cta():
    # 운영자 지시(2026-06-22): 증언 목소리가 마지막 CTA('댓글 확인하세요')까지 하면
    # 어색하다 → 증언은 앞부분(공감되는 문제 장면)에서, 결과·CTA는 메인 나레이션.
    beats = build_beats(_product())
    voices = {b["role"]: b.get("voice") for b in beats}
    assert voices["problem"] == "testimony"
    assert voices.get("cta") in (None, "main")
    assert voices.get("result") in (None, "main")


def test_model_template_injects_model_clips_at_start_and_middle(monkeypatch):
    # 운영자 지시(2026-06-19): 깜빡이는 몽타주 대신 기존 promo 구성에 모델 영상을
    # 처음(hook)·중간(usage)에만 끼워넣는다.
    import clipcart.video.promo.beats as bmod
    monkeypatch.setattr(bmod, "is_model", lambda: True)
    beats = build_beats(_product())
    hook = next(b for b in beats if b["role"] == "hook")
    usage = next(b for b in beats if b["role"] == "usage")
    assert hook["source"] == "modelclip:0"
    assert (usage.get("shots") or [])[0] == "modelclip:1"


def test_promo_has_no_model_clip_tokens(monkeypatch):
    import clipcart.video.promo.beats as bmod
    monkeypatch.setattr(bmod, "is_model", lambda: False)
    beats = build_beats(_product())
    blob = " ".join((b.get("source", "") + " " + " ".join(b.get("shots") or [])) for b in beats)
    assert "modelclip" not in blob
