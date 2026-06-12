"""셀러 제공 제품 영상(B-roll) 비트 배선 테스트.

알리 어필리에이트 API의 product_video_url(mp4)은 엔진이 이미 다운로드하고
editor가 productvideo 토큰(음원 제거·크롭 포함)을 지원하지만, beats가
토큰을 내보내지 않아 사장돼 있었다. 사용(usage) 장면 선두에 단일 배치한다
— 같은 클립이 여러 장면에 반복되면 어색하므로 한 장면만 쓴다.
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


def test_seller_video_leads_usage_scene():
    beats = build_beats(_product(video_url="https://video.aliexpress-media.com/x.mp4"))
    assert _usage(beats)["shots"][0] == "productvideo"


def test_without_video_no_productvideo_token():
    beats = build_beats(_product())
    tokens = []
    for b in beats:
        tokens.extend(b.get("shots") or [])
        tokens.append(b.get("source", ""))
    assert "productvideo" not in tokens


def test_seller_video_used_in_single_scene_only():
    beats = build_beats(
        _product(
            video_url="https://video.aliexpress-media.com/x.mp4",
            image_urls=["a.jpg", "b.jpg", "c.jpg"],  # 갤러리 있는 경로도 동일
        )
    )
    count = sum((b.get("shots") or []).count("productvideo") for b in beats)
    count += sum(1 for b in beats if b.get("source") == "productvideo")
    assert count == 1
    assert _usage(beats)["shots"][0] == "productvideo"
