"""영상 템플릿 선택 — CLIPCART_TEMPLATE.

- promo (기본): 검정 3단 광고 톤(휘익 슬램, 노랑/빨강 강조).
- story ("이야기 릴스"): 밝고 화사한 크림 톤, 부드러운 크로스페이드, 1인칭 관찰
  스토리텔링. 엔진을 갈아엎지 않고 분기로 공존한다 — story가 꺼지면 promo와
  완전히 동일하게 동작한다.

스펙: docs/templates/reels-storytelling.md
"""

from __future__ import annotations

import os


def current_template() -> str:
    return (os.getenv("CLIPCART_TEMPLATE", "") or "promo").strip().lower()


def is_story() -> bool:
    return current_template() == "story"
