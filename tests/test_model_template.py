"""'model' 템플릿 — 모델 사용 클립 생성 프롬프트 테스트.

운영자 지시(2026-06-19): 별도 몽타주 대신 일반 promo 구성에 모델 사용 영상을
처음·중간에만 끼워넣는다. 모델 클립의 인물 페르소나(30대 후반·가정일)와 제품
일관성 지시만 여기서 검증한다. 클립 주입(modelclip 토큰) 배치는 test_beats.py.
"""

from __future__ import annotations

from clipcart.video.promo.model import model_scenes


def _product():
    return {
        "product_id": "AE_M1",
        "product_name": "확장형 스텐 빨래건조대",
        "display_name": "스텐 건조대",
        "source": "aliexpress",
        "price": 39000,
        "image_url": "https://img/x.jpg",
        "niche": {"keyword": "스텐 빨래 건조대 대형", "category": "세탁",
                  "title_keyword": "스텐 건조대", "hook": "h", "problem": "p",
                  "usage": "u", "benefit": "b", "downside": "d", "old_way": "o", "target": "t"},
    }


def test_two_model_clips_for_start_and_middle():
    scenes = model_scenes(_product())
    assert [s["role"] for s in scenes] == ["hero", "use"]


def test_gen_prompts_show_late30s_woman_using_product():
    for s in model_scenes(_product()):
        g = s["gen"].lower()
        assert "woman" in g
        assert "late thirties" in g          # 30대 후반(운영자 지시)
        assert "use" in g                     # 사용하는 모습(정적 토킹헤드 아님)
        assert "identical" in g               # 제품 일관성
        assert "9:16" in s["gen"]             # 세로
        assert "no text" in g                 # 워터마크/자막 금지


def test_motion_prompts_keep_product_identical():
    for s in model_scenes(_product()):
        assert "identical" in s["motion"].lower()
