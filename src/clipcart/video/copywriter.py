"""상품 + 니치 템플릿 + 포맷 프로파일 → 영상 대본/메타데이터 생성."""

from __future__ import annotations

import hashlib
import os
from datetime import date
from typing import Any

from clipcart.disclosure import disclosure_for
from clipcart.research.auto_select import short_product_name
from clipcart.video.compliance import sanitize_text


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


def _pick_title(product: dict[str, Any], profile: dict[str, Any]) -> tuple[str, str]:
    """(제목, 사용한 템플릿) 반환 — 템플릿 키는 posts/metrics 조인용 라벨."""
    niche = product["niche"]
    values = _SafeDict(
        hook=niche["hook"],
        old_way=niche["old_way"],
        title_keyword=niche["title_keyword"],
        problem_short=niche["old_way"],
        price_won=f"{product['price']:,}",
    )
    # 값이 없으면 해당 플레이스홀더가 남아 템플릿이 자동 탈락하도록, 있는 것만 넣는다
    if niche.get("target"):
        values["target"] = niche["target"]
    # 사회적 증거형 재료: 알리 판매량(없으면 {sold_count} 템플릿이 자동 탈락)
    sold = int(product.get("review_count") or 0)
    if sold > 0:
        values["sold_count"] = f"{sold:,}"
    templates = profile.get("title_templates") or []
    # A/B 테스트: 특정 훅 템플릿을 강제(env). 못 그리면 일반 선택으로 폴백.
    forced = os.getenv("CLIPCART_TITLE_TEMPLATE", "").strip()
    if forced:
        rendered = forced.format_map(values)
        if "{" not in rendered and rendered and len(rendered) <= 90:
            return rendered, forced
    seed = int(hashlib.md5(f"{date.today()}{product['product_id']}".encode()).hexdigest(), 16)
    usable = []
    for tpl in templates:
        rendered = tpl.format_map(values)
        if "{" not in rendered and rendered and len(rendered) <= 90:
            usable.append((rendered, tpl))
    if not usable:
        usable = [(niche["hook"], "{hook}")]
    return usable[seed % len(usable)]


def build_creative(product: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    niche = product["niche"]
    name = short_product_name(product)
    price = product["price"]
    rocket = product.get("is_rocket", False)

    # 소스별 고지가 곧 의무 고지. 소스 무관 default를 덧붙이면 타 소스 고지가
    # 섞여 허위 고지가 되므로(예: 알리 영상에 쿠팡 고지) 덧붙이지 않는다.
    src_disclosure = disclosure_for(product)
    disclosure_full = src_disclosure

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
            "disclosure": src_disclosure,
        },
    ]

    title_raw, title_template = _pick_title(product, profile)
    title = sanitize_text(title_raw)
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
    # 금지어 정화 — 단, 의무 고지는 보존(고지 문구는 정화 대상 아님)
    description = sanitize_text(description)
    if disclosure_full not in description:  # 정화가 고지를 건드렸다면 원복 보장
        description = description + "\n" + disclosure_full
    for sc in scenes:
        sc["narration"] = sanitize_text(sc["narration"])
        if sc.get("caption"):
            sc["caption"] = sanitize_text(sc["caption"])

    return {
        "title": title,
        "title_template": title_template,
        "description": description,
        "disclosure": src_disclosure,
        "tags": list(profile.get("tags") or []),
        "hashtags": profile.get("hashtags") or [],
        "pinned_comment": (
            f"제품 보러가기 → {product['affiliate_url']}\n{src_disclosure}"
        ),
        "scenes": scenes,
        "thumbnail_line1": accent.rstrip(","),
        "thumbnail_line2": hook_rest or niche["title_keyword"],
        "tts_voice": profile.get("tts_voice", "ko-KR-SunHiNeural"),
        "tts_rate": profile.get("tts_rate", "+12%"),
    }
