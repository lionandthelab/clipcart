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


def test_live_entries_only_include_actually_public_videos():
    # posts 원장의 PUBLISHED가 실제 공개와 어긋날 수 있다(운영자 비공개 처리 등,
    # P001 실측) — YouTube 조회로 살아있는 영상의 제품만 페이지에 올린다.
    from clipcart.bio.page import live_published_entries

    posts = [
        {"post_id": "live1", "product_id": "CP884", "platform": "youtube_shorts",
         "status": "PUBLISHED", "source": "coupang", "published_at": "2026-06-10T07:20:00",
         "title": "t1", "affiliate_url": "https://link.coupang.com/a/V1"},
        {"post_id": "dead1", "product_id": "CP999", "platform": "youtube_shorts",
         "status": "PUBLISHED", "source": "coupang", "published_at": "2026-06-09T07:20:00",
         "title": "t2", "affiliate_url": "https://link.coupang.com/a/V2"},
        {"post_id": "x", "product_id": "CP777", "platform": "youtube_shorts",
         "status": "REPLACED_PRIVATE_MISMATCH", "source": "coupang",
         "published_at": "2026-06-08T07:20:00", "title": "t3", "affiliate_url": "u"},
    ]
    products = {"CP884": {"product_name": "배수구 거름망", "coupang_product_id": "884"}}
    entries = live_published_entries(posts, {"live1"}, products)
    assert [e["product_id"] for e in entries] == ["CP884"]
    assert entries[0]["coupang_product_id"] == "884"
    assert entries[0]["date"] == "2026-06-10"
    assert entries[0]["product_name"] == "배수구 거름망"


def test_localize_images_downloads_once_and_soft_fails(tmp_path):
    # CDN 핫링크는 브라우저/지역에 따라 차단될 수 있다 — 빌드 시 로컬 동봉.
    from clipcart.bio.page import localize_images

    calls = []

    def fake_fetch(url, timeout=20):
        calls.append(url)

        class R:
            ok = "bad" not in url
            content = b"x" * 20000

        return R()

    entries = [{"product_id": "CP1"}, {"product_id": "CP2"}]
    products = {
        "CP1": {"image_url": "https://cdn/ok.jpg"},
        "CP2": {"image_url": "https://cdn/bad.jpg"},
    }
    images = localize_images(entries, products, tmp_path, fetch=fake_fetch)
    assert images == {"CP1": "img/CP1.jpg"}
    assert (tmp_path / "img" / "CP1.jpg").exists()
    # 재실행 시 캐시 사용(재다운로드 없음)
    images2 = localize_images(entries, products, tmp_path, fetch=fake_fetch)
    assert images2 == {"CP1": "img/CP1.jpg"}
    assert calls.count("https://cdn/ok.jpg") == 1


def test_render_page_prefers_local_image():
    e = _entry("CP2", name="새제품")
    html = render_page([e], {"CP2": _product("CP2")}, {"CP2": "u2"}, images={"CP2": "img/CP2.jpg"})
    assert 'src="img/CP2.jpg"' in html
    assert "https://img/x.jpg" not in html  # 핫링크 미사용


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
