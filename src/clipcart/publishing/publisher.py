from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from clipcart.config import DEFAULT_DISCLOSURE, INBOX_DIR
from clipcart.publishing.instagram import InstagramPublisher
from clipcart.publishing.pinterest import PinterestPublisher
from clipcart.publishing.tiktok import TikTokPublisher
from clipcart.publishing.youtube import YouTubePublisher
from clipcart.storage import load_posts, load_products, save_posts

DEFAULT_PLATFORMS = ["instagram_reels", "tiktok", "pinterest"]


def _build_caption(product: dict[str, Any]) -> str:
    downside = product.get("known_downside") or product.get("risk") or "사용 환경에 따라 다름"
    problem = product.get("problem") or product.get("product_name", "")
    return (
        f"{problem} 때문에 불편한 사람에게 추천.\n\n"
        f"아쉬운 점: {downside}\n\n"
        f"제품 링크는 프로필에 정리해뒀습니다.\n\n"
        f"{DEFAULT_DISCLOSURE}"
    )


def _build_title(product: dict[str, Any]) -> str:
    angle = product.get("video_angle") or product.get("product_name", "")
    if "?" in angle:
        return angle[:100]
    return f"{angle} - 단점까지 보고 결정하세요"[:100]


def publish_product(
    product_id: str,
    *,
    dry_run: bool = True,
    platforms: list[str] | None = None,
    video_url: str | None = None,
    cover_url: str | None = None,
    video_path: Path | None = None,
) -> dict[str, Any]:
    products = load_products()
    product = next((p for p in products if p.get("product_id") == product_id), None)
    if not product:
        return {"status": "FAILED", "reason": f"상품 {product_id} 없음"}

    if product.get("human_approval") != "APPROVED":
        return {
            "status": "BLOCKED",
            "reason": "사람 승인 필요. 먼저 APPROVE 명령으로 승인하세요.",
            "human_action": f"APPROVE {product_id}",
        }

    video_file = video_path or (INBOX_DIR / f"{product_id}.mp4")
    if not video_file.exists() and not video_url:
        return {
            "status": "FAILED",
            "reason": f"영상 없음: {video_file}",
            "human_action": f"VIDEO READY {product_id} path={INBOX_DIR / f'{product_id}.mp4'}",
        }

    title = _build_title(product)
    caption = _build_caption(product)
    tags = ["청소템", "생활꿀템", "살림템", "자취템"]
    affiliate_link = product.get("affiliate_url") or product.get("product_url")

    selected = platforms or DEFAULT_PLATFORMS
    ig = InstagramPublisher()
    tt = TikTokPublisher()
    pin = PinterestPublisher()
    yt = YouTubePublisher()

    results = []
    for name in selected:
        if name == "youtube_shorts":
            result = yt.publish(video_file, title, caption, tags, dry_run=dry_run)
        elif name == "instagram_reels":
            if video_url:
                result = ig.publish_reel(video_url, caption, dry_run=dry_run)
            else:
                result = ig.publish(video_file, title, caption, tags, dry_run=dry_run)
        elif name == "tiktok":
            result = tt.publish(video_file, title, caption, tags, dry_run=dry_run)
        elif name == "pinterest":
            result = pin.publish(
                video_file,
                title,
                caption,
                tags,
                dry_run=dry_run,
                cover_image_url=cover_url,
                link=affiliate_link,
            )
        else:
            result = None
            results.append({"platform": name, "success": False, "error": "지원하지 않는 플랫폼"})
            continue
        results.append(result.to_dict())

    if not dry_run:
        posts = load_posts()
        now = datetime.now(timezone.utc).isoformat()
        for r in results:
            if r.get("success"):
                posts.append(
                    {
                        "post_id": r.get("post_id"),
                        "product_id": product_id,
                        "platform": r.get("platform"),
                        "post_url": r.get("post_url"),
                        "published_at": now,
                        "status": "PUBLISHED",
                    }
                )
        save_posts(posts)

    all_ok = all(r.get("success") for r in results)
    return {
        "product_id": product_id,
        "status": "PUBLISHED" if all_ok else "PARTIAL" if any(r.get("success") for r in results) else "FAILED",
        "dry_run": dry_run,
        "posts": results,
    }
