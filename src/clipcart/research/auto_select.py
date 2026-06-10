"""쿠팡 파트너스 API 기반 상품 자동 선정.

니치 풀을 순환하며 후보를 검색하고, 필터·점수화를 거쳐
오늘 게시할 상품 1개를 고른다. 같은 니치/상품은 재사용하지 않는다.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

from clipcart.config import DATA_DIR
from clipcart.coupang import create_deeplinks, search_products
from clipcart.research import history
from clipcart.research.niches import NICHES, PRODUCT_EXCLUDE_KEYWORDS
from clipcart.research.scoring import ScoreInput, score_product

NICHE_STATE_FILE = DATA_DIR / "niche_state.json"

PRICE_MIN = 4000
PRICE_MAX = 35000


def _load_state() -> dict[str, Any]:
    if NICHE_STATE_FILE.exists():
        return json.loads(NICHE_STATE_FILE.read_text(encoding="utf-8"))
    return {"used_keywords": [], "used_product_ids": []}


def _save_state(state: dict[str, Any]) -> None:
    NICHE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    NICHE_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_excluded(name: str) -> bool:
    return any(kw in name for kw in PRODUCT_EXCLUDE_KEYWORDS)


def _derive_score(item: dict[str, Any]) -> Any:
    price = int(item.get("productPrice") or 0)
    impulse = 5 if price < 10000 else 4 if price < 20000 else 3
    price_fit = 5 if 5000 <= price <= 20000 else 4
    return score_product(
        f"CP{item['productId']}",
        ScoreInput(
            problem_strength=5,  # 큐레이션 니치 = 검증된 문제
            video_ease=5,
            impulse_buy=impulse,
            review_trust=4 if item.get("isRocket") else 3,
            price_fit=price_fit,
            claim_risk=1,
        ),
    )


def _shorten_link(item: dict[str, Any], sub_id: str | None) -> str:
    """검색 결과의 긴 추적 URL을 짧은 affiliate 링크로 변환 (실패 시 원본)."""
    long_url = item.get("productUrl", "")
    try:
        qs = parse_qs(urlparse(long_url).query)
        item_id = (qs.get("itemId") or [""])[0]
        vendor_item_id = (qs.get("vendorItemId") or [""])[0]
        page_url = f"https://www.coupang.com/vp/products/{item['productId']}"
        if item_id:
            page_url += f"?itemId={item_id}"
            if vendor_item_id:
                page_url += f"&vendorItemId={vendor_item_id}"
        links = create_deeplinks([page_url], sub_id=sub_id)
        short = links[0].get("shortenUrl") if links else ""
        return short or long_url
    except Exception:
        return long_url


MAX_SEARCH_CALLS_PER_RUN = 5  # 쿠팡 검색 API 실측 rate limit(시간당 ~10회) 보호


def select_today_product(force_keyword: str | None = None) -> dict[str, Any] | None:
    """오늘의 상품 1개 선정. 실패 시 None."""
    # subId는 파트너스에 등록된 채널 ID만 정산 인정 — 미등록 임의값은 전달하지 않는다
    sub_id = os.getenv("COUPANG_SUB_ID", "") or None
    state = _load_state()
    used_keywords = set(state.get("used_keywords", []))
    # 중복 차단: niche_state(시도 가드) + 히스토리(실제 업로드, 권위)
    used_product_ids = set(state.get("used_product_ids", [])) | history.used_coupang_ids()
    used_names = history.used_name_keys()

    # 니치 순서: 최근 덜 쓴 것 우선(같은 문제 반복 방지). GAP일 이내 사용분은 뒤로.
    last_used = history.keyword_last_used()
    gap_days = int(os.getenv("CLIPCART_KEYWORD_GAP_DAYS", "10"))
    ranked = sorted(NICHES, key=lambda n: (last_used.get(n["keyword"], ""), n["keyword"]))
    fresh = [n for n in ranked if history.days_since(last_used.get(n["keyword"], "")) >= gap_days]
    niche_queue = fresh or ranked
    if force_keyword:
        niche_queue = [n for n in NICHES if n["keyword"] == force_keyword] or niche_queue

    for niche in niche_queue[:MAX_SEARCH_CALLS_PER_RUN]:
        try:
            items = search_products(niche["keyword"], limit=10, sub_id=sub_id)
        except Exception as exc:
            if "403" in str(exc) or "429" in str(exc):
                return None  # rate limit — 즉시 중단, 재시도 금지
            continue

        candidates = [
            it
            for it in items
            if PRICE_MIN <= int(it.get("productPrice") or 0) <= PRICE_MAX
            and not _is_excluded(it.get("productName", ""))
            and str(it.get("productId")) not in used_product_ids
            and history.name_key(it.get("productName", "")) not in used_names
            and it.get("productImage")
            and it.get("productUrl")
        ]
        if not candidates:
            continue
        # 로켓배송 우선, 그다음 검색 랭크 순
        candidates.sort(key=lambda x: (not x.get("isRocket"), x.get("rank", 99)))
        item = candidates[0]

        score = _derive_score(item)
        if score.decision == "REJECT":
            continue

        affiliate_url = _shorten_link(item, sub_id)
        product = {
            "product_id": f"CP{item['productId']}",
            "coupang_product_id": str(item["productId"]),
            "created_at": date.today().isoformat(),
            "status": "AUTO_SELECTED",
            "product_name": item.get("productName", ""),
            "display_name": niche["title_keyword"],
            "category": niche["category"],
            "source": "coupang_partners",
            "product_url": item.get("productUrl", ""),
            "affiliate_url": affiliate_url,
            "price": int(item.get("productPrice") or 0),
            "is_rocket": bool(item.get("isRocket")),
            "image_url": item.get("productImage", ""),
            "score": score.score,
            "score_breakdown": score.score_breakdown,
            "niche": niche,
            "problem": niche["problem"],
            "video_angle": niche["hook"],
            "known_downside": niche["downside"],
        }

        state["used_keywords"] = sorted(used_keywords | {niche["keyword"]})
        state["used_product_ids"] = sorted(set(state.get("used_product_ids", [])) | {str(item["productId"])})
        state["last_selected"] = {
            "date": date.today().isoformat(),
            "product_id": product["product_id"],
            "keyword": niche["keyword"],
        }
        _save_state(state)
        return product

    return None


_CLEAN_NAME_RE = re.compile(r"[,\[\(].*$")


def short_product_name(product: dict[str, Any]) -> str:
    """긴 쿠팡 상품명 대신 영상용 짧은 이름."""
    return product.get("display_name") or _CLEAN_NAME_RE.sub("", product.get("product_name", "")).strip()
