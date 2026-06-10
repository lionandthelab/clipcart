"""AliExpress 상품 자동 선정기 테스트.

라이브 API 대신 query_products를 모킹해, 필터·중복차단·필드매핑을 고정한다.
"""

from __future__ import annotations

import clipcart.research.auto_select_ali as sel


def _item(pid, title, price, *, volume=500, rate="95.0%", promo=True, img=True, original=None):
    return {
        "product_id": str(pid),
        "product_title": title,
        "target_sale_price": str(price),
        "target_sale_price_currency": "KRW",
        "target_original_price": str(original) if original else None,
        "target_original_price_currency": "KRW" if original else None,
        "lastest_volume": volume,
        "evaluate_rate": rate,
        "product_main_image_url": "https://img/x.jpg" if img else "",
        "product_detail_url": f"https://www.aliexpress.com/item/{pid}.html",
        "promotion_link": f"https://s.click.aliexpress.com/e/_{pid}" if promo else "",
    }


def _patch_clean_history(monkeypatch):
    monkeypatch.setattr(sel.history, "used_aliexpress_ids", lambda: set())
    monkeypatch.setattr(sel.history, "used_name_keys", lambda: set())
    monkeypatch.setattr(sel.history, "keyword_last_used", lambda: {})
    monkeypatch.setattr(sel, "_load_state", lambda: {"used_keywords": [], "used_product_ids": []})
    monkeypatch.setattr(sel, "_save_state", lambda state: None)
    # 선택된 제품의 제휴링크는 link.generate로 만든다(제품별 딥링크)
    monkeypatch.setattr(
        sel, "generate_affiliate_links",
        lambda urls, tracking_id=None: [{"source_value": urls[0], "promotion_link": "https://s.click.aliexpress.com/e/_GEN"}],
    )


def test_selects_valid_candidate_and_maps_fields(monkeypatch):
    _patch_clean_history(monkeypatch)
    kw = "배수구 거름망 스테인리스"
    monkeypatch.setattr(
        sel, "query_products",
        lambda keyword, **kw_: [_item(1005, "스테인리스 배수구 거름망 채반", 6900)] if keyword == kw else [],
    )

    product = sel.select_today_product(force_keyword=kw)
    assert product is not None
    assert product["source"] == "aliexpress"
    assert product["aliexpress_product_id"] == "1005"
    assert product["product_id"] == "AE1005"
    assert product["price"] == 6900
    assert product["affiliate_url"] == "https://s.click.aliexpress.com/e/_GEN"
    assert product["image_url"] == "https://img/x.jpg"
    assert product["niche"]["keyword"] == kw
    assert "is_rocket" not in product  # 알리는 로켓배송 아님 → 배송 과장 금지


def test_discount_pct_derived_from_real_original_price(monkeypatch):
    _patch_clean_history(monkeypatch)
    kw = "배수구 거름망 스테인리스"
    monkeypatch.setattr(
        sel, "query_products",
        lambda keyword, **kw_: [_item(1, "스테인리스 배수구 거름망", 4760, original=9517)],
    )
    p = sel.select_today_product(force_keyword=kw)
    assert p["original_price"] == 9517
    assert p["discount_pct"] == 50  # 실측 정가 기반


def test_no_discount_fields_when_original_missing_or_trivial(monkeypatch):
    _patch_clean_history(monkeypatch)
    kw = "배수구 거름망 스테인리스"
    monkeypatch.setattr(
        sel, "query_products",
        lambda keyword, **kw_: [_item(1, "스테인리스 배수구 거름망", 3540, original=3843)],
    )
    p = sel.select_today_product(force_keyword=kw)
    # 8% 수준의 미미한 할인은 대본 소재로 쓰지 않는다 (과장 인상 방지)
    assert p.get("discount_pct") is None


def test_excluded_keyword_is_filtered(monkeypatch):
    _patch_clean_history(monkeypatch)
    kw = "배수구 거름망 스테인리스"
    monkeypatch.setattr(
        sel, "query_products",
        lambda keyword, **kw_: [_item(1, "살균 항균 배수구 거름망", 6900)],
    )
    assert sel.select_today_product(force_keyword=kw) is None


def test_price_out_of_band_is_filtered(monkeypatch):
    _patch_clean_history(monkeypatch)
    kw = "배수구 거름망 스테인리스"
    monkeypatch.setattr(
        sel, "query_products",
        lambda keyword, **kw_: [_item(1, "스테인리스 배수구 거름망", 90000)],
    )
    assert sel.select_today_product(force_keyword=kw) is None


def test_used_aliexpress_id_is_skipped(monkeypatch):
    _patch_clean_history(monkeypatch)
    monkeypatch.setattr(sel.history, "used_aliexpress_ids", lambda: {"1005"})
    kw = "배수구 거름망 스테인리스"
    monkeypatch.setattr(
        sel, "query_products",
        lambda keyword, **kw_: [_item(1005, "스테인리스 배수구 거름망 채반", 6900)],
    )
    assert sel.select_today_product(force_keyword=kw) is None


def test_product_type_mismatch_is_skipped(monkeypatch):
    _patch_clean_history(monkeypatch)
    kw = "배수구 거름망 스테인리스"
    # 대본은 '거름망'인데 상품은 '브러쉬' → product_type_ok 실패해야
    monkeypatch.setattr(
        sel, "query_products",
        lambda keyword, **kw_: [_item(1, "주방 청소 브러쉬", 6900)],
    )
    assert sel.select_today_product(force_keyword=kw) is None
