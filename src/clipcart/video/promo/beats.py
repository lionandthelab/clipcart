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
from clipcart.video.compliance import sanitize_text
from clipcart.video.promo.broll import get_broll


# 카테고리별 제품 화보샷 배경 (제품은 그대로, 배경/구도만 촬영한 듯하게).
# 2020년대 신축 한국 아파트 마감으로 명시 — 그냥 'Korean ~'이면 낡은 인테리어가 나온다.
_SHOT_SCENES: dict[str, list[str]] = {
    "주방": [
        "a sleek white quartz countertop with handleless cabinets in a modern 2020s "
        "Korean apartment kitchen, bright daylight",
        "a contemporary kitchen island near a large window in a modern Korean apartment, morning light",
    ],
    "욕실": [
        "a wall-hung vanity with large-format gray porcelain tiles and a frameless glass "
        "shower in a modern 2020s Korean apartment bathroom, soft daylight",
        "matte-black fixtures and clean minimalist tiling in a contemporary Korean bathroom, gentle window light",
    ],
    "정리/수납": [
        "a clean built-in shelf in a modern minimal 2020s Korean apartment, contemporary styling, bright daylight",
        "a tidy contemporary white desk near a large window in a modern Korean apartment",
    ],
    "세탁": [
        "a modern Korean apartment laundry area with a contemporary front-load washer and neatly folded towels, bright light",
        "a clean contemporary utility shelf beside a modern front-load washing machine",
    ],
    "청소": [
        "a bright modern 2020s Korean apartment living room with light wood flooring and contemporary furniture, warm daylight",
        "a sunlit windowsill in a tidy modern Korean apartment",
    ],
    "반려동물": [
        "a contemporary rug in a cozy modern Korean apartment living room, warm afternoon light",
        "a soft neutral sofa corner in a modern Korean apartment, gentle daylight",
    ],
}
_DEFAULT_SCENES = [
    "a bright clean table in a modern 2020s Korean apartment, contemporary interior, soft window light",
    "a neat contemporary shelf in a modern Korean apartment with warm natural light",
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
    # 2020년대 신축 한국 아파트 배경으로 고정해 '요즘 우리 집' 공감을 만든다.
    empathy = (
        f"{br['pain']}, close-up of the messy frustrating situation itself in a modern "
        f"2020s Korean apartment, grimy buildup and clutter clearly visible, no people, no hands"
    )

    # 실사용 컨텍스트 화보샷 — 실제 쓰이는 자리에 놓인 모습
    in_use_scene = (
        f"placed where it is actually used in a modern 2020s Korean home ({scenes[0]}), "
        f"natural daily-life context"
    )

    # 전환 장면: 기존 방식의 도구들이 방치된 모습 (실망의 흔적, 사람 없음)
    switch_scene = (
        f"worn-out old tools and failed makeshift solutions related to "
        f"'{br['pain']}', abandoned in a modern 2020s Korean apartment, the problem still unsolved, "
        f"no people, no hands"
    )

    review_card = product.get("review_card_path")

    # ---- 실측 수치 카피 (API 데이터만, 날조 금지) -------------------------- #
    discount_pct = product.get("discount_pct")
    original_price = product.get("original_price")
    try:
        rating = float(product.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0.0
    orders = int(product.get("review_count") or 0)

    if discount_pct and original_price:
        # 획기적 실측 할인: 정가→현재가를 숫자로 박는다
        product_line = (
            f"{name}. 정가 {original_price:,}원이 지금 {discount_pct}% 할인, {price:,}원이에요."
        )
        product_emphasis = f"{discount_pct}% 할인"
        product_caption = f"{name} · {original_price:,}원 → {price:,}원"
    else:
        product_line = f"{name}. 단돈 {price:,}원. {rocket_line}"
        product_emphasis = f"{price:,}원"
        product_caption = f"{name} · {price:,}원"

    # 만족도/주문수는 충분히 인상적일 때만 대본에 얹는다
    if rating >= 90 and orders >= 100:
        result_stats_line = f" 이미 {orders:,}명이 시켰고, 만족도 {rating:g}%예요."
        result_emphasis = f"만족도 {rating:g}%"
    else:
        result_stats_line = ""
        result_emphasis = name  # 제품명 유지(썸네일 프레임 노출 대비)

    # 실제 제품 사진(알리 갤러리)이 충분하면 화보샷/모션샷 대신 실사진 → 실사용 느낌.
    gallery_n = len(product.get("image_urls") or [])
    has_gallery = gallery_n >= 2
    if has_gallery:
        product_shots: list[str] | None = ["productimg:0", "productimg:1"]
        usage_shots = [f"pexels:{br['use']}", "productimg:2", "productimg:3"]
        result_shots = [f"pexels:{br['clean']}", "productimg:4"]
    else:
        product_shots = None
        usage_shots = [f"pexels:{br['use']}", f"motionshot:{in_use_scene}", f"pexels:{br['use']}"]
        result_shots = [f"pexels:{br['clean']}", f"productshot:{scenes[1 % len(scenes)]}"]

    # 셀러 제공 제품 영상(알리 product_video_url)을 메인으로(운영자 지시 2026-06-13):
    # 제품·사용 두 장면 모두 셀러영상으로 연다. editor가 중국어 자막이 적은 구간을
    # 장면마다 다르게 뽑아 반복 인상을 줄이고, 음원 제거·하단 크롭으로 자막을 밀어낸다.
    has_seller_video = bool(product.get("video_url"))
    if has_seller_video:
        product_shots = ["productvideo", *(product_shots or [f"motionshot:{scenes[0]}"])]
        usage_shots = ["productvideo", *usage_shots]

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
            "role": "switch",
            "tone": "switch",
            # 기존 방식 실패 공감 → 차별화 전환 (구매의욕 자극, 보장 표현 금지)
            "narration": (
                f"{niche['old_way']}, 해보셨죠? 실망했다면 이번엔 다릅니다."
            ),
            "caption": "써봤는데 실망했던 사람, 주목",
            "source": f"gemini:{switch_scene}",
            "fallback": f"pexels:{br['pain']}",
            "emphasis": "이번엔 다릅니다",
            "color": "yellow",
        },
        {
            "role": "product",
            "tone": "product",
            "narration": product_line,
            "caption": product_caption,
            # 실제 리스팅 사진 우선(실사용 느낌). 갤러리 없으면 화보샷→Kling 모션.
            **({"shots": product_shots} if product_shots else {"source": f"motionshot:{scenes[0]}"}),
            "fallback": "product",
            "emphasis": product_emphasis,
            "color": "red",
        },
        {
            "role": "usage",
            "tone": "usage",
            "narration": f"쓰는 법도 쉬워요. {niche['usage']}",
            "caption": niche["usage"],
            # 실사용 느낌 — 실영상 + 실제 제품 사진 퀵컷 (갤러리 없으면 모션샷)
            "shots": usage_shots,
            "fallback": "product",
            "color": "white",
        },
        {
            "role": "result",
            "tone": "result",
            "narration": (
                f"{niche['benefit']}{result_stats_line} "
                f"이게 {price:,}원이면, 장바구니 안 담을 이유가 없죠."
            ),
            "caption": niche["benefit"],
            # 결과 2컷 퀵컷: 깨끗해진 실영상 + 실제 제품 사진(없으면 화보샷)
            "shots": result_shots,
            "fallback": "product",
            # 수치가 인상적이면 만족도 슬램, 아니면 제품명(썸네일 프레임 대비)
            "emphasis": result_emphasis,
            "color": "yellow",
        },
        {
            "role": "cta",
            "tone": "cta",
            "narration": f"단점도 솔직히, {niche['downside']}. 링크는 고정 댓글에 있어요.",
            "caption": "링크는 고정 댓글에 ▼",
            # 실데이터(평점/주문수) 리뷰 요약 카드 — 신빙성. 없으면 제품컷.
            "source": f"file:{review_card}" if review_card else "product",
            "fallback": "product",
            "color": "white",
            "disclosure": disclosure_for(product),
        },
    ]
    # 금지어 정화 — 상품명/니치에 섞인 과장어로 게시 차단되는 것 방지(고지는 보존)
    for b in beats:
        b["narration"] = sanitize_text(b["narration"])
        if b.get("caption"):
            b["caption"] = sanitize_text(b["caption"])
        if b.get("emphasis"):
            b["emphasis"] = sanitize_text(b["emphasis"])
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
