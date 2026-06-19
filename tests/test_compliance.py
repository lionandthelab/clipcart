"""컴플라이언스 하드게이트가 소스별 고지를 인식하는지 테스트."""

from __future__ import annotations

from clipcart.aliexpress import ALIEXPRESS_DISCLOSURE
from clipcart.coupang import COUPANG_DISCLOSURE
from clipcart.video.compliance import check_texts


LINK = "https://link.coupang.com/a/TEST"


def _creative(disclosure: str) -> dict:
    return {
        "title": "배수구 청소 아직도 손으로 하세요?",
        "description": f"{disclosure}\n\n👉 영상 속 제품 바로가기: {LINK}\n배수구 머리카락 치우기 곤욕인 사람에게.",
        "disclosure": disclosure,
        "affiliate_url": LINK,
        "pinned_comment": f"제품 보러가기 → {LINK}\n{disclosure}",
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


def test_valid_creative_with_link_passes_gate():
    assert check_texts(_creative(COUPANG_DISCLOSURE)) == []


def test_empty_affiliate_link_is_blocked():
    # 쿠팡 productUrl 없음·알리 promotion_link 빈값 등으로 링크가 비면
    # 클릭 0으로 직결 → 하드 차단
    c = _creative(COUPANG_DISCLOSURE)
    c["affiliate_url"] = ""
    c["pinned_comment"] = f"제품 보러가기 → \n{COUPANG_DISCLOSURE}"
    c["description"] = f"{COUPANG_DISCLOSURE}\n\n링크 없는 설명"
    assert any("제휴 링크" in issue for issue in check_texts(c))


def test_affiliate_link_absent_from_pinned_comment_is_blocked():
    c = _creative(COUPANG_DISCLOSURE)
    c["pinned_comment"] = f"제품 보러가기 → 프로필 링크 참고\n{COUPANG_DISCLOSURE}"
    assert any("고정댓글" in issue for issue in check_texts(c))


def test_affiliate_link_absent_from_description_is_blocked():
    c = _creative(COUPANG_DISCLOSURE)
    c["description"] = f"{COUPANG_DISCLOSURE}\n\n링크 없는 설명"
    assert any("설명란" in issue and "링크" in issue for issue in check_texts(c))


def test_banned_expression_in_pinned_comment_is_flagged():
    c = _creative(COUPANG_DISCLOSURE)
    c["pinned_comment"] = f"제품 보러가기 → {LINK} 무조건 사세요\n{COUPANG_DISCLOSURE}"
    assert any("금지 표현" in issue for issue in check_texts(c))


def test_affiliate_url_with_banned_substring_not_flagged_as_banned():
    # 폴백 raw URL에 '100%' 같은 ASCII 금지어가 부분일치해도, URL은 광고문구가
    # 아니므로 금지표현 오탐으로 차단되면 안 된다(리뷰 발견).
    url = "https://www.coupang.com/vp/products/x?d=100%"
    c = _creative(COUPANG_DISCLOSURE)
    c["affiliate_url"] = url
    c["pinned_comment"] = f"제품 보러가기 → {url}\n{COUPANG_DISCLOSURE}"
    c["description"] = f"{COUPANG_DISCLOSURE}\n\n👉 영상 속 제품 바로가기: {url}\n설명"
    assert not any("금지 표현" in issue for issue in check_texts(c))
