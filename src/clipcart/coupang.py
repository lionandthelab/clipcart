"""쿠팡 파트너스 Open API 클라이언트 (HMAC 서명)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from typing import Any
from urllib.parse import quote, urlencode

import requests

BASE_URL = "https://api-gateway.coupang.com"
API_PREFIX = "/v2/providers/affiliate_open_api/apis/openapi/v1"

# 쿠팡 파트너스 의무 고지 문구
COUPANG_DISCLOSURE = (
    "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
)

# bestcategories 카테고리 ID
CATEGORY_IDS = {
    "주방용품": "1013",
    "생활용품": "1014",
    "홈인테리어": "1015",
    "반려동물용품": "1029",
}


class CoupangApiError(RuntimeError):
    pass


def _credentials() -> tuple[str, str]:
    access = os.getenv("COUPANG_ACCESS_KEY", "") or os.getenv("COUPANG_ACES_KEY", "")
    secret = os.getenv("COUPANG_SECRET_KEY", "")
    if not access or not secret:
        raise CoupangApiError("쿠팡 파트너스 키 없음 (.env COUPANG_ACCESS_KEY/COUPANG_SECRET_KEY)")
    return access, secret


def _auth_header(method: str, path: str, query: str) -> str:
    access, secret = _credentials()
    signed_date = time.strftime("%y%m%d", time.gmtime()) + "T" + time.strftime("%H%M%S", time.gmtime()) + "Z"
    message = signed_date + method + path + query
    signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return (
        f"CEA algorithm=HmacSHA256, access-key={access}, "
        f"signed-date={signed_date}, signature={signature}"
    )


def _request(method: str, path: str, params: dict[str, Any] | None = None, body: Any = None) -> Any:
    query = urlencode(params, quote_via=quote) if params else ""
    url = BASE_URL + path + (f"?{query}" if query else "")
    headers = {
        "Authorization": _auth_header(method, path, query),
        "Content-Type": "application/json;charset=UTF-8",
    }
    resp = requests.request(
        method,
        url,
        headers=headers,
        data=json.dumps(body) if body is not None else None,
        timeout=30,
    )
    if resp.status_code != 200:
        raise CoupangApiError(f"쿠팡 API {resp.status_code}: {resp.text[:300]}")
    payload = resp.json()
    if str(payload.get("rCode", "0")) != "0":
        raise CoupangApiError(f"쿠팡 API rCode={payload.get('rCode')}: {payload.get('rMessage', '')[:200]}")
    return payload.get("data")


def search_products(keyword: str, limit: int = 10, sub_id: str | None = None) -> list[dict[str, Any]]:
    """키워드 상품 검색. productUrl은 affiliate 추적 링크."""
    params: dict[str, Any] = {"keyword": keyword, "limit": limit}
    if sub_id:
        params["subId"] = sub_id
    data = _request("GET", f"{API_PREFIX}/products/search", params)
    if not data:
        return []
    return data.get("productData") or []


def best_category_products(category_id: str, limit: int = 20, sub_id: str | None = None) -> list[dict[str, Any]]:
    """카테고리 베스트 상품."""
    params: dict[str, Any] = {"limit": limit}
    if sub_id:
        params["subId"] = sub_id
    data = _request("GET", f"{API_PREFIX}/products/bestcategories/{category_id}", params)
    return data or []


def goldbox_products(sub_id: str | None = None) -> list[dict[str, Any]]:
    """골드박스(오늘의 특가) 상품."""
    params: dict[str, Any] = {}
    if sub_id:
        params["subId"] = sub_id
    data = _request("GET", f"{API_PREFIX}/products/goldbox", params or None)
    return data or []


def _report(kind: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    params = {
        "startDate": start_date.replace("-", ""),
        "endDate": end_date.replace("-", ""),
    }
    data = _request("GET", f"{API_PREFIX}/reports/{kind}", params)
    return data or []


def report_clicks(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """일자·subId별 클릭 수 (date/trackingCode/subId/click)."""
    return _report("clicks", start_date, end_date)


def report_orders(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """주문 내역 (subId/productName/gmv/commission 등). 24시간 쿠키로 타 상품 주문 포함."""
    return _report("orders", start_date, end_date)


def report_commission(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """일자·subId별 커미션 합계 (commission/gmv/order/click)."""
    return _report("commission", start_date, end_date)


def make_sub_id(base: str | None, product_id: str | int) -> str:
    """상품(영상)별 리포트 귀속용 subId. 정산은 trackingCode 기준이라 값은 자유.

    리포트 칼럼에서 사람이 읽을 수 있도록 `채널접두사 + 상품ID` 형태로 만들고,
    포맷 리스크를 피해 소문자 영숫자만 남긴다.
    """
    base_clean = re.sub(r"[^a-z0-9]", "", (base or "").lower()) or "clipcart"
    pid = re.sub(r"[^0-9]", "", str(product_id))
    return base_clean[: 50 - len(pid)][:20] + pid


def create_deeplinks(urls: list[str], sub_id: str | None = None) -> list[dict[str, Any]]:
    """쿠팡 URL을 affiliate 단축링크로 변환."""
    body: dict[str, Any] = {"coupangUrls": urls}
    if sub_id:
        body["subId"] = sub_id
    data = _request("POST", f"{API_PREFIX}/deeplink", None, body)
    return data or []
