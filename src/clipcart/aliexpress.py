"""AliExpress 어필리에이트 Open API 클라이언트.

open.aliexpress.com(IOP 시스템)에서 만든 앱(app_key/app_secret)으로 어필리에이트
메서드를 호출한다. 쿠팡 클라이언트와 동일하게 키는 .env에서 읽고, 코드에 비밀값을
두지 않는다.

기본 게이트웨이/서명:
  - IOP: https://api-sg.aliexpress.com/sync , sign_method=sha256 (HMAC-SHA256)
  - 레거시(gw.api.taobao.com)로 전환하려면 env CLIPCART_ALI_GATEWAY / CLIPCART_ALI_SIGN_METHOD=md5

서명 규칙(공통):
  1. sign 키를 제외한 파라미터를 key 오름차순 정렬
  2. 구분자 없이 "key+value" 이어붙임
  3. sha256 → HMAC-SHA256(secret) / md5 → MD5(secret + concat + secret)
  4. 대문자 hex

주요 메서드:
  - aliexpress.affiliate.product.query  : 키워드 상품 검색
  - aliexpress.affiliate.link.generate  : 제휴 추적 링크 생성(tracking_id 필요)
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any

import requests

GATEWAY = os.getenv("CLIPCART_ALI_GATEWAY", "https://api-sg.aliexpress.com/sync")
SIGN_METHOD = os.getenv("CLIPCART_ALI_SIGN_METHOD", "sha256")

# 운영자 지시: 한국 배송/원화/한국어 기준 (영어 채널 아님)
DEFAULT_SHIP_TO = os.getenv("CLIPCART_ALI_SHIP_TO", "KR")
DEFAULT_CURRENCY = os.getenv("CLIPCART_ALI_CURRENCY", "KRW")
DEFAULT_LANGUAGE = os.getenv("CLIPCART_ALI_LANGUAGE", "KO")

# 알리익스프레스 어필리에이트 의무 고지 (공정위 확정형 표현 — 조건부 금지)
ALIEXPRESS_DISCLOSURE = (
    "이 영상은 알리익스프레스 어필리에이트 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
)


class AliExpressApiError(RuntimeError):
    pass


def _credentials() -> tuple[str, str]:
    key = os.getenv("ALIEXPRESS_APP_KEY", "")
    secret = os.getenv("ALIEXPRESS_APP_SECRET", "")
    if not key or not secret:
        raise AliExpressApiError("알리 앱 키 없음 (.env ALIEXPRESS_APP_KEY/ALIEXPRESS_APP_SECRET)")
    return key, secret


def _sign(params: dict[str, str], secret: str, sign_method: str = SIGN_METHOD) -> str:
    items = sorted((k, v) for k, v in params.items() if k != "sign")
    concat = "".join(f"{k}{v}" for k, v in items)
    if sign_method == "md5":
        base = f"{secret}{concat}{secret}".encode("utf-8")
        return hashlib.md5(base).hexdigest().upper()
    return hmac.new(secret.encode("utf-8"), concat.encode("utf-8"), hashlib.sha256).hexdigest().upper()


def _timestamp() -> str:
    if SIGN_METHOD == "md5":
        # 레거시 게이트웨이: GMT+8 "yyyy-MM-dd HH:mm:ss"
        return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 8 * 3600))
    # IOP: epoch milliseconds (GMT)
    return str(int(time.time() * 1000))


def _call(method: str, biz: dict[str, Any]) -> dict[str, Any]:
    key, secret = _credentials()
    params: dict[str, str] = {
        "app_key": key,
        "method": method,
        "sign_method": SIGN_METHOD,
        "timestamp": _timestamp(),
        "format": "json",
        "v": "2.0",
    }
    for k, v in biz.items():
        if v is not None and v != "":
            params[k] = str(v)
    params["sign"] = _sign(params, secret)

    resp = requests.post(GATEWAY, data=params, timeout=30)
    if resp.status_code != 200:
        raise AliExpressApiError(f"알리 API {resp.status_code}: {resp.text[:300]}")
    payload = resp.json()
    if "error_response" in payload:
        er = payload["error_response"]
        raise AliExpressApiError(
            f"알리 API code={er.get('code')} {er.get('msg', '')[:200]} {er.get('sub_msg', '')[:200]}"
        )
    return payload


def _result(payload: dict[str, Any], response_key: str) -> dict[str, Any]:
    return (payload.get(response_key) or {}).get("resp_result", {}).get("result", {}) or {}


def query_products(
    keywords: str,
    *,
    page_size: int = 20,
    page_no: int = 1,
    sort: str = "LAST_VOLUME_DESC",
    tracking_id: str | None = None,
    ship_to: str = DEFAULT_SHIP_TO,
    currency: str = DEFAULT_CURRENCY,
    language: str = DEFAULT_LANGUAGE,
    category_ids: str | None = None,
) -> list[dict[str, Any]]:
    """키워드 상품 검색. tracking_id를 주면 결과에 promotion_link(제휴링크)가 포함된다.

    가격 필터는 통화 단위 모호성(원/센트) 때문에 클라이언트에서 처리하므로 여기서 보내지 않는다.
    """
    biz: dict[str, Any] = {
        "keywords": keywords,
        "page_size": page_size,
        "page_no": page_no,
        "sort": sort,
        "target_currency": currency,
        "target_language": language,
        "ship_to_country": ship_to,
        "tracking_id": tracking_id or os.getenv("ALIEXPRESS_TRACKING_ID") or None,
        "category_ids": category_ids,
        "fields": (
            "product_id,product_title,target_sale_price,target_sale_price_currency,"
            "target_original_price,target_original_price_currency,"
            "evaluate_rate,lastest_volume,product_main_image_url,product_detail_url,"
            "promotion_link,first_level_category_name,original_price"
        ),
    }
    payload = _call("aliexpress.affiliate.product.query", biz)
    result = _result(payload, "aliexpress_affiliate_product_query_response")
    return (result.get("products") or {}).get("product") or []


def generate_affiliate_links(
    urls: list[str],
    tracking_id: str | None = None,
    promotion_link_type: int = 0,
) -> list[dict[str, Any]]:
    """제품 URL을 제휴 추적 링크로 변환. tracking_id 필수(없으면 수수료 미집계)."""
    biz: dict[str, Any] = {
        "source_values": ",".join(urls),
        "promotion_link_type": promotion_link_type,
        "tracking_id": tracking_id or os.getenv("ALIEXPRESS_TRACKING_ID"),
    }
    payload = _call("aliexpress.affiliate.link.generate", biz)
    result = _result(payload, "aliexpress_affiliate_link_generate_response")
    return (result.get("promotion_links") or {}).get("promotion_link") or []
