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


def render_page(
    entries: list[dict[str, Any]],
    products_by_id: dict[str, dict[str, Any]],
    links: dict[str, str],
) -> str:
    """모바일 우선 단일 HTML. 고지는 첫 부분(공정위), 최신 게시 순."""
    items = _dedupe_newest_first(entries)
    esc = html_mod.escape

    cards = []
    for e in items:
        pid = e.get("product_id", "")
        p = products_by_id.get(pid) or {}
        url = links.get(pid) or e.get("affiliate_url", "")
        if not url:
            continue
        name = esc(p.get("display_name") or e.get("product_name", ""))
        price = p.get("price")
        price_txt = f"{int(price):,}원" if price else ""
        badge = "알리익스프레스" if "ali" in (e.get("source") or "") else "쿠팡"
        img = (
            f'<img src="{esc(p["image_url"])}" alt="{name}" loading="lazy">'
            if p.get("image_url")
            else ""
        )
        cards.append(
            f'<a class="card" href="{esc(url)}" target="_blank" rel="sponsored nofollow">'
            f"{img}<div class='meta'><strong>{name}</strong>"
            f"<span>{price_txt} · {badge}</span></div></a>"
        )

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
    """history + products로 bio 페이지 생성, bio 링크 캐시 갱신."""
    from clipcart.coupang import create_deeplinks
    from clipcart.research.history import load_history
    from clipcart.storage import load_products

    entries = load_history()
    products_by_id = {p.get("product_id"): p for p in load_products()}
    cache: dict[str, str] = {}
    if BIO_LINKS_FILE.exists():
        text = BIO_LINKS_FILE.read_text(encoding="utf-8").strip()
        cache = json.loads(text) if text else {}

    links = ensure_bio_links(entries, cache, create_deeplinks)
    BIO_LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    BIO_LINKS_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    html = render_page(entries, products_by_id, links)
    out = output_path or (Path(__file__).resolve().parents[3] / "docs" / "bio" / "index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return {"output": str(out), "items": len({e.get('product_id') for e in entries})}
