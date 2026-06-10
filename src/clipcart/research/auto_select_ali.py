"""AliExpress 어필리에이트 API 기반 상품 자동 선정.

쿠팡 선정기(auto_select)와 같은 니치 풀·점수 체계·중복차단 원장을 공유하되,
알리 응답 필드(target_sale_price/lastest_volume/promotion_link 등)에 맞춰 매핑한다.
알리는 한국어 키워드 검색이 동작하므로 별도 영어 키워드 매핑이 필요 없다.

선정 커서는 data/niche_state_ali.json(쿠팡과 분리),
권위 원장은 data/history.json(쿠팡과 공유 — 같은 니치 반복을 두 소스에 걸쳐 방지).
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from clipcart.aliexpress import generate_affiliate_links, query_products
from clipcart.config import DATA_DIR
from clipcart.research import history
from clipcart.research.niches import NICHES, PRODUCT_EXCLUDE_KEYWORDS, product_type_ok
from clipcart.research.scoring import ScoreInput, score_product

NICHE_STATE_FILE = DATA_DIR / "niche_state_ali.json"

# 알리는 초저가가 많다 — 쿠팡보다 하한을 낮춘다(과도한 저가/저품질은 점수에서 거른다)
PRICE_MIN = int(os.getenv("CLIPCART_ALI_PRICE_MIN", "2500"))
PRICE_MAX = int(os.getenv("CLIPCART_ALI_PRICE_MAX", "30000"))

MAX_SEARCH_CALLS_PER_RUN = 8


def _load_state() -> dict[str, Any]:
    if NICHE_STATE_FILE.exists():
        return json.loads(NICHE_STATE_FILE.read_text(encoding="utf-8"))
    return {"used_keywords": [], "used_product_ids": []}


def _save_state(state: dict[str, Any]) -> None:
    NICHE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    NICHE_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_excluded(name: str) -> bool:
    return any(kw in name for kw in PRODUCT_EXCLUDE_KEYWORDS)


def _price_of(item: dict[str, Any]) -> int:
    raw = item.get("target_sale_price") or item.get("sale_price") or 0
    try:
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return 0


def _volume_of(item: dict[str, Any]) -> int:
    try:
        return int(item.get("lastest_volume") or 0)
    except (TypeError, ValueError):
        return 0


def _rate_of(item: dict[str, Any]) -> float:
    try:
        return float(str(item.get("evaluate_rate") or "0").rstrip("%"))
    except (TypeError, ValueError):
        return 0.0


def _derive_score(item: dict[str, Any]) -> Any:
    price = _price_of(item)
    impulse = 5 if price < 10000 else 4 if price < 20000 else 3
    price_fit = 5 if 3000 <= price <= 20000 else 4
    rate, volume = _rate_of(item), _volume_of(item)
    review_trust = 5 if rate >= 90 and volume >= 300 else 4 if rate >= 85 or volume >= 100 else 3
    return score_product(
        f"AE{item['product_id']}",
        ScoreInput(
            problem_strength=5,  # 큐레이션 니치 = 검증된 문제
            video_ease=5,
            impulse_buy=impulse,
            review_trust=review_trust,
            price_fit=price_fit,
            claim_risk=1,
        ),
    )


def _has_link(item: dict[str, Any]) -> bool:
    return bool(item.get("product_detail_url") or item.get("promotion_link"))


def _resolve_affiliate_link(item: dict[str, Any], tracking_id: str | None) -> str:
    """선택된 제품의 제품별 딥 제휴링크를 link.generate로 생성.

    product.query의 promotion_link는 제품 무관 generic일 수 있어, detail_url로
    제품별 추적 링크를 따로 만든다. 실패 시 query 링크/원본 URL로 폴백.
    """
    detail = item.get("product_detail_url") or ""
    if detail:
        try:
            links = generate_affiliate_links([detail], tracking_id=tracking_id)
            promo = links[0].get("promotion_link") if links else ""
            if promo:
                return promo
        except Exception:  # noqa: BLE001
            pass
    return item.get("promotion_link") or detail


def select_today_product(force_keyword: str | None = None) -> dict[str, Any] | None:
    """오늘의 알리 상품 1개 선정. 실패 시 None."""
    tracking_id = os.getenv("ALIEXPRESS_TRACKING_ID") or None
    state = _load_state()
    used_keywords = set(state.get("used_keywords", []))
    used_product_ids = set(state.get("used_product_ids", [])) | history.used_aliexpress_ids()
    used_names = history.used_name_keys()

    # 니치 순서: 최근 덜 쓴 것 우선(쿠팡과 공유하는 히스토리 기준 → 두 소스가 같은 문제 반복 방지)
    last_used = history.keyword_last_used()
    gap_days = int(os.getenv("CLIPCART_KEYWORD_GAP_DAYS", "10"))
    ranked = sorted(NICHES, key=lambda n: (last_used.get(n["keyword"], ""), n["keyword"]))
    fresh = [n for n in ranked if history.days_since(last_used.get(n["keyword"], "")) >= gap_days]
    niche_queue = fresh or ranked
    if force_keyword:
        niche_queue = [n for n in NICHES if n["keyword"] == force_keyword] or niche_queue

    for niche in niche_queue[:MAX_SEARCH_CALLS_PER_RUN]:
        try:
            items = query_products(niche["keyword"], page_size=12, tracking_id=tracking_id)
        except Exception as exc:  # noqa: BLE001
            if any(t in str(exc).lower() for t in ("limit", "flow", "429", "qps")):
                return None  # rate limit — 즉시 중단
            continue

        candidates = [
            it
            for it in items
            if PRICE_MIN <= _price_of(it) <= PRICE_MAX
            and not _is_excluded(it.get("product_title", ""))
            and product_type_ok(it.get("product_title", ""), niche["keyword"])
            and str(it.get("product_id")) not in used_product_ids
            and history.name_key(it.get("product_title", "")) not in used_names
            and it.get("product_main_image_url")
            and _has_link(it)
        ]
        if not candidates:
            continue
        # 판매량 많은 순 → 평점 순 (검증된 인기 상품 우선)
        candidates.sort(key=lambda x: (_volume_of(x), _rate_of(x)), reverse=True)
        item = candidates[0]

        score = _derive_score(item)
        if score.decision == "REJECT":
            continue

        product = {
            "product_id": f"AE{item['product_id']}",
            "aliexpress_product_id": str(item["product_id"]),
            "created_at": date.today().isoformat(),
            "status": "AUTO_SELECTED",
            "product_name": item.get("product_title", ""),
            "display_name": niche["title_keyword"],
            "category": niche["category"],
            "source": "aliexpress",
            "product_url": item.get("product_detail_url", ""),
            "affiliate_url": _resolve_affiliate_link(item, tracking_id),
            "price": _price_of(item),
            "image_url": item.get("product_main_image_url", ""),
            "rating": _rate_of(item),
            "review_count": _volume_of(item),
            "score": score.score,
            "score_breakdown": score.score_breakdown,
            "niche": niche,
            "problem": niche["problem"],
            "video_angle": niche["hook"],
            "known_downside": niche["downside"],
        }

        state["used_keywords"] = sorted(used_keywords | {niche["keyword"]})
        state["used_product_ids"] = sorted(
            set(state.get("used_product_ids", [])) | {str(item["product_id"])}
        )
        state["last_selected"] = {
            "date": date.today().isoformat(),
            "product_id": product["product_id"],
            "keyword": niche["keyword"],
        }
        _save_state(state)
        return product

    return None
