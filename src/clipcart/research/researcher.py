from __future__ import annotations

from datetime import date
from typing import Any

from clipcart.research.scoring import ScoreInput, score_product
from clipcart.research.seeds import CLEANING_PRODUCTS
from clipcart.storage import load_products, save_products

EXCLUDED_KEYWORDS = [
    "건강기능",
    "다이어트",
    "의료",
    "살균",
    "항균",
    "세균",
    "로봇청소기",
    "자석창문",
]


def _passes_compliance(name: str, risk_notes: str) -> bool:
    text = f"{name} {risk_notes}".lower()
    return not any(kw in text for kw in EXCLUDED_KEYWORDS)


def find_products(
    category: str = "청소",
    price_min: int = 3000,
    price_max: int = 30000,
    max_products: int = 30,
) -> dict[str, Any]:
    today = date.today().isoformat()
    batch_id = f"batch_{today.replace('-', '')}_001"

    candidates = [
        p
        for p in CLEANING_PRODUCTS
        if p["category"] == category
        and price_min <= p["price"] <= price_max
        and _passes_compliance(p["product_name"], p.get("risk_notes", ""))
    ][:max_products]

    scored: list[dict[str, Any]] = []
    for raw in candidates:
        result = score_product(
            raw["product_id"],
            ScoreInput(
                problem_strength=raw["ratings"]["problem_strength"],
                video_ease=raw["ratings"]["video_ease"],
                impulse_buy=raw["ratings"]["impulse_buy"],
                review_trust=raw["ratings"]["review_trust"],
                price_fit=raw["ratings"]["price_fit"],
                claim_risk=raw["ratings"]["claim_risk"],
                regulatory_risk=raw.get("regulatory_risk", False),
            ),
        )
        if result.decision == "REJECT":
            continue

        scored.append(
            {
                "product_id": raw["product_id"],
                "created_at": today,
                "status": "CANDIDATE",
                "product_name": raw["product_name"],
                "category": raw["category"],
                "source": raw["source"],
                "product_url": raw["product_url"],
                "affiliate_url": raw.get("affiliate_url") or raw["product_url"],
                "price": raw["price"],
                "rating": raw.get("rating"),
                "review_count": raw.get("review_count"),
                "score": result.score,
                "score_breakdown": result.score_breakdown,
                "problem": raw["problem_statement"],
                "video_angle": raw["video_angle"],
                "before_scene": raw.get("before_scene", ""),
                "after_scene": raw.get("after_scene", ""),
                "known_downside": raw.get("known_downside", ""),
                "why_selected": raw.get("why_selected", ""),
                "risk": raw.get("risk_notes", ""),
                "risk_status": "PASS",
                "human_approval": "PENDING",
                "decision": result.decision,
                "decision_reason": result.reason,
            }
        )

    scored.sort(key=lambda p: p["score"], reverse=True)
    recommended = scored[:8]

    existing = {p["product_id"]: p for p in load_products()}
    for p in scored:
        existing[p["product_id"]] = p
    save_products(list(existing.values()))

    return {
        "date": today,
        "batch_id": batch_id,
        "summary": f"{category} 카테고리 후보 {len(candidates)}개 중 {len(recommended)}개 추천",
        "products": [
            {
                "product_id": p["product_id"],
                "product_name": p["product_name"],
                "category": p["category"],
                "product_url": p["product_url"],
                "affiliate_url": p["affiliate_url"],
                "price": p["price"],
                "rating": p.get("rating"),
                "review_count": p.get("review_count"),
                "score": p["score"],
                "problem": p["problem"],
                "video_angle": p["video_angle"],
                "why_selected": p.get("why_selected", ""),
                "known_downside": p.get("known_downside", ""),
                "risk": p.get("risk", ""),
                "human_action": f"APPROVE {p['product_id']} 또는 REJECT {p['product_id']}",
            }
            for p in recommended
        ],
    }
