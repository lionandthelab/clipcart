"""대본 스타일(레퍼토리) — 형식적 문장을 여러 톤으로 돌려 다양화.

전환/사용/결과/CTA 같은 '틀'에 해당하는 문장이 매번 똑같으면 AI스럽고
지루하다(운영자 피드백 2026-06-14). 상품별로 스타일을 골라 같은 구조라도
말투가 달라지게 한다. A/B용으로 CLIPCART_SCRIPT_STYLE로 강제할 수 있고,
선택된 스타일명은 posts/metrics에 기록돼 어떤 말투가 잘 먹히는지 비교한다.

어색했던 '{old_way}, 해보셨죠?'(명사구+동사어미 충돌)는 명사구에 자연스럽게
붙는 표현으로 교체한다.
"""

from __future__ import annotations

import hashlib
import os
from datetime import date
from typing import Any


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render_line(template: str, **ctx: Any) -> str:
    """스타일 문장 렌더. 누락 변수는 그대로 남겨(테스트가 잡도록) 한다."""
    return template.format_map(_SafeDict(**ctx))


# 각 스타일: 전환/사용/결과꼬리/CTA 문장 + 전환 자막·강조어.
# 모든 switch는 명사구 old_way에 자연스럽게 붙는다('해보셨죠' 금지).
SCRIPT_STYLES: list[dict[str, str]] = [
    {
        "name": "casual",  # 친근·구어체
        "switch": "{old_way}, 솔직히 좀 번거롭죠. 요즘은 이렇게들 바꿔요.",
        "switch_caption": "아직 그렇게 쓰세요?",
        "switch_emphasis": "요즘은 이렇게",
        "usage": "쓰는 것도 어렵지 않아요. {usage}",
        "result_tail": "이 가격이면 한번 써볼 만하죠.",
        "cta": "단점도 솔직히 있어요. {downside}. 링크는 고정 댓글에 둘게요.",
    },
    {
        "name": "direct",  # 직설·실용
        "switch": "{old_way}, 이제 안 해도 돼요.",
        "switch_caption": "이제 그만해도 됩니다",
        "switch_emphasis": "이제 안 해도 돼요",
        "usage": "방법은 간단해요. {usage}",
        "result_tail": "가격도 {price:,}원이라 부담 없고요.",
        "cta": "물론 {downside}. 자세한 건 고정 댓글 링크에서 확인하세요.",
    },
    {
        "name": "empathetic",  # 공감·스토리
        "switch": "{old_way}, 매번 은근 신경 쓰이죠. 이거 하나로 한결 편해져요.",
        "switch_caption": "매번 신경 쓰였다면",
        "switch_emphasis": "한결 편해져요",
        "usage": "사용법도 직관적이에요. {usage}",
        "result_tail": "그 정도 값이면 충분히 합리적이죠.",
        "cta": "아쉬운 점도 하나, {downside}. 구매 링크는 고정 댓글에 있어요.",
    },
]

_BY_NAME = {s["name"]: s for s in SCRIPT_STYLES}


def pick_script_style(product: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """(스타일명, 스타일) 반환. env 강제 우선, 아니면 상품ID 해시로 안정 선택."""
    forced = os.getenv("CLIPCART_SCRIPT_STYLE", "").strip()
    if forced in _BY_NAME:
        return forced, _BY_NAME[forced]
    seed = int(hashlib.md5(f"{date.today()}{product.get('product_id','')}".encode()).hexdigest(), 16)
    style = SCRIPT_STYLES[seed % len(SCRIPT_STYLES)]
    return style["name"], style
