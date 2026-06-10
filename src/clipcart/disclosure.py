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
