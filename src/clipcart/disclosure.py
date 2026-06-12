"""상품 소스별 의무 고지 리졸버.

쿠팡 상품엔 쿠팡 파트너스 고지, 알리 상품엔 알리익스프레스 어필리에이트 고지를
쓴다. 소스가 다른데 같은 고지를 쓰면 허위 고지가 되므로(컴플라이언스 위반) 단일
진실원천으로 분기한다.
"""

from __future__ import annotations

from typing import Any

from clipcart.aliexpress import ALIEXPRESS_DISCLOSURE
from clipcart.coupang import COUPANG_DISCLOSURE


def disclosure_for(product: dict[str, Any]) -> str:
    source = (product.get("source") or "").lower()
    if "ali" in source:
        return ALIEXPRESS_DISCLOSURE
    return COUPANG_DISCLOSURE


# 썸네일/상단 배지용 표기 (2026-06-13 운영자 지시: 길게 쓰지 않고 '광고'만).
# 전체 고지는 설명란 첫 부분 + 영상 끝 자막(disclosure_for)에서 — 뱃지는 보조 표기.
AD_BADGE = "광고"
SHORT_DISCLOSURE_COUPANG = "광고 · 쿠팡 파트너스 수수료 지급"
SHORT_DISCLOSURE_ALIEXPRESS = "광고 · 알리익스프레스 어필리에이트"


def short_disclosure_for(product: dict[str, Any]) -> str:
    """소스별 짧은 배지 문구. 소스와 다른 고지를 쓰면 허위 고지가 되므로 분기한다."""
    source = (product.get("source") or "").lower()
    if "ali" in source:
        return SHORT_DISCLOSURE_ALIEXPRESS
    return SHORT_DISCLOSURE_COUPANG
