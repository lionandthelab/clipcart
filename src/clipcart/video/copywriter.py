"""상품 + 니치 템플릿 + 포맷 프로파일 → 영상 대본/메타데이터 생성."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from clipcart.config import DEFAULT_DISCLOSURE
from clipcart.coupang import COUPANG_DISCLOSURE
from clipcart.research.auto_select import short_product_name


def _first_sentence(text: str, limit: int = 46) -> str:
    for sep in [". ", "? ", "! "]:
        if sep in text:
            text = text.split(sep)[0] + sep.strip()
            break
    return text[:limit].rstrip(" .") if len(text) > limit else text.rstrip(".")


def _split_hook(hook: str) -> tuple[str, str]:
    if "," in hook:
        head, tail = hook.split(",", 1)
        return head.strip() + ",", tail.strip()
    words = hook.split()
    if len(words) >= 4:
        mid = len(words) // 2
        return " ".join(words[:mid]), " ".join(words[mid:])
    return hook, ""


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _pick_title(product: dict[str, Any], profile: dict[str, Any]) -> str:
    niche = product["niche"]
    values = _SafeDict(
        hook=niche["hook"],
        old_way=niche["old_way"],
        title_keyword=niche["title_keyword"],
        problem_short=niche["old_way"],
        price_won=f"{product['price']:,}",
    )
    templates = profile.get("title_templates") or []
    seed = int(hashlib.md5(f"{date.today()}{product['product_id']}".encode()).hexdigest(), 16)
    usable = []
    for tpl in templates:
        rendered = tpl.format_map(values)
        if "{" not in rendered and len(rendered) <= 90:
            usable.append(rendered)
    if not usable:
        usable = [niche["hook"]]
    return usable[seed % len(usable)]


def build_creative(product: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    niche = product["niche"]
    name = short_product_name(product)
    price = product["price"]
    rocket = product.get("is_rocket", False)

    disclosure_full = COUPANG_DISCLOSURE
    if DEFAULT_DISCLOSURE and DEFAULT_DISCLOSURE not in disclosure_full:
        disclosure_full = f"{COUPANG_DISCLOSURE}\n{DEFAULT_DISCLOSURE}"

    accent, hook_rest = _split_hook(niche["hook"])

    rocket_line = "심지어 로켓배송." if rocket else "가격도 부담 없죠."
    result_clincher = f"이게 {price:,}원이면, 장바구니 안 담을 이유가 없죠."

    scenes: list[dict[str, Any]] = [
        {
            "name": "hook",
            "style": "blur_dark",
            "zoom": "in",
            # 훅: 가장 빠르고 단호하게
            "narration": niche["hook"],
            "rate": "+34%",
        },
        {
            "name": "problem",
            "style": "zoom_focus",
            "zoom": "in",
            "narration": niche["problem"],
            "rate": "+30%",
        },
        {
            "name": "product",
            "style": "white_card",
            "zoom": "out",
            "narration": f"해결책은 간단해요. {name}. 단돈 {price:,}원. {rocket_line}",
            "rate": "+26%",
            "caption": name,
            "price_text": f"{price:,}원",
            "rocket": rocket,
            "sub": "제품 정보는 설명란 링크에서",
        },
        {
            "name": "usage",
            "style": "zoom_focus",
            "zoom": "out",
            "narration": f"쓰는 법도 쉬워요. {niche['usage']}",
            "rate": "+32%",
        },
        {
            "name": "result",
            "style": "zoom_focus",
            "zoom": "in",
            "narration": f"{niche['benefit']} {result_clincher}",
            "rate": "+30%",
        },
        {
            "name": "downside_cta",
            "style": "blur_dark",
            "zoom": "in",
            "narration": f"물론 단점도 있어요. {niche['downside']}. 그래도 끌린다면, 링크는 고정 댓글에 있어요.",
            "rate": "+24%",
            "disclosure": COUPANG_DISCLOSURE,
        },
    ]

    title = _pick_title(product, profile)
    hashtags = " ".join(profile.get("hashtags") or [])
    description = (profile.get("description_template") or "").format_map(
        _SafeDict(
            hook=niche["hook"],
            affiliate_url=product["affiliate_url"],
            target=niche["target"],
            benefit_short=_first_sentence(niche["benefit"], 60),
            downside=niche["downside"],
            disclosure=disclosure_full,
            hashtags=hashtags,
        )
    )

    return {
        "title": title,
        "description": description,
        "tags": list(profile.get("tags") or []),
        "hashtags": profile.get("hashtags") or [],
        "pinned_comment": (
            f"제품 보러가기 → {product['affiliate_url']}\n{COUPANG_DISCLOSURE}"
        ),
        "scenes": scenes,
        "thumbnail_line1": accent.rstrip(","),
        "thumbnail_line2": hook_rest or niche["title_keyword"],
        "tts_voice": profile.get("tts_voice", "ko-KR-SunHiNeural"),
        "tts_rate": profile.get("tts_rate", "+12%"),
    }
