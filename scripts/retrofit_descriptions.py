"""기존 라이브 영상 설명문을 현재 format_profile 템플릿으로 일괄 갱신.

제목·태그는 보존하고 description만 현재 템플릿(프로필/bio 링크 CTA)으로 교체한다.
신규 업로드는 데일리 파이프라인이 자동으로 현재 템플릿을 쓰므로, 이 스크립트는
과거에 올라간 영상의 설명문을 새 CTA로 맞추는 **백필용**이다(템플릿이 바뀌면 재실행).

게시 전 컴플라이언스 게이트(check_texts)를 그대로 적용 — 금지어/고지 누락 시 그
영상만 건너뛴다(전체 중단 아님).

사용:
  python scripts/retrofit_descriptions.py          # dry-run: 무엇을 바꿀지 출력만
  python scripts/retrofit_descriptions.py --live    # 실제 YouTube 설명문 업데이트
"""

from __future__ import annotations

import sys

import clipcart.config  # noqa: F401 — import 시 .env 로드(load_dotenv)
from clipcart.storage import load_posts, load_products
from clipcart.video.compliance import check_texts
from clipcart.video.copywriter import build_creative
from clipcart.video.profile import load_profile


def live_youtube_posts(posts: list[dict]) -> list[dict]:
    return [
        p
        for p in posts
        if p.get("platform") == "youtube_shorts"
        and p.get("status") == "PUBLISHED"
        and p.get("post_id")
    ]


def rebuilt_creative(post: dict, product: dict, profile: dict) -> dict:
    """게시된 링크(subId 포함)를 그대로 살려 현재 템플릿으로 creative 재생성."""
    prod = dict(product)
    # 설명문 링크는 그 영상의 실제 게시 링크(상품별 subId)여야 측정이 맞다
    prod["affiliate_url"] = post.get("affiliate_url") or prod.get("affiliate_url")
    return build_creative(prod, profile)


def main(live: bool) -> int:
    posts = load_posts()
    products = {p.get("product_id"): p for p in load_products()}
    profile = load_profile()
    targets = live_youtube_posts(posts)

    publisher = None
    if live:
        from clipcart.publishing.youtube import YouTubePublisher

        publisher = YouTubePublisher()

    ok = skipped = failed = 0
    log_lines: list[str] = []
    for post in targets:
        vid = post["post_id"]
        pid = post.get("product_id", "")
        product = products.get(pid)
        if not product or not product.get("niche"):
            skipped += 1
            log_lines.append(f"SKIP  {vid}  {pid}  (product/niche 없음)")
            continue

        creative = rebuilt_creative(post, product, profile)
        title = post.get("title") or creative["title"]
        description = creative["description"]
        tags = list(profile.get("tags") or [])

        issues = check_texts({**creative, "title": title})
        if issues:
            skipped += 1
            log_lines.append(f"SKIP  {vid}  {pid}  컴플라이언스: {issues}")
            continue

        if not live:
            ok += 1
            log_lines.append(f"DRY   {vid}  {pid}  설명문 {len(description)}자 갱신 예정")
            continue

        success = publisher.update_metadata(vid, title, description, tags)
        if success:
            ok += 1
            log_lines.append(f"OK    {vid}  {pid}  설명문 갱신 완료")
        else:
            failed += 1
            log_lines.append(f"FAIL  {vid}  {pid}  YouTube update_metadata 실패")

    mode = "LIVE" if live else "DRY-RUN"
    summary = f"[{mode}] 대상 {len(targets)}편 · 성공 {ok} · 건너뜀 {skipped} · 실패 {failed}"
    report = "\n".join([summary, *log_lines])
    sys.stdout.buffer.write((report + "\n").encode("utf-8"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(live="--live" in sys.argv))
