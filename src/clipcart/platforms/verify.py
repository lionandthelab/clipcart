from __future__ import annotations

from typing import Any

import requests

from clipcart.config import (
    load_instagram_config,
    load_pinterest_config,
    load_tiktok_config,
)
from clipcart.publishing.instagram import InstagramPublisher
from clipcart.publishing.pinterest import PinterestPublisher
from clipcart.publishing.tiktok import TikTokPublisher
from clipcart.publishing.youtube import YouTubePublisher

TIKTOK_API = "https://open.tiktokapis.com/v2"
PINTEREST_API = "https://api.pinterest.com/v5"


def verify_all() -> dict[str, Any]:
    ig_cfg = load_instagram_config()
    tt_cfg = load_tiktok_config()
    pin_cfg = load_pinterest_config()

    result: dict[str, Any] = {"youtube_shorts": YouTubePublisher().verify()}

    ig_pub = InstagramPublisher(ig_cfg)
    if ig_cfg.configured:
        result["instagram_reels"] = ig_pub.verify()
    else:
        result["instagram_reels"] = {
            "ok": False,
            "configured": False,
            "missing": _missing(ig_cfg, ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_BUSINESS_ACCOUNT_ID"]),
        }

    if tt_cfg.configured:
        resp = requests.get(
            f"{TIKTOK_API}/user/info/",
            headers={"Authorization": f"Bearer {tt_cfg.access_token}"},
            params={"fields": "open_id,display_name"},
            timeout=30,
        )
        if resp.ok:
            user = resp.json().get("data", {}).get("user", {})
            result["tiktok"] = {
                "ok": True,
                "display_name": user.get("display_name"),
                "open_id": user.get("open_id"),
            }
        else:
            result["tiktok"] = {"ok": False, "error": resp.text[:300]}
    else:
        result["tiktok"] = {
            "ok": False,
            "configured": False,
            "missing": _missing(tt_cfg, ["TIKTOK_ACCESS_TOKEN"]),
        }

    if pin_cfg.configured:
        resp = requests.get(
            f"{PINTEREST_API}/user_account",
            headers={"Authorization": f"Bearer {pin_cfg.access_token}"},
            timeout=30,
        )
        if resp.ok:
            data = resp.json()
            result["pinterest"] = {
                "ok": True,
                "username": data.get("username"),
                "board_id": pin_cfg.board_id or "(미설정)",
            }
        else:
            result["pinterest"] = {"ok": False, "error": resp.text[:300]}
    else:
        result["pinterest"] = {
            "ok": False,
            "configured": False,
            "missing": _missing(pin_cfg, ["PINTEREST_ACCESS_TOKEN", "PINTEREST_BOARD_ID"]),
        }

    return result


def _missing(cfg: object, keys: list[str]) -> list[str]:
    import os

    return [k for k in keys if not os.getenv(k)]
