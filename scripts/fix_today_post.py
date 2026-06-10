"""오늘 게시물 보정: subId 반영 링크 재생성 → 설명 갱신 → 링크 댓글 등록."""

import json
import os
import sys

import clipcart.config  # noqa: F401  (load_dotenv)
from clipcart.publishing.youtube import YouTubePublisher
from clipcart.research.auto_select import _shorten_link
from clipcart.storage import load_posts, load_products, save_posts, upsert_product
from clipcart.video.copywriter import build_creative
from clipcart.video.profile import load_profile

sys.stdout.reconfigure(encoding="utf-8")

pid = sys.argv[1] if len(sys.argv) > 1 else "CP8843938097"
product = next(p for p in load_products() if p["product_id"] == pid)
post = next(p for p in load_posts() if p.get("product_id") == pid)

sub_id = os.getenv("COUPANG_SUB_ID") or None
new_link = _shorten_link(
    {"productUrl": product["product_url"], "productId": int(product["coupang_product_id"])},
    sub_id,
)
product["affiliate_url"] = new_link
creative = build_creative(product, load_profile())

yt = YouTubePublisher()
video_id = post["post_id"]
metadata_updated = yt.update_metadata(video_id, creative["title"], creative["description"], creative["tags"])
comment_id = yt.post_comment(video_id, creative["pinned_comment"])

upsert_product(product)
posts = load_posts()
for p in posts:
    if p.get("product_id") == pid:
        p["affiliate_url"] = new_link
        p["comment_id"] = comment_id
save_posts(posts)

print(json.dumps({
    "video_id": video_id,
    "new_affiliate_url": new_link,
    "sub_id": sub_id,
    "metadata_updated": metadata_updated,
    "comment_id": comment_id,
    "comment_text": creative["pinned_comment"],
}, ensure_ascii=False, indent=2))
