"""전자동 데일리 파이프라인.

선정 → 대본/메타 생성 → 영상 렌더링 → 컴플라이언스 검수 → YouTube 업로드 → 기록.
컴플라이언스 검사가 하나라도 실패하면 게시하지 않는다.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from pathlib import Path

from clipcart.config import LOGS_DIR, OUTBOX_DIR
from clipcart.publishing.youtube import YouTubePublisher
from clipcart.research.auto_select import select_today_product
from clipcart.storage import load_posts, load_products, save_posts, upsert_product
from clipcart.video.compliance import check_texts, check_video
from clipcart.video.copywriter import build_creative
from clipcart.video.engine import make_video
from clipcart.video.profile import load_profile


def _log(entry: dict[str, Any]) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"at": datetime.now(timezone.utc).isoformat(), **entry}
    with (LOGS_DIR / "publishing.log").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _already_posted_today() -> dict[str, Any] | None:
    today = date.today().isoformat()
    for post in load_posts():
        if post.get("platform") == "youtube_shorts" and str(post.get("published_at", "")).startswith(today):
            return post
    return None


def _todays_ready_product() -> dict[str, Any] | None:
    """오늘 이미 렌더링까지 끝난(미게시) 상품 — 재실행 시 재선정/재렌더 방지."""
    today = date.today().isoformat()
    for p in load_products():
        if (
            p.get("status") == "VIDEO_READY"
            and p.get("created_at") == today
            and p.get("video_path")
            and Path(p["video_path"]).exists()
        ):
            return p
    return None


def run_daily(live: bool = False, force: bool = False, keyword: str | None = None) -> dict[str, Any]:
    if not force:
        existing = _already_posted_today()
        if existing:
            return {
                "status": "SKIPPED",
                "reason": f"오늘 이미 게시됨: {existing.get('post_url')}",
            }

    resume = None if keyword else _todays_ready_product()
    if resume:
        product = resume
        creative = build_creative(product, load_profile())
        video_path = Path(product["video_path"])
        thumb_path = OUTBOX_DIR / "publishing" / f"{product['product_id']}_thumb.jpg"
    else:
        product = select_today_product(force_keyword=keyword)
        if not product:
            result = {"status": "FAILED", "reason": "조건에 맞는 상품을 찾지 못함", "next_action": "니치 풀 점검"}
            _log(result)
            return result

        package = make_video(product)
        creative = package["creative"]
        video_path = package["video_path"]
        thumb_path = package["thumbnail_path"]

    issues = check_texts(creative) + check_video(video_path)
    if issues:
        result = {
            "status": "BLOCKED",
            "product_id": product["product_id"],
            "issues": issues,
            "video_path": str(video_path),
        }
        upsert_product({**product, "status": "NEEDS_REVISION", "compliance_issues": issues})
        _log(result)
        return result

    upsert_product({**product, "status": "VIDEO_READY", "video_path": str(video_path)})

    if not live:
        result = {
            "status": "DRY_RUN_OK",
            "product_id": product["product_id"],
            "product_name": product["product_name"],
            "price": product["price"],
            "affiliate_url": product["affiliate_url"],
            "title": creative["title"],
            "video_path": str(video_path),
            "thumbnail_path": str(thumb_path),
            "next_action": "clipcart daily --live",
        }
        _log(result)
        return result

    yt = YouTubePublisher()
    publish_result = yt.publish(
        video_path,
        creative["title"],
        creative["description"],
        creative["tags"],
        dry_run=False,
    )

    if not publish_result.success:
        result = {
            "status": "FAILED",
            "product_id": product["product_id"],
            "platform": "youtube_shorts",
            "reason": publish_result.error,
            "video_path": str(video_path),
        }
        _log(result)
        return result

    thumbnail_set = yt.set_thumbnail(publish_result.post_id, thumb_path)

    now = datetime.now(timezone.utc).isoformat()
    posts = load_posts()
    posts.append(
        {
            "post_id": publish_result.post_id,
            "product_id": product["product_id"],
            "platform": "youtube_shorts",
            "post_url": publish_result.post_url,
            "published_at": now,
            "status": "PUBLISHED",
            "title": creative["title"],
            "affiliate_url": product["affiliate_url"],
            "thumbnail_set": thumbnail_set,
        }
    )
    save_posts(posts)
    upsert_product({**product, "status": "PUBLISHED", "post_url": publish_result.post_url})

    result = {
        "status": "PUBLISHED",
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "price": product["price"],
        "title": creative["title"],
        "post_url": publish_result.post_url,
        "affiliate_url": product["affiliate_url"],
        "thumbnail_set": thumbnail_set,
        "pinned_comment_suggestion": creative["pinned_comment"],
        "manual_steps": [
            "YouTube Studio에서 '유료 프로모션 포함' 체크 (API 설정 불가)",
            "고정댓글로 pinned_comment_suggestion 등록",
        ],
    }
    _log(result)
    return result
