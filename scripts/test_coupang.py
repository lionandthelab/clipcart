import json
import sys

import clipcart.config  # noqa: F401  (load_dotenv)
from clipcart.coupang import best_category_products, search_products

sys.stdout.reconfigure(encoding="utf-8")

r = search_products("창틀 청소 브러시", limit=3, sub_id="salrim-auto")
print("=== search ===")
print(json.dumps(r[:2], ensure_ascii=False, indent=2)[:1600])

b = best_category_products("1014", limit=3, sub_id="salrim-auto")
print("=== best 1014 ===")
print(json.dumps(b[:1], ensure_ascii=False, indent=2)[:900])
