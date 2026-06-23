"""AliExpress 어필리에이트 API 클라이언트 단위 테스트.

라이브 API(앱 승인/ tracking_id 필요)에 의존하지 않고, 서명 수학과
요청 조립·응답 파싱을 픽스처로 고정한다.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

import clipcart.aliexpress as ali


def _expected_sha256(params: dict, secret: str) -> str:
    items = sorted((k, v) for k, v in params.items() if k != "sign")
    concat = "".join(f"{k}{v}" for k, v in items)
    return hmac.new(secret.encode(), concat.encode(), hashlib.sha256).hexdigest().upper()


def test_sign_sha256_sorts_and_hmacs():
    params = {
        "method": "aliexpress.affiliate.product.query",
        "app_key": "12345",
        "keywords": "배수구 거름망",
    }
    sig = ali._sign(params, "SECRET", "sha256")
    assert sig == _expected_sha256(params, "SECRET")
    assert sig == sig.upper()


def test_sign_excludes_sign_key_itself():
    secret = "S"
    base = {"app_key": "k", "v": "2.0"}
    with_sign = {**base, "sign": "STALE"}
    assert ali._sign(base, secret, "sha256") == ali._sign(with_sign, secret, "sha256")


def test_sign_is_order_independent():
    secret = "S"
    a = {"b": "2", "a": "1", "c": "3"}
    b = {"c": "3", "a": "1", "b": "2"}
    assert ali._sign(a, secret, "sha256") == ali._sign(b, secret, "sha256")


def test_sign_md5_wraps_secret_both_sides():
    secret = "SEC"
    params = {"app_key": "k", "method": "m"}
    concat = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    expected = hashlib.md5(f"{secret}{concat}{secret}".encode()).hexdigest().upper()
    assert ali._sign(params, secret, "md5") == expected


class _FakeResp:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


def test_query_products_parses_response_and_signs(monkeypatch):
    monkeypatch.setenv("ALIEXPRESS_APP_KEY", "K")
    monkeypatch.setenv("ALIEXPRESS_APP_SECRET", "S")
    monkeypatch.delenv("ALIEXPRESS_TRACKING_ID", raising=False)
    captured: dict = {}

    def fake_post(url, data=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return _FakeResp(
            {
                "aliexpress_affiliate_product_query_response": {
                    "resp_result": {
                        "resp_code": 200,
                        "result": {
                            "products": {
                                "product": [
                                    {"product_id": "100", "product_title": "스테인리스 배수구 거름망"}
                                ]
                            }
                        },
                    }
                }
            }
        )

    monkeypatch.setattr(ali.requests, "post", fake_post)
    out = ali.query_products("배수구 거름망", page_size=5)

    assert out and out[0]["product_id"] == "100"
    assert captured["url"] == ali.GATEWAY
    assert captured["data"]["method"] == "aliexpress.affiliate.product.query"
    assert captured["data"]["app_key"] == "K"
    assert "sign" in captured["data"] and captured["data"]["sign"]
    # 한국 타깃 기본값이 비즈 파라미터로 전달돼야 한다
    assert captured["data"]["ship_to_country"] == "KR"
    assert captured["data"]["target_currency"] == "KRW"
    assert captured["data"]["target_language"] == "KO"


def test_call_raises_on_error_response(monkeypatch):
    monkeypatch.setenv("ALIEXPRESS_APP_KEY", "K")
    monkeypatch.setenv("ALIEXPRESS_APP_SECRET", "S")
    monkeypatch.setattr(
        ali.requests,
        "post",
        lambda *a, **k: _FakeResp(
            {"error_response": {"code": "15", "msg": "App access denied", "sub_msg": "no scope"}}
        ),
    )
    with pytest.raises(ali.AliExpressApiError):
        ali.query_products("x")


def test_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("ALIEXPRESS_APP_KEY", raising=False)
    monkeypatch.delenv("ALIEXPRESS_APP_SECRET", raising=False)
    with pytest.raises(ali.AliExpressApiError):
        ali.query_products("x")


def test_generate_affiliate_links_parses_promotion_link(monkeypatch):
    monkeypatch.setenv("ALIEXPRESS_APP_KEY", "K")
    monkeypatch.setenv("ALIEXPRESS_APP_SECRET", "S")
    monkeypatch.setenv("ALIEXPRESS_TRACKING_ID", "clipcart")
    captured: dict = {}

    def fake_post(url, data=None, timeout=None):
        captured["data"] = data
        return _FakeResp(
            {
                "aliexpress_affiliate_link_generate_response": {
                    "resp_result": {
                        "resp_code": 200,
                        "result": {
                            "promotion_links": {
                                "promotion_link": [
                                    {
                                        "source_value": "https://www.aliexpress.com/item/100.html",
                                        "promotion_link": "https://s.click.aliexpress.com/e/_abc",
                                    }
                                ]
                            }
                        },
                    }
                }
            }
        )

    monkeypatch.setattr(ali.requests, "post", fake_post)
    links = ali.generate_affiliate_links(["https://www.aliexpress.com/item/100.html"])

    assert links[0]["promotion_link"].startswith("https://s.click.aliexpress.com/")
    assert captured["data"]["tracking_id"] == "clipcart"
    assert captured["data"]["method"] == "aliexpress.affiliate.link.generate"


def test_parse_order_list_extracts_orders():
    res = {"orders": {"order": [
        {"order_number": "1", "estimated_paid_commission": "100"},
        {"order_number": "2", "estimated_paid_commission": "50"},
    ]}, "total_record_count": "2"}
    out = ali.parse_order_list(res)
    assert len(out) == 2
    assert out[0]["order_number"] == "1"


def test_parse_order_list_normalizes_single_and_empty():
    assert ali.parse_order_list({}) == []
    assert ali.parse_order_list({"orders": {"order": {"order_number": "x"}}}) == [{"order_number": "x"}]
