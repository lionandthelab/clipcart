"""컴플라이언스 하드게이트가 소스별 고지를 인식하는지 테스트."""

from __future__ import annotations

from clipcart.aliexpress import ALIEXPRESS_DISCLOSURE
from clipcart.coupang import COUPANG_DISCLOSURE
from clipcart.video.compliance import check_texts


def _creative(disclosure: str) -> dict:
    return {
        "title": "배수구 청소 아직도 손으로 하세요?",
        "description": f"{disclosure}\n\n배수구 머리카락 치우기 곤욕인 사람에게.",
        "disclosure": disclosure,
        "scenes": [
            # 공정위 시작·끝 표시: 첫 장면(훅)과 마지막 장면 모두 고지 (실제 beats 동작)
            {"narration": "배수구 청소 아직도 손으로 하세요?", "caption": "", "disclosure": disclosure},
            {"narration": "링크는 고정 댓글에", "caption": "", "disclosure": disclosure},
        ],
    }


def test_aliexpress_disclosure_passes_gate():
    assert check_texts(_creative(ALIEXPRESS_DISCLOSURE)) == []


def test_coupang_disclosure_still_passes_gate():
    assert check_texts(_creative(COUPANG_DISCLOSURE)) == []


def test_missing_disclosure_in_description_is_flagged():
    c = _creative(ALIEXPRESS_DISCLOSURE)
    c["description"] = "고지 문구가 빠진 설명"
    assert any("고지" in issue for issue in check_texts(c))


def test_no_disclosure_scene_is_flagged():
    c = _creative(ALIEXPRESS_DISCLOSURE)
    c["scenes"] = [{"narration": "x", "caption": "", "disclosure": None}]
    assert any("고지 장면" in issue for issue in check_texts(c))


def test_banned_expression_still_flagged_for_aliexpress():
    c = _creative(ALIEXPRESS_DISCLOSURE)
    c["title"] = "이거 사면 무조건 해결됩니다"
    assert any("금지 표현" in issue for issue in check_texts(c))


def test_foreign_source_disclosure_contamination_is_flagged():
    # 알리 상품 설명에 쿠팡 고지가 섞이면 허위 고지 → 차단돼야
    c = _creative(ALIEXPRESS_DISCLOSURE)
    c["description"] = f"{ALIEXPRESS_DISCLOSURE}\n{COUPANG_DISCLOSURE}\n설명"
    assert any("혼입" in issue for issue in check_texts(c))


def test_coupang_only_description_has_no_contamination_flag():
    c = _creative(COUPANG_DISCLOSURE)
    assert not any("혼입" in issue for issue in check_texts(c))
