from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clipcart.config import DATA_DIR


def _read_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    data = json.loads(text)
    return data if isinstance(data, list) else [data]


def _write_json(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_products() -> list[dict[str, Any]]:
    return _read_json(DATA_DIR / "products.json")


def save_products(products: list[dict[str, Any]]) -> None:
    _write_json(DATA_DIR / "products.json", products)


def upsert_product(product: dict[str, Any]) -> None:
    products = load_products()
    idx = next(
        (i for i, p in enumerate(products) if p.get("product_id") == product.get("product_id")),
        None,
    )
    if idx is None:
        products.append(product)
    else:
        products[idx] = {**products[idx], **product}
    save_products(products)


def load_videos() -> list[dict[str, Any]]:
    return _read_json(DATA_DIR / "videos.json")


def save_videos(videos: list[dict[str, Any]]) -> None:
    _write_json(DATA_DIR / "videos.json", videos)


def load_metrics() -> list[dict[str, Any]]:
    return _read_json(DATA_DIR / "metrics.json")


def save_metrics(snapshots: list[dict[str, Any]]) -> None:
    _write_json(DATA_DIR / "metrics.json", snapshots)


def load_posts() -> list[dict[str, Any]]:
    return _read_json(DATA_DIR / "posts.json")


def save_posts(posts: list[dict[str, Any]]) -> None:
    _write_json(DATA_DIR / "posts.json", posts)
