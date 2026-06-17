"""'model' 템플릿(미모 여성 광고) 장면·프롬프트 계획 테스트.

GPT-image-2로 인물+제품을 레퍼런스 일관성 있게 생성 → Kling 모션. ≤15초,
말 적게, 모던/쿨한 광고. 순수 계획 로직만 테스트(생성·렌더는 수동 검증).
"""

from __future__ import annotations

from clipcart.disclosure import disclosure_for
from clipcart.video.compliance import check_texts
from clipcart.video.promo.model import model_compliance_scenes, model_scenes


def _product(name="확장형 스텐 빨래건조대", price=39000, bundle=False):
    return {
        "product_id": "AE_M1",
        "product_name": "세탁기 먼지 거름망 30매" if bundle else name,
        "display_name": "스텐 건조대",
        "source": "aliexpress",
        "price": 3900 if bundle else price,
        "affiliate_url": "https://s.click.aliexpress.com/e/_X",
        "niche": {
            "keyword": "스텐 빨래 건조대 대형", "category": "세탁",
            "title_keyword": "스텐 건조대", "old_way": "휘청대는 건조대",
            "hook": "빨래 건조대, 자꾸 휘청거리고 모자라죠?",
            "problem": "p", "usage": "u", "benefit": "b",
            "downside": "부피가 좀 있어요", "target": "t",
        },
    }


def test_three_scenes_with_expected_roles():
    scenes = model_scenes(_product())
    assert [s["role"] for s in scenes] == ["hero", "lifestyle", "closing"]


def test_gen_prompts_enforce_persona_and_product_consistency():
    for s in model_scenes(_product()):
        g = s["gen"].lower()
        assert "woman" in g                      # 미모 여성
        assert "identical" in g                  # 제품 일관성
        assert "9:16" in s["gen"]                # 세로
        assert "no text" in g                    # 자막/워터마크 금지(자막은 우리가 얹음)


def test_motion_prompt_keeps_product_identical():
    for s in model_scenes(_product()):
        assert "identical" in s["motion"].lower()


def test_narration_is_minimal_and_purposeful():
    scenes = model_scenes(_product())
    narr = {s["role"]: s["narration"] for s in scenes}
    assert narr["hero"] == "빨래 건조대, 자꾸 휘청거리고 모자라죠?"  # 훅
    assert narr["lifestyle"] == ""  # 비주얼 순간(무음)
    assert "프로필 링크" in narr["closing"]
    # 말 적게: 비어있지 않은 내레이션은 2개 이하
    assert sum(1 for v in narr.values() if v.strip()) <= 2


def test_closing_uses_price_and_per_unit_for_bundle():
    closing = next(s for s in model_scenes(_product(bundle=True)) if s["role"] == "closing")
    assert "개당 약 130원" in closing["narration"]  # 3900/30


def test_closing_uses_total_price_for_single_item():
    closing = next(s for s in model_scenes(_product()) if s["role"] == "closing")
    assert "39,000원" in closing["narration"]


def test_no_banned_words_in_narration():
    for s in model_scenes(_product()):
        for banned in ("무조건", "100%", "완벽", "평생", "효과 보장"):
            assert banned not in s["narration"]


def test_compliance_scenes_pass_gate():
    product = _product()
    scenes = model_scenes(product)
    creative = {
        "title": "스텐 건조대",
        "description": f"{disclosure_for(product)}\n\n좋은 제품.",
        "disclosure": disclosure_for(product),
        "scenes": model_compliance_scenes(product, scenes),
    }
    # 시작·끝 고지 + 설명란 고지 → 게이트 통과
    assert check_texts(creative) == []
    assert creative["scenes"][0]["disclosure"] == disclosure_for(product)
    assert creative["scenes"][-1]["disclosure"] == disclosure_for(product)
