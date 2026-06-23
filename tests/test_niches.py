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
