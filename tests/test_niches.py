"""니치 풀 회귀 가드 — 새 니치 추가 시 스키마/컴플라이언스 실수를 막는다."""

from __future__ import annotations

from clipcart.research.niches import NICHES
from clipcart.video.compliance import BANNED_EXPRESSIONS

REQUIRED = [
    "keyword", "category", "title_keyword", "old_way",
    "hook", "problem", "usage", "benefit", "downside", "target",
]


def test_all_niches_have_required_nonempty_fields():
    for n in NICHES:
        for f in REQUIRED:
            assert n.get(f, "").strip(), f"{n.get('keyword')} 필드 누락: {f}"


def test_no_niche_contains_banned_expression():
    for n in NICHES:
        blob = " ".join(n.get(f, "") for f in REQUIRED)
        bad = [b for b in BANNED_EXPRESSIONS if b in blob]
        assert not bad, f"{n['keyword']} 금지표현 포함: {bad}"


def test_niche_keywords_unique():
    kws = [n["keyword"] for n in NICHES]
    assert len(kws) == len(set(kws)), "중복 keyword 존재"


def test_niche_pool_covers_cadence():
    # 알리 4편/일 × 니치 겹침 회피 10일 = 약 40 니치 필요. 풀이 그보다 넉넉해야
    # 선정이 막히지 않는다(2026-06-23 업로드 중단 원인이 풀 부족+큐버그였음).
    assert len(NICHES) >= 40


def test_pet_category_is_paused():
    # 조회수 664/662뷰로 지속 최하위 — 일시 중단(2026-06-27). 재개 시 이 테스트 삭제.
    pet = [n for n in NICHES if n.get("category") == "반려동물"]
    assert not pet, f"반려동물 카테고리 중단 중: {[n['keyword'] for n in pet]}"


def test_electric_appliance_products_are_excluded():
    # 로봇청소기·전동/진공 가전은 제외 카테고리(고가 가전·전기 안전)
    from clipcart.research.niches import PRODUCT_EXCLUDE_KEYWORDS

    def excluded(name):  # _is_excluded와 동일: 원문 그대로 부분일치
        return any(kw in name for kw in PRODUCT_EXCLUDE_KEYWORDS)

    assert excluded("스마트 진공 청소 로봇 미니 물걸레 흡입 및 청소 통합형 완전 자동 청소 로봇")
    assert excluded("무선 전동 진공청소기 가정용")
    # 비전기 생활용품은 통과해야 함(오탐 방지)
    assert not excluded("극세사 물걸레 청소포 100매")
    assert not excluded("유리창 양면 자석 청소기")  # 수동 자석 청소기는 가전 아님
    assert not excluded("욕실 흡착 선반")            # 흡착(吸着)은 흡입(吸入)과 다름
