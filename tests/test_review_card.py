"""실데이터 리뷰 요약 카드 테스트.

허위 후기 작성은 금지행동(1.2) — 카드에는 API가 주는 실측치(평점·주문수)만
들어가야 하고, 데이터가 없으면 카드를 만들지 않아야 한다.
"""

from __future__ import annotations

from clipcart.video.promo.review_card import compose_review_card, review_summary


def _product(rating=95.6, volume=121):
    return {
        "product_id": "AE1",
        "source": "aliexpress",
        "rating": rating,
        "review_count": volume,
    }


def test_summary_converts_percent_to_five_star_scale():
    s = review_summary(_product())
    assert s is not None
    assert s["stars"] == 4.8  # 95.6% → 4.8/5
    assert s["satisfaction"] == "95.6%"
    assert s["orders"] == 121
    assert s["platform"] == "알리익스프레스"


def test_summary_is_none_without_real_data():
    # 실측치가 없으면 카드 자체를 만들지 않는다 (날조 금지)
    assert review_summary(_product(rating=0)) is None
    assert review_summary(_product(rating=None)) is None


def test_compose_writes_card_image(tmp_path):
    out = compose_review_card(_product(), tmp_path / "card.png")
    assert out is not None and out.exists() and out.stat().st_size > 5_000


def test_compose_returns_none_without_data(tmp_path):
    assert compose_review_card(_product(rating=None), tmp_path / "card.png") is None
