"""소스별 의무 고지 리졸버 테스트."""

from __future__ import annotations

from clipcart.aliexpress import ALIEXPRESS_DISCLOSURE
from clipcart.coupang import COUPANG_DISCLOSURE
from clipcart.disclosure import disclosure_for


def test_coupang_source_returns_coupang_disclosure():
    assert disclosure_for({"source": "coupang_partners"}) == COUPANG_DISCLOSURE


def test_aliexpress_source_returns_aliexpress_disclosure():
    assert disclosure_for({"source": "aliexpress"}) == ALIEXPRESS_DISCLOSURE


def test_unknown_source_falls_back_to_coupang():
    # 기존 쿠팡 파이프라인 호환 — source 미지정이면 쿠팡 고지
    assert disclosure_for({}) == COUPANG_DISCLOSURE
    assert disclosure_for({"source": "쿠팡"}) == COUPANG_DISCLOSURE
