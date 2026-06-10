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

    price_line = f"가격은 {price:,}원"
    price_line += "이고 로켓배송도 됩니다." if rocket else "입니다."

    disclosure_full = COUPANG_DISCLOSURE
    if DEFAULT_DISCLOSURE and DEFAULT_DISCLOSURE not in disclosure_full:
        disclosure_full = f"{COUPANG_DISCLOSURE}\n{DEFAULT_DISCLOSURE}"

    accent, hook_rest = _split_hook(niche["hook"])
    scenes: list[dict[str, Any]] = [
        {
            "name": "hook",
            "style": "blur_dark",
            "zoom": "in",
            "narration": niche["hook"],
            "accent": accent,
            "caption": hook_rest,
            "rate": "+16%",  # 훅은 본문보다 빠르고 단호하게
        },
        {
            "name": "problem",
            "style": "zoom_focus",
            "zoom": "in",
            "narration": niche["problem"],
            "caption": _first_sentence(niche["problem"]),
        },
        {
            "name": "product",
            "style": "white_card",
            "zoom": "out",
            "narration": f"그래서 가져온 게 {name}. {price_line}",
            "caption": name,
            "price_text": f"{price:,}원",
            "rocket": rocket,
            "sub": "제품 정보는 설명란 링크에서",
        },
        {
            "name": "usage",
            "style": "zoom_focus",
            "zoom": "out",
            "narration": niche["usage"],
            "caption": _first_sentence(niche["usage"]),
        },
        {
            "name": "result",
            "style": "zoom_focus",
            "zoom": "in",
            "narration": niche["benefit"],
            "caption": _first_sentence(niche["benefit"]),
        },
        {
            "name": "downside_cta",
            "style": "blur_dark",
            "zoom": "in",
            "narration": f"아쉬운 점도 있어요. {niche['downside']}. 구매 링크는 설명란에 있습니다.",
            "caption": niche["downside"],
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
