"""묶음 수량 파싱 + 개당 가격.

압도적으로 싼 제품을 어필할 때, 묶음이면 개당 가격을 알려준다. 잘못된 개당
표기는 신뢰를 깨므로(허위 가격) 애매하면 단품으로 본다:
- 옵션 표기('30/20/10장')나 서로 다른 수량 토큰이 여럿이면 묶음으로 안 봄.
- 치수·용량 단위(cm/kg/ml/단 등)는 수량이 아니다.
"""

from __future__ import annotations

import re

# 한글 카운터는 \b가 한국어 접미사(10매입)에서 깨지므로 경계 없이, 라틴(p/pcs)은
# 오탐 방지로 경계와 함께 매칭한다. 긴 단위(개입)를 앞에 둬 우선 매칭.
_COUNT_KO = re.compile(r"(\d+)\s*(개입|개|장|매|입|팩|세트)")
_COUNT_EN = re.compile(r"(\d+)\s*(pcs|p)\b", re.IGNORECASE)
_UNIT_NORM = {"개입": "개", "입": "개", "팩": "개", "세트": "세트", "pcs": "개", "p": "개"}
_MAX_SANE = 500  # 이보다 큰 '수량'은 파싱 오류로 보고 무시


def parse_pack(name: str) -> tuple[int, str]:
    """상품명에서 (묶음 수량, 단위어) 추출. 애매하면 (1, '개')."""
    text = name or ""
    # 옵션 표기('30/20/10') → 단일 묶음 수량 아님
    if re.search(r"\d+\s*/\s*\d+", text):
        return 1, "개"
    matches = _COUNT_KO.findall(text) + _COUNT_EN.findall(text)
    counts: list[tuple[int, str]] = []
    for num, unit in matches:
        n = int(num)
        if 2 <= n <= _MAX_SANE:
            counts.append((n, _UNIT_NORM.get(unit.lower(), unit)))
    if not counts:
        return 1, "개"
    distinct = {c[0] for c in counts}
    if len(distinct) != 1:
        return 1, "개"  # 서로 다른 수량 토큰 다수 → 보수적
    return counts[0]


def per_unit_price(price: int, count: int) -> int:
    if not count or count <= 0:
        return 0
    return round(price / count)


def unit_phrase(price: int, count: int) -> str | None:
    """개당 가격 문구. 진짜 묶음(2개 이상, 현실적 수량)일 때만."""
    if count < 2 or count > _MAX_SANE:
        return None
    pu = per_unit_price(price, count)
    if pu <= 0:
        return None
    return f"개당 약 {pu:,}원"
