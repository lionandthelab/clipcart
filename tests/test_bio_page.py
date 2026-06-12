"""링크인바이오 정적 페이지 생성기 테스트.

채널 설명에 둘 단일 URL → 게시 이력 전체의 제품 링크 모음 페이지.
쿠팡 링크는 bio 전용 subId(`bio{상품ID}`)로 재생성해 채널설명발
클릭을 영상발 클릭과 분리 측정한다. 알리는 subId 미지원이라
기존 제휴링크를 그대로 쓴다.
"""

from __future__ import annotations

from clipcart.bio.page import bio_sub_id, ensure_bio_links, render_page


def _entry(pid, source="coupang", name="배수구 거름망", url="https://link.coupang.com/a/V1"):
    return {
        "product_id": pid,
        "coupang_product_id": pid.removeprefix("CP") if pid.startswith("CP") else None,
        "source": source,
        "product_name": name,
        "title": f"{name} 영상",
        "date": "2026-06-12",
        "affiliate_url": url,
    }


def _product(pid, **over):
    base = {
        "product_id": pid,
        "product_url": f"https://www.coupang.com/vp/products/{pid.removeprefix('CP')}",
        "image_url": "https://img/x.jpg",
        "price": 6900,
        "display_name": "배수구 거름망",
    }
    base.update(over)
    return base


def test_bio_sub_id_for_coupang_only():
    assert bio_sub_id(_entry("CP884")) == "bio884"
    assert bio_sub_id(_entry("AE100", source="aliexpress")) is None


def test_ensure_bio_links_regenerates_coupang_with_bio_sub_id():
    captured = {}

    def fake_deeplink(urls, sub_id=None):
        captured["urls"], captured["sub_id"] = urls, sub_id
        return [{"shortenUrl": "https://link.coupang.com/a/BIO1"}]

    cache: dict = {}
    links = ensure_bio_links([_entry("CP884")], cache, fake_deeplink)
    assert links["CP884"] == "https://link.coupang.com/a/BIO1"
    assert captured["sub_id"] == "bio884"
    # products.json의 product_url은 link.coupang.com 추적링크라 딥링크 변환이
    # 거부된다("url convert failed" 실측) — 일반 상품 페이지 URL을 직접 구성한다
    assert captured["urls"] == ["https://www.coupang.com/vp/products/884"]
    assert cache["CP884"] == "https://link.coupang.com/a/BIO1"  # 재호출 방지 캐시


def test_ensure_bio_links_uses_cache_without_api_call():
    def boom(urls, sub_id=None):
        raise AssertionError("캐시가 있으면 API를 부르지 않는다")

    cache = {"CP884": "https://link.coupang.com/a/CACHED"}
    links = ensure_bio_links([_entry("CP884")], cache, boom)
    assert links["CP884"] == "https://link.coupang.com/a/CACHED"


def test_ensure_bio_links_falls_back_on_api_error():
    def boom(urls, sub_id=None):
        raise RuntimeError("API down")

    links = ensure_bio_links([_entry("CP884", url="https://link.coupang.com/a/V1")], {}, boom)
    assert links["CP884"] == "https://link.coupang.com/a/V1"  # 원본 링크 폴백


def test_render_page_disclosure_first_newest_first_dedup():
    e_old = {**_entry("CP1", name="옛제품"), "date": "2026-06-01"}
    e_new = {**_entry("CP2", name="새제품"), "date": "2026-06-12"}
    e_dup = {**_entry("CP2", name="새제품"), "date": "2026-06-11"}
    ali = {**_entry("AE3", source="aliexpress", name="알리제품", url="https://s.click.aliexpress.com/e/_X"), "date": "2026-06-05"}
    html = render_page(
        [e_old, e_new, e_dup, ali],
        {"CP2": _product("CP2", display_name="새제품")},  # 영상용 짧은 이름이 표기 우선
        {"CP1": "u1", "CP2": "u2", "AE3": "https://s.click.aliexpress.com/e/_X"},
    )

    assert "쿠팡 파트너스 활동의 일환" in html
    assert "알리익스프레스 어필리에이트" in html
    # 고지가 첫 상품 링크보다 먼저 (공정위: 첫 부분 고지)
    assert html.index("쿠팡 파트너스") < html.index("u2")
    # 최신순 + product_id 중복 제거
    assert html.index("새제품") < html.index("알리제품") < html.index("옛제품")
    assert html.count("<strong>새제품</strong>") == 1  # 카드 1장 (img alt 중복 제외)
    assert 'rel="sponsored nofollow"' in html
