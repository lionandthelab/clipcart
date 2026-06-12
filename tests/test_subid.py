"""영상(상품)별 쿠팡 subId 귀속 테스트.

영상마다 고유 subId를 딥링크에 실어 보내면 파트너스 리포트(clicks/orders/
commission)의 subId 칼럼으로 클릭·수익을 영상 단위로 귀속할 수 있다.
정산 자체는 계정 trackingCode 기준이므로 subId 값은 분류용 메타데이터다
(2026-06-12 reports API 실측으로 확인).
"""

from __future__ import annotations

import clipcart.research.auto_select as sel
from clipcart.coupang import make_sub_id


def test_make_sub_id_joins_base_and_product_id():
    assert make_sub_id("salrimshorts", "8843938097") == "salrimshorts8843938097"


def test_make_sub_id_defaults_base_when_missing():
    assert make_sub_id(None, 123) == "clipcart123"
    assert make_sub_id("", 123) == "clipcart123"


def test_make_sub_id_sanitizes_base_to_lower_alnum():
    assert make_sub_id("My-Channel_01", "99") == "mychannel0199"


def test_make_sub_id_caps_total_length():
    sid = make_sub_id("a" * 100, "8843938097")
    assert len(sid) <= 50
    assert sid.endswith("8843938097")


# --- 선정 파이프라인 통합: 상품별 subId가 딥링크와 product 레코드에 실리는가 ---


def _coupang_item(pid: int, name: str, price: int) -> dict:
    return {
        "productId": pid,
        "productName": name,
        "productPrice": price,
        "productImage": "https://img/x.jpg",
        "productUrl": (
            f"https://link.coupang.com/re/AFFSDP?lptag=AF123&pageKey={pid}"
            "&itemId=111&vendorItemId=222"
        ),
        "isRocket": True,
        "rank": 1,
    }


def _patch_clean_history(monkeypatch):
    monkeypatch.setattr(sel.history, "used_coupang_ids", lambda: set())
    monkeypatch.setattr(sel.history, "used_name_keys", lambda: set())
    monkeypatch.setattr(sel.history, "keyword_last_used", lambda: {})
    monkeypatch.setattr(sel, "_load_state", lambda: {"used_keywords": [], "used_product_ids": []})
    monkeypatch.setattr(sel, "_save_state", lambda state: None)


def test_selected_product_carries_per_product_sub_id(monkeypatch):
    _patch_clean_history(monkeypatch)
    monkeypatch.setenv("COUPANG_SUB_ID", "salrimshorts")
    kw = "배수구 거름망 스테인리스"
    monkeypatch.setattr(
        sel, "search_products",
        lambda keyword, limit=10, sub_id=None: (
            [_coupang_item(8843938097, "스테인리스 배수구 거름망 채반", 6900)] if keyword == kw else []
        ),
    )
    captured: dict = {}

    def fake_deeplinks(urls, sub_id=None):
        captured["sub_id"] = sub_id
        return [{"shortenUrl": "https://link.coupang.com/a/SHORT"}]

    monkeypatch.setattr(sel, "create_deeplinks", fake_deeplinks)

    product = sel.select_today_product(force_keyword=kw)
    assert product is not None
    # 딥링크는 상품별 subId로 생성되고, 같은 값이 레코드에 남아 리포트 조인 키가 된다
    assert captured["sub_id"] == "salrimshorts8843938097"
    assert product["sub_id"] == "salrimshorts8843938097"
    assert product["affiliate_url"] == "https://link.coupang.com/a/SHORT"
