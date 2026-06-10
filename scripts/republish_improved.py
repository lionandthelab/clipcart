"""개선된 영상을 새 Short로 업로드하고, 같은 제품의 기존 영상은 비공개 처리."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import clipcart.config  # noqa: F401
from googleapiclient.discovery import build

from clipcart.config import OUTBOX_DIR
from clipcart.publishing.youtube import YouTubePublisher
from clipcart.storage import load_posts, load_products, save_posts, upsert_product
from clipcart.video.compliance import check_texts, check_video
from clipcart.video.copywriter import build_creative
from clipcart.video.profile import load_profile

sys.stdout.reconfigure(encoding="utf-8")

pid = sys.argv[1] if len(sys.argv) > 1 else "CP8843938097"
old_video_id = sys.argv[2] if len(sys.argv) > 2 else None

product = next(p for p in load_products() if p["product_id"] == pid)
creative = build_creative(product, load_profile())
video_path = OUTBOX_DIR / "publishing" / f"{pid}.mp4"
thumb_path = OUTBOX_DIR / "publishing" / f"{pid}_thumb.jpg"

issues = check_texts(creative) + check_video(video_path)
if issues:
    raise SystemExit(f"컴플라이언스 실패: {issues}")

yt = YouTubePublisher()
res = yt.publish(video_path, creative["title"], creative["description"], creative["tags"], dry_run=False)
if not res.success:
    raise SystemExit(f"업로드 실패: {res.error}")

thumb_set = yt.set_thumbnail(res.post_id, thumb_path)
comment_id = yt.post_comment(res.post_id, creative["pinned_comment"])

# 기존 영상 비공개 처리 (되돌릴 수 있음)
old_hidden = None
if old_video_id:
    youtube = build("youtube", "v3", credentials=yt._build_credentials())
    youtube.videos().update(
        part="status",
        body={"id": old_video_id, "status": {"privacyStatus": "private"}},
    ).execute()
    old_hidden = old_video_id

now = datetime.now(timezone.utc).isoformat()
posts = load_posts()
for p in posts:
    if p.get("post_id") == old_video_id:
        p["status"] = "REPLACED_PRIVATE"
posts.append({
    "post_id": res.post_id,
    "product_id": pid,
    "platform": "youtube_shorts",
    "post_url": res.post_url,
    "published_at": now,
    "status": "PUBLISHED",
    "title": creative["title"],
    "affiliate_url": product["affiliate_url"],
    "thumbnail_set": thumb_set,
    "comment_id": comment_id,
    "engine": "v2-kinetic",
})
save_posts(posts)
upsert_product({**product, "status": "PUBLISHED", "post_url": res.post_url})

from datetime import date as _date

from clipcart.research import history

history.record({
    "date": _date.today().isoformat(),
    "post_id": res.post_id,
    "product_id": pid,
    "coupang_product_id": product.get("coupang_product_id"),
    "product_name": product.get("product_name"),
    "niche_keyword": product.get("niche", {}).get("keyword"),
    "category": product.get("category"),
    "title": creative["title"],
    "post_url": res.post_url,
    "affiliate_url": product["affiliate_url"],
})

print(json.dumps({
    "new_post_url": res.post_url,
    "new_video_id": res.post_id,
    "thumbnail_set": thumb_set,
    "comment_id": comment_id,
    "old_video_hidden": old_hidden,
    "title": creative["title"],
}, ensure_ascii=False, indent=2))
