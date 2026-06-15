"""링크인바이오 정적 페이지 생성기.

채널 설명·프로필에 둘 단일 URL이 게시 이력 전체의 제품 링크 모음으로
연결된다(inpock 대체 — API 없는 외부 서비스 대신 자체 정적 페이지).
쿠팡 링크는 bio 전용 subId(`bio{상품ID}`)로 재생성해 채널설명발 클릭을
영상발 클릭과 분리 측정한다. 알리는 subId 미지원이라 기존 링크 사용.
"""

from __future__ import annotations

import html as html_mod
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from clipcart.aliexpress import ALIEXPRESS_DISCLOSURE
from clipcart.config import DATA_DIR
from clipcart.coupang import COUPANG_DISCLOSURE

BIO_LINKS_FILE = DATA_DIR / "bio_links.json"

DeeplinkFn = Callable[..., list[dict[str, Any]]]


def bio_sub_id(entry: dict[str, Any]) -> str | None:
    """bio 페이지 전용 subId. 쿠팡만 지원(알리는 subId 개념 없음)."""
    cp_id = entry.get("coupang_product_id")
    if (entry.get("source") or "coupang").startswith("coupang") and cp_id:
        return f"bio{cp_id}"
    return None


def ensure_bio_links(
    entries: list[dict[str, Any]],
    cache: dict[str, str],
    deeplink_fn: DeeplinkFn,
) -> dict[str, str]:
    """항목별 bio 링크 확보. 쿠팡은 bio subId 딥링크(캐시), 실패·미지원은 원본 폴백."""
    links: dict[str, str] = {}
    for entry in entries:
        pid = entry.get("product_id", "")
        if pid in cache:
            links[pid] = cache[pid]
            continue
        sub_id = bio_sub_id(entry)
        # products.json의 product_url은 link.coupang.com 추적링크라 딥링크 변환이
        # 거부됨("url convert failed") — 일반 상품 페이지 URL을 직접 구성한다
        cp_id = entry.get("coupang_product_id")
        product_url = f"https://www.coupang.com/vp/products/{cp_id}" if cp_id else None
        if sub_id and product_url:
            try:
                res = deeplink_fn([product_url], sub_id=sub_id)
                short = res[0].get("shortenUrl") if res else ""
                if short:
                    cache[pid] = short
                    links[pid] = short
                    continue
            except Exception:  # noqa: BLE001 — 링크 1건 실패가 페이지 전체를 막지 않는다
                pass
        links[pid] = entry.get("affiliate_url", "")
    return links


def live_published_entries(
    posts: list[dict[str, Any]],
    live_video_ids: set[str],
    products_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """현재 실제 공개 중인 영상의 제품만. posts 원장의 PUBLISHED는 실제 공개와
    어긋날 수 있어(운영자 비공개 처리 등, P001 실측) YouTube 조회 결과로 거른다."""
    out = []
    for p in posts:
        if p.get("platform") != "youtube_shorts" or p.get("status") != "PUBLISHED":
            continue
        if p.get("post_id") not in live_video_ids:
            continue
        pid = p.get("product_id", "")
        prod = products_by_id.get(pid) or {}
        cp_id = prod.get("coupang_product_id") or (
            pid.removeprefix("CP") if pid.startswith("CP") else None
        )
        out.append(
            {
                "product_id": pid,
                "coupang_product_id": cp_id,
                "source": p.get("source", "coupang"),
                "product_name": prod.get("product_name") or p.get("title", ""),
                "date": str(p.get("published_at", ""))[:10],
                "affiliate_url": p.get("affiliate_url", ""),
            }
        )
    return out


def localize_images(
    entries: list[dict[str, Any]],
    products_by_id: dict[str, dict[str, Any]],
    out_dir: Path,
    fetch: Callable[..., Any] | None = None,
) -> dict[str, str]:
    """제품 이미지를 빌드 시 내려받아 페이지에 동봉. CDN 핫링크는 브라우저/지역에
    따라 차단될 수 있다(멀티탭 정리함 실측). 실패는 항목 단위 soft-fail."""
    if fetch is None:
        fetch = requests.get
    images: dict[str, str] = {}
    img_dir = out_dir / "img"
    for entry in entries:
        pid = entry.get("product_id", "")
        rel = f"img/{pid}.jpg"
        dest = img_dir / f"{pid}.jpg"
        if dest.exists():
            images[pid] = rel
            continue
        url = (products_by_id.get(pid) or {}).get("image_url")
        if not url:
            continue
        try:
            r = fetch(url, timeout=20)
            if r.ok and len(r.content) > 1000:
                img_dir.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(r.content)
                images[pid] = rel
        except Exception:  # noqa: BLE001
            continue
    return images


def _dedupe_newest_first(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(entries, key=lambda e: e.get("date", ""), reverse=True)
    seen: set[str] = set()
    out = []
    for e in ordered:
        pid = e.get("product_id", "")
        if pid and pid not in seen:
            seen.add(pid)
            out.append(e)
    return out


def _price_html(p: dict[str, Any], esc: Callable[[str], str]) -> str:
    """가격 줄. 원가·할인%가 있으면(알리 API) 정가 취소선 + 할인 배지."""
    price = p.get("price")
    if not price:
        return ""
    orig = p.get("original_price")
    disc = p.get("discount_pct")
    if orig and disc:
        return (
            f"<s>{int(orig):,}원</s> <b>{int(price):,}원</b> "
            f"<em>{int(disc)}%↓</em>"
        )
    return f"{int(price):,}원"


def _proof_html(p: dict[str, Any], is_ali: bool) -> str:
    """사회적 증거. 알리는 만족도%(evaluate_rate)·판매량, 쿠팡은 별점·리뷰수."""
    try:
        rating = float(p.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0.0
    reviews = int(p.get("review_count") or 0)
    bits: list[str] = []
    if is_ali:
        if rating:
            bits.append(f"만족도 {rating:g}%")
        if reviews:
            bits.append(f"{reviews:,}개 판매")
    else:
        if rating:
            bits.append(f"★{rating:g}")
        if reviews:
            bits.append(f"리뷰 {reviews:,}")
    return " · ".join(bits)


def _card_html(
    e: dict[str, Any],
    products_by_id: dict[str, dict[str, Any]],
    links: dict[str, str],
    images: dict[str, str] | None,
    esc: Callable[[str], str],
    *,
    highlight: bool = False,
) -> str:
    pid = e.get("product_id", "")
    p = products_by_id.get(pid) or {}
    url = links.get(pid) or e.get("affiliate_url", "")
    if not url:
        return ""
    name = esc(p.get("display_name") or e.get("product_name", ""))
    is_ali = "ali" in (e.get("source") or "")
    badge = "알리익스프레스" if is_ali else "쿠팡"
    price_txt = _price_html(p, esc)
    proof = _proof_html(p, is_ali)
    # 로컬 동봉 이미지 우선 — CDN 핫링크는 환경에 따라 차단될 수 있다
    img_src = (images or {}).get(pid) or p.get("image_url", "")
    img = f'<img src="{esc(img_src)}" alt="{name}" loading="lazy">' if img_src else ""
    proof_span = f"<span class='proof'>{esc(proof)}</span>" if proof else ""
    cls = "card hot" if highlight else "card"
    return (
        f'<a class="{cls}" href="{esc(url)}" target="_blank" rel="sponsored nofollow">'
        f"{img}<div class='meta'><strong>{name}</strong>"
        f"<span>{price_txt} · {badge}</span>{proof_span}</div></a>"
    )


def render_page(
    entries: list[dict[str, Any]],
    products_by_id: dict[str, dict[str, Any]],
    links: dict[str, str],
    images: dict[str, str] | None = None,
) -> str:
    """모바일 우선 단일 HTML. 고지는 첫 부분(공정위), 최신 게시 순.

    맨 위 '오늘의 제품'(최신 1건)을 강조하고, 나머지는 카테고리로 묶는다 —
    대다수 유입이 최신 영상이라 방금 본 제품을 바로 찾게 하고, 과거 영상
    시청자는 카테고리로 탐색하게 한다.
    """
    items = _dedupe_newest_first(entries)
    esc = html_mod.escape

    sections: list[str] = []
    if items:
        top = _card_html(items[0], products_by_id, links, images, esc, highlight=True)
        if top:
            sections.append('<div class="label">오늘의 제품</div>')
            sections.append(top)
        # 나머지를 카테고리별로(첫 등장=최신 순서 보존)
        groups: dict[str, list[dict[str, Any]]] = {}
        order: list[str] = []
        for e in items[1:]:
            cat = (products_by_id.get(e.get("product_id", "")) or {}).get("category") or "기타"
            if cat not in groups:
                groups[cat] = []
                order.append(cat)
            groups[cat].append(e)
        for cat in order:
            rendered = [
                _card_html(e, products_by_id, links, images, esc) for e in groups[cat]
            ]
            rendered = [c for c in rendered if c]
            if rendered:
                sections.append(f'<div class="label">{esc(cat)}</div>')
                sections.extend(rendered)
    cards = sections

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>살림해결소 — 영상 속 제품 링크</title>
<style>
body{{font-family:-apple-system,'Apple SD Gothic Neo','Noto Sans KR',sans-serif;margin:0;background:#f6f6f4;color:#222}}
.wrap{{max-width:480px;margin:0 auto;padding:20px 16px 48px}}
h1{{font-size:22px;margin:8px 0 4px}}
.disclosure{{font-size:12px;color:#666;background:#fff;border:1px solid #e5e5e0;border-radius:10px;padding:10px 12px;margin:12px 0 20px;line-height:1.6}}
.card{{display:flex;gap:12px;align-items:center;background:#fff;border:1px solid #e5e5e0;border-radius:14px;padding:12px;margin-bottom:12px;text-decoration:none;color:inherit}}
.card img{{width:72px;height:72px;object-fit:cover;border-radius:10px;flex:none}}
.card .meta{{display:flex;flex-direction:column;gap:4px;font-size:14px}}
.card .meta span{{color:#888;font-size:12px}}
.card.hot{{border-color:#FFD400;border-width:2px}}
.label{{font-size:13px;font-weight:700;color:#666;margin:20px 4px 8px}}
.label:first-of-type{{margin-top:4px}}
.card .meta span.proof{{color:#aaa;font-size:11px}}
.card .meta s{{color:#bbb;font-size:12px}}
.card .meta b{{font-size:14px}}
.card .meta em{{color:#FF3B30;font-style:normal;font-weight:700;font-size:12px}}
footer{{font-size:11px;color:#999;text-align:center;margin-top:28px}}
</style>
</head>
<body>
<div class="wrap">
<h1>살림해결소</h1>
<p style="font-size:14px;color:#555;margin:0">영상에서 소개한 제품을 모아뒀습니다.</p>
<div class="disclosure">{esc(COUPANG_DISCLOSURE)}<br>{esc(ALIEXPRESS_DISCLOSURE)}</div>
{chr(10).join(cards)}
<footer>업데이트: {generated} · 살림해결소</footer>
</div>
</body>
</html>
"""


def build_bio_page(output_path: Path | None = None) -> dict[str, Any]:
    """현재 공개 중인 게시물 기준으로 bio 페이지 생성. 이미지 동봉, 링크 캐시 갱신."""
    from clipcart.coupang import create_deeplinks
    from clipcart.storage import load_posts, load_products

    posts = load_posts()
    products_by_id = {p.get("product_id"): p for p in load_products()}

    # 실제 공개 상태 검증 — 원장이 PUBLISHED여도 비공개 처리된 영상이 있다(P001 실측).
    # 조회 실패 시(키 없음 등) 원장 그대로 폴백: 페이지가 비는 것보다 낫다.
    video_ids = [
        p["post_id"]
        for p in posts
        if p.get("post_id") and p.get("platform") == "youtube_shorts" and p.get("status") == "PUBLISHED"
    ]
    try:
        from clipcart.analytics.collector import fetch_video_stats

        live_ids = set(fetch_video_stats(video_ids).keys())
    except Exception:  # noqa: BLE001
        live_ids = set(video_ids)

    entries = live_published_entries(posts, live_ids, products_by_id)

    cache: dict[str, str] = {}
    if BIO_LINKS_FILE.exists():
        text = BIO_LINKS_FILE.read_text(encoding="utf-8").strip()
        cache = json.loads(text) if text else {}
    links = ensure_bio_links(entries, cache, create_deeplinks)
    BIO_LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    BIO_LINKS_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    out = output_path or (Path(__file__).resolve().parents[3] / "docs" / "bio" / "index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    images = localize_images(entries, products_by_id, out.parent)
    html = render_page(entries, products_by_id, links, images=images)
    out.write_text(html, encoding="utf-8")
    return {
        "output": str(out),
        "items": len({e.get("product_id") for e in entries}),
        "excluded_not_live": len(video_ids) - len(live_ids & set(video_ids)),
    }
