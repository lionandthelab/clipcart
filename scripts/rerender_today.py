"""오늘 선정된 상품을 재렌더링 (선정 단계 건너뜀)."""

import json
import sys

from clipcart.storage import load_products, upsert_product
from clipcart.video.engine import make_video

sys.stdout.reconfigure(encoding="utf-8")

pid = sys.argv[1] if len(sys.argv) > 1 else None
products = load_products()
product = next(
    (p for p in products if (p["product_id"] == pid if pid else p.get("status") == "VIDEO_READY")),
    None,
)
if not product:
    raise SystemExit("재렌더링할 상품 없음")

pkg = make_video(product)
upsert_product({**product, "status": "VIDEO_READY", "video_path": str(pkg["video_path"])})
print(json.dumps({
    "product_id": product["product_id"],
    "video_path": str(pkg["video_path"]),
    "thumbnail_path": str(pkg["thumbnail_path"]),
    "title": pkg["creative"]["title"],
}, ensure_ascii=False, indent=2))
