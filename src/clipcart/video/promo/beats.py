"""marketing_promo 비트 생성 — 제품+니치 → hook→problem→product→proof→cta.

steward-lab video_engine 의 Beat/ShortScript 구조를 clipcart로 단순화.
각 비트: role, narration(KO/TTS), caption(자막), tone(감정), source(미디어 소스),
emphasis(슬램 단어), color. source는 'pexels:<query>' | 'product' | 'gemini:<subject>'.
내레이션은 살림해결소 문체 규칙 준수(과장 금지, 단점 1개, 확정형 고지).
"""

from __future__ import annotations

from typing import Any

from clipcart.disclosure import disclosure_for
from clipcart.research.auto_select import short_product_name
from clipcart.video.promo.broll import get_broll


# 카테고리별 제품 화보샷 배경 (제품은 그대로, 배경/구도만 촬영한 듯하게)
_SHOT_SCENES: dict[str, list[str]] = {
    "주방": [
        "a bright marble kitchen counter in a sunlit Korean kitchen",
        "a warm wooden dining table near a window, morning light",
    ],
    "욕실": [
        "a clean white bathroom shelf with soft daylight and a small green plant",
        "light gray bathroom tiles with gentle window light",
    ],
    "정리/수납": [
        "a neat wooden shelf in a cozy minimal Korean apartment",
        "a tidy white desk near a bright window",
    ],
    "세탁": [
        "a bright laundry room counter with neatly folded towels",
        "a clean white shelf beside a modern washing machine",
    ],
    "청소": [
        "a bright clean living room floor with warm morning light",
        "a sunlit windowsill in a tidy Korean apartment",
    ],
    "반려동물": [
        "a cozy living room rug in warm afternoon light",
        "a soft neutral sofa corner with gentle daylight",
    ],
}
_DEFAULT_SCENES = [
    "a bright clean table in a cozy Korean apartment, soft window light",
    "a neat white shelf with warm natural light",
]


def _shot_scenes(category: str) -> list[str]:
    return _SHOT_SCENES.get(category, _DEFAULT_SCENES)


def build_beats(product: dict[str, Any]) -> list[dict[str, Any]]:
    niche = product["niche"]
    name = short_product_name(product)
    price = product["price"]
    rocket = product.get("is_rocket", False)
    br = get_broll(niche)
    scenes = _shot_scenes(product.get("category", ""))

    rocket_line = "심지어 로켓배송이라 내일 와요." if rocket else "가격도 부담 없죠."

    # 공감용 문제 장면 — AI티 방지: 사람/손 없이 배경·상황만 실사 폰카풍.
    # (생성 인물은 부자연스러워 공감을 깨므로 상황의 지저분함/귀찮음만 보여준다)
    empathy = (
        f"{br['pain']}, close-up of the messy frustrating situation itself, "
        f"grimy buildup and clutter clearly visible, no people, no hands"
    )

    # 실사용 컨텍스트 화보샷 — 실제 쓰이는 자리에 놓인 모습
    in_use_scene = (
        f"placed where it is actually used in a real Korean home ({scenes[0]}), "
        f"natural daily-life context"
    )

    review_card = product.get("review_card_path")

    beats: list[dict[str, Any]] = [
        {
            "role": "hook",
            "tone": "hook",
            "narration": niche["hook"],
            "caption": niche["hook"],
            # 훅: 실영상 우선(주목), 미스 시 공감 생성 이미지
            "source": f"pexels:{br['pain']}",
            "fallback": f"gemini:{empathy}",
            "emphasis": niche["title_keyword"],
            "color": "yellow",
        },
        {
            "role": "problem",
            "tone": "problem",
            "narration": niche["problem"],
            "caption": niche["problem"],
            # 문제: 공감 생성 이미지 우선(더러움/귀찮음 확실히), 미스 시 실영상
            "source": f"gemini:{empathy}",
            "fallback": f"pexels:{br['pain']}",
            "color": "white",
        },
        {
            "role": "product",
            "tone": "product",
            "narration": f"해결책은 간단해요. {name}. 단돈 {price:,}원. {rocket_line}",
            "caption": f"{name} · {price:,}원",
            # 제품 추출 → 예쁜 배경/구도 화보샷. 생성 실패 시 원본 제품컷.
            "source": f"productshot:{scenes[0]}",
            "fallback": "product",
            "emphasis": f"{price:,}원",
            "color": "red",
        },
        {
            "role": "usage",
            "tone": "usage",
            "narration": f"쓰는 법도 쉬워요. {niche['usage']}",
            "caption": niche["usage"],
            # 실사용 느낌 — 짧게 여러 구도 퀵컷 (실영상 2컷 + 실사용 자리 화보샷)
            "shots": [
                f"pexels:{br['use']}",
                f"productshot:{in_use_scene}",
                f"pexels:{br['use']}",
            ],
            "fallback": "product",
            "color": "white",
        },
        {
            "role": "result",
            "tone": "result",
            "narration": f"{niche['benefit']} 이게 {price:,}원이면, 장바구니 안 담을 이유가 없죠.",
            "caption": niche["benefit"],
            # 결과도 2컷 퀵컷: 깨끗해진 실영상 + 제품 화보샷
            "shots": [
                f"pexels:{br['clean']}",
                f"productshot:{scenes[1 % len(scenes)]}",
            ],
            "fallback": "product",
            # 대형 강조 자막이 썸네일 프레임으로 노출되는 경우가 많다 —
            # 범용 '장바구니' 대신 제품명을 박아 어떤 제품 영상인지 보이게 한다
            "emphasis": name,
            "color": "yellow",
        },
        {
            "role": "cta",
            "tone": "cta",
            "narration": f"단점도 솔직히 말할게요. {niche['downside']}. 그래도 끌린다면, 링크는 고정 댓글에 있어요.",
            "caption": "링크는 고정 댓글에 ▼",
            # 실데이터(평점/주문수) 리뷰 요약 카드 — 신빙성. 없으면 제품컷.
            "source": f"file:{review_card}" if review_card else "product",
            "fallback": "product",
            "color": "white",
            "disclosure": disclosure_for(product),
        },
    ]
    return beats


def beats_to_scenes(beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """컴플라이언스 검사가 쓰는 scenes 형태로 변환(narration/caption/disclosure)."""
    return [
        {
            "name": b["role"],
            "narration": b["narration"],
            "caption": b.get("caption", ""),
            "disclosure": b.get("disclosure"),
        }
        for b in beats
    ]
