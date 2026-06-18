"""거부감 줄이고 긍정적·제품/사용 위주로 (운영자 지시 2026-06-19).

더러움/방치를 강조하던 공감·전환 장면 프롬프트에서 거부감 유발 표현을
없애고, 전환 장면은 제품/사용 모습으로 돌린다.
"""

from __future__ import annotations

from clipcart.research.niches import NICHES
from clipcart.video.promo.beats import build_beats


def _product(kw="배수구 거름망 스테인리스"):
    niche = next(n for n in NICHES if n["keyword"] == kw)
    return {"product_id": "CPX", "price": 8900, "niche": niche, "product_name": "x",
            "display_name": niche["title_keyword"], "source": "coupang", "is_rocket": True,
            "image_urls": ["a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg"]}


def _all_media_text(beats):
    parts = []
    for b in beats:
        parts.append(b.get("source", ""))
        parts.append(b.get("fallback", ""))
        parts.extend(b.get("shots") or [])
    return " ".join(parts).lower()


def test_no_offputting_words_in_any_scene_prompt():
    text = _all_media_text(build_beats(_product()))
    for bad in ("grimy", "clutter", "messy", "worn-out", "abandoned", "unsolved", "filthy"):
        assert bad not in text, f"거부감 표현 '{bad}' 잔존"


def test_switch_scene_shows_product_or_usage_not_dirt():
    beats = build_beats(_product())
    switch = next(b for b in beats if b["role"] == "switch")
    blob = (switch.get("source", "") + " " + " ".join(switch.get("shots") or [])).lower()
    # 전환은 제품/사용(productshot/productimg/productvideo/pexels use) 위주
    assert any(k in blob for k in ("product", "use"))
