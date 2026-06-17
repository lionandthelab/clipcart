"""묶음 수량 파싱 + 개당 가격 테스트.

압도적으로 싼 제품의 가격 어필을 위해, 묶음(N장/N개/N매…)이면 수량을 파악해
개당 가격을 알려준다. 단, 잘못된 개당 표기는 신뢰를 깨므로 애매하면(옵션
'30/20/10', 서로 다른 수량 토큰 다수) 묶음으로 보지 않는다(개수 1).
"""

from __future__ import annotations

from clipcart.video.promo.pricing import parse_pack, per_unit_price, unit_phrase


def test_parses_clear_single_count():
    assert parse_pack("메디안 어린이 펌핑치약 30장") == (30, "장")
    assert parse_pack("롯데칠성 트레비 라임 2개") == (2, "개")
    assert parse_pack("실리콘 배수 패드 2p") == (2, "개")
    assert parse_pack("주방 행주 10매입") == (10, "매")


def test_no_count_returns_one():
    assert parse_pack("확장형 스텐 빨래건조대 대형") == (1, "개")
    assert parse_pack("") == (1, "개")


def test_size_tokens_are_not_counted():
    # cm/kg/ml/단 등 치수·단위는 수량이 아니다
    assert parse_pack("스텐 건조대 60cm 2단") == (1, "개")
    assert parse_pack("세제 1000ml 대용량") == (1, "개")


def test_ambiguous_option_set_is_not_a_bundle():
    # 재단 옵션 '30/20/10장'은 단일 묶음 수량이 아님 → 개수 1(개당 표기 금지)
    assert parse_pack("교체용 필터면 30/20/10장")[0] == 1
    # 서로 다른 수량 토큰 다수도 보수적으로 1
    assert parse_pack("물티슈 100매 10팩")[0] == 1


def test_per_unit_price():
    assert per_unit_price(3900, 30) == 130
    assert per_unit_price(5000, 1) == 5000
    assert per_unit_price(0, 0) == 0  # 방어


def test_unit_phrase_only_for_real_bundles():
    assert unit_phrase(3900, 30) == "개당 약 130원"
    assert unit_phrase(5000, 1) is None       # 단품
    assert unit_phrase(1000, 0) is None        # 방어
    # 비현실적 수량(파싱 오류 방지)은 표기 안 함
    assert unit_phrase(5000, 5000) is None


def test_beats_product_narration_uses_per_unit_for_bundle():
    # 묶음 제품이면 제품 장면 내레이션·강조에 개당 가격이 들어간다
    from clipcart.research.niches import NICHES
    from clipcart.video.promo.beats import build_beats

    niche = next(n for n in NICHES if n["keyword"] == "세탁기 먼지 거름망 부직포")
    product = {
        "product_id": "AE_TESTBUNDLE", "price": 3900,
        "product_name": "세탁기 먼지 거름망 부직포 필터 30매", "display_name": niche["title_keyword"],
        "source": "aliexpress", "niche": niche,
    }
    beats = build_beats(product)
    prod = next(b for b in beats if b["role"] == "product")
    assert "개당 약 130원" in prod["narration"]
    assert prod["emphasis"] == "개당 약 130원"


def test_beats_single_item_no_per_unit():
    from clipcart.research.niches import NICHES
    from clipcart.video.promo.beats import build_beats

    niche = next(n for n in NICHES if n["keyword"] == "스텐 빨래 건조대 대형")
    product = {
        "product_id": "AE_SINGLE", "price": 39000,
        "product_name": "확장형 스텐 빨래건조대 대형", "display_name": niche["title_keyword"],
        "source": "aliexpress", "niche": niche,
    }
    beats = build_beats(product)
    prod = next(b for b in beats if b["role"] == "product")
    assert "개당" not in prod["narration"]
