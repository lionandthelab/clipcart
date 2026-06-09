from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoreInput:
    problem_strength: int  # 1-5
    video_ease: int
    impulse_buy: int
    review_trust: int
    price_fit: int
    claim_risk: int  # 1-5, higher = worse
    regulatory_risk: bool = False


@dataclass
class ScoreResult:
    score: int
    score_breakdown: dict[str, int]
    decision: str
    reason: str
    human_review_required: bool


def score_product(product_id: str, inp: ScoreInput) -> ScoreResult:
    if inp.regulatory_risk:
        return ScoreResult(
            score=0,
            score_breakdown={
                "problem_strength": 0,
                "video_ease": 0,
                "impulse_buy": 0,
                "review_trust": 0,
                "price_fit": 0,
                "claim_risk": 0,
                "regulatory_risk": 100,
            },
            decision="REJECT",
            reason="규제 위험 카테고리",
            human_review_required=False,
        )

    breakdown = {
        "problem_strength": inp.problem_strength * 6,
        "video_ease": inp.video_ease * 5,
        "impulse_buy": inp.impulse_buy * 4,
        "review_trust": inp.review_trust * 3,
        "price_fit": inp.price_fit * 2,
        "claim_risk": inp.claim_risk * 4,
        "regulatory_risk": 0,
    }
    total = (
        breakdown["problem_strength"]
        + breakdown["video_ease"]
        + breakdown["impulse_buy"]
        + breakdown["review_trust"]
        + breakdown["price_fit"]
        - breakdown["claim_risk"]
    )

    if total >= 80:
        decision = "APPROVE_CANDIDATE"
        reason = "강력 추천. 사람 승인 요청."
    elif total >= 70:
        decision = "APPROVE_CANDIDATE"
        reason = "보류. 대체 상품과 비교 후 승인 검토."
    elif total >= 60:
        decision = "APPROVE_CANDIDATE"
        reason = "테스트 후보. 우선순위 낮음."
    else:
        decision = "REJECT"
        reason = "점수 미달"

    return ScoreResult(
        score=total,
        score_breakdown=breakdown,
        decision=decision,
        reason=reason,
        human_review_required=decision == "APPROVE_CANDIDATE",
    )
