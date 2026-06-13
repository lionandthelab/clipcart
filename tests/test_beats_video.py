"""셀러 제공 제품 영상(B-roll) 비트 배선 테스트.

알리 어필리에이트 API의 product_video_url(mp4)을 제품 영상의 메인 소재로
쓴다(운영자 지시 2026-06-13): 제품·사용 두 장면을 셀러영상으로 연다.
editor가 장면마다 중국어 자막이 적은 '다른' 구간을 뽑아 반복 인상을 줄인다.
"""

from __future__ import annotations

from clipcart.research.niches import NICHES
from clipcart.video.promo.beats import build_beats


def _product(**over):
    niche = next(n for n in NICHES if n["keyword"] == "멀티탭 정리함")
    base = {
        "product_id": "AE1",
        "product_name": "멀티탭 정리함 케이블 박스",
        "display_name": niche["title_keyword"],
        "source": "aliexpress",
        "price": 2780,
        "niche": niche,
    }
    base.update(over)
    return base


def _usage(beats):
    return next(b for b in beats if b["role"] == "usage")


def _product_beat(beats):
    return next(b for b in beats if b["role"] == "product")


def test_seller_video_leads_product_and_usage_scenes():
    beats = build_beats(_product(video_url="https://video.aliexpress-media.com/x.mp4"))
    assert _product_beat(beats)["shots"][0] == "productvideo"
    assert _usage(beats)["shots"][0] == "productvideo"


def test_without_video_no_productvideo_token():
    beats = build_beats(_product())
    tokens = []
    for b in beats:
        tokens.extend(b.get("shots") or [])
        tokens.append(b.get("source", ""))
    assert "productvideo" not in tokens


def test_seller_video_leads_exactly_two_scenes():
    # 제품·사용 두 장면에만 — result/hook 등 다른 장면엔 넣지 않는다(반복 과다 방지)
    beats = build_beats(
        _product(
            video_url="https://video.aliexpress-media.com/x.mp4",
            image_urls=["a.jpg", "b.jpg", "c.jpg"],
        )
    )
    count = sum((b.get("shots") or []).count("productvideo") for b in beats)
    count += sum(1 for b in beats if b.get("source") == "productvideo")
    assert count == 2
    assert _product_beat(beats)["shots"][0] == "productvideo"
    assert _usage(beats)["shots"][0] == "productvideo"
