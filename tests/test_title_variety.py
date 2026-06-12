"""제목 템플릿 다변화·기록 테스트.

같은 제품도 훅에 따라 성과가 크게 갈리므로, (1) 어떤 템플릿이 쓰였는지
creative에 기록해 metrics와 조인할 수 있게 하고, (2) 값 누락으로 영구
탈락하던 {target} 호명형을 살리고, (3) 판매량 데이터가 있을 때만 켜지는
사회적 증거형을 지원한다.
"""

from __future__ import annotations

from clipcart.video.copywriter import build_creative


def _product(**over):
    base = {
        "product_id": "CP123",
        "product_name": "스테인리스 배수구 거름망 채반",
        "display_name": "배수구 거름망",
        "source": "coupang_partners",
        "price": 6900,
        "is_rocket": True,
        "affiliate_url": "https://link.coupang.com/a/SHORT",
        "niche": {
            "keyword": "배수구 거름망 스테인리스",
            "category": "욕실",
            "title_keyword": "배수구 거름망",
            "old_way": "배수구 머리카락 손으로 빼기",
            "hook": "배수구 청소, 아직 손으로 하세요?",
            "problem": "샤워하고 나면 배수구에 머리카락이 한가득.",
            "usage": "배수구 위에 올려두기만 하면 됩니다.",
            "benefit": "손 안 대고 비울 수 있어요.",
            "downside": "배수구 지름이 안 맞으면 들뜰 수 있습니다",
            "target": "배수구 머리카락 치우는 게 곤욕인 사람",
        },
    }
    base.update(over)
    return base


def _profile(templates):
    return {"title_templates": templates, "description_template": "{disclosure}", "hashtags": [], "tags": []}


def test_creative_records_which_template_was_used():
    creative = build_creative(_product(), _profile(["아직도 {old_way}? 이거 보세요"]))
    assert creative["title_template"] == "아직도 {old_way}? 이거 보세요"
    assert creative["title"] == "아직도 배수구 머리카락 손으로 빼기? 이거 보세요"


def test_target_callout_template_renders():
    creative = build_creative(_product(), _profile(["{target}만 보세요"]))
    assert creative["title"] == "배수구 머리카락 치우는 게 곤욕인 사람만 보세요"
    assert creative["title_template"] == "{target}만 보세요"


def test_sold_count_template_used_when_volume_exists():
    ali = _product(source="aliexpress", review_count=1284, rating=96.0)
    creative = build_creative(ali, _profile(["{sold_count}개 팔린 {title_keyword}, 단점까지 보세요"]))
    assert creative["title"] == "1,284개 팔린 배수구 거름망, 단점까지 보세요"


def test_sold_count_template_skipped_without_volume():
    # 쿠팡 API엔 판매량/리뷰 수가 없다 — 값 없으면 해당 템플릿은 자동 탈락하고 폴백
    creative = build_creative(
        _product(),
        _profile(["{sold_count}개 팔린 {title_keyword}, 단점까지 보세요", "{hook}"]),
    )
    assert creative["title"] == "배수구 청소, 아직 손으로 하세요?"
    assert creative["title_template"] == "{hook}"
