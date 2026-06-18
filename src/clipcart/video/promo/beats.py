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
from clipcart.video.promo.pricing import parse_pack, unit_phrase
from clipcart.video.promo.script import pick_script_style, render_line


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
    # 대본 말투(레퍼토리) — 매번 같은 문장 방지. pick은 상품ID 해시라 engine에서
    # 다시 호출해도 같은 스타일이 나온다(라벨 기록용).
    _, style = pick_script_style(product)

    rocket_line = "심지어 로켓배송이라 내일 와요." if rocket else "가격도 부담 없죠."

    # 공감 장면 — 거부감 대신 '요즘 우리 집'의 사소한 불편을 밝고 깔끔하게(운영자
    # 지시 2026-06-19: 더러움 강조 금지). 사람/손 없이 상황만, 밝은 톤.
    empathy = (
        f"the everyday spot related to '{br['pain']}' in a bright tidy modern 2020s "
        f"Korean apartment, clean and relatable, pleasant natural light, no people, no hands"
    )

    # 실사용 컨텍스트 화보샷 — 실제 쓰이는 자리에 놓인 모습
    in_use_scene = (
        f"placed where it is actually used in a modern 2020s Korean home ({scenes[0]}), "
        f"natural daily-life context"
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

    # 묶음이면 개당 가격을 어필 (압도적으로 싼 가격 강조). 상품명에서 수량 파싱.
    pack_count, pack_unit = parse_pack(product.get("product_name", ""))
    unit = unit_phrase(price, pack_count)  # '개당 약 130원' 또는 None

    if unit:
        # 개당 가격이 핵심 어필 — 총액과 함께, 슬램은 개당가
        product_line = f"{name}. {pack_count}{pack_unit}에 {price:,}원, {unit}꼴이에요."
        product_emphasis = unit
        product_caption = f"{name} · {price:,}원 ({unit})"
    elif discount_pct and original_price:
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
            # 공정위 시작 고지 — 영상 '시작'에도 소스별 확정형 고지를 베이크인(끝부분만 표기 불인정)
            "disclosure": disclosure_for(product),
        },
        {
            "role": "problem",
            "tone": "problem",
            "narration": niche["problem"],
            "caption": niche["problem"],
            # 문제: 밝고 깔끔한 공감 장면(거부감 X), 미스 시 실영상
            "source": f"gemini:{empathy}",
            "fallback": f"pexels:{br['use']}",
            "color": "white",
        },
        {
            "role": "switch",
            "tone": "switch",
            # 전환은 긍정적으로 — 제품이 쓰이는 모습을 보여준다(운영자 지시 2026-06-19).
            "narration": render_line(style["switch"], old_way=niche["old_way"]),
            "caption": style["switch_caption"],
            **(
                {"shots": ["productimg:0", f"pexels:{br['use']}"]}
                if has_gallery
                else {"source": f"productshot:{in_use_scene}"}
            ),
            "fallback": f"pexels:{br['use']}",
            "emphasis": style["switch_emphasis"],
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
            "narration": render_line(style["usage"], usage=niche["usage"]),
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
                f"{render_line(style['result_tail'], price=price)}"
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
            # 단점 짚는 부분은 제거(운영자 지시 2026-06-19) — CTA는 링크 안내만
            "narration": render_line(style["cta"]),
            "caption": "링크는 고정 댓글에 ▼",
            # 실데이터(평점/주문수) 리뷰 요약 카드 — 신빙성. 없으면 제품컷.
            "source": f"file:{review_card}" if review_card else "product",
            "fallback": "product",
            "color": "white",
            "disclosure": disclosure_for(product),
        },
    ]
    # 고지는 시작·끝 화면 자막 + 설명란으로 충족 — cta에 구두 '광고예요'는 넣지 않는다.

    # 두 여성 목소리(나레이션 + 증언) — 공감·체감 라인(problem 불편 / result 변화)을
    # 증언 보이스로(운영자 지시 2026-06-19: 일반 promo에도 적용). 일반·관찰 화법
    # 그대로라 허위후기 아님 — 가짜 후기 표현은 컴플라이언스가 차단. 증언 보이스가
    # 미설정(env)이면 메인으로 폴백돼 단일 보이스로 동작한다.
    for b in beats:
        if b["role"] in ("problem", "result"):
            b["voice"] = "testimony"

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
